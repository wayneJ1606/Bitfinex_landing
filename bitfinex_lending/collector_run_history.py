from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FIELDS = (
    "run_id",
    "collector",
    "started_at",
    "finished_at",
    "status",
    "quality",
    "expected_interval_minutes",
    "successful_units",
    "failed_units",
    "row_counts_json",
    "failures_json",
    "permission_checked",
    "duration_seconds",
    "schema_version",
)
SCHEMA_VERSION = "collector-run-history-v1"


class CollectorRunHistoryError(RuntimeError):
    """Raised when exact collector run history cannot be saved or loaded."""


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"timestamp must be ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class CollectorRunRecord:
    run_id: str
    collector: str
    started_at: str
    finished_at: str
    status: str
    expected_interval_minutes: int
    successful_units: int
    failed_units: int
    row_counts: dict[str, int]
    failures: dict[str, str]
    permission_checked: bool | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        if self.collector not in {"public", "private"}:
            raise ValueError("collector must be public or private")
        if self.status not in {"success", "partial", "failed"}:
            raise ValueError("status must be success, partial, or failed")
        started = _instant(self.started_at)
        finished = _instant(self.finished_at)
        if finished < started:
            raise ValueError("finished_at must not precede started_at")
        if self.expected_interval_minutes <= 0:
            raise ValueError("expected_interval_minutes must be positive")
        if self.successful_units < 0 or self.failed_units < 0:
            raise ValueError("unit counts must be nonnegative")

    @property
    def duration_seconds(self) -> float:
        return (_instant(self.finished_at) - _instant(self.started_at)).total_seconds()


def _target(root: Path, record: CollectorRunRecord) -> Path:
    started = _instant(record.started_at)
    return (
        Path(root)
        / started.strftime("%Y")
        / started.strftime("%m")
        / started.strftime("%d")
        / f"{record.collector}.csv"
    )


def _serialize(record: CollectorRunRecord) -> dict[str, object]:
    return {
        "run_id": record.run_id,
        "collector": record.collector,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "status": record.status,
        "quality": "exact",
        "expected_interval_minutes": record.expected_interval_minutes,
        "successful_units": record.successful_units,
        "failed_units": record.failed_units,
        "row_counts_json": json.dumps(record.row_counts, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "failures_json": json.dumps(record.failures, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "permission_checked": "" if record.permission_checked is None else str(record.permission_checked).lower(),
        "duration_seconds": record.duration_seconds,
        "schema_version": SCHEMA_VERSION,
    }


def append_collector_run(root: Path, record: CollectorRunRecord) -> Path:
    target = _target(Path(root), record)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, str]] = []
    if target.exists():
        try:
            with target.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if tuple(reader.fieldnames or ()) != FIELDS:
                    raise CollectorRunHistoryError(f"unexpected run history header: {target}")
                existing = list(reader)
        except (OSError, csv.Error) as exc:
            raise CollectorRunHistoryError(f"cannot read run history {target}: {exc}") from exc
    if any(row["run_id"] == record.run_id and row["collector"] == record.collector for row in existing):
        return target
    temporary = target.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(existing)
            writer.writerow(_serialize(record))
        temporary.replace(target)
    except (OSError, csv.Error) as exc:
        temporary.unlink(missing_ok=True)
        raise CollectorRunHistoryError(f"cannot write run history {target}: {exc}") from exc
    return target


def _deserialize(row: dict[str, str]) -> CollectorRunRecord:
    return CollectorRunRecord(
        run_id=row["run_id"],
        collector=row["collector"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        expected_interval_minutes=int(row["expected_interval_minutes"]),
        successful_units=int(row["successful_units"]),
        failed_units=int(row["failed_units"]),
        row_counts={key: int(value) for key, value in json.loads(row["row_counts_json"]).items()},
        failures={key: str(value) for key, value in json.loads(row["failures_json"]).items()},
        permission_checked=None if row["permission_checked"] == "" else row["permission_checked"] == "true",
    )


def load_collector_runs(root: Path) -> tuple[CollectorRunRecord, ...]:
    root = Path(root)
    records: list[CollectorRunRecord] = []
    seen: set[tuple[str, str]] = set()
    if root.exists():
        for path in sorted(root.rglob("*.csv")):
            try:
                with path.open(encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if tuple(reader.fieldnames or ()) != FIELDS:
                        raise CollectorRunHistoryError(f"unexpected run history header: {path}")
                    for row in reader:
                        record = _deserialize(row)
                        key = (record.collector, record.run_id)
                        if key not in seen:
                            seen.add(key)
                            records.append(record)
            except (OSError, csv.Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise CollectorRunHistoryError(f"cannot load run history {path}: {exc}") from exc
    records.sort(key=lambda record: (_instant(record.started_at), record.collector, record.run_id))
    return tuple(records)
