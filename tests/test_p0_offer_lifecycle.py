from __future__ import annotations

import csv
import json
from pathlib import Path

from bitfinex_lending.p0_offer_lifecycle import build_offer_lifecycle


def _write_history(path: Path, payloads: list[list[object]]) -> None:
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
                    "/v2/auth/r/funding/offers/hist",
                    "account-v1",
                    json.dumps(payload),
                )
            )


def test_lifecycle_collapses_repeated_history_and_uses_latest_state(tmp_path: Path) -> None:
    history = tmp_path / "account" / "funding_offers_history.csv"
    output = tmp_path / "modeling" / "p0_offer_lifecycle.csv"
    active = [1, "fUST", 1_000_000, 1_000_000, 160, 160, "LIMIT", None, None, 0, "ACTIVE", None, None, None, 0.00025, 2]
    executed = [1, "fUST", 1_000_000, 1_600_000, 0, 160, "LIMIT", None, None, 0, "EXECUTED at 0.025%", None, None, None, 0.00025, 2]
    canceled = [2, "fUSD", 2_000_000, 2_300_000, 80, 80, "LIMIT", None, None, 0, "CANCELED", None, None, None, 0.0003, 7]
    _write_history(history, [active, active, executed, canceled])

    count = build_offer_lifecycle(history, output)

    assert count == 2
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    usdt = next(row for row in rows if row["offer_id"] == "1")
    assert usdt["asset"] == "USDT"
    assert usdt["api_symbol"] == "fUST"
    assert usdt["outcome"] == "executed"
    assert usdt["status"] == "EXECUTED at 0.025%"
    assert usdt["lifecycle_minutes"] == "10.0"
    assert usdt["observation_count"] == "3"
    usd = next(row for row in rows if row["offer_id"] == "2")
    assert usd["outcome"] == "canceled"


def test_lifecycle_marks_unknown_status_without_inventing_execution(tmp_path: Path) -> None:
    history = tmp_path / "account" / "funding_offers_history.csv"
    output = tmp_path / "modeling" / "p0_offer_lifecycle.csv"
    payload = [3, "fUST", 1_000_000, 1_000_000, 50, 50, "LIMIT", None, None, 0, "PARTIALLY FILLED", None, None, None, 0.0002, 2]
    _write_history(history, [payload])

    build_offer_lifecycle(history, output)

    with output.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["outcome"] == "other"


def test_lifecycle_reads_all_daily_files_from_dataset_directory(tmp_path: Path) -> None:
    history = tmp_path / "account" / "funding_offers_history"
    output = tmp_path / "modeling" / "p0_offer_lifecycle.csv"
    first = [1, "fUST", 1_000_000, 1_000_000, 160, 160, "LIMIT", None, None, 0, "ACTIVE", None, None, None, 0.00025, 2]
    second = [2, "fUST", 2_000_000, 2_000_000, 160, 160, "LIMIT", None, None, 0, "CANCELED", None, None, None, 0.00025, 2]
    _write_history(history / "2026" / "08" / "17.csv", [first])
    _write_history(history / "2026" / "08" / "18.csv", [second])

    count = build_offer_lifecycle(history, output)

    assert count == 2
