from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .collector_run_history import CollectorRunRecord, load_collector_runs


@dataclass(frozen=True)
class ReadinessConfig:
    min_public_hours: float = 1440.0
    min_hourly_coverage: float = 0.90
    max_public_gap_minutes: float = 360.0
    min_strategy_observations: int = 30
    # These thresholds are retained only to make historical private diagnostics comparable.
    min_slot_coverage: float = 0.90
    min_success_rate: float = 0.95
    max_private_gap_minutes: float = 30.0
    min_offers: int = 30
    min_executed: int = 5
    min_canceled: int = 5
    min_matched_trades: int = 20
    min_alignment_rate: float = 0.90


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _bucket(value: datetime, minutes: int) -> int:
    return int(value.timestamp()) // (minutes * 60)


def _coverage(records: list[CollectorRunRecord], start: datetime, end: datetime, *, success_only: bool) -> float:
    first, last = _bucket(start, 60), _bucket(end, 60)
    expected = max(1, last - first + 1)
    buckets = {
        _bucket(_instant(record.started_at), 60)
        for record in records
        if first <= _bucket(_instant(record.started_at), 60) <= last
        and (not success_only or record.status == "success")
    }
    return min(1.0, len(buckets) / expected)


def _max_success_gap(records: list[CollectorRunRecord], start: datetime, end: datetime) -> float:
    times = sorted(_instant(record.started_at) for record in records if record.status == "success")
    if not times:
        return math.inf
    gaps = [max(0.0, (times[0] - start).total_seconds() / 60)]
    gaps.extend((later - earlier).total_seconds() / 60 for earlier, later in zip(times, times[1:]))
    gaps.append(max(0.0, (end - times[-1]).total_seconds() / 60))
    return max(gaps)


def _strategy_observations(path: Path) -> list[int]:
    rows = _read_rows(path)
    observations: list[int] = []
    for number, row in enumerate(rows, start=2):
        if not row.get("strategy_id") or row.get("observations") is None:
            raise ValueError(f"invalid strategy coverage row {number}: expected strategy_id,observations")
        try:
            value = int(row["observations"])
        except ValueError as error:
            raise ValueError(f"invalid strategy coverage row {number}: observations must be an integer") from error
        if value < 0:
            raise ValueError(f"invalid strategy coverage row {number}: observations must be nonnegative")
        observations.append(value)
    return observations


def _private_diagnostics(
    private: list[CollectorRunRecord], public_start: datetime | None, public_end: datetime | None,
    private_status_path: Path, lifecycle_path: Path, matches_path: Path, alignment_path: Path,
    config: ReadinessConfig,
) -> dict[str, object]:
    latest_status: dict[str, object] = {}
    if private_status_path.exists():
        latest_status = json.loads(private_status_path.read_text(encoding="utf-8"))
    latest_private_finished_at = max((_instant(record.finished_at) for record in private), default=None)
    status_finished_at: datetime | None = None
    if isinstance(latest_status.get("finished_at"), str):
        try:
            status_finished_at = _instant(latest_status["finished_at"])
        except ValueError:
            pass
    status_gap = (
        abs((status_finished_at - latest_private_finished_at).total_seconds() / 60)
        if status_finished_at is not None and latest_private_finished_at is not None else None
    )
    status_aligned = status_gap is not None and status_gap <= config.max_private_gap_minutes
    status_ok = latest_status.get("status") == "success" and not latest_status.get("failures") and status_aligned
    lifecycle, matches, alignment = _read_rows(lifecycle_path), _read_rows(matches_path), _read_rows(alignment_path)
    unique_offers = len({row.get("offer_id", "") for row in lifecycle if row.get("offer_id", "")})
    executed = sum(row.get("outcome") == "executed" for row in lifecycle)
    canceled = sum(row.get("outcome") == "canceled" for row in lifecycle)
    matched_trades = sum(int(row.get("matched_trade_count", "0") or 0) for row in matches if row.get("match_status") == "matched")
    if public_start is not None and public_end is not None:
        aligned = [row for row in alignment if row.get("collected_at") and public_start <= _instant(row["collected_at"]) <= public_end]
    else:
        aligned = []
    alignment_rate = sum(row.get("market_matched") in {"1", "true", "True"} for row in aligned) / len(aligned) if aligned else 0.0
    checks = {
        "latest_private_status": status_ok, "unique_offers": unique_offers >= config.min_offers,
        "executed_offers": executed >= config.min_executed, "canceled_offers": canceled >= config.min_canceled,
        "matched_trades": matched_trades >= config.min_matched_trades,
        "market_alignment": alignment_rate >= config.min_alignment_rate,
    }
    return {"checks": checks, "metrics": {
        "latest_private_run_finished_at": latest_private_finished_at.isoformat() if latest_private_finished_at else "",
        "latest_private_status_finished_at": status_finished_at.isoformat() if status_finished_at else "",
        "latest_private_status_gap_minutes": round(status_gap, 6) if status_gap is not None else "",
        "latest_private_status_aligned": status_aligned, "latest_private_status": latest_status.get("status", "missing"),
        "unique_offers": unique_offers, "executed_offers": executed, "canceled_offers": canceled,
        "matched_trades": matched_trades, "alignment_observations": len(aligned),
        "market_alignment_rate": round(alignment_rate, 6),
    }}


