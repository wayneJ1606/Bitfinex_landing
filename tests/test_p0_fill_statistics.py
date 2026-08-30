from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bitfinex_lending.p0_fill_statistics import (
    FillStatisticsError,
    PERIOD_DAYS,
    RATE_QUANTILES,
    WAIT_HOURS,
    estimate_candidates,
)
from bitfinex_lending.p0_market_history import MarketHour


UTC = timezone.utc


def _hour(
    observed_at: datetime,
    *,
    ask_rate: float = 0.0002,
    traded_high: float = 0.0003,
    visible_demand_amount: float = 10_000.0,
    traded_volume: float = 20_000.0,
) -> MarketHour:
    return MarketHour(
        observed_at=observed_at,
        api_symbol="fUST",
        asset="USDT",
        frr=0.0002,
        ask_rate=ask_rate,
        visible_demand_amount=visible_demand_amount,
        traded_high=traded_high,
        traded_volume=traded_volume,
        funding_amount_used=1_000_000.0,
    )


def _hourly_history(days: int, end: str) -> tuple[MarketHour, ...]:
    end_at = datetime.fromisoformat(end)
    start = end_at - timedelta(days=days)
    return tuple(
        _hour(
            start + timedelta(hours=index),
            ask_rate=0.0002 + (index % 5) * 0.00001,
        )
        for index in range(days * 24 + 1)
    )


def _candidate(estimates, *, quantile: float, period: int, wait: int):
    return next(
        item
        for item in estimates
        if item.rate_quantile == quantile
        and item.period_days == period
        and item.wait_hours == wait
    )


def test_estimates_all_100_strategy_cells_from_past_only() -> None:
    history = _hourly_history(days=35, end="2026-08-05T00:00:00+00:00")
    as_of = datetime.fromisoformat("2026-08-01T00:00:00+00:00")

    estimates = estimate_candidates(history, as_of=as_of)

    assert len(estimates) == len(RATE_QUANTILES) * len(PERIOD_DAYS) * len(WAIT_HOURS) == 100
    assert {item.period_days for item in estimates} == {2, 5, 10, 30}
    assert {item.wait_hours for item in estimates} == {1, 3, 6, 12, 24}
    assert {item.rate_quantile for item in estimates} == {0.10, 0.25, 0.50, 0.75, 0.90}
    assert all(item.training_end < as_of for item in estimates)
    assert all(item.api_symbol == "fUST" and item.asset == "USDT" for item in estimates)

    future_extreme = _hour(as_of + timedelta(hours=1), ask_rate=0.9, traded_high=0.9)
    with_future = estimate_candidates(history + (future_extreme,), as_of=as_of)
    assert [item.daily_rate for item in with_future] == [item.daily_rate for item in estimates]


def test_fill_requires_a_later_trade_high_and_capacity_is_capped() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (
        _hour(start, traded_high=0.0001),
        _hour(
            start + timedelta(hours=1),
            traded_high=0.0002,
            visible_demand_amount=900.0,
            traded_volume=700.0,
        ),
    )

    estimates = estimate_candidates(history, as_of=start + timedelta(hours=2))
    target = _candidate(estimates, quantile=0.50, period=2, wait=1)

    assert target.daily_rate == pytest.approx(0.0002)
    assert target.observations == 1
    assert target.fills == 1
    assert target.fill_probability == pytest.approx(1.0)
    assert target.average_wait_hours == pytest.approx(1.0)
    assert target.deployable_amount == pytest.approx(700.0)
    assert target.expected_duration_hours == pytest.approx(48.0)
    assert target.expected_net_profit_per_1000 == pytest.approx(0.34)
    assert target.net_profit_p10_per_1000 == pytest.approx(0.34)
    assert target.calibration_status == "insufficient_private_data"
    assert target.duration_status == "nominal_period_assumption"


