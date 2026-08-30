from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

from .p0_economics import net_interest
from .p0_market_history import MarketHour


RATE_QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)
PERIOD_DAYS = (2, 5, 10, 30)
WAIT_HOURS = (1, 3, 6, 12, 24)
PRIVATE_SAMPLE_MINIMUM = 30
PUBLIC_PRIOR_WEIGHT = 30


class FillStatisticsError(ValueError):
    """Raised when candidate estimates cannot be calculated safely."""


@dataclass(frozen=True)
class CandidateEstimate:
    strategy_id: str
    api_symbol: str
    asset: str
    as_of: datetime
    training_start: datetime
    training_end: datetime
    rate_quantile: float
    daily_rate: float
    period_days: int
    wait_hours: int
    observations: int
    fills: int
    fill_probability: float
    average_wait_hours: float
    deployable_amount: float
    expected_duration_hours: float
    expected_net_profit_per_1000: float
    net_profit_p10_per_1000: float
    calibration_status: str
    duration_status: str


def _quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _matching_private_fills(
    rows: Iterable[Mapping[str, object]],
    *,
    api_symbol: str,
    rate_quantile: float,
    daily_rate: float,
    period_days: int,
    wait_hours: int,
) -> tuple[bool, ...]:
    def filled(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes"}

    outcomes: list[bool] = []
    for row in rows:
        if row.get("api_symbol") != api_symbol:
            continue
        if "filled" in row:
            if (
                float(row.get("rate_quantile", -1)) == rate_quantile
                and int(row.get("period_days", -1)) == period_days
                and int(row.get("wait_hours", -1)) == wait_hours
            ):
                outcomes.append(filled(row["filled"]))
            continue
        if (
            int(row.get("offer_period", -1)) == period_days
            and math.isclose(float(row.get("offer_rate", math.nan)), daily_rate, rel_tol=1e-9, abs_tol=1e-12)
            and row.get("match_status") == "matched"
        ):
            outcomes.append(float(row.get("wait_minutes", math.inf)) <= wait_hours * 60)
    return tuple(outcomes)


def _matching_private_durations(
    rows: Iterable[Mapping[str, object]],
    *,
    api_symbol: str,
    period_days: int,
) -> tuple[float, ...]:
    durations = tuple(
        float(row["duration_hours"])
        for row in rows
        if row.get("api_symbol") == api_symbol
        and int(row.get("period_days", -1)) == period_days
    )
    return tuple(value for value in durations if math.isfinite(value) and value > 0)


def _profit_per_1000(daily_rate: float, duration_hours: float) -> float:
    seconds = max(1, round(duration_hours * 3600))
    return float(net_interest(Decimal("1000"), Decimal(str(daily_rate)), seconds))


def estimate_candidates(
    history: Iterable[MarketHour],
    as_of: datetime,
    *,
    private_matches: Iterable[Mapping[str, object]] = (),
    private_durations: Iterable[Mapping[str, object]] = (),
) -> tuple[CandidateEstimate, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise FillStatisticsError("as_of must include a timezone")
    training = tuple(sorted((row for row in history if row.observed_at < as_of), key=lambda row: row.observed_at))
    if not training:
        return ()

    api_symbol = training[0].api_symbol
    asset = training[0].asset
    if any(row.api_symbol != api_symbol or row.asset != asset for row in training):
        raise FillStatisticsError("history must contain one API symbol and asset")
    rates = tuple(row.ask_rate for row in training)
    private_matches = tuple(private_matches)
    private_durations = tuple(private_durations)
    estimates: list[CandidateEstimate] = []

    for rate_quantile in RATE_QUANTILES:
        daily_rate = _quantile(rates, rate_quantile)
        quantile_label = round(rate_quantile * 100)
        for period_days in PERIOD_DAYS:
            durations = _matching_private_durations(
                private_durations,
                api_symbol=api_symbol,
                period_days=period_days,
            )
            if len(durations) >= PRIVATE_SAMPLE_MINIMUM:
                expected_duration_hours = sum(durations) / len(durations)
                duration_status = "private_duration_calibrated"
            else:
                expected_duration_hours = float(period_days * 24)
                duration_status = "nominal_period_assumption"

            profit_if_filled = _profit_per_1000(daily_rate, expected_duration_hours)
            for wait_hours in WAIT_HOURS:
                observed_waits: list[float] = []
                capacities: list[float] = []
                public_profits: list[float] = []
                fills = 0
                full_window_end = training[-1].observed_at

                for decision_index, decision in enumerate(training):
                    deadline = decision.observed_at + timedelta(hours=wait_hours)
                    if deadline > full_window_end:
                        continue
                    future = (
                        row
                        for row in training[decision_index + 1 :]
                        if row.observed_at <= deadline
                    )
                    fill = next((row for row in future if row.traded_high >= daily_rate), None)
                    if fill is None:
                        observed_waits.append(float(wait_hours))
                        public_profits.append(0.0)
                        continue
                    fills += 1
                    observed_waits.append((fill.observed_at - decision.observed_at).total_seconds() / 3600)
                    capacities.append(max(0.0, min(fill.visible_demand_amount, fill.traded_volume)))
                    public_profits.append(profit_if_filled)

                observations = len(observed_waits)
                public_probability = fills / observations if observations else 0.0
                matching_private = _matching_private_fills(
                    private_matches,
                    api_symbol=api_symbol,
                    rate_quantile=rate_quantile,
                    daily_rate=daily_rate,
                    period_days=period_days,
                    wait_hours=wait_hours,
                )
                if len(matching_private) >= PRIVATE_SAMPLE_MINIMUM:
                    fill_probability = (
                        public_probability * PUBLIC_PRIOR_WEIGHT + sum(matching_private)
                    ) / (PUBLIC_PRIOR_WEIGHT + len(matching_private))
                    calibration_status = "private_calibrated"
                else:
                    fill_probability = public_probability
                    calibration_status = "insufficient_private_data"

                estimates.append(
                    CandidateEstimate(
                        strategy_id=f"{api_symbol}-q{quantile_label:02d}-p{period_days}-w{wait_hours}",
                        api_symbol=api_symbol,
                        asset=asset,
                        as_of=as_of,
                        training_start=training[0].observed_at,
                        training_end=training[-1].observed_at,
                        rate_quantile=rate_quantile,
                        daily_rate=daily_rate,
                        period_days=period_days,
                        wait_hours=wait_hours,
                        observations=observations,
                        fills=fills,
                        fill_probability=fill_probability,
                        average_wait_hours=(sum(observed_waits) / observations if observations else float(wait_hours)),
                        deployable_amount=(sum(capacities) / len(capacities) if capacities else 0.0),
                        expected_duration_hours=expected_duration_hours,
                        expected_net_profit_per_1000=profit_if_filled * fill_probability,
                        net_profit_p10_per_1000=(_quantile(public_profits, 0.10) if public_profits else 0.0),
                        calibration_status=calibration_status,
                        duration_status=duration_status,
                    )
                )

    return tuple(estimates)
