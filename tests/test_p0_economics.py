from decimal import Decimal

import pytest

from bitfinex_lending.p0_economics import (
    EconomicsError,
    billable_seconds,
    capital_levels,
    gross_interest,
    net_interest,
    split_capital,
)


def test_official_example_treats_api_rate_as_a_decimal_daily_rate() -> None:
    assert gross_interest(Decimal("10000"), Decimal("0.0006"), 86400) == Decimal("6.0000")
    assert net_interest(Decimal("10000"), Decimal("0.0006"), 86400) == Decimal("5.100000")


def test_net_interest_applies_exactly_the_visible_fifteen_percent_fee() -> None:
    assert net_interest(Decimal("1000"), Decimal("0.001"), 86400) == Decimal("0.8500")


def test_billable_seconds_defaults_to_one_hour_minimum_and_can_be_disabled() -> None:
    assert billable_seconds(600) == 3600
    assert billable_seconds(600, minimum_one_hour=False) == 600
    assert billable_seconds(3601) == 3601


def test_capital_levels_are_the_exact_thousand_unit_grid() -> None:
    assert capital_levels() == tuple(Decimal(index * 1000) for index in range(1, 11))


@pytest.mark.parametrize(
    ("principal", "expected"),
    [
        (Decimal("1000"), (Decimal("1000"),)),
        (Decimal("3000"), (Decimal("1000"),) * 3),
        (Decimal("10000"), (Decimal("1000"),) * 10),
    ],
)
def test_split_capital_returns_only_thousand_unit_tranches(
    principal: Decimal, expected: tuple[Decimal, ...]
) -> None:
    assert split_capital(principal) == expected


@pytest.mark.parametrize(
    "principal",
    [Decimal("999"), Decimal("1001"), Decimal("11000"), Decimal("0"), Decimal("-1000")],
)
def test_split_capital_rejects_principals_outside_the_approved_grid(principal: Decimal) -> None:
    with pytest.raises(EconomicsError):
        split_capital(principal)


@pytest.mark.parametrize("value", [True, Decimal("NaN"), Decimal("Infinity"), Decimal("0"), Decimal("-1"), 1.0])
def test_interest_rejects_invalid_or_inexact_principal(value: object) -> None:
    with pytest.raises(EconomicsError):
        gross_interest(value, Decimal("0.0002"), 3600)


@pytest.mark.parametrize("value", [True, Decimal("NaN"), Decimal("Infinity"), Decimal("0"), Decimal("-0.0002"), 0.0002])
def test_interest_rejects_invalid_or_inexact_daily_rate(value: object) -> None:
    with pytest.raises(EconomicsError):
        gross_interest(Decimal("1000"), value, 3600)


@pytest.mark.parametrize("seconds", [True, Decimal("NaN"), Decimal("Infinity"), 0, -1, 1.5])
def test_interest_and_billing_reject_invalid_duration(seconds: object) -> None:
    with pytest.raises(EconomicsError):
        gross_interest(Decimal("1000"), Decimal("0.0002"), seconds)
    with pytest.raises(EconomicsError):
        billable_seconds(seconds)

