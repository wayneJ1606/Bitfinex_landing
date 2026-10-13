from __future__ import annotations

import math

import pytest

from bitfinex_lending.backtesting import BacktestConfig, BacktestError, run_backtest
from bitfinex_lending.models import ModelPrediction


def _predictions() -> tuple[ModelPrediction, ...]:
    return tuple(
        ModelPrediction(
            run_at="2026-01-01T00:00:00+00:00",
            market="fUSD",
            feature_time=f"2026-01-01T0{index}:00:00+00:00",
            model_name="baseline_previous",
            predicted_rate=predicted,
            actual_next_rate=actual,
            prediction_error=predicted - actual,
        )
        for index, (predicted, actual) in enumerate(((0.1, 0.2), (0.05, 0.01), (0.2, 0.3)))
    )


def test_backtest_calculates_fill_and_wait_metrics() -> None:
    result = run_backtest(_predictions(), BacktestConfig(min_rate=0.1))
    assert len(result) == 1
    item = result[0]
    assert (item.signals, item.fills) == (2, 2)
    assert item.fill_rate == pytest.approx(1.0)
    assert item.capital_utilization == pytest.approx((2 / 3) * 0.10)
    assert item.average_wait_hours == pytest.approx(2.0)
    assert item.max_consecutive_misses == 0
    assert item.total_simulated_return == pytest.approx(
        1000.0 * 0.10 * (0.2 + 0.3) / 24
    )
    assert item.simulated_annualized_return == pytest.approx(
        (item.total_simulated_return / 1000.0) * (365 * 24) / 3
    )


def test_backtest_counts_signal_misses_and_groups_models() -> None:
    rows = _predictions() + (ModelPrediction("r", "fBTC", "2026-01-01T00:00:00+00:00", "tree", 0.2, 0.01, 0.19),)
    result = run_backtest(rows, BacktestConfig(min_rate=0.1))
    assert [(item.market, item.model_name) for item in result] == [("fBTC", "tree"), ("fUSD", "baseline_previous")]
    btc = result[0]
    assert (btc.signals, btc.fills, btc.max_consecutive_misses) == (1, 0, 1)


@pytest.mark.parametrize("config", [BacktestConfig(capital=0), BacktestConfig(allocation_fraction=1.1), BacktestConfig(hours_per_period=0)])
def test_backtest_rejects_invalid_configuration(config: BacktestConfig) -> None:
    with pytest.raises(BacktestError):
        run_backtest(_predictions(), config)
