from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .backtesting import BacktestResult
from .models import ModelEvaluation, ModelPrediction, ModelingResult


@dataclass(frozen=True)
class DecisionSupportRow:
    market: str
    status: str
    selected_model: str | None
    latest_prediction: float | None
    observation_low: float | None
    observation_high: float | None
    baseline_prediction: float | None
    fill_rate: float | None
    average_wait_hours: float | None
    limitation: str
    human_review_required: bool
    no_automatic_trading: bool


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_decision_support(
    result: ModelingResult, backtests: Iterable[BacktestResult]
) -> tuple[DecisionSupportRow, ...]:
    evaluations: dict[str, list[ModelEvaluation]] = {}
    predictions: dict[tuple[str, str], list[ModelPrediction]] = {}
    backtest_map = {(item.market, item.model_name): item for item in backtests}
    for item in result.evaluations:
        evaluations.setdefault(item.market, []).append(item)
    for item in result.predictions:
        predictions.setdefault((item.market, item.model_name), []).append(item)
    rows: list[DecisionSupportRow] = []
    for status in sorted(result.statuses, key=lambda item: item.market):
        if status.status != "trained":
            rows.append(DecisionSupportRow(status.market, status.status, None, None, None, None, None, None, None, status.message, True, True))
            continue
        market_evaluations = sorted(evaluations.get(status.market, ()), key=lambda item: (item.rmse, item.model_name))
        if not market_evaluations:
            rows.append(DecisionSupportRow(status.market, "limited", None, None, None, None, None, None, None, "no model evaluation available", True, True))
            continue
        best = market_evaluations[0]
        best_predictions = sorted(predictions.get((status.market, best.model_name), ()), key=lambda item: item.feature_time)
        actuals = [item.actual_next_rate for item in best_predictions]
        baseline = sorted(predictions.get((status.market, "baseline_previous"), ()), key=lambda item: item.feature_time)
        backtest = backtest_map.get((status.market, best.model_name))
        rows.append(
            DecisionSupportRow(
                market=status.market,
                status=status.status,
                selected_model=best.model_name,
                latest_prediction=best_predictions[-1].predicted_rate if best_predictions else None,
                observation_low=_percentile(actuals, 0.1) if actuals else None,
                observation_high=_percentile(actuals, 0.9) if actuals else None,
                baseline_prediction=baseline[-1].predicted_rate if baseline else None,
                fill_rate=backtest.fill_rate if backtest else None,
                average_wait_hours=backtest.average_wait_hours if backtest else None,
                limitation="研究用統計；結果需人工確認資料品質與市場狀況",
                human_review_required=True,
                no_automatic_trading=True,
            )
        )
    return tuple(rows)
