from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .csv_export import FIELD_NAMES, CsvExportError
from .models import FundingBookRow


SUPPORTED_MARKETS = frozenset({"fUSD", "fUST", "fBTC", "fETH"})


def _validate_rows(rows: Sequence[FundingBookRow]) -> FundingBookRow:
    if not rows:
        raise ValueError("daily CSV export requires at least one row")
    first = rows[0]
    if any(row.run_id != first.run_id or row.market != first.market for row in rows):
        raise ValueError("daily CSV rows must share run_id and market")
    if first.market not in SUPPORTED_MARKETS:
        raise ValueError("daily CSV rows must use a supported market")
    return first


def _utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("fetched_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _serialize(rows: Sequence[FundingBookRow]) -> list[tuple[object, ...]]:
    return [
        (
            row.run_id,
            row.market,
            row.rate,
            row.period,
            row.count,
            row.amount,
            row.side,
            row.fetched_at,
        )
        for row in rows
    ]


def append_daily_snapshot(
    rows: Sequence[FundingBookRow], output_root: Path
) -> Path:
    first = _validate_rows(rows)
    observed_at = _utc_date(first.fetched_at)
    if any(_utc_date(row.fetched_at).date() != observed_at.date() for row in rows[1:]):
        raise ValueError("daily CSV rows must share the same UTC date")
    target = Path(output_root) / observed_at.strftime("%Y/%m/%d") / f"{first.market}.csv"
    temporary = target.with_suffix(".csv.tmp")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing: list[list[str]] = []
        if target.exists():
            with target.open(encoding="utf-8", newline="") as stream:
                existing = list(csv.reader(stream))
            if any(row and row[0] == first.run_id for row in existing[1:]):
                return target

        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            if existing:
                writer.writerows(existing)
            else:
                writer.writerow(FIELD_NAMES)
            writer.writerows(_serialize(rows))
        temporary.replace(target)
    except (OSError, csv.Error) as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise CsvExportError(f"failed to append daily CSV: {error}") from error
    return target
