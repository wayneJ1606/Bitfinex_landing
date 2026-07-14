from __future__ import annotations

import math
import re

import pytest

from bitfinex_lending.feature_calculation import (
    FeatureCalculationError,
    calculate_features,
)
from bitfinex_lending.models import FundingBookRow


def row(
    *,
    market: str = "fUSD",
    fetched_at: str = "2026-07-14T12:00:00+00:00",
    rate: float = 0.0002,
    period: int = 2,
    count: int = 1,
    amount: float = 10.0,
    side: str = "offer",
    run_id: str = "run-1",
) -> FundingBookRow:
    return FundingBookRow(
        run_id=run_id,
        market=market,
        rate=rate,
        period=period,
        count=count,
        amount=amount,
        side=side,  # type: ignore[arg-type]
        fetched_at=fetched_at,
    )


def test_calculate_features_aggregates_and_orders_each_market() -> None:
    usd_later = "2026-07-14T13:00:00+00:00"
    usd_earlier = "2026-07-14T12:00:00+00:00"
    rows = (
        row(fetched_at=usd_later, rate=0.0005, amount=20.0, count=4),
        row(fetched_at=usd_earlier, rate=0.0002, amount=10.0, count=2),
        row(
            fetched_at=usd_earlier,
            rate=0.0004,
            period=6,
            amount=-30.0,
            count=3,
            side="demand",
        ),
        row(
            market="fBTC",
            fetched_at="2026-07-15T01:00:00+08:00",
            rate=0.0007,
            period=3,
            amount=-5.0,
            count=7,
            side="demand",
        ),
    )

    features = calculate_features(rows)
    usd_first, usd_second, btc_only = features

    assert [item.market for item in features] == ["fUSD", "fUSD", "fBTC"]
    assert usd_first.feature_time == usd_earlier
    assert usd_first.hour == 12
    assert usd_first.day_of_week == 1
    assert usd_first.avg_rate == pytest.approx(0.0003)
    assert usd_first.weighted_avg_rate == pytest.approx(
        (0.0002 * 10.0 + 0.0004 * 30.0) / 40.0
    )
    assert usd_first.min_rate == 0.0002
    assert usd_first.max_rate == 0.0004
    assert usd_first.total_amount == 40.0
    assert usd_first.avg_period == 4.0
    assert usd_first.offer_count == 2
    assert usd_first.demand_count == 3
    assert usd_first.rate_spread == pytest.approx(0.0002)
    assert usd_first.previous_weighted_avg_rate is None
    assert usd_first.rate_change is None
    assert usd_first.amount_change is None
    assert usd_first.target_next_weighted_avg_rate == usd_second.weighted_avg_rate
    assert usd_second.previous_weighted_avg_rate == usd_first.weighted_avg_rate
    assert usd_second.rate_change == pytest.approx(
        usd_second.weighted_avg_rate - usd_first.weighted_avg_rate
    )
    assert usd_second.amount_change == pytest.approx(
        usd_second.total_amount - usd_first.total_amount
    )
    assert usd_second.target_next_weighted_avg_rate is None
    assert btc_only.hour == 17
    assert btc_only.day_of_week == 1
    assert btc_only.previous_weighted_avg_rate is None
    assert btc_only.target_next_weighted_avg_rate is None


def test_calculate_features_returns_empty_tuple_for_empty_input() -> None:
    assert calculate_features(()) == ()


@pytest.mark.parametrize(
    ("invalid_row", "reason"),
    [
        (row(fetched_at="not-a-time"), "invalid timestamp"),
        (row(fetched_at="2026-07-14T12:00:00"), "timezone offset"),
        (row(amount=0.0), "amount must not be zero"),
        (row(rate=math.inf), "rate must be finite"),
        (row(amount=math.nan), "amount must be finite"),
        (row(period=0), "period must be positive"),
        (row(count=-1), "count must be nonnegative"),
        (row(amount=-10.0, side="offer"), "offer amount must be positive"),
        (row(amount=10.0, side="demand"), "demand amount must be negative"),
    ],
)
def test_calculate_features_rejects_invalid_rows(
    invalid_row: FundingBookRow, reason: str
) -> None:
    prefix = f"invalid snapshot {invalid_row.market} at {invalid_row.fetched_at}:"

    with pytest.raises(
        FeatureCalculationError,
        match=f"^{re.escape(prefix)}.*{re.escape(reason)}",
    ):
        calculate_features((invalid_row,))


def test_calculate_features_rejects_inconsistent_snapshot_metadata() -> None:
    first = row(run_id="run-1")
    second = row(rate=0.0003, amount=20.0, run_id="run-2")

    with pytest.raises(
        FeatureCalculationError,
        match=r"^invalid snapshot fUSD at .*: inconsistent run_id$",
    ):
        calculate_features((first, second))


def test_calculate_features_rejects_zero_total_absolute_amount() -> None:
    # A custom numeric value can be nonzero while contributing zero absolute weight.
    class ZeroWeight(float):
        def __abs__(self) -> float:
            return 0.0

    invalid = row(amount=ZeroWeight(10.0))

    with pytest.raises(
        FeatureCalculationError,
        match=r"^invalid snapshot fUSD at .*: total absolute amount must be positive$",
    ):
        calculate_features((invalid,))