def evaluate_p0_readiness(
    run_history_root: Path, private_status_path: Path, lifecycle_path: Path, matches_path: Path,
    alignment_path: Path, output_path: Path, *, config: ReadinessConfig | None = None,
    strategy_coverage_path: Path | None = None,
) -> dict[str, object]:
    config = config or ReadinessConfig()
    public = sorted((item for item in load_collector_runs(Path(run_history_root)) if item.collector == "public"), key=lambda item: _instant(item.started_at))
    private = sorted((item for item in load_collector_runs(Path(run_history_root)) if item.collector == "private"), key=lambda item: _instant(item.started_at))
    if public:
        public_start, public_end = _instant(public[0].started_at), max(_instant(item.finished_at) for item in public)
        public_hours = (public_end - public_start).total_seconds() / 3600
        public_hourly_coverage = _coverage(public, public_start, public_end, success_only=True)
        public_gap = _max_success_gap(public, public_start, public_end)
    else:
        public_start = public_end = None
        public_hours, public_hourly_coverage, public_gap = 0.0, 0.0, math.inf
    coverage_rows = _strategy_observations(Path(strategy_coverage_path) if strategy_coverage_path is not None else Path("data/modeling/p0_strategy/strategy_coverage.csv"))
    checks = {
        "public_history_duration": public_hours >= config.min_public_hours,
        "public_hourly_coverage": public_hourly_coverage >= config.min_hourly_coverage,
        "public_max_gap": bool(public) and public_gap <= config.max_public_gap_minutes,
        "strategy_observations": bool(coverage_rows) and all(value >= config.min_strategy_observations for value in coverage_rows),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    diagnostics = _private_diagnostics(private, public_start, public_end, Path(private_status_path), Path(lifecycle_path), Path(matches_path), Path(alignment_path), config)
    diagnostics["metrics"].update({
        "public_runs": len(public), "public_max_success_gap_minutes": round(public_gap, 6),
        "public_success_rate": round(sum(item.status == "success" for item in public) / len(public), 6) if public else 0.0,
    })
    result: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "status": "ready" if not reasons else "not_ready",
        "quality": "public_market_history", "metrics": {
            "public_history_start": public_start.isoformat() if public_start else "",
            "public_history_end": public_end.isoformat() if public_end else "",
            "public_history_hours": round(public_hours, 6), "public_hourly_coverage": round(public_hourly_coverage, 6),
            "public_max_success_gap_minutes": round(public_gap, 6), "strategy_coverage_rows": len(coverage_rows),
            "strategy_min_observations": min(coverage_rows) if coverage_rows else 0,
        }, "checks": checks, "diagnostics": diagnostics, "thresholds": asdict(config), "reasons": reasons,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate P0 public-data readiness without running a backtest")
    parser.add_argument("--run-history-root", type=Path, default=Path("data/metadata/collector_runs"))
    parser.add_argument("--private-status", type=Path, default=Path("data/metadata/account_collector_status.json"))
    parser.add_argument("--lifecycle", type=Path, default=Path("data/modeling/p0_offer_lifecycle.csv"))
    parser.add_argument("--matches", type=Path, default=Path("data/modeling/p0_offer_trade_matches.csv"))
    parser.add_argument("--alignment", type=Path, default=Path("data/modeling/p0_aligned_private_market.csv"))
    parser.add_argument("--strategy-coverage", type=Path, default=Path("data/modeling/p0_strategy/strategy_coverage.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/metadata/p0_data_readiness.json"))
    args = parser.parse_args()
    result = evaluate_p0_readiness(args.run_history_root, args.private_status, args.lifecycle, args.matches, args.alignment, args.output, strategy_coverage_path=args.strategy_coverage)
    print(json.dumps({"status": result["status"], "reasons": result["reasons"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
