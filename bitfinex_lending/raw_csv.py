from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
import math
from pathlib import Path
from typing import Iterator

from .models import FundingBookRow


RAW_FIELDS = (
    "run_id",
    "market",
    "rate",
    "period",
    "count",
    "amount",
    "side",
    "fetched_at",
)
SUPPORTED_MARKETS = frozenset({"fUSD", "fUST", "fBTC", "fETH"})


class RawCsvError(ValueError):
    pass


@dataclass(frozen=True)
class MergedRawSnapshots:
    rows: tuple[FundingBookRow, ...]
    primary_snapshots: int
    fallback_snapshots: int
    selected_primary_snapshots: int
    selected_fallback_snapshots: int
    overlapping_hours: int
    discarded_same_source_snapshots: int
    discarded_fallback_snapshots: int


def load_raw_snapshots(root: Path) -> tuple[FundingBookRow, ...]:
    root = Path(root)
    try:
        exists = root.exists()
    except OSError as error:
        raise _root_error(error) from error
    if not exists:
        return ()
    try:
        is_directory = root.is_dir()
    except OSError as error:
        raise _root_error(error) from error
    if not is_directory:
        raise RawCsvError("invalid raw CSV root: raw root must be a directory")
    try:
        paths = sorted(root.rglob("*.csv"), key=lambda item: item.as_posix())
    except OSError as error:
        raise _root_error(error) from error

    parsed: list[tuple[datetime, FundingBookRow]] = []
    seen_rows: set[tuple[object, ...]] = set()
    run_times: dict[tuple[str, str], str] = {}
    for path in paths:
        _validate_raw_path(path, root)
        for line_number, values in _read_rows(path, root):
            row, timestamp = _parse_row(values, path, root, line_number)
            run_key = (row.run_id, row.market)
            previous_time = run_times.setdefault(run_key, row.fetched_at)
            if previous_time != row.fetched_at:
                raise _csv_error(
                    root, path, line_number, "run_id has conflicting fetched_at"
                )
            row_key = (
                row.run_id,
                row.market,
                row.fetched_at,
                row.rate,
                row.period,
                row.count,
                row.amount,
                row.side,
            )
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                parsed.append((timestamp, row))

    return tuple(
        row
        for _, row in sorted(
            parsed,
            key=lambda item: (
                item[1].market,
                item[0],
                item[1].run_id,
                item[1].rate,
            ),
        )
    )


def load_merged_raw_snapshots(
    primary_root: Path, fallback_root: Path
) -> MergedRawSnapshots:
    """Select one intact snapshot per market-hour, preferring primary data."""
    primary_rows = load_raw_snapshots(primary_root)
    fallback_rows = load_raw_snapshots(fallback_root)
    primary = _hourly_snapshots(primary_rows)
    fallback = _hourly_snapshots(fallback_rows)
    primary_hours = set(primary)
    fallback_hours = set(fallback)
    overlapping_hours = primary_hours.intersection(fallback_hours)

    selected: list[tuple[datetime, tuple[FundingBookRow, ...]]] = []
    for hour_key, snapshots in primary.items():
        selected.append(_latest_snapshot(snapshots))
    for hour_key, snapshots in fallback.items():
        if hour_key not in primary:
            selected.append(_latest_snapshot(snapshots))

    rows = tuple(
        row
        for _, snapshot_rows in sorted(
            selected,
            key=lambda item: (item[1][0].market, item[0], item[1][0].run_id),
        )
        for row in snapshot_rows
    )
    primary_snapshot_count = sum(len(items) for items in primary.values())
    fallback_snapshot_count = sum(len(items) for items in fallback.values())
    discarded_same_source = sum(
        max(0, len(items) - 1)
        for hourly in (primary, fallback)
        for items in hourly.values()
    )
    discarded_fallback = sum(len(fallback[key]) for key in overlapping_hours)
    return MergedRawSnapshots(
        rows=rows,
        primary_snapshots=primary_snapshot_count,
        fallback_snapshots=fallback_snapshot_count,
        selected_primary_snapshots=len(primary),
        selected_fallback_snapshots=len(fallback_hours - primary_hours),
        overlapping_hours=len(overlapping_hours),
        discarded_same_source_snapshots=discarded_same_source,
        discarded_fallback_snapshots=discarded_fallback,
    )


def _hourly_snapshots(
    rows: tuple[FundingBookRow, ...],
) -> dict[tuple[str, datetime], list[tuple[datetime, tuple[FundingBookRow, ...]]]]:
    snapshots: dict[tuple[str, str, str], list[FundingBookRow]] = {}
    for row in rows:
        snapshots.setdefault((row.market, row.fetched_at, row.run_id), []).append(row)

    hourly: dict[
        tuple[str, datetime], list[tuple[datetime, tuple[FundingBookRow, ...]]]
    ] = {}
    for (market, fetched_at, _), snapshot_rows in snapshots.items():
        timestamp = datetime.fromisoformat(fetched_at).astimezone(timezone.utc)
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        hourly.setdefault((market, hour), []).append((timestamp, tuple(snapshot_rows)))
    return hourly


