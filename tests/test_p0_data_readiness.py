from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bitfinex_lending.collector_run_history import CollectorRunRecord, append_collector_run
from bitfinex_lending.p0_data_readiness import ReadinessConfig, evaluate_p0_readiness


def _run(root: Path, when: datetime, *, status: str = "success") -> None:
    append_collector_run(root, CollectorRunRecord(
        run_id=f"public-{when.isoformat()}", collector="public", started_at=when.isoformat(),
        finished_at=(when + timedelta(seconds=2)).isoformat(), status=status,
        expected_interval_minutes=60, successful_units=int(status == "success"),
        failed_units=int(status != "success"), row_counts={"rows": 1},
        failures={} if status == "success" else {"unit": "failed"},
    ))


def _csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _private_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    status = root / "status.json"
    status.write_text(json.dumps({"status": "partial", "failures": {"private": "failed"}}), encoding="utf-8")
    lifecycle = _csv(root / "lifecycle.csv", ("offer_id", "outcome"), [{"offer_id": "private-id", "outcome": "executed"}])
    matches = _csv(root / "matches.csv", ("offer_id", "match_status", "matched_trade_count"), [
        {"offer_id": "private-id", "match_status": "matched", "matched_trade_count": 2},
        {"offer_id": "other", "match_status": "matched_amount_partial", "matched_trade_count": 99},
    ])
    alignment = _csv(root / "alignment.csv", ("collected_at", "market_matched"), [])
    return status, lifecycle, matches, alignment


def _coverage(root: Path, observations: list[int]) -> Path:
    return _csv(root / "strategy_coverage.csv", ("strategy_id", "observations"), [
        {"strategy_id": f"cell-{index}", "observations": value}
        for index, value in enumerate(observations)
    ])


def _config() -> ReadinessConfig:
    return ReadinessConfig(min_public_hours=60 * 24, min_hourly_coverage=0.90,
                           max_public_gap_minutes=360, min_strategy_observations=30)


def _sixty_day_public_history(root: Path, *, skip_every_tenth: bool = False) -> None:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    for hour in range(60 * 24 + 1):
        if not (skip_every_tenth and hour not in {0, 60 * 24} and hour % 10 == 0):
            _run(root, start + timedelta(hours=hour))


def _evaluate(root: Path, coverage: Path, *, config: ReadinessConfig | None = None) -> dict[str, object]:
    status, lifecycle, matches, alignment = _private_inputs(root)
    return evaluate_p0_readiness(root / "runs", status, lifecycle, matches, alignment,
                                 root / "readiness.json", config=config or _config(),
                                 strategy_coverage_path=coverage)


def test_ready_for_60_day_public_history_and_coverage_without_private_events(tmp_path: Path) -> None:
    # 90% hourly coverage and no public gap greater than six hours.
    _sixty_day_public_history(tmp_path / "runs", skip_every_tenth=True)

    result = _evaluate(tmp_path, _coverage(tmp_path, [30, 31]))

    assert result["status"] == "ready"
    assert result["reasons"] == []
    assert set(result["checks"]) == {"public_history_duration", "public_hourly_coverage", "public_max_gap", "strategy_observations"}
    assert result["diagnostics"]["checks"]["latest_private_status"] is False
    assert result["diagnostics"]["metrics"]["matched_trades"] == 2
    assert json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))["status"] == "ready"


def test_each_public_or_strategy_gate_is_formally_blocking(tmp_path: Path) -> None:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    config = _config()

    duration_root = tmp_path / "duration"
    _run(duration_root / "runs", start)
    duration = _evaluate(duration_root, _coverage(duration_root, [30]), config=config)
    assert "public_history_duration" in duration["reasons"]

    sparse_root = tmp_path / "sparse"
    for hour in range(0, 60 * 24 + 1, 10):
        _run(sparse_root / "runs", start + timedelta(hours=hour))
    sparse = _evaluate(sparse_root, _coverage(sparse_root, [30]), config=config)
    assert {"public_hourly_coverage", "public_max_gap"} <= set(sparse["reasons"])

    low_root = tmp_path / "low"
    _sixty_day_public_history(low_root / "runs")
    low = _evaluate(low_root, _coverage(low_root, [29]), config=config)
    assert "strategy_observations" in low["reasons"]


def test_empty_strategy_coverage_is_a_formal_failure(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, _coverage(tmp_path, []), config=ReadinessConfig(
        min_public_hours=0, min_hourly_coverage=0, max_public_gap_minutes=360, min_strategy_observations=30,
    ))

    assert result["status"] == "not_ready"
    assert result["checks"]["strategy_observations"] is False


def test_private_diagnostics_preserve_boundary_gap_and_exact_match_counting(tmp_path: Path) -> None:
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    _run(tmp_path / "runs", start, status="partial")
    _run(tmp_path / "runs", start + timedelta(minutes=90))
    _run(tmp_path / "runs", start + timedelta(minutes=120), status="partial")
    config = ReadinessConfig(min_public_hours=0, min_hourly_coverage=0, max_public_gap_minutes=60, min_strategy_observations=0)

    result = _evaluate(tmp_path, _coverage(tmp_path, [0]), config=config)

    assert result["diagnostics"]["metrics"]["public_max_success_gap_minutes"] == 90.0
    assert result["diagnostics"]["metrics"]["matched_trades"] == 2
    assert result["checks"]["public_max_gap"] is False
