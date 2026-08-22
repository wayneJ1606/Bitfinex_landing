from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bitfinex_lending.p0_public_fill_proxy import (
    PublicFundingHour,
    estimate_public_fill_proxy,
    load_fust_public_hours,
)


def hours(highs: tuple[str, ...], ask: str = "0.001") -> tuple[PublicFundingHour, ...]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return tuple(
        PublicFundingHour(start + timedelta(hours=index), Decimal(ask), Decimal(high))
        for index, high in enumerate(highs)
    )


def test_proxy_uses_future_trade_high_and_charges_waiting_time() -> None:
    rows = hours(("0", "0", "0", "0.001", "0.001", "0.001"))
    estimates = estimate_public_fill_proxy(
        rows,
        lookback_hours=2,
        quantiles=(Decimal("0.5"),),
        wait_hours=(1,),
        periods=(2,),
    )

    result = estimates[0]
    assert result.observations == 3
    assert result.proxy_fills == 3
    assert result.proxy_fill_probability == Decimal("1")
    assert result.average_success_wait_hours == Decimal("1")
    assert result.average_candidate_daily_rate == Decimal("0.001")
    assert result.expected_30d_net_profit_per_1000 == pytest.approx(
        Decimal("1.7") * Decimal("720") / Decimal("49")
    )
    assert result.idle_fraction == pytest.approx(Decimal("1") / Decimal("49"))


def test_proxy_reports_zero_return_when_candidate_rate_never_trades() -> None:
    result = estimate_public_fill_proxy(
        hours(("0", "0", "0", "0", "0", "0")),
        lookback_hours=2,
        quantiles=(Decimal("0.5"),),
        wait_hours=(2,),
        periods=(5,),
    )[0]

    assert result.proxy_fill_probability == Decimal("0")
    assert result.expected_30d_net_profit_per_1000 == Decimal("0")
    assert result.idle_fraction == Decimal("1")


def test_longer_wait_can_capture_a_later_public_trade() -> None:
    rows = hours(("0", "0", "0", "0", "0.001", "0.001"))
    short, long = estimate_public_fill_proxy(
        rows,
        lookback_hours=2,
        quantiles=(Decimal("0.5"),),
        wait_hours=(1, 2),
        periods=(2,),
    )

    assert short.wait_hours == 1
    assert long.wait_hours == 2
    assert long.proxy_fill_probability > short.proxy_fill_probability


def write_csv(path: Path, fields: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def test_loader_pairs_fust_ticker_and_candle_by_utc_hour(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "ticker" / "2026" / "08" / "01" / "fUST.csv",
        ("collected_at", "market", "ask"),
        (
            ("2026-08-01T00:47:00+00:00", "fUST", "0.001"),
            ("2026-08-01T01:47:00+00:00", "fUST", "0.002"),
        ),
    )
    write_csv(
        tmp_path / "funding_candles" / "2026" / "08" / "01" / "fUST.csv",
        ("collected_at", "market", "high"),
        (
            ("2026-08-01T00:47:00+00:00", "fUST", "0.0011"),
            ("2026-08-01T01:47:00+00:00", "fUST", "0.0021"),
        ),
    )

    loaded = load_fust_public_hours(tmp_path)

    assert loaded == (
        PublicFundingHour(datetime(2026, 8, 1, tzinfo=timezone.utc), Decimal("0.001"), Decimal("0.0011")),
        PublicFundingHour(datetime(2026, 8, 1, 1, tzinfo=timezone.utc), Decimal("0.002"), Decimal("0.0021")),
    )
