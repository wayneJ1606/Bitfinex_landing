"""Experimental fUST fill proxy based only on public hourly market observations."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .p0_economics import net_interest


APPROVED_QUANTILES = tuple(Decimal(value) for value in ("0.10", "0.25", "0.50", "0.75", "0.90"))
APPROVED_WAITS = (1, 3, 6, 12, 24)
APPROVED_PERIODS = (2, 5, 10, 30)


class PublicFillProxyError(ValueError):
    """Raised when public data cannot support a chronological proxy estimate."""


@dataclass(frozen=True)
class PublicFundingHour:
    observed_at: datetime
    ask_rate: Decimal
    traded_high: Decimal


@dataclass(frozen=True)
class PublicFillEstimate:
    strategy_id: str
    rate_quantile: Decimal
    period_days: int
    wait_hours: int
    observations: int
    proxy_fills: int
    proxy_fill_probability: Decimal
    average_success_wait_hours: Decimal
    average_candidate_daily_rate: Decimal
    expected_30d_net_profit_per_1000: Decimal
    idle_fraction: Decimal
    confidence: str = "very_low"
    method: str = "public_trade_high_proxy"


def _number(value: str, field: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise PublicFillProxyError(f"{field} must be a decimal") from error
    if not number.is_finite():
        raise PublicFillProxyError(f"{field} must be finite")
    return number


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PublicFillProxyError("collected_at must be ISO 8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PublicFillProxyError("collected_at must include timezone")
    return parsed.astimezone(timezone.utc)


def _series(root: Path, category: str, field: str) -> dict[datetime, tuple[datetime, Decimal]]:
    category_root = root / category
    result: dict[datetime, tuple[datetime, Decimal]] = {}
    if not category_root.exists():
        return result
    for path in sorted(category_root.rglob("fUST.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("market") != "fUST":
                    continue
                collected_at = _instant(row.get("collected_at", ""))
                value = _number(row.get(field, ""), field)
                if value < 0 or (field == "ask" and value == 0):
                    raise PublicFillProxyError(f"{field} has an invalid value")
                hour = collected_at.replace(minute=0, second=0, microsecond=0)
                previous = result.get(hour)
                if previous is None or collected_at > previous[0]:
                    result[hour] = (collected_at, value)
    return result


def load_fust_public_hours(market_root: Path) -> tuple[PublicFundingHour, ...]:
    """Pair the latest fUST ticker and funding-candle observation in each UTC hour."""
    root = Path(market_root)
    asks = _series(root, "ticker", "ask")
    highs = _series(root, "funding_candles", "high")
    return tuple(
        PublicFundingHour(hour, asks[hour][1], highs[hour][1])
        for hour in sorted(asks.keys() & highs.keys())
    )


def _quantile(values: tuple[Decimal, ...], fraction: Decimal) -> Decimal:
    ordered = sorted(values)
    position = Decimal(len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (Decimal("1") - weight) + ordered[upper] * weight


def estimate_public_fill_proxy(
    hours: tuple[PublicFundingHour, ...],
    *,
    lookback_hours: int = 24,
    quantiles: tuple[Decimal, ...] = APPROVED_QUANTILES,
    wait_hours: tuple[int, ...] = APPROVED_WAITS,
    periods: tuple[int, ...] = APPROVED_PERIODS,
) -> tuple[PublicFillEstimate, ...]:
    """Estimate conditional 30-day profit from past-only rate candidates and later trades."""
    ordered = tuple(sorted(hours, key=lambda row: row.observed_at))
    if lookback_hours < 2:
        raise PublicFillProxyError("lookback_hours must be at least 2")
    if any(row.observed_at.tzinfo is None or row.observed_at.utcoffset() is None for row in ordered):
        raise PublicFillProxyError("observed_at must include timezone")
    if any(later.observed_at - earlier.observed_at != timedelta(hours=1) for earlier, later in zip(ordered, ordered[1:])):
        raise PublicFillProxyError("public proxy requires continuous hourly observations")
    if any(row.ask_rate <= 0 or row.traded_high < 0 for row in ordered):
        raise PublicFillProxyError("rates must be positive and trade highs nonnegative")
    if any(value <= 0 or value >= 1 for value in quantiles):
        raise PublicFillProxyError("quantiles must be between zero and one")
    if any(value <= 0 for value in wait_hours):
        raise PublicFillProxyError("wait_hours must be positive")
    if any(value not in APPROVED_PERIODS for value in periods):
        raise PublicFillProxyError("period must be one of 2, 5, 10, or 30 days")

    estimates: list[PublicFillEstimate] = []
    for quantile in quantiles:
        for wait in wait_hours:
            decision_indexes = range(lookback_hours, len(ordered) - wait)
            observations = len(decision_indexes)
            if observations <= 0:
                continue
            for period in periods:
                fills = 0
                success_wait = Decimal("0")
                candidate_sum = Decimal("0")
                profit_sum = Decimal("0")
                cycle_hours_sum = Decimal("0")
                idle_hours_sum = Decimal("0")
                for index in decision_indexes:
                    candidate = _quantile(
                        tuple(row.ask_rate for row in ordered[index - lookback_hours:index]),
                        quantile,
                    )
                    candidate_sum += candidate
                    filled_after: int | None = None
                    for offset, future in enumerate(ordered[index + 1:index + wait + 1], start=1):
                        if future.traded_high >= candidate:
                            filled_after = offset
                            break
                    if filled_after is None:
                        cycle_hours_sum += Decimal(wait)
                        idle_hours_sum += Decimal(wait)
                        continue
                    fills += 1
                    actual_wait = Decimal(filled_after)
                    success_wait += actual_wait
                    idle_hours_sum += actual_wait
                    cycle_hours_sum += actual_wait + Decimal(period * 24)
                    profit_sum += net_interest(
                        Decimal("1000"), candidate, period * 86400
                    )
                estimates.append(
                    PublicFillEstimate(
                        strategy_id=f"q{int(quantile * 100):02d}-p{period}-w{wait}",
                        rate_quantile=quantile,
                        period_days=period,
                        wait_hours=wait,
                        observations=observations,
                        proxy_fills=fills,
                        proxy_fill_probability=Decimal(fills) / Decimal(observations),
                        average_success_wait_hours=(success_wait / Decimal(fills)) if fills else Decimal("0"),
                        average_candidate_daily_rate=candidate_sum / Decimal(observations),
                        expected_30d_net_profit_per_1000=(profit_sum / cycle_hours_sum * Decimal("720")) if cycle_hours_sum else Decimal("0"),
                        idle_fraction=(idle_hours_sum / cycle_hours_sum) if cycle_hours_sum else Decimal("1"),
                    )
                )
    return tuple(estimates)
