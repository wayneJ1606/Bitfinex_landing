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
    min_exact_hours: float = 168.0
    min_slot_coverage: float = 0.90
    min_hourly_coverage: float = 0.90
    min_success_rate: float = 0.95
    max_private_gap_minutes: float = 30.0
    max_public_gap_minutes: float = 120.0
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
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _bucket(value: datetime, minutes: int) -> int:
    seconds = minutes * 60
    return int(value.timestamp()) // seconds


def _coverage(
    records: list[CollectorRunRecord],
    start: datetime,
    end: datetime,
    minutes: int,
    *,
    success_only: bool = False,
) -> float:
    first = _bucket(start, minutes)
    last = _bucket(end, minutes)
    expected = max(1, last - first + 1)
    buckets = {
        _bucket(_instant(record.started_at), minutes)
        for record in records
        if first <= _bucket(_instant(record.started_at), minutes) <= last
        and (not success_only or record.status == "success")
    }
    return min(1.0, len(buckets) / expected)


def _records_in_buckets(
    records: list[CollectorRunRecord],
    start: datetime,
    end: datetime,
    minutes: int,
) -> list[CollectorRunRecord]:
    first = _bucket(start, minutes)
    last = _bucket(end, minutes)
    return [
        record
        for record in records
        if first <= _bucket(_instant(record.started_at), minutes) <= last
    ]


def _success_rate(records: list[CollectorRunRecord]) -> float:
    if not records:
        return 0.0
    return sum(record.status == "success" for record in records) / len(records)


def _max_success_gap(
    records: list[CollectorRunRecord], start: datetime, end: datetime
) -> float:
    times = sorted(
        _instant(record.started_at)
        for record in records
        if record.status == "success"
    )
    if not times:
        return math.inf
    gaps = [max(0.0, (times[0] - start).total_seconds() / 60)]
    gaps.extend(
        (later - earlier).total_seconds() / 60 for earlier, later in zip(times, times[1:])
    )
    gaps.append(max(0.0, (end - times[-1]).total_seconds() / 60))
    return max(gaps)


