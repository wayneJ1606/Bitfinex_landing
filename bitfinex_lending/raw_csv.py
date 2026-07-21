from __future__ import annotations

import csv
from datetime import datetime, timezone
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
SUPPORTED_MARKETS = frozenset({"fUSD", "fBTC", "fETH"})


class RawCsvError(ValueError):
    pass


def load_raw_snapshots(root: Path) -> tuple[FundingBookRow, ...]:
    root = Path(root)
    if not root.exists():
        return ()

    parsed: list[tuple[datetime, FundingBookRow]] = []
    seen_rows: set[tuple[object, ...]] = set()
    run_times: dict[tuple[str, str], str] = {}
    for path in sorted(root.rglob("*.csv"), key=lambda item: item.as_posix()):
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
