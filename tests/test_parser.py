from __future__ import annotations

import pytest

from bitfinex_lending.parser import ParseError, parse_book


FETCHED_AT = "2026-07-14T12:00:00+00:00"


def test_parse_book_converts_offer_and_demand_rows() -> None:
    rows = parse_book(
        [[0.0002, 2, 3, 10.5], [0.0003, 7, 1, -4.0]],
        market="fUSD",
        run_id="run-1",
        fetched_at=FETCHED_AT,
    )

    assert [row.side for row in rows] == ["offer", "demand"]
    assert rows[0].market == "fUSD"
    assert rows[0].run_id == "run-1"
    assert rows[0].fetched_at == FETCHED_AT
    assert (rows[0].rate, rows[0].period, rows[0].count, rows[0].amount) == (
        0.0002,
        2,
        3,
        10.5,
    )


def test_parse_book_accepts_empty_payload() -> None:
    assert parse_book([], "fUSD", "run-1", FETCHED_AT) == ()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"rate": 1}, "book payload must be a list"),
        ([[1, 2, 3]], "book row 0 must contain 4 values"),
        ([[True, 2, 3, 4]], "book row 0 rate must be numeric"),
        ([[1, 2.5, 3, 4]], "book row 0 period must be an integer"),
        ([[1, 2, 3.5, 4]], "book row 0 count must be an integer"),
        ([[1, 2, 3, "amount"]], "book row 0 amount must be numeric"),
        ([[1, 2, 3, 0]], "book row 0 amount must not be zero"),
    ],
)
def test_parse_book_rejects_invalid_payload(payload: object, message: str) -> None:
    with pytest.raises(ParseError, match=f"^{message}$"):
        parse_book(payload, "fUSD", "run-1", FETCHED_AT)

