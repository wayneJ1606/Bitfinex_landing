from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bitfinex_lending.p0_market_history import MarketHistoryError, load_market_hours


def _write(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _market_row(*, collected_at: str, market: str = "fUST") -> dict[str, object]:
    return {"collected_at": collected_at, "market": market}


def _public_fixture(market_root: Path, raw_root: Path, *, ticker_at: str = "2026-08-01T01:00:00+00:00") -> None:
    day = ("2026", "08", "01")
    ticker = _market_row(collected_at=ticker_at)
    ticker.update({"frr": "0.0002", "ask": "0.0003"})
    _write(market_root / "ticker" / Path(*day) / "fUST.csv", ("collected_at", "market", "frr", "ask"), [ticker])
    candle = _market_row(collected_at="2026-08-01T00:30:00+00:00")
    candle.update({"high": "0.0004", "volume": "1200"})
    _write(market_root / "funding_candles" / Path(*day) / "fUST.csv", ("collected_at", "market", "high", "volume"), [candle])
    stats = _market_row(collected_at="2026-08-01T00:40:00+00:00")
    stats.update({"funding_amount_used": "9000"})
    _write(market_root / "funding_stats" / Path(*day) / "fUST.csv", ("collected_at", "market", "funding_amount_used"), [stats])
    _write(
        raw_root / "2026" / "08" / "01" / "fUST.csv",
        ("run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"),
        [
            {"run_id": "snapshot", "market": "fUST", "rate": "0.0003", "period": "2", "count": "1", "amount": "-11", "side": "demand", "fetched_at": "2026-08-01T00:45:00+00:00"},
            {"run_id": "snapshot", "market": "fUST", "rate": "0.0004", "period": "2", "count": "1", "amount": "7", "side": "offer", "fetched_at": "2026-08-01T00:45:00+00:00"},
        ],
    )


def test_loads_daily_public_rows_as_same_symbol_hourly_usdt_history(tmp_path: Path) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    usd_ticker = _market_row(collected_at="2026-08-01T01:00:00+00:00", market="fUSD")
    usd_ticker.update({"frr": "99", "ask": "99"})
    _write(tmp_path / "market" / "ticker" / "2026" / "08" / "01" / "fUSD.csv", ("collected_at", "market", "frr", "ask"), [usd_ticker])

    rows = load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")

    assert len(rows) == 1
    assert rows[0].observed_at == datetime(2026, 8, 1, 1, tzinfo=timezone.utc)
    assert rows[0].api_symbol == "fUST"
    assert rows[0].asset == "USDT"
    assert rows[0].frr == 0.0002
    assert rows[0].ask_rate == 0.0003
    assert rows[0].visible_demand_amount == 11.0
    assert rows[0].traded_high == 0.0004
    assert rows[0].traded_volume == 1200.0
    assert rows[0].funding_amount_used == 9000.0


def test_rejects_unpaired_future_or_stale_required_public_snapshots(tmp_path: Path) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    candle_path = tmp_path / "market" / "funding_candles" / "2026" / "08" / "01" / "fUST.csv"
    candle = _market_row(collected_at="2026-08-01T02:31:00+00:00")
    candle.update({"high": "0.0004", "volume": "1200"})
    _write(candle_path, ("collected_at", "market", "high", "volume"), [candle])

    with pytest.raises(MarketHistoryError, match="candle"):
        load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")


def test_rejects_required_pairing_that_is_91_minutes_old(tmp_path: Path) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    candle_path = tmp_path / "market" / "funding_candles" / "2026" / "08" / "01" / "fUST.csv"
    candle = _market_row(collected_at="2026-07-31T23:29:00+00:00")
    candle.update({"high": "0.0004", "volume": "1200"})
    _write(candle_path, ("collected_at", "market", "high", "volume"), [candle])

    with pytest.raises(MarketHistoryError, match="candle"):
        load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")


def test_keeps_all_offer_raw_snapshot_as_zero_visible_demand(tmp_path: Path) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    _write(
        tmp_path / "raw" / "2026" / "08" / "01" / "fUST.csv",
        ("run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"),
        [{"run_id": "offers-only", "market": "fUST", "rate": "0.0004", "period": "2", "count": "1", "amount": "7", "side": "offer", "fetched_at": "2026-08-01T00:45:00+00:00"}],
    )

    rows = load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")

    assert rows[0].visible_demand_amount == 0.0


@pytest.mark.parametrize(
    ("path", "field", "value", "message"),
    [
        ("ticker", "collected_at", "2026-08-01T01:00:00", "timezone"),
        ("ticker", "frr", "nan", "finite"),
    ],
)
def test_rejects_invalid_required_public_values(tmp_path: Path, path: str, field: str, value: str, message: str) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    target = tmp_path / "market" / path / "2026" / "08" / "01" / "fUST.csv"
    rows = list(csv.DictReader(target.open(encoding="utf-8", newline="")))
    rows[0][field] = value
    _write(target, tuple(rows[0]), rows)

    with pytest.raises(MarketHistoryError, match=message):
        load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")


def test_rejects_conflicting_duplicate_hourly_observations_and_unsupported_symbols(tmp_path: Path) -> None:
    _public_fixture(tmp_path / "market", tmp_path / "raw")
    ticker = _market_row(collected_at="2026-08-01T01:30:00+00:00")
    ticker.update({"frr": "0.0002", "ask": "0.00031"})
    _write(tmp_path / "market" / "ticker" / "2026" / "08" / "01" / "duplicate.csv", ("collected_at", "market", "frr", "ask"), [ticker])

    with pytest.raises(MarketHistoryError, match="conflicting hourly"):
        load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")
    with pytest.raises(MarketHistoryError, match="unsupported"):
        load_market_hours(tmp_path / "market", tmp_path / "raw", "fUSD")