def evaluate_p0_readiness(
    run_history_root: Path,
    private_status_path: Path,
    lifecycle_path: Path,
    matches_path: Path,
    alignment_path: Path,
    output_path: Path,
    *,
    config: ReadinessConfig | None = None,
) -> dict[str, object]:
    config = config or ReadinessConfig()
    all_records = load_collector_runs(Path(run_history_root))
    public = [record for record in all_records if record.collector == "public"]
    private = [record for record in all_records if record.collector == "private"]
    overlap_start: datetime | None = None
    overlap_end: datetime | None = None
    if public and private:
        overlap_start = max(_instant(public[0].started_at), _instant(private[0].started_at))
        overlap_end = min(_instant(public[-1].finished_at), _instant(private[-1].finished_at))
        if overlap_end < overlap_start:
            overlap_start = overlap_end = None

    if overlap_start is not None and overlap_end is not None:
        exact_hours = (overlap_end - overlap_start).total_seconds() / 3600
        public_window = _records_in_buckets(public, overlap_start, overlap_end, 60)
        private_window = _records_in_buckets(private, overlap_start, overlap_end, 5)
        public_slot_coverage = _coverage(public_window, overlap_start, overlap_end, 60)
        private_slot_coverage = _coverage(private_window, overlap_start, overlap_end, 5)
        public_hourly_coverage = _coverage(public_window, overlap_start, overlap_end, 60, success_only=True)
        private_hourly_coverage = _coverage(private_window, overlap_start, overlap_end, 60, success_only=True)
    else:
        exact_hours = public_slot_coverage = private_slot_coverage = 0.0
        public_hourly_coverage = private_hourly_coverage = 0.0
        public_window = []
        private_window = []

    public_success_rate = _success_rate(public_window)
    private_success_rate = _success_rate(private_window)
    if overlap_start is not None and overlap_end is not None:
        public_gap = _max_success_gap(public_window, overlap_start, overlap_end)
        private_gap = _max_success_gap(private_window, overlap_start, overlap_end)
    else:
        public_gap = private_gap = math.inf

    latest_status: dict[str, object] = {}
    if Path(private_status_path).exists():
        latest_status = json.loads(Path(private_status_path).read_text(encoding="utf-8"))
    latest_private_finished_at = (
        max(_instant(record.finished_at) for record in private) if private else None
    )
    status_finished_at: datetime | None = None
    status_finished_value = latest_status.get("finished_at")
    if isinstance(status_finished_value, str):
        try:
            status_finished_at = _instant(status_finished_value)
        except ValueError:
            pass
    latest_private_status_gap_minutes: float | None = None
    if status_finished_at is not None and latest_private_finished_at is not None:
        latest_private_status_gap_minutes = abs(
            (status_finished_at - latest_private_finished_at).total_seconds() / 60
        )
    latest_private_status_aligned = (
        latest_private_status_gap_minutes is not None
        and latest_private_status_gap_minutes <= config.max_private_gap_minutes
    )
    latest_private_ok = (
        latest_status.get("status") == "success"
        and not latest_status.get("failures")
        and latest_private_status_aligned
    )

    lifecycle = _read_rows(Path(lifecycle_path))
    unique_offers = len({row.get("offer_id", "") for row in lifecycle if row.get("offer_id", "")})
    executed = sum(row.get("outcome") == "executed" for row in lifecycle)
    canceled = sum(row.get("outcome") == "canceled" for row in lifecycle)
    matches = _read_rows(Path(matches_path))
    matched_trades = sum(
        int(row.get("matched_trade_count", "0") or 0)
        for row in matches
        if row.get("match_status") == "matched"
    )

    alignment = _read_rows(Path(alignment_path))
    if overlap_start is not None and overlap_end is not None:
        aligned_window = [
            row
            for row in alignment
            if row.get("collected_at")
            and overlap_start <= _instant(row["collected_at"]) <= overlap_end
        ]
    else:
        aligned_window = []
    alignment_rate = (
        sum(row.get("market_matched") in {"1", "true", "True"} for row in aligned_window)
        / len(aligned_window)
        if aligned_window
        else 0.0
    )

    checks = {
        "exact_history_duration": exact_hours >= config.min_exact_hours,
        "public_slot_coverage": public_slot_coverage >= config.min_slot_coverage,
        "private_slot_coverage": private_slot_coverage >= config.min_slot_coverage,
        "public_hourly_coverage": public_hourly_coverage >= config.min_hourly_coverage,
        "private_hourly_coverage": private_hourly_coverage >= config.min_hourly_coverage,
        "public_success_rate": public_success_rate >= config.min_success_rate,
        "private_success_rate": private_success_rate >= config.min_success_rate,
        "public_max_gap": bool(public_window) and public_gap <= config.max_public_gap_minutes,
        "private_max_gap": bool(private_window) and private_gap <= config.max_private_gap_minutes,
        "latest_private_status": latest_private_ok,
        "unique_offers": unique_offers >= config.min_offers,
        "executed_offers": executed >= config.min_executed,
        "canceled_offers": canceled >= config.min_canceled,
        "matched_trades": matched_trades >= config.min_matched_trades,
        "market_alignment": alignment_rate >= config.min_alignment_rate,
    }
    reasons = [name for name, passed in checks.items() if not passed]
    metrics: dict[str, object] = {
        "exact_overlap_start": overlap_start.isoformat() if overlap_start else "",
        "exact_overlap_end": overlap_end.isoformat() if overlap_end else "",
        "exact_overlap_hours": round(exact_hours, 6),
        "public_exact_runs": len(public_window),
        "private_exact_runs": len(private_window),
        "public_slot_coverage": round(public_slot_coverage, 6),
        "private_slot_coverage": round(private_slot_coverage, 6),
        "public_hourly_coverage": round(public_hourly_coverage, 6),
        "private_hourly_coverage": round(private_hourly_coverage, 6),
        "public_success_rate": round(public_success_rate, 6),
        "private_success_rate": round(private_success_rate, 6),
        "public_failure_rate": round(1 - public_success_rate, 6),
        "private_failure_rate": round(1 - private_success_rate, 6),
        "public_max_success_gap_minutes": round(public_gap, 6),
        "private_max_success_gap_minutes": round(private_gap, 6),
        "latest_private_run_finished_at": (
            latest_private_finished_at.isoformat() if latest_private_finished_at else ""
        ),
        "latest_private_status_finished_at": (
            status_finished_at.isoformat() if status_finished_at else ""
        ),
        "latest_private_status_gap_minutes": (
            round(latest_private_status_gap_minutes, 6)
            if latest_private_status_gap_minutes is not None
            else ""
        ),
        "latest_private_status_aligned": latest_private_status_aligned,
        "unique_offers": unique_offers,
        "executed_offers": executed,
        "canceled_offers": canceled,
        "matched_trades": matched_trades,
        "alignment_observations": len(aligned_window),
        "market_alignment_rate": round(alignment_rate, 6),
        "latest_private_status": latest_status.get("status", "missing"),
    }
    result: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if not reasons else "not_ready",
        "quality": "exact_run_history",
        "metrics": metrics,
        "checks": checks,
        "thresholds": asdict(config),
        "reasons": reasons,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate P0 exact data readiness without running a backtest")
    parser.add_argument("--run-history-root", type=Path, default=Path("data/metadata/collector_runs"))
    parser.add_argument("--private-status", type=Path, default=Path("data/metadata/account_collector_status.json"))
    parser.add_argument("--lifecycle", type=Path, default=Path("data/modeling/p0_offer_lifecycle.csv"))
    parser.add_argument("--matches", type=Path, default=Path("data/modeling/p0_offer_trade_matches.csv"))
    parser.add_argument("--alignment", type=Path, default=Path("data/modeling/p0_aligned_private_market.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/metadata/p0_data_readiness.json"))
    args = parser.parse_args()
    result = evaluate_p0_readiness(
        args.run_history_root,
        args.private_status,
        args.lifecycle,
        args.matches,
        args.alignment,
        args.output,
    )
    print(json.dumps({"status": result["status"], "reasons": result["reasons"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
