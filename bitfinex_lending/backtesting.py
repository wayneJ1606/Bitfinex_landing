from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Iterable

from .models import ModelPrediction


class BacktestError(ValueError):
    """Raised when backtest inputs or configuration are not trustworthy."""


@dataclass(frozen=True)
class BacktestConfig:
    capital: float = 1000.0
    allocation_fraction: float = 0.10
    min_rate: float = 0.0
    hours_per_period: float = 1.0


@dataclass(frozen=True)
class BacktestResult:
    market: str
    model_name: str
    observations: int
    signals: int
    fills: int
    fill_rate: float
    capital_utilization: float
    average_wait_hours: float
    max_consecutive_misses: int
    total_simulated_return: float
    simulated_annualized_return: float


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise BacktestError(f"feature_time must be ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BacktestError("feature_time must include a timezone offset")
    return parsed


def _validate_config(config: BacktestConfig) -> None:
    values = (config.capital, config.allocation_fraction, config.min_rate, config.hours_per_period)
    if any(not math.isfinite(float(value)) for value in values):
        raise BacktestError("backtest configuration must be finite")
    if config.capital <= 0:
        raise BacktestError("capital must be greater than zero")
    if not 0 < config.allocation_fraction <= 1:
        raise BacktestError("allocation_fraction must be in (0, 1]")
    if config.hours_per_period <= 0:
        raise BacktestError("hours_per_period must be greater than zero")


def run_backtest(
    predictions: Iterable[ModelPrediction], config: BacktestConfig | None = None
) -> tuple[BacktestResult, ...]:
    config = config or BacktestConfig()
    _validate_config(config)
    grouped: dict[tuple[str, str], list[ModelPrediction]] = defaultdict(list)
    for row in predictions:
        if not all(math.isfinite(float(value)) for value in (row.predicted_rate, row.actual_next_rate)):
            raise BacktestError("prediction rates must be finite")
        _timestamp(row.feature_time)
        grouped[(row.market, row.model_name)].append(row)

    results: list[BacktestResult] = []
    for (market, model_name), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: _timestamp(row.feature_time))
        signals = [row for row in ordered if row.predicted_rate >= config.min_rate]
        fills = [row for row in signals if row.actual_next_rate >= config.min_rate]
        fill_times = [_timestamp(row.feature_time) for row in fills]
        waits = [
            (current - previous).total_seconds() / 3600
            for previous, current in zip(fill_times, fill_times[1:], strict=False)
        ]
        max_misses = 0
        consecutive = 0
        for row in signals:
            if row.actual_next_rate < config.min_rate:
                consecutive += 1
                max_misses = max(max_misses, consecutive)
            else:
                consecutive = 0
        period_fraction_of_day = config.hours_per_period / 24
        total_return = sum(
            config.capital
            * config.allocation_fraction
            * row.actual_next_rate
            * period_fraction_of_day
            for row in fills
        )
        elapsed_hours = max(1.0, len(ordered) * config.hours_per_period)
        annualized = (total_return / config.capital) * (365 * 24) / elapsed_hours
        results.append(
            BacktestResult(
                market=market,
                model_name=model_name,
                observations=len(ordered),
                signals=len(signals),
                fills=len(fills),
                fill_rate=(len(fills) / len(signals)) if signals else 0.0,
                capital_utilization=(
                    len(fills) / len(ordered) * config.allocation_fraction
                ),
                average_wait_hours=sum(waits) / len(waits) if waits else 0.0,
                max_consecutive_misses=max_misses,
                total_simulated_return=total_return,
                simulated_annualized_return=annualized,
            )
        )
    return tuple(results)
