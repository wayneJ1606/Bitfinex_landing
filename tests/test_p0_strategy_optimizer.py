from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from bitfinex_lending.p0_economics import EconomicsError
from bitfinex_lending.p0_fill_statistics import CandidateEstimate
from bitfinex_lending.p0_strategy_optimizer import (
    OptimizerError,
    optimize_portfolios,
)


def candidate(
    strategy_id: str,
    *,
    expected: float,
    p10: float,
    deployable: float,
    daily_rate: float = 0.0002,
    fill_probability: float = 0.8,
    average_wait_hours: float = 0.5,
    expected_duration_hours: float = 48.0,
) -> CandidateEstimate:
    as_of = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return CandidateEstimate(
        strategy_id=strategy_id,
        api_symbol="fUST",
        asset="USDT",
        as_of=as_of,
        training_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        training_end=datetime(2026, 7, 31, tzinfo=timezone.utc),
        rate_quantile=0.5,
        daily_rate=daily_rate,
        period_days=2,
        wait_hours=1,
        observations=100,
        fills=round(100 * fill_probability),
        fill_probability=fill_probability,
        average_wait_hours=average_wait_hours,
        deployable_amount=deployable,
        expected_duration_hours=expected_duration_hours,
        expected_net_profit_per_1000=expected,
        net_profit_p10_per_1000=p10,
        calibration_status="public_only",
        duration_status="nominal_period_assumption",
    )


def test_3000_principal_selects_three_tranches_with_capacity_limit() -> None:
    estimates = (
        candidate("high", expected=12, p10=2, deployable=2000),
        candidate("stable", expected=9, p10=6, deployable=5000),
    )

    highest, stable = optimize_portfolios(estimates, Decimal("3000"))

    assert sum((leg.starting_principal for leg in highest.legs), Decimal()) == Decimal("3000")
    assert [leg.strategy_id for leg in highest.legs].count("high") == 2
    assert [leg.strategy_id for leg in highest.legs].count("stable") == 1
    assert stable.portfolio_type == "stable_alternative"
    assert all(leg.strategy_id == "stable" for leg in stable.legs)


@pytest.mark.parametrize("principal, expected_legs", [(Decimal("1000"), 1), (Decimal("10000"), 10)])
def test_approved_capital_levels_create_one_leg_per_1000(
    principal: Decimal,
    expected_legs: int,
) -> None:
    estimates = (candidate("roomy", expected=5, p10=3, deployable=10000),)

    highest, stable = optimize_portfolios(estimates, principal)

    assert len(highest.legs) == expected_legs
    assert len(stable.legs) == expected_legs
    assert highest.principal == principal
    assert highest.ending_capital == principal + highest.net_interest


def test_fee_is_fifteen_percent_of_expected_gross_interest() -> None:
    estimate = candidate(
        "certain",
        expected=1,
        p10=1,
        deployable=1000,
        daily_rate=0.001,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=24.0,
    )

    highest, _ = optimize_portfolios((estimate,), Decimal("1000"), horizon_days=1)

    assert highest.gross_interest == Decimal("1.0000")
    assert highest.fee == Decimal("0.150000")
    assert highest.net_interest == Decimal("0.850000")
    assert highest.ending_capital == Decimal("1000.850000")


def test_waiting_and_failed_fills_are_reported_as_idle_time() -> None:
    estimate = candidate(
        "sometimes",
        expected=1,
        p10=0,
        deployable=1000,
        fill_probability=0.5,
        average_wait_hours=2.0,
        expected_duration_hours=8.0,
    )

    highest, _ = optimize_portfolios((estimate,), Decimal("1000"), horizon_days=1)

    assert highest.idle_fraction == pytest.approx(8 / 24)
    assert highest.legs[0].expected_wait_hours == 1.5


def test_complete_cycles_reinvest_returned_principal_and_interest() -> None:
    estimate = candidate(
        "compound",
        expected=1,
        p10=1,
        deployable=1000,
        daily_rate=0.01,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=24.0,
    )

    highest, _ = optimize_portfolios((estimate,), Decimal("1000"), horizon_days=3)

    simple_net_interest = Decimal("1000") * Decimal("0.01") * Decimal("0.85") * 3
    assert highest.net_interest > simple_net_interest
    assert highest.legs[0].expected_ending_capital == highest.ending_capital


def test_highest_return_ranks_by_horizon_ending_capital_not_one_cycle_profit() -> None:
    long_cycle = candidate(
        "long-cycle",
        expected=20,
        p10=1,
        deployable=1000,
        daily_rate=0.001,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=720.0,
    )
    compounding = candidate(
        "compounding",
        expected=1,
        p10=1,
        deployable=1000,
        daily_rate=0.002,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=24.0,
    )

    highest, _ = optimize_portfolios((long_cycle, compounding), Decimal("1000"))

    assert highest.legs[0].strategy_id == "compounding"


def test_stable_alternative_ranks_by_horizon_p10_profit() -> None:
    one_long_cycle = candidate(
        "one-long-cycle",
        expected=1,
        p10=5,
        deployable=1000,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=720.0,
    )
    many_short_cycles = candidate(
        "many-short-cycles",
        expected=1,
        p10=1,
        deployable=1000,
        fill_probability=1.0,
        average_wait_hours=0.0,
        expected_duration_hours=24.0,
    )

    _, stable = optimize_portfolios((one_long_cycle, many_short_cycles), Decimal("1000"))

    assert stable.legs[0].strategy_id == "many-short-cycles"
    assert stable.net_profit_p10 == Decimal("30")


@pytest.mark.parametrize("principal", [Decimal("999"), Decimal("1500"), Decimal("11000")])
def test_rejects_non_approved_capital(principal: Decimal) -> None:
    with pytest.raises(EconomicsError):
        optimize_portfolios((candidate("one", expected=1, p10=1, deployable=10000),), principal)


def test_rejects_candidates_without_enough_combined_capacity() -> None:
    estimates = (candidate("small", expected=1, p10=1, deployable=1000),)

    with pytest.raises(OptimizerError, match="capacity"):
        optimize_portfolios(estimates, Decimal("2000"))


def test_rejects_mixed_assets() -> None:
    usdt = candidate("usdt", expected=1, p10=1, deployable=1000)
    btc = CandidateEstimate(**{**usdt.__dict__, "strategy_id": "btc", "api_symbol": "fBTC", "asset": "BTC"})

    with pytest.raises(OptimizerError, match="one asset"):
        optimize_portfolios((usdt, btc), Decimal("1000"))
