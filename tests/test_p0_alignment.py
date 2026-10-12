from __future__ import annotations

import csv
import json
from pathlib import Path

from bitfinex_lending.p0_alignment import build_p0_alignment


TICKER_FIELDS = (
    "collected_at,market,frr,bid,bid_period,bid_size,ask,ask_period,ask_size,"
    "daily_change,daily_change_perc,last_price,volume,high,low,first_trade,"
    "frr_amount_available\n"
)


def _write_account(path: Path, rows: list[tuple[str, str, list[object]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("event_id", "collected_at", "source_timestamp", "source_endpoint", "schema_version", "raw_payload")
        )
        for event_id, collected_at, payload in rows:
            writer.writerow((event_id, collected_at, payload[2], "/private", "account-v1", json.dumps(payload)))


def _write_ticker(path: Path, rows: list[tuple[str, str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(TICKER_FIELDS)
        writer = csv.writer(stream)
        for collected_at, market, frr in rows:
            writer.writerow((collected_at, market, frr, 0.0002, 2, 100, 0.0003, 2, 100, 0, 0, frr, 1, frr, frr, 0, 1))


def test_alignment_uses_latest_prior_matching_market_snapshot(tmp_path: Path) -> None:
    account = tmp_path / "account"
    market = tmp_path / "market"
    output = tmp_path / "aligned.csv"
    offer = [1, "fUST", 1000, 1000, 160.0, 160.0, "LIMIT", None, None, 0, "ACTIVE", None, None, None, 0.00025, 2]
    _write_account(
        account / "funding_offers.csv",
        [("1", "2026-08-18T00:05:00+00:00", offer), ("1", "2026-08-18T00:10:00+00:00", offer)],
    )
    _write_ticker(
        market / "ticker" / "fUST.csv",
        [("2026-08-18T00:00:00+00:00", "fUST", 0.0002), ("2026-08-18T00:10:00+00:00", "fUST", 0.0004)],
    )

    count = build_p0_alignment(account, market, output)

    assert count == 2
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["asset"] == "USDT"
    assert rows[0]["api_symbol"] == "fUST"
    assert rows[0]["market_collected_at"] == "2026-08-18T00:00:00+00:00"
    assert rows[0]["market_frr"] == "0.0002"
    assert rows[0]["is_first_seen"] == "1"
    assert rows[1]["is_first_seen"] == "0"


def test_alignment_parses_trade_and_rejects_snapshot_older_than_tolerance(tmp_path: Path) -> None:
    account = tmp_path / "account"
    market = tmp_path / "market"
    output = tmp_path / "aligned.csv"
    trade = [10, "fUSD", 1000, 99, 160.0, 0.0003, 7, 1]
    _write_account(account / "funding_trades.csv", [("10", "2026-08-18T02:00:00+00:00", trade)])
    _write_ticker(market / "ticker" / "fUSD.csv", [("2026-08-18T00:00:00+00:00", "fUSD", 0.0002)])

    build_p0_alignment(account, market, output, tolerance_minutes=90)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["offer_id"] == "99"
    assert row["rate"] == "0.0003"
    assert row["period"] == "7"
    assert row["market_matched"] == "0"
    assert row["market_collected_at"] == ""


def test_alignment_reads_partitioned_account_and_market_files(tmp_path: Path) -> None:
    account = tmp_path / "account"
    market = tmp_path / "market"
    output = tmp_path / "aligned.csv"
    offer = [1, "fUST", 1, 2, 160, 160, "LIMIT", None, None, 0, "ACTIVE", None, None, None, 0.0002, 2]
    _write_account(
        account / "funding_offers" / "2026" / "08" / "18.csv",
        [("1", "2026-08-18T02:00:00+00:00", offer)],
    )
    _write_ticker(
        market / "ticker" / "2026" / "08" / "18" / "fUST.csv",
        [("2026-08-18T01:00:00+00:00", "fUST", 0.0002)],
    )

    count = build_p0_alignment(account, market, output)

    assert count == 1
    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["market_matched"] == "1"
