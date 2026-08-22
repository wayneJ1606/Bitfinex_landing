from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bitfinex_lending.collector_run_history import CollectorRunRecord, append_collector_run
from bitfinex_lending.p0_data_readiness import ReadinessConfig, evaluate_p0_readiness


def _run(root: Path, collector: str, when: datetime, *, status: str = "success") -> None:
    interval = 60 if collector == "public" else 5
    append_collector_run(
        root,
        CollectorRunRecord(
            run_id=f"{collector}-{when.isoformat()}",
            collector=collector,
            started_at=when.isoformat(),
            finished_at=(when + timedelta(seconds=2)).isoformat(),
            status=status,
            expected_interval_minutes=interval,
            successful_units=1 if status == "success" else 0,
            failed_units=0 if status == "success" else 1,
            row_counts={"rows": 1},
            failures={} if status == "success" else {"unit": "failed"},
            permission_checked=True if collector == "private" else None,
        ),
    )


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _inputs(tmp_path: Path) -> dict[str, Path]:
    lifecycle = tmp_path / "lifecycle.csv"
    matches = tmp_path / "matches.csv"
    alignment = tmp_path / "alignment.csv"
    status = tmp_path / "status.json"
    _write_csv(
        lifecycle,
        ("offer_id", "outcome"),
        [
            {"offer_id": "1", "outcome": "executed"},
            {"offer_id": "2", "outcome": "executed"},
            {"offer_id": "3", "outcome": "canceled"},
        ],
    )
    _write_csv(
        matches,
        ("offer_id", "match_status", "matched_trade_count"),
        [{"offer_id": "1", "match_status": "matched", "matched_trade_count": 1}],
    )
    _write_csv(
        alignment,
        ("collected_at", "market_matched"),
        [
            {"collected_at": "2026-08-19T00:30:00+00:00", "market_matched": 1},
            {"collected_at": "2026-08-19T01:30:00+00:00", "market_matched": 1},
        ],
    )
    status.write_text(
        json.dumps(
            {
                "status": "success",
                "failures": {},
                "finished_at": "2026-08-19T03:00:02+00:00",
            }
        ),
        encoding="utf-8",
    )
    return {"lifecycle": lifecycle, "matches": matches, "alignment": alignment, "status": status}


def _config() -> ReadinessConfig:
    return ReadinessConfig(
        min_exact_hours=2,
        min_slot_coverage=0.9,
        min_hourly_coverage=0.9,
        min_success_rate=0.9,
        max_private_gap_minutes=10,
        max_public_gap_minutes=90,
        min_offers=3,
        min_executed=2,
        min_canceled=1,
        min_matched_trades=1,
        min_alignment_rate=0.9,
    )