def _latest_snapshot(
    snapshots: list[tuple[datetime, tuple[FundingBookRow, ...]]],
) -> tuple[datetime, tuple[FundingBookRow, ...]]:
    return max(snapshots, key=lambda item: (item[0], item[1][0].run_id))


def _root_error(error: OSError) -> RawCsvError:
    return RawCsvError(f"invalid raw CSV root: {error}")


def _validate_raw_path(path: Path, root: Path) -> None:
    relative = path.relative_to(root)
    parts = relative.parts
    reason = "path must match YYYY/MM/DD/<supported-market>.csv"
    if len(parts) != 4:
        raise _csv_error(root, path, 1, reason)

    year, month, day, filename = parts
    if (
        len(year) != 4
        or len(month) != 2
        or len(day) != 2
        or not year.isdigit()
        or not month.isdigit()
        or not day.isdigit()
    ):
        raise _csv_error(root, path, 1, reason)
    try:
        date(int(year), int(month), int(day))
    except ValueError as error:
        raise _csv_error(root, path, 1, reason) from error

    filename_path = Path(filename)
    if filename_path.suffix != ".csv":
        raise _csv_error(root, path, 1, reason)
    if filename_path.stem not in SUPPORTED_MARKETS:
        raise _csv_error(root, path, 1, "unsupported market in path")


def _csv_error(
    root: Path, path: Path, line_number: int, reason: str
) -> RawCsvError:
    relative_path = path.relative_to(root).as_posix()
    return RawCsvError(
        f"invalid raw CSV {relative_path} row {line_number}: {reason}"
    )


def _read_rows(
    path: Path, root: Path
) -> Iterator[tuple[int, dict[str, str]]]:
    line_number = 1
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                header = next(reader)
            except StopIteration:
                raise _csv_error(root, path, 1, "missing field") from None

            if len(set(header)) != len(header):
                raise _csv_error(root, path, 1, "duplicate field")
            if tuple(header) != RAW_FIELDS:
                if any(field not in header for field in RAW_FIELDS):
                    reason = "missing field"
                elif any(field not in RAW_FIELDS for field in header):
                    reason = "extra field"
                else:
                    reason = "fields must be in the expected order"
                raise _csv_error(root, path, 1, reason)

            for line_number, row in enumerate(reader, start=2):
                if len(row) < len(RAW_FIELDS):
                    raise _csv_error(root, path, line_number, "missing field")
                if len(row) > len(RAW_FIELDS):
                    raise _csv_error(root, path, line_number, "extra field")
                yield line_number, dict(zip(RAW_FIELDS, row, strict=True))
    except RawCsvError:
        raise
    except UnicodeDecodeError as error:
        raise _csv_error(root, path, line_number, "invalid UTF-8") from error
    except OSError as error:
        raise _csv_error(root, path, line_number, str(error)) from error
    except csv.Error as error:
        raise _csv_error(root, path, line_number, str(error)) from error


def _utc_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("invalid timestamp") from error
    if timestamp.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return timestamp.astimezone(timezone.utc)


def _parse_float(value: str, field: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a number") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be finite")
    return parsed


def _parse_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an integer") from error


def _parse_row(
    values: dict[str, str], path: Path, root: Path, line_number: int
) -> tuple[FundingBookRow, datetime]:
    try:
        market = values["market"]
        if market not in SUPPORTED_MARKETS:
            raise ValueError("unsupported market")
        if path.stem != market:
            raise ValueError("path market does not match row")

        timestamp = _utc_timestamp(values["fetched_at"])
        rate = _parse_float(values["rate"], "rate")
        period = _parse_int(values["period"], "period")
        count = _parse_int(values["count"], "count")
        amount = _parse_float(values["amount"], "amount")
        side = values["side"]

        if period <= 0:
            raise ValueError("period must be positive")
        if count < 0:
            raise ValueError("count must be nonnegative")
        if amount == 0:
            raise ValueError("amount must not be zero")
        if side == "offer" and amount < 0:
            raise ValueError("offer amount must be positive")
        if side == "demand" and amount > 0:
            raise ValueError("demand amount must be negative")
        if side not in {"offer", "demand"}:
            raise ValueError("side must be offer or demand")

        row = FundingBookRow(
            run_id=values["run_id"],
            market=market,
            rate=rate,
            period=period,
            count=count,
            amount=amount,
            side=side,  # type: ignore[arg-type]
            fetched_at=timestamp.isoformat(),
        )
        return row, timestamp
    except (KeyError, TypeError, ValueError) as error:
        raise _csv_error(root, path, line_number, str(error)) from error
