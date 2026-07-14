from __future__ import annotations

from typing import Literal

from .models import FundingBookRow


class ParseError(ValueError):
    """Raised when a funding-book payload violates the expected schema."""


def _numeric(value: object, *, row_index: int, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParseError(f"book row {row_index} {field} must be numeric")
    return float(value)


def _integer(value: object, *, row_index: int, field: str) -> int:
    number = _numeric(value, row_index=row_index, field=field)
    if not number.is_integer():
        raise ParseError(f"book row {row_index} {field} must be an integer")
    return int(number)


def _parse_row(
    raw_row: object,
    *,
    row_index: int,
    market: str,
    run_id: str,
    fetched_at: str,
) -> FundingBookRow:
    if not isinstance(raw_row, (list, tuple)) or len(raw_row) != 4:
        raise ParseError(f"book row {row_index} must contain 4 values")

    rate = _numeric(raw_row[0], row_index=row_index, field="rate")
    period = _integer(raw_row[1], row_index=row_index, field="period")
    count = _integer(raw_row[2], row_index=row_index, field="count")
    amount = _numeric(raw_row[3], row_index=row_index, field="amount")
    if amount == 0:
        raise ParseError(f"book row {row_index} amount must not be zero")
    side: Literal["offer", "demand"] = "offer" if amount > 0 else "demand"

    return FundingBookRow(
        run_id=run_id,
        market=market,
        rate=rate,
        period=period,
        count=count,
        amount=amount,
        side=side,
        fetched_at=fetched_at,
    )


def parse_book(
    payload: object,
    market: str,
    run_id: str,
    fetched_at: str,
) -> tuple[FundingBookRow, ...]:
    if not isinstance(payload, list):
        raise ParseError("book payload must be a list")
    return tuple(
        _parse_row(
            raw_row,
            row_index=index,
            market=market,
            run_id=run_id,
            fetched_at=fetched_at,
        )
        for index, raw_row in enumerate(payload)
    )