def test_non_fill_waits_the_full_window_and_has_zero_capacity_and_profit() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (
        _hour(start, ask_rate=0.0002, traded_high=0.0001),
        _hour(start + timedelta(hours=1), ask_rate=0.0002, traded_high=0.00019),
    )

    target = _candidate(
        estimate_candidates(history, as_of=start + timedelta(hours=2)),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert target.observations == 1
    assert target.fills == 0
    assert target.fill_probability == 0.0
    assert target.average_wait_hours == 1.0
    assert target.deployable_amount == 0.0
    assert target.expected_net_profit_per_1000 == 0.0
    assert target.net_profit_p10_per_1000 == 0.0


def test_private_fill_calibration_requires_30_comparable_anonymous_rows() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (_hour(start), _hour(start + timedelta(hours=1)))
    common = {
        "api_symbol": "fUST",
        "rate_quantile": 0.50,
        "period_days": 2,
        "wait_hours": 1,
        "filled": False,
    }

    below_threshold = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_matches=tuple(dict(common) for _ in range(29)),
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )
    calibrated = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_matches=tuple(dict(common) for _ in range(30)),
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert below_threshold.calibration_status == "insufficient_private_data"
    assert below_threshold.fill_probability == 1.0
    assert calibrated.calibration_status == "private_calibrated"
    assert calibrated.fill_probability == pytest.approx(0.5)


def test_private_csv_false_text_is_not_counted_as_a_fill() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (_hour(start), _hour(start + timedelta(hours=1)))
    private_rows = tuple(
        {
            "api_symbol": "fUST",
            "rate_quantile": "0.50",
            "period_days": "2",
            "wait_hours": "1",
            "filled": "false",
        }
        for _ in range(30)
    )

    target = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_matches=private_rows,
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert target.fill_probability == pytest.approx(0.5)


def test_existing_offer_trade_match_rows_calibrate_by_rate_period_and_wait() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (_hour(start), _hour(start + timedelta(hours=1)))
    private_rows = tuple(
        {
            "api_symbol": "fUST",
            "offer_rate": "0.0002",
            "offer_period": "2",
            "wait_minutes": "90",
            "match_status": "matched",
        }
        for _ in range(30)
    )

    target = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_matches=private_rows,
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert target.calibration_status == "private_calibrated"
    assert target.fill_probability == pytest.approx(0.5)


def test_inexact_private_trade_matches_do_not_calibrate() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (_hour(start), _hour(start + timedelta(hours=1)))
    private_rows = tuple(
        {
            "api_symbol": "fUST",
            "offer_rate": "0.0002",
            "offer_period": "2",
            "wait_minutes": "30",
            "match_status": "matched_amount_partial",
        }
        for _ in range(30)
    )

    target = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_matches=private_rows,
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert target.calibration_status == "insufficient_private_data"
    assert target.fill_probability == 1.0


def test_private_duration_calibration_requires_30_comparable_closed_rows() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    history = (_hour(start), _hour(start + timedelta(hours=1)))
    common = {"api_symbol": "fUST", "period_days": 2, "duration_hours": 12.0}

    nominal = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_durations=tuple(dict(common) for _ in range(29)),
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )
    calibrated = _candidate(
        estimate_candidates(
            history,
            as_of=start + timedelta(hours=2),
            private_durations=tuple(dict(common) for _ in range(30)),
        ),
        quantile=0.50,
        period=2,
        wait=1,
    )

    assert nominal.duration_status == "nominal_period_assumption"
    assert nominal.expected_duration_hours == 48.0
    assert calibrated.duration_status == "private_duration_calibrated"
    assert calibrated.expected_duration_hours == 12.0
    assert calibrated.expected_net_profit_per_1000 == pytest.approx(0.085)


def test_rejects_naive_as_of_and_mixed_market_history() -> None:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(FillStatisticsError, match="as_of must include a timezone"):
        estimate_candidates((_hour(start),), as_of=datetime(2026, 8, 2))

    mixed = (
        _hour(start),
        MarketHour(
            observed_at=start + timedelta(hours=1),
            api_symbol="fBTC",
            asset="BTC",
            frr=0.0002,
            ask_rate=0.0002,
            visible_demand_amount=1.0,
            traded_high=0.0003,
            traded_volume=1.0,
            funding_amount_used=1.0,
        ),
    )
    with pytest.raises(FillStatisticsError, match="one API symbol and asset"):
        estimate_candidates(mixed, as_of=start + timedelta(hours=2))
