from __future__ import annotations

import csv
import json
from pathlib import Path

from bitfinex_lending.collector_run_history import (
    CollectorRunRecord,
    append_collector_run,
    load_collector_runs,
)


def _record(run_id: str = "run-1") -> CollectorRunRecord:
    return CollectorRunRecord(
        run_id=run_id,
        collector="private",
        started_at="2026-08-19T00:30:00+08:00",
        finished_at="2026-08-19T00:30:03+08:00",
        status="success",
        expected_interval_minutes=5,
        successful_units=5,
        failed_units=0,
        row_counts={"funding_trades": 25},
        failures={},
        permission_checked=True,
    )


def test_appends_exact_run_to_utc_daily_file_and_deduplicates_run_id(tmp_path: Path) -> None:
    root = tmp_path / "collector_runs"

    first = append_collector_run(root, _record())
    second = append_collector_run(root, _record())

    assert first == root / "2026" / "08" / "18" / "private.csv"
    assert second == first
    with first.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["quality"] == "exact"
    assert json.loads(rows[0]["row_counts_json"]) == {"funding_trades": 25}
    assert rows[0]["duration_seconds"] == "3.0"


def test_loads_public_and_private_partitioned_history_in_time_order(tmp_path: Path) -> None:
    root = tmp_path / "collector_runs"
    later = _record("private-later")
    public = CollectorRunRecord(
        run_id="public-earlier",
        collector="public",
        started_at="2026-08-18T16:00:00Z",
        finished_at="2026-08-18T16:00:05Z",
        status="partial",
        expected_interval_minutes=60,
        successful_units=16,
        failed_units=1,
        row_counts={"fUSD": 50},
        failures={"ticker:fUST": "http_error"},
    )
    append_collector_run(root, later)
    append_collector_run(root, public)

    records = load_collector_runs(root)

    assert [record.run_id for record in records] == ["public-earlier", "private-later"]
    assert records[0].failures == {"ticker:fUST": "http_error"}
