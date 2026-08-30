"""Allocate approved funding capital across historical strategy estimates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from numbers import Integral
from typing import Iterable

from .p0_economics import VISIBLE_PROVIDER_FEE, gross_interest, net_interest, split_capital
from .p0_fill_statistics import CandidateEstimate


HOURS_PER_DAY = 24
SECONDS_PER_HOUR = 3600
TRANCHE = Decimal("1000")


class OptimizerError(ValueError):
    """Raised when candidate estimates cannot fund an approved portfolio."""


@dataclass(frozen=True)
class StrategyLeg:
    strategy_id: str
    starting_principal: Decimal
    daily_rate: Decimal
    period_days: int
    wait_hours: int
    fill_probability: float
    expected_wait_hours: float
    expected_net_interest: Decimal
    expected_ending_capital: Decimal


@dataclass(frozen=True)
class PortfolioResult:
    asset: str
    principal: Decimal
    portfolio_type: str
    legs: tuple[StrategyLeg, ...]
    gross_interest: Decimal
    fee: Decimal
    net_interest: Decimal
    ending_capital: Decimal
    idle_fraction: float
    net_profit_p10: Decimal


@dataclass(frozen=True)
class _LegSimulation:
    leg: StrategyLeg
    gross_interest: Decimal
    fee: Decimal
    idle_hours: float
    net_profit_p10: Decimal


def _validate_estimates(estimates: tuple[CandidateEstimate, ...]) -> str:
    if not estimates:
        raise OptimizerError("candidate capacity is insufficient for the requested principal")
    assets = {(row.api_symbol, row.asset) for row in estimates}
    if len(assets) != 1:
        raise OptimizerError("candidate estimates must contain one asset and API symbol")
    if len({row.strategy_id for row in estimates}) != len(estimates):
        raise OptimizerError("candidate strategy identifiers must be unique")

    for row in estimates:
        numeric_values = (
            row.daily_rate,
            row.fill_probability,
            row.average_wait_hours,
            row.deployable_amount,
            row.expected_duration_hours,
            row.expected_net_profit_per_1000,
            row.net_profit_p10_per_1000,
        )
        if not all(math.isfinite(value) for value in numeric_values):
            raise OptimizerError("candidate estimates must contain finite numeric values")
        if row.daily_rate <= 0 or row.expected_duration_hours <= 0 or row.wait_hours <= 0:
            raise OptimizerError("candidate rate, duration, and wait must be positive")
        if not 0 <= row.fill_probability <= 1:
            raise OptimizerError("fill probability must be between zero and one")
        if row.average_wait_hours < 0 or row.deployable_amount < 0:
            raise OptimizerError("candidate wait and capacity cannot be negative")
    return estimates[0].asset


def _capacity_slots(estimate: CandidateEstimate) -> int:
    return max(0, math.floor(estimate.deployable_amount / float(TRANCHE)))


def _simulate_leg(estimate: CandidateEstimate, horizon_hours: int) -> _LegSimulation:
    probability = Decimal(str(estimate.fill_probability))
    daily_rate = Decimal(str(estimate.daily_rate))
    cycle_hours = (
        estimate.fill_probability
        * (estimate.average_wait_hours + estimate.expected_duration_hours)
        + (1 - estimate.fill_probability) * estimate.wait_hours
    )
    if not math.isfinite(cycle_hours) or cycle_hours <= 0:
        raise OptimizerError("candidate expected cycle must be positive and finite")

    cycle_count = math.floor(horizon_hours / cycle_hours)
    expected_wait_per_cycle = (
        estimate.fill_probability * estimate.average_wait_hours
        + (1 - estimate.fill_probability) * estimate.wait_hours
    )
    duration_seconds = max(1, round(estimate.expected_duration_hours * SECONDS_PER_HOUR))

    capital = TRANCHE
    total_gross = Decimal()
    total_net = Decimal()
    for _ in range(cycle_count):
        expected_gross = gross_interest(capital, daily_rate, duration_seconds) * probability
        expected_net = net_interest(capital, daily_rate, duration_seconds) * probability
        total_gross += expected_gross
        total_net += expected_net
        capital += expected_net

    used_hours = cycle_count * cycle_hours
    idle_hours = cycle_count * expected_wait_per_cycle + max(0.0, horizon_hours - used_hours)
    p10_profit = Decimal(str(estimate.net_profit_p10_per_1000)) * cycle_count
    leg = StrategyLeg(
        strategy_id=estimate.strategy_id,
        starting_principal=TRANCHE,
        daily_rate=daily_rate,
        period_days=estimate.period_days,
        wait_hours=estimate.wait_hours,
        fill_probability=estimate.fill_probability,
        expected_wait_hours=expected_wait_per_cycle,
        expected_net_interest=total_net,
        expected_ending_capital=capital,
    )
    return _LegSimulation(
        leg=leg,
        gross_interest=total_gross,
        fee=total_gross * VISIBLE_PROVIDER_FEE,
        idle_hours=idle_hours,
        net_profit_p10=p10_profit,
    )


def _allocate(
    estimates: tuple[CandidateEstimate, ...],
    principal: Decimal,
    *,
    horizon_hours: int,
    portfolio_type: str,
) -> PortfolioResult:
    candidate_simulations = {
        row.strategy_id: _simulate_leg(row, horizon_hours) for row in estimates
    }
    if portfolio_type == "highest_return":
        ranked = sorted(
            estimates,
            key=lambda row: (
                -candidate_simulations[row.strategy_id].leg.expected_ending_capital,
                row.strategy_id,
            ),
        )
    else:
        ranked = sorted(
            estimates,
            key=lambda row: (
                -candidate_simulations[row.strategy_id].net_profit_p10,
                -candidate_simulations[row.strategy_id].leg.expected_ending_capital,
                row.strategy_id,
            ),
        )

    slots_needed = len(split_capital(principal))
    selected: list[CandidateEstimate] = []
    for estimate in ranked:
        available = min(_capacity_slots(estimate), slots_needed - len(selected))
        selected.extend((estimate,) * available)
        if len(selected) == slots_needed:
            break
    if len(selected) != slots_needed:
        raise OptimizerError("candidate capacity is insufficient for the requested principal")

    simulations = tuple(candidate_simulations[row.strategy_id] for row in selected)
    gross = sum((row.gross_interest for row in simulations), Decimal())
    fee = sum((row.fee for row in simulations), Decimal())
    net = sum((row.leg.expected_net_interest for row in simulations), Decimal())
    idle_denominator = horizon_hours * len(simulations)
    idle_fraction = (
        sum(row.idle_hours for row in simulations) / idle_denominator
        if idle_denominator
        else 0.0
    )
    return PortfolioResult(
        asset=estimates[0].asset,
        principal=principal,
        portfolio_type=portfolio_type,
        legs=tuple(row.leg for row in simulations),
        gross_interest=gross,
        fee=fee,
        net_interest=net,
        ending_capital=principal + net,
        idle_fraction=idle_fraction,
        net_profit_p10=sum((row.net_profit_p10 for row in simulations), Decimal()),
    )


def optimize_portfolios(
    estimates: Iterable[CandidateEstimate],
    principal: Decimal,
    horizon_days: int = 30,
) -> tuple[PortfolioResult, PortfolioResult]:
    """Return highest-expected-return and downside-stable portfolios."""
    tranches = split_capital(principal)
    if isinstance(horizon_days, bool) or not isinstance(horizon_days, Integral) or horizon_days <= 0:
        raise OptimizerError("horizon_days must be a positive whole number")
    rows = tuple(estimates)
    _validate_estimates(rows)
    amount = sum(tranches, Decimal())
    horizon_hours = int(horizon_days) * HOURS_PER_DAY
    return (
        _allocate(rows, amount, horizon_hours=horizon_hours, portfolio_type="highest_return"),
        _allocate(rows, amount, horizon_hours=horizon_hours, portfolio_type="stable_alternative"),
    )
