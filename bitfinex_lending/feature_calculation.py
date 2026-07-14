from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import math
from typing import Sequence

from bitfinex_lending.models import FundingBookRow, ModelingFeature


class FeatureCalculationError(ValueError):
    """Raised when source rows cannot produce trustworthy features."""


def _error(row: FundingBookRow, reason: str) -> FeatureCalculationError:
    return FeatureCalculationError(
        f"invalid snapshot {row.market} at {row.fetched_at}: {reason}"
    )


def _timestamp(row: FundingBookRow) -> datetime:
    try:
        timestamp = datetime.fromisoformat(row.fetched_at)
    except (TypeError, ValueError) as exc:
        raise _error(row, "invalid timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise _error(row, "timestamp must include a timezone offset")
    return timestamp.astimezone(timezone.utc)


def _validate(row: FundingBookRow) -> datetime:
    timestamp = _timestamp(row)
    if not math.isfinite(row.rate):
        raise _error(row, "rate must be finite")
    if not math.isfinite(row.amount):
        raise _error(row, "amount must be finite")
    if row.period <= 0:
        raise _error(row, "period must be positive")
    if row.count < 0:
        raise _error(row, "count must be nonnegative")
    if row.amount == 0:
        raise _error(row, "amount must not be zero")
    if row.side == "offer" and row.amount < 0:
        raise _error(row, "offer amount must be positive")
    if row.side == "demand" and row.amount > 0:
        raise _error(row, "demand amount must be negative")
    if row.side not in ("offer", "demand"):
        raise _error(row, "side must be offer or demand")
    return timestamp


def calculate_features(
    rows: Sequence[FundingBookRow],
) -> tuple[ModelingFeature, ...]:
    """Aggregate normalized funding-book rows into chronological market features."""
    snapshots: dict[tuple[str, str], list[FundingBookRow]] = defaultdict(list)
    timestamps: dict[tuple[str, str], datetime] = {}
    market_order: dict[str, int] = {}

    for row in rows:
        timestamp = _validate(row)
        key = (row.market, row.fetched_at)
        market_order.setdefault(row.market, len(market_order))
        snapshots[key].append(row)
        timestamps[key] = timestamp

    current: dict[str, list[ModelingFeature]] = defaultdict(list)
    for key in sorted(
        snapshots,
        key=lambda item: (market_order[item[0]], timestamps[item]),
    ):
        snapshot_rows = snapshots[key]
        first = snapshot_rows[0]
        if any(item.run_id != first.run_id for item in snapshot_rows[1:]):
            raise _error(first, "inconsistent run_id")

        weights = [abs(item.amount) for item in snapshot_rows]
        total_amount = sum(weights)
        if total_amount <= 0:
            raise _error(first, "total absolute amount must be positive")
        rates = [item.rate for item in snapshot_rows]
        timestamp = timestamps[key]
        current[first.market].append(
            ModelingFeature(
                market=first.market,
                feature_time=first.fetched_at,
                hour=timestamp.hour,
                day_of_week=timestamp.weekday(),
                avg_rate=sum(rates) / len(rates),
                weighted_avg_rate=sum(
                    item.rate * weight
                    for item, weight in zip(snapshot_rows, weights, strict=True)
                )
                / total_amount,
                min_rate=min(rates),
                max_rate=max(rates),
                total_amount=total_amount,
                avg_period=sum(item.period for item in snapshot_rows)
                / len(snapshot_rows),
                offer_count=sum(
                    item.count for item in snapshot_rows if item.side == "offer"
                ),
                demand_count=sum(
                    item.count for item in snapshot_rows if item.side == "demand"
                ),
                rate_spread=max(rates) - min(rates),
                previous_weighted_avg_rate=None,
                rate_change=None,
                amount_change=None,
                target_next_weighted_avg_rate=None,
            )
        )

    result: list[ModelingFeature] = []
    for market in market_order:
        market_features = current[market]
        for index, feature in enumerate(market_features):
            previous = market_features[index - 1] if index else None
            next_feature = (
                market_features[index + 1]
                if index + 1 < len(market_features)
                else None
            )
            result.append(
                replace(
                    feature,
                    previous_weighted_avg_rate=(
                        previous.weighted_avg_rate if previous else None
                    ),
                    rate_change=(
                        feature.weighted_avg_rate - previous.weighted_avg_rate
                        if previous
                        else None
                    ),
                    amount_change=(
                        feature.total_amount - previous.total_amount
                        if previous
                        else None
                    ),
                    target_next_weighted_avg_rate=(
                        next_feature.weighted_avg_rate if next_feature else None
                    ),
                )
            )
    return tuple(result)