def test_reports_ready_when_all_exact_history_and_sample_gates_pass(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    for minutes in range(0, 181, 5):
        _run(history, "private", start + timedelta(minutes=minutes))
    for hours in range(4):
        _run(history, "public", start + timedelta(hours=hours))
    paths = _inputs(tmp_path)
    output = tmp_path / "readiness.json"

    result = evaluate_p0_readiness(
        history,
        paths["status"],
        paths["lifecycle"],
        paths["matches"],
        paths["alignment"],
        output,
        config=_config(),
    )

    assert result["status"] == "ready"
    assert result["reasons"] == []
    assert result["metrics"]["exact_overlap_hours"] >= 2
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "ready"


def test_reports_each_failed_gate_without_claiming_readiness(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "public", start, status="partial")
    _run(history, "private", start)
    paths = _inputs(tmp_path)
    paths["status"].write_text(
        json.dumps({"status": "partial", "failures": {"funding_trades": "failed"}}),
        encoding="utf-8",
    )

    result = evaluate_p0_readiness(
        history,
        paths["status"],
        paths["lifecycle"],
        paths["matches"],
        paths["alignment"],
        tmp_path / "readiness.json",
        config=_config(),
    )

    assert result["status"] == "not_ready"
    assert "exact_history_duration" in result["reasons"]
    assert "public_success_rate" in result["reasons"]
    assert "latest_private_status" in result["reasons"]


def test_staggered_schedules_share_interval_buckets_without_false_private_failure(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "private", start)
    _run(history, "public", start + timedelta(minutes=3))
    _run(history, "private", start + timedelta(minutes=5))
    paths = _inputs(tmp_path)

    result = evaluate_p0_readiness(
        history,
        paths["status"],
        paths["lifecycle"],
        paths["matches"],
        paths["alignment"],
        tmp_path / "readiness.json",
        config=ReadinessConfig(
            min_exact_hours=0,
            min_slot_coverage=0,
            min_hourly_coverage=0,
            min_success_rate=0,
            max_private_gap_minutes=10,
            max_public_gap_minutes=90,
            min_offers=0,
            min_executed=0,
            min_canceled=0,
            min_matched_trades=0,
            min_alignment_rate=0,
        ),
    )

    assert result["metrics"]["private_exact_runs"] == 1
    assert result["metrics"]["private_success_rate"] == 1.0
    assert result["metrics"]["private_slot_coverage"] == 1.0
    assert result["checks"]["private_max_gap"] is True


def test_counts_trade_rows_only_for_exactly_matched_offers(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "public", start)
    _run(history, "private", start)
    paths = _inputs(tmp_path)
    _write_csv(
        paths["matches"],
        ("offer_id", "match_status", "matched_trade_count"),
        [
            {"offer_id": "1", "match_status": "matched", "matched_trade_count": 2},
            {"offer_id": "2", "match_status": "matched", "matched_trade_count": 3},
            {"offer_id": "3", "match_status": "matched_amount_partial", "matched_trade_count": 7},
            {"offer_id": "4", "match_status": "matched_time_inconsistent", "matched_trade_count": 5},
            {"offer_id": "5", "match_status": "trade_without_offer_history", "matched_trade_count": 9},
        ],
    )

    result = evaluate_p0_readiness(
        history,
        paths["status"],
        paths["lifecycle"],
        paths["matches"],
        paths["alignment"],
        tmp_path / "readiness.json",
        config=ReadinessConfig(
            min_exact_hours=0,
            min_slot_coverage=0,
            min_hourly_coverage=0,
            min_success_rate=0,
            max_private_gap_minutes=10,
            max_public_gap_minutes=10,
            min_offers=0,
            min_executed=0,
            min_canceled=0,
            min_matched_trades=5,
            min_alignment_rate=0,
        ),
    )

    assert result["metrics"]["matched_trades"] == 5
    assert result["checks"]["matched_trades"] is True


def test_public_max_gap_includes_leading_and_trailing_boundaries(tmp_path: Path) -> None:
    for name, success_at, expected_gap in (("leading", 90, 90.0), ("trailing", 30, 90.033333)):
        case = tmp_path / name
        history = case / "collector_runs"
        start = datetime(2026, 8, 19, tzinfo=timezone.utc)
        _run(history, "public", start, status="partial")
        _run(history, "public", start + timedelta(minutes=success_at))
        _run(history, "public", start + timedelta(minutes=120), status="partial")
        _run(history, "private", start)
        _run(history, "private", start + timedelta(minutes=120))
        paths = _inputs(case)

        result = evaluate_p0_readiness(
            history,
            paths["status"],
            paths["lifecycle"],
            paths["matches"],
            paths["alignment"],
            case / "readiness.json",
            config=ReadinessConfig(
                min_exact_hours=0,
                min_slot_coverage=0,
                min_hourly_coverage=0,
                min_success_rate=0,
                max_private_gap_minutes=999,
                max_public_gap_minutes=60,
                min_offers=0,
                min_executed=0,
                min_canceled=0,
                min_matched_trades=0,
                min_alignment_rate=0,
            ),
        )

        assert result["checks"]["public_max_gap"] is False
        assert result["metrics"]["public_max_success_gap_minutes"] == expected_gap


def test_public_max_gap_fails_when_window_contains_no_successes(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "public", start, status="partial")
    _run(history, "private", start)
    paths = _inputs(tmp_path)

    result = evaluate_p0_readiness(
        history,
        paths["status"],
        paths["lifecycle"],
        paths["matches"],
        paths["alignment"],
        tmp_path / "readiness.json",
        config=ReadinessConfig(
            min_exact_hours=0,
            min_slot_coverage=0,
            min_hourly_coverage=0,
            min_success_rate=0,
            max_private_gap_minutes=10,
            max_public_gap_minutes=10,
            min_offers=0,
            min_executed=0,
            min_canceled=0,
            min_matched_trades=0,
            min_alignment_rate=0,
        ),
    )

    assert result["checks"]["public_max_gap"] is False
    assert result["metrics"]["public_max_success_gap_minutes"] == float("inf")


def test_private_status_requires_a_finished_at_timestamp(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "public", start)
    _run(history, "private", start)
    paths = _inputs(tmp_path)
    paths["status"].write_text(json.dumps({"status": "success", "failures": {}}), encoding="utf-8")

    result = evaluate_p0_readiness(
        history, paths["status"], paths["lifecycle"], paths["matches"], paths["alignment"],
        tmp_path / "readiness.json", config=_config(),
    )

    assert result["checks"]["latest_private_status"] is False
    assert result["metrics"]["latest_private_status_finished_at"] == ""
    assert result["metrics"]["latest_private_status_aligned"] is False


def test_private_status_rejects_stale_or_malformed_finished_at(tmp_path: Path) -> None:
    for name, finished_at in (
        ("stale", "2026-08-18T23:49:02+00:00"),
        ("malformed", "not-a-timestamp"),
    ):
        case = tmp_path / name
        history = case / "collector_runs"
        start = datetime(2026, 8, 19, tzinfo=timezone.utc)
        _run(history, "public", start)
        _run(history, "private", start)
        paths = _inputs(case)
        paths["status"].write_text(
            json.dumps({"status": "success", "failures": {}, "finished_at": finished_at}),
            encoding="utf-8",
        )

        result = evaluate_p0_readiness(
            history, paths["status"], paths["lifecycle"], paths["matches"], paths["alignment"],
            case / "readiness.json", config=_config(),
        )

        assert result["checks"]["latest_private_status"] is False
        assert result["metrics"]["latest_private_status_aligned"] is False


def test_private_status_accepts_fresh_aligned_success(tmp_path: Path) -> None:
    history = tmp_path / "collector_runs"
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(history, "public", start)
    _run(history, "private", start)
    paths = _inputs(tmp_path)
    paths["status"].write_text(
        json.dumps(
            {
                "status": "success",
                "failures": {},
                "finished_at": "2026-08-19T00:00:02+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_p0_readiness(
        history, paths["status"], paths["lifecycle"], paths["matches"], paths["alignment"],
        tmp_path / "readiness.json", config=_config(),
    )

    assert result["checks"]["latest_private_status"] is True
    assert result["metrics"]["latest_private_status_finished_at"] == "2026-08-19T00:00:02+00:00"
    assert result["metrics"]["latest_private_status_gap_minutes"] == 0.0
    assert result["metrics"]["latest_private_status_aligned"] is True
