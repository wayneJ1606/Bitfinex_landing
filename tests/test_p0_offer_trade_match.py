from __future__ import annotations

import csv
import json
from pathlib import Path

from bitfinex_lending.p0_offer_trade_match import build_offer_trade_matches


LIFECYCLE_FIELDS = (
    "offer_id",
    "api_symbol",
    "asset",
    "created_at",
    "updated_at",
    "first_collected_at",
    "last_collected_at",
    "lifecycle_minutes",
    "amount_original",
    "amount_remaining",
    "rate",
    "period",
    "status",
    "outcome",
    "observation_count",
)


def _write_lifecycle(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LIFECYCLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_trades(path: Path, payloads: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("event_id", "collected_at", "source_timestamp", "source_endpoint", "schema_version", "raw_payload")
        )
        for index, payload in enumerate(payloads):
            writer.writerow(
                (
                    payload[0],
                    f"2026-08-18T00:0{index}:00+00:00",
                    payload[2],
                    "/v2/auth/r/funding/trades/hist",
                    "account-v1",
                    json.dumps(payload),
                )
            )


def _offer(offer_id: int, outcome: str = "executed") -> dict[str, object]:
    return {
        "offer_id": offer_id,
        "api_symbol": "fUST",
        "asset": "USDT",
        "created_at": "1970-01-12T13:46:40+00:00",
        "updated_at": "1970-01-12T13:56:40+00:00",
        "first_collected_at": "2026-08-18T00:11:00+00:00",
        "last_collected_at": "2026-08-18T00:12:00+00:00",
        "lifecycle_minutes": 10,
        "amount_original": 160,
        "amount_remaining": 0 if outcome == "executed" else 160,
        "rate": 0.00025,
        "period": 2,
        "status": "EXECUTED" if outcome == "executed" else "CANCELED",
        "outcome": outcome,
        "observation_count": 1,
    }


def test_matches_unique_trades_and_calculates_wait_and_amount(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    first = [100, "fUST", 1_000_600_000, 10, 60, 0.00025, 2, None]
    second = [101, "fUST", 1_000_900_000, 10, 100, 0.00025, 2, None]
    _write_trades(trades, [first, first, second])

    summary = build_offer_trade_matches(lifecycle, trades, output)

    assert summary == {"matched": 1}
    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched"
    assert row["matched_trade_count"] == "2"
    assert row["matched_amount"] == "160.0"
    assert row["first_trade_at"] == "1970-01-12T13:56:40+00:00"
    assert row["last_trade_at"] == "1970-01-12T14:01:40+00:00"
    assert row["wait_minutes"] == "10.0"
    assert row["symbol_consistent"] == "true"
    assert row["rate_consistent"] == "true"
    assert row["period_consistent"] == "true"


def test_classifies_missing_and_orphan_records_without_inventing_failure(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10), _offer(20, "canceled")])
    _write_trades(trades, [[200, "fUSD", 1_001_200_000, 30, 50, 0.0003, 7, None]])

    summary = build_offer_trade_matches(lifecycle, trades, output)

    assert summary == {
        "canceled_without_trade": 1,
        "executed_trade_not_in_current_history": 1,
        "trade_without_offer_history": 1,
    }
    with output.open(encoding="utf-8", newline="") as stream:
        rows = {row["offer_id"]: row for row in csv.DictReader(stream)}
    assert rows["10"]["match_status"] == "executed_trade_not_in_current_history"
    assert rows["20"]["match_status"] == "canceled_without_trade"
    assert rows["30"]["match_status"] == "trade_without_offer_history"
    assert rows["30"]["matched_trade_count"] == "1"
    assert rows["30"]["matched_amount"] == "50.0"


def test_flags_trade_before_offer_instead_of_reporting_negative_wait(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    offer = _offer(10)
    offer["created_at"] = "1970-01-12T14:06:40+00:00"
    _write_lifecycle(lifecycle, [offer])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 160, 0.00025, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_time_inconsistent"
    assert row["wait_minutes"] == ""


def test_treats_bitfinex_eight_decimal_trade_rate_as_same_offer_rate(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    offer = _offer(10)
    offer["rate"] = 0.00030136986301369865
    _write_lifecycle(lifecycle, [offer])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 160, 0.00030137, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["rate_consistent"] == "true"


def test_trade_match_reads_partitioned_trade_directory(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "account" / "funding_trades"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(
        trades / "2026" / "08" / "18.csv",
        [[100, "fUST", 1_000_600_000, 10, 160, 0.00025, 2, None]],
    )

    summary = build_offer_trade_matches(lifecycle, trades, output)

    assert summary == {"matched": 1}


def test_rejects_symbol_inconsistent_trade_but_keeps_audit_details(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(trades, [[100, "fUSD", 1_000_600_000, 10, 160, 0.00025, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_attributes_inconsistent"
    assert row["matched_trade_count"] == "1"
    assert row["matched_amount"] == "160.0"
    assert row["symbol_consistent"] == "false"
    assert row["rate_consistent"] == "true"
    assert row["period_consistent"] == "true"


def test_rejects_rate_inconsistent_trade(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 160, 0.0003, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_attributes_inconsistent"
    assert row["rate_consistent"] == "false"


def test_rejects_period_inconsistent_trade(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 160, 0.00025, 7, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_attributes_inconsistent"
    assert row["period_consistent"] == "false"


def test_rejects_consistent_trade_amount_below_offer_amount(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 159, 0.00025, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_amount_partial"
    assert row["matched_amount"] == "159.0"


def test_rejects_consistent_trade_amount_above_offer_amount(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    trades = tmp_path / "trades.csv"
    output = tmp_path / "matches.csv"
    _write_lifecycle(lifecycle, [_offer(10)])
    _write_trades(trades, [[100, "fUST", 1_000_600_000, 10, 161, 0.00025, 2, None]])

    build_offer_trade_matches(lifecycle, trades, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["match_status"] == "matched_amount_excess"
    assert row["matched_amount"] == "161.0"
