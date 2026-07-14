from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .models import FundingBookRow


FIELD_NAMES = (
    "run_id",
    "market",
    "rate",
    "period",
    "count",
    "amount",
    "side",
    "fetched_at",
)


class CsvExportError(RuntimeError):
    """Raised when an atomic snapshot export cannot be completed."""


def _filename(rows: Sequence[FundingBookRow]) -> str:
    first = rows[0]
    safe_timestamp = first.fetched_at.replace(":", "-").replace("+", "_")
    return f"{safe_timestamp}_{first.market}_{first.run_id}.csv"


def export_snapshot(
    rows: Sequence[FundingBookRow], output_directory: Path
) -> Path:
    if not rows:
        raise ValueError("CSV export requires at least one row")
    first = rows[0]
    if any(row.run_id != first.run_id or row.market != first.market for row in rows):
        raise ValueError("CSV export rows must share run_id and market")

    output_directory = Path(output_directory)
    target_path = output_directory / _filename(rows)
    temporary_path = target_path.with_suffix(".csv.tmp")
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELD_NAMES)
            writer.writerows(
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
            )
        temporary_path.replace(target_path)
    except (OSError, csv.Error) as error:
        temporary_path.unlink(missing_ok=True)
        raise CsvExportError(f"failed to export CSV: {error}") from error
    return target_path

