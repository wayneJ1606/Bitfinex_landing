from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bitfinex_lending.models import ModelPrediction
from bitfinex_lending.p0_market_history import MarketHour
from bitfinex_lending.p0_walk_forward import WalkForwardError, run_walk_forward


UTC = timezone.utc


def hourly_history(days: int) -> tuple[MarketHour, ...]:
    start = datetime(2026, 6, 1, tzinfo=UTC)
    return tuple(
        MarketHour(
            observed_at=start + timedelta(hours=index),
            api_symbol="fUST",
            asset="USDT",
            frr=0.0002,
            ask_rate=0.0002 + (index % 24) * 0.000001,
            visible_demand_amount=20_000.0,
            traded_high=0.0003,
            traded_volume=50_000.0,
            funding_amount_used=1_000_000.0,
        )
        for index in range(days * 24 + 1)
    )


def _evaluation(result: object, strategy_type: str, principal: Decimal = Decimal("1000")):
    return next(
        row
        for row in result.results
        if row.strategy_type == strategy_type
        and row.portfolio.principal == principal
        and row.portfolio.portfolio_type == "highest_return"
    )


def test_walk_forward_uses_past_30_days_and_only_complete_future_windows() -> None:
    rows = hourly_history(days=61)

    result = run_walk_forward(rows, predictions=(), private_matches=())

    assert result.training_start == rows[0].observed_at
    assert result.first_decision_at >= rows[0].observed_at + timedelta(days=30)
    assert result.last_decision_at <= rows[-1].observed_at - timedelta(days=30)
    assert result.first_decision_at.hour == 2
    assert {row.strategy_type for row in result.results} >= {
        "fixed_median",
        "frr",
        "quick_fill",
        "optimized_without_prediction",
    }


def test_future_rate_outlier_cannot_change_same_decision() -> None:
    rows = hourly_history(days=61)
    decision_at = rows[0].observed_at + timedelta(days=30, hours=2)
    changed = tuple(
        replace(row, ask_rate=0.5)
        if row.observed_at == decision_at + timedelta(hours=1)
        else row
        for row in rows
    )

    original = _evaluation(run_walk_forward(rows), "optimized_without_prediction")
    with_outlier = _evaluation(run_walk_forward(changed), "optimized_without_prediction")

    assert original.decision_at == decision_at
    assert tuple(leg.daily_rate for leg in original.portfolio.legs) == tuple(
        leg.daily_rate for leg in with_outlier.portfolio.legs
    )


def test_future_fill_outcome_scores_realized_profit_without_changing_selection() -> None:
    rows = hourly_history(days=61)
    decision_at = rows[0].observed_at + timedelta(days=30, hours=2)
    blocked = tuple(
        replace(row, traded_high=0.0)
        if decision_at < row.observed_at <= decision_at + timedelta(days=30)
        else row
        for row in rows
    )

    filled = _evaluation(run_walk_forward(rows), "optimized_without_prediction")
    unfilled = _evaluation(run_walk_forward(blocked), "optimized_without_prediction")

    assert tuple(leg.daily_rate for leg in filled.forecast_portfolio.legs) == tuple(
        leg.daily_rate for leg in unfilled.forecast_portfolio.legs
    )
    assert filled.portfolio.ending_capital > Decimal("1000")
    assert unfilled.portfolio.ending_capital == Decimal("1000")


def test_eligible_prediction_adds_assisted_and_unassisted_comparisons() -> None:
    rows = hourly_history(days=61)
    decision_at = rows[0].observed_at + timedelta(days=30, hours=2)
    prediction_time = decision_at - timedelta(hours=1)
    prediction = ModelPrediction(
        run_at=prediction_time.isoformat(),
        market="fUST",
        feature_time=prediction_time.isoformat(),
        model_name="linear_regression",
        predicted_rate=0.00021,
        actual_next_rate=0.9,
        prediction_error=-0.89979,
    )

    result = run_walk_forward(rows, predictions=(prediction,))

    strategy_types = {row.strategy_type for row in result.results}
    assert "optimized_with_prediction" in strategy_types
    assert "optimized_without_prediction" in strategy_types
    assisted = _evaluation(result, "optimized_with_prediction")
    assert assisted.predicted_rate == pytest.approx(0.00021)
    assert assisted.prediction_fallback is False


def test_prediction_created_after_decision_is_not_used() -> None:
    rows = hourly_history(days=61)
    decision_at = rows[0].observed_at + timedelta(days=30, hours=2)
    future_prediction = ModelPrediction(
        run_at=(decision_at + timedelta(hours=1)).isoformat(),
        market="fUST",
        feature_time=(decision_at - timedelta(hours=1)).isoformat(),
        model_name="linear_regression",
        predicted_rate=0.00021,
        actual_next_rate=0.0002,
        prediction_error=0.00001,
    )

    result = run_walk_forward(rows, predictions=(future_prediction,))

    assert "optimized_with_prediction" not in {row.strategy_type for row in result.results}


def test_prediction_below_every_candidate_records_lowest_rate_fallback() -> None:
    rows = hourly_history(days=61)
    decision_at = rows[0].observed_at + timedelta(days=30, hours=2)
    prediction_time = decision_at - timedelta(hours=1)
    prediction = ModelPrediction(
        run_at=prediction_time.isoformat(),
        market="fUST",
        feature_time=prediction_time.isoformat(),
        model_name="linear_regression",
        predicted_rate=0.000001,
        actual_next_rate=0.0002,
        prediction_error=-0.000199,
    )

    result = run_walk_forward(rows, predictions=(prediction,))
    assisted = _evaluation(result, "optimized_with_prediction")
    quick_fill = _evaluation(result, "quick_fill")

    assert assisted.prediction_fallback is True
    assert {leg.daily_rate for leg in assisted.portfolio.legs} == {
        leg.daily_rate for leg in quick_fill.portfolio.legs
    }


def test_strategy_observation_coverage_counts_each_walk_forward_decision() -> None:
    result = run_walk_forward(hourly_history(days=62))

    coverage = dict(result.strategy_observations)
    assert len(coverage) == 100
    assert set(coverage.values()) == {2}


def test_baseline_keeps_principal_idle_when_market_capacity_is_too_small() -> None:
    constrained = tuple(
        replace(row, visible_demand_amount=1000.0, traded_volume=1000.0)
        for row in hourly_history(days=61)
    )

    result = run_walk_forward(constrained)
    baseline = _evaluation(result, "fixed_median", Decimal("10000"))

    assert baseline.portfolio.principal == Decimal("10000")
    assert sum(
        (leg.starting_principal for leg in baseline.forecast_portfolio.legs),
        Decimal(),
    ) == Decimal("1000")
    assert baseline.portfolio.ending_capital >= Decimal("10000")
    assert baseline.portfolio.idle_fraction >= 0.9


def test_rejects_history_without_one_complete_decision_window() -> None:
    with pytest.raises(WalkForwardError, match="30 days"):
        run_walk_forward(hourly_history(days=59))
