"""Past-only daily walk-forward comparisons for P0 funding strategies."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from .models import ModelPrediction
from .p0_economics import capital_levels, gross_interest, net_interest
from .p0_fill_statistics import CandidateEstimate, estimate_candidates
from .p0_fixed_baselines import BaselineDefinition, baseline_definitions
from .p0_market_history import MarketHour
from .p0_strategy_optimizer import PortfolioResult, StrategyLeg, optimize_portfolios


UTC = timezone.utc
INITIAL_TRAINING_DAYS = 30
OUTCOME_DAYS = 30
DECISION_HOUR_UTC = 2


class WalkForwardError(ValueError):
    """Raised when a chronological walk-forward run cannot be evaluated safely."""


@dataclass(frozen=True)
class WalkForwardEvaluation:
    decision_at: datetime
    strategy_type: str
    portfolio: PortfolioResult
    forecast_portfolio: PortfolioResult
    predicted_rate: float | None = None
    prediction_fallback: bool = False


@dataclass(frozen=True)
class WalkForwardResult:
    asset: str
    generated_at: datetime
    training_start: datetime
    first_decision_at: datetime
    last_decision_at: datetime
    results: tuple[WalkForwardEvaluation, ...]
    strategy_observations: tuple[tuple[str, int], ...]


def _aware_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _validate_history(history: Iterable[MarketHour]) -> tuple[MarketHour, ...]:
    rows = tuple(sorted(history, key=lambda row: row.observed_at))
    if not rows:
        raise WalkForwardError("history must contain at least 30 days before and after a decision")
    if any(row.observed_at.tzinfo is None or row.observed_at.utcoffset() is None for row in rows):
        raise WalkForwardError("history timestamps must include a timezone")
    if len({(row.api_symbol, row.asset) for row in rows}) != 1:
        raise WalkForwardError("history must contain one API symbol and asset")
    if len({row.observed_at for row in rows}) != len(rows):
        raise WalkForwardError("history timestamps must be unique")
    return rows


def _decision_times(rows: tuple[MarketHour, ...]) -> tuple[datetime, ...]:
    earliest = rows[0].observed_at + timedelta(days=INITIAL_TRAINING_DAYS)
    latest = rows[-1].observed_at - timedelta(days=OUTCOME_DAYS)
    return tuple(
        row.observed_at
        for row in rows
        if earliest <= row.observed_at <= latest
        and row.observed_at.astimezone(UTC).hour == DECISION_HOUR_UTC
        and row.observed_at.minute == 0
        and row.observed_at.second == 0
    )


def _latest_prediction(
    predictions: tuple[ModelPrediction, ...],
    *,
    api_symbol: str,
    decision_at: datetime,
) -> ModelPrediction | None:
    eligible: list[tuple[datetime, datetime, str, ModelPrediction]] = []
    decision_utc = decision_at.astimezone(UTC)
    for row in predictions:
        if row.market != api_symbol or not math.isfinite(row.predicted_rate) or row.predicted_rate <= 0:
            continue
        feature_time = _aware_utc(row.feature_time)
        run_at = _aware_utc(row.run_at)
        if feature_time is None or run_at is None:
            continue
        if feature_time <= decision_utc and run_at <= decision_utc:
            eligible.append((feature_time, run_at, row.model_name, row))
    return max(eligible, default=(None, None, "", None), key=lambda item: item[:3])[3]


def _mapping_time(row: Mapping[str, object]) -> datetime | None:
    for key in ("matched_at", "trade_at", "offer_updated_at", "offer_created_at", "observed_at"):
        value = row.get(key)
        if value is not None:
            return _aware_utc(str(value))
    return None


def _past_private_rows(
    rows: tuple[Mapping[str, object], ...],
    decision_at: datetime,
) -> tuple[Mapping[str, object], ...]:
    decision_utc = decision_at.astimezone(UTC)
    return tuple(
        row for row in rows if (observed_at := _mapping_time(row)) is not None and observed_at < decision_utc
    )


def _find_candidate(
    estimates: tuple[CandidateEstimate, ...],
    definition: BaselineDefinition,
) -> CandidateEstimate:
    if definition.rate_quantile is None:
        raise WalkForwardError("FRR baseline requires a current market rate")
    try:
        return next(
            row
            for row in estimates
            if row.rate_quantile == definition.rate_quantile
            and row.period_days == definition.period_days
            and row.wait_hours == definition.wait_hours
        )
    except StopIteration as error:
        raise WalkForwardError(f"missing baseline candidate: {definition.strategy_type}") from error


def _frr_candidate(
    estimates: tuple[CandidateEstimate, ...],
    current_frr: float,
) -> CandidateEstimate:
    if not math.isfinite(current_frr) or current_frr <= 0:
        raise WalkForwardError("current FRR must be positive and finite")
    comparable = tuple(row for row in estimates if row.period_days == 2 and row.wait_hours == 1)
    if not comparable:
        raise WalkForwardError("missing FRR baseline candidate statistics")
    proxy = min(comparable, key=lambda row: (abs(row.daily_rate - current_frr), row.strategy_id))
    duration_seconds = max(1, round(proxy.expected_duration_hours * 3600))
    profit_if_filled = float(
        net_interest(Decimal("1000"), Decimal(str(current_frr)), duration_seconds)
    )
    rate_ratio = current_frr / proxy.daily_rate
    return replace(
        proxy,
        strategy_id=f"{proxy.api_symbol}-frr-p2-w1",
        rate_quantile=-1.0,
        daily_rate=current_frr,
        expected_net_profit_per_1000=profit_if_filled * proxy.fill_probability,
        net_profit_p10_per_1000=proxy.net_profit_p10_per_1000 * rate_ratio,
    )


def _score_portfolio(
    forecast: PortfolioResult,
    *,
    decision_at: datetime,
    outcome_rows: tuple[MarketHour, ...],
) -> PortfolioResult:
    """Score fixed past-selected legs against the following 30 days."""
    horizon_end = decision_at + timedelta(days=OUTCOME_DAYS)
    used_capacity: dict[datetime, Decimal] = {}
    realized_legs: list[StrategyLeg] = []
    gross_total = Decimal()
    net_total = Decimal()
    idle_hours_total = 0.0

    for leg in forecast.legs:
        cursor = decision_at
        capital = leg.starting_principal
        leg_gross = Decimal()
        leg_net = Decimal()
        leg_idle_hours = 0.0

        while cursor < horizon_end:
            deadline = min(cursor + timedelta(hours=leg.wait_hours), horizon_end)
            fill: MarketHour | None = None
            for row in outcome_rows:
                if not cursor < row.observed_at <= deadline or row.observed_at >= horizon_end:
                    continue
                if row.traded_high < float(leg.daily_rate):
                    continue
                capacity = Decimal(str(max(0.0, min(row.visible_demand_amount, row.traded_volume))))
                remaining = capacity - used_capacity.get(row.observed_at, Decimal())
                if remaining >= capital:
                    fill = row
                    break

            if fill is None:
                leg_idle_hours += (deadline - cursor).total_seconds() / 3600
                cursor = deadline
                continue

            leg_idle_hours += (fill.observed_at - cursor).total_seconds() / 3600
            used_capacity[fill.observed_at] = used_capacity.get(fill.observed_at, Decimal()) + capital
            loan_end = min(
                fill.observed_at + timedelta(days=leg.period_days),
                horizon_end,
            )
            active_seconds = round((loan_end - fill.observed_at).total_seconds())
            if active_seconds > 0:
                earned_gross = gross_interest(capital, leg.daily_rate, active_seconds)
                earned_net = net_interest(capital, leg.daily_rate, active_seconds)
                leg_gross += earned_gross
                leg_net += earned_net
                capital += earned_net
            cursor = loan_end

        gross_total += leg_gross
        net_total += leg_net
        idle_hours_total += leg_idle_hours
        realized_legs.append(
            replace(
                leg,
                expected_net_interest=leg_net,
                expected_ending_capital=capital,
            )
        )

    total_slots = int(forecast.principal / Decimal("1000"))
    unallocated_slots = max(0, total_slots - len(realized_legs))
    idle_hours_total += unallocated_slots * OUTCOME_DAYS * 24
    denominator = OUTCOME_DAYS * 24 * total_slots
    return PortfolioResult(
        asset=forecast.asset,
        principal=forecast.principal,
        portfolio_type=forecast.portfolio_type,
        legs=tuple(realized_legs),
        gross_interest=gross_total,
        fee=gross_total - net_total,
        net_interest=net_total,
        ending_capital=forecast.principal + net_total,
        idle_fraction=(idle_hours_total / denominator if denominator else 0.0),
        net_profit_p10=forecast.net_profit_p10,
    )


def _baseline_forecast(
    candidate: CandidateEstimate,
    principal: Decimal,
) -> PortfolioResult:
    total_slots = int(principal / Decimal("1000"))
    available_slots = min(
        total_slots,
        max(0, math.floor(candidate.deployable_amount / 1000)),
    )
    if available_slots == 0:
        return PortfolioResult(
            asset=candidate.asset,
            principal=principal,
            portfolio_type="highest_return",
            legs=(),
            gross_interest=Decimal(),
            fee=Decimal(),
            net_interest=Decimal(),
            ending_capital=principal,
            idle_fraction=1.0,
            net_profit_p10=Decimal(),
        )

    allocated = Decimal(available_slots * 1000)
    forecast, _ = optimize_portfolios((candidate,), allocated)
    if allocated == principal:
        return forecast
    unallocated_slots = total_slots - available_slots
    return replace(
        forecast,
        principal=principal,
        ending_capital=principal + forecast.net_interest,
        idle_fraction=(
            forecast.idle_fraction * available_slots + unallocated_slots
        ) / total_slots,
    )
def _append_baselines(
    output: list[WalkForwardEvaluation],
    *,
    estimates: tuple[CandidateEstimate, ...],
    decision_row: MarketHour,
    decision_at: datetime,
    outcome_rows: tuple[MarketHour, ...],
) -> None:
    definitions = baseline_definitions()
    candidates = {
        "fixed_median": _find_candidate(estimates, definitions[0]),
        "frr": _frr_candidate(estimates, decision_row.frr),
        "quick_fill": _find_candidate(estimates, definitions[2]),
    }
    for principal in capital_levels():
        for strategy_type in ("fixed_median", "frr", "quick_fill"):
            forecast = _baseline_forecast(candidates[strategy_type], principal)
            output.append(
                WalkForwardEvaluation(
                    decision_at=decision_at,
                    strategy_type=strategy_type,
                    portfolio=_score_portfolio(
                        forecast,
                        decision_at=decision_at,
                        outcome_rows=outcome_rows,
                    ),
                    forecast_portfolio=forecast,
                )
            )


def _append_optimized(
    output: list[WalkForwardEvaluation],
    *,
    estimates: tuple[CandidateEstimate, ...],
    decision_at: datetime,
    strategy_type: str,
    predicted_rate: float | None = None,
    prediction_fallback: bool = False,
    outcome_rows: tuple[MarketHour, ...],
) -> None:
    for principal in capital_levels():
        highest, stable = optimize_portfolios(estimates, principal)
        output.extend(
            (
                WalkForwardEvaluation(
                    decision_at=decision_at,
                    strategy_type=strategy_type,
                    portfolio=_score_portfolio(
                        highest,
                        decision_at=decision_at,
                        outcome_rows=outcome_rows,
                    ),
                    forecast_portfolio=highest,
                    predicted_rate=predicted_rate,
                    prediction_fallback=prediction_fallback,
                ),
                WalkForwardEvaluation(
                    decision_at=decision_at,
                    strategy_type=strategy_type,
                    portfolio=_score_portfolio(
                        stable,
                        decision_at=decision_at,
                        outcome_rows=outcome_rows,
                    ),
                    forecast_portfolio=stable,
                    predicted_rate=predicted_rate,
                    prediction_fallback=prediction_fallback,
                ),
            )
        )


def run_walk_forward(
    history: Iterable[MarketHour],
    *,
    predictions: Iterable[ModelPrediction] = (),
    private_matches: Iterable[Mapping[str, object]] = (),
    private_durations: Iterable[Mapping[str, object]] = (),
) -> WalkForwardResult:
    """Evaluate one past-only decision at 02:00 UTC for each eligible day."""
    rows = _validate_history(history)
    decisions = _decision_times(rows)
    if not decisions:
        raise WalkForwardError("history must contain at least 30 days before and after a decision")

    predictions = tuple(predictions)
    private_matches = tuple(private_matches)
    private_durations = tuple(private_durations)
    rows_by_time = {row.observed_at: row for row in rows}
    output: list[WalkForwardEvaluation] = []
    coverage: Counter[str] = Counter()

    for decision_at in decisions:
        estimates = estimate_candidates(
            rows,
            decision_at,
            private_matches=_past_private_rows(private_matches, decision_at),
            private_durations=_past_private_rows(private_durations, decision_at),
        )
        if not estimates:
            continue
        coverage.update(row.strategy_id for row in estimates)
        decision_row = rows_by_time[decision_at]
        outcome_end = decision_at + timedelta(days=OUTCOME_DAYS)
        outcome_rows = tuple(
            row for row in rows if decision_at < row.observed_at <= outcome_end
        )
        _append_baselines(
            output,
            estimates=estimates,
            decision_row=decision_row,
            decision_at=decision_at,
            outcome_rows=outcome_rows,
        )
        _append_optimized(
            output,
            estimates=estimates,
            decision_at=decision_at,
            strategy_type="optimized_without_prediction",
            outcome_rows=outcome_rows,
        )

        prediction = _latest_prediction(
            predictions,
            api_symbol=decision_row.api_symbol,
            decision_at=decision_at,
        )
        if prediction is not None:
            filtered = tuple(row for row in estimates if row.daily_rate <= prediction.predicted_rate)
            fallback = not filtered
            if fallback:
                lowest_rate = min(row.daily_rate for row in estimates)
                filtered = tuple(row for row in estimates if row.daily_rate == lowest_rate)
            _append_optimized(
                output,
                estimates=filtered,
                decision_at=decision_at,
                strategy_type="optimized_with_prediction",
                predicted_rate=prediction.predicted_rate,
                prediction_fallback=fallback,
                outcome_rows=outcome_rows,
            )

    if not output:
        raise WalkForwardError("history did not produce evaluable walk-forward results")
    return WalkForwardResult(
        asset=rows[0].asset,
        generated_at=rows[-1].observed_at,
        training_start=rows[0].observed_at,
        first_decision_at=decisions[0],
        last_decision_at=decisions[-1],
        results=tuple(output),
        strategy_observations=tuple(sorted(coverage.items())),
    )
