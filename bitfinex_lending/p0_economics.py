"""Authoritative, Decimal-safe economics for public Bitfinex funding offers."""

from decimal import Decimal, InvalidOperation
from numbers import Integral
from typing import Final


SECONDS_PER_DAY: Final = Decimal("86400")
VISIBLE_PROVIDER_FEE: Final = Decimal("0.15")
TRANCHE: Final = Decimal("1000")
MINIMUM_BILLABLE_SECONDS: Final = 3600
MAXIMUM_TRANCHES: Final = 10


class EconomicsError(ValueError):
    """Raised when an economics input is not an approved positive exact value."""


def _positive_decimal(value: object, name: str) -> Decimal:
    """Return a finite positive Decimal without admitting binary float inputs."""
    if isinstance(value, bool) or isinstance(value, float):
        raise EconomicsError(f"{name} must be an exact Decimal-compatible value")
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise EconomicsError(f"{name} must be an exact Decimal-compatible value") from error
    if not number.is_finite() or number <= 0:
        raise EconomicsError(f"{name} must be finite and greater than zero")
    return number


def _positive_seconds(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise EconomicsError(f"{name} must be a whole number greater than zero")
    return int(value)


def billable_seconds(actual_seconds: int, minimum_one_hour: bool = True) -> int:
    """Return positive elapsed seconds, applying the optional one-hour minimum."""
    seconds = _positive_seconds(actual_seconds, "actual_seconds")
    return max(seconds, MINIMUM_BILLABLE_SECONDS) if minimum_one_hour else seconds


def gross_interest(principal: Decimal, daily_rate: Decimal, seconds: int) -> Decimal:
    """Calculate gross interest using Bitfinex's decimal daily API rate."""
    amount = _positive_decimal(principal, "principal")
    rate = _positive_decimal(daily_rate, "daily_rate")
    duration = _positive_seconds(seconds, "seconds")
    return amount * rate * Decimal(duration) / SECONDS_PER_DAY


def net_interest(principal: Decimal, daily_rate: Decimal, seconds: int) -> Decimal:
    """Calculate interest after the public visible 15 percent funding fee."""
    return gross_interest(principal, daily_rate, seconds) * (Decimal("1") - VISIBLE_PROVIDER_FEE)


def capital_levels() -> tuple[Decimal, ...]:
    """Return the approved 1,000 through 10,000 principal levels."""
    return tuple(TRANCHE * index for index in range(1, MAXIMUM_TRANCHES + 1))


def split_capital(principal: Decimal) -> tuple[Decimal, ...]:
    """Split an approved principal level into 1,000-unit tranches."""
    amount = _positive_decimal(principal, "principal")
    if amount not in capital_levels():
        raise EconomicsError("principal must be 1000 through 10000 in 1000-unit increments")
    return (TRANCHE,) * int(amount / TRANCHE)
