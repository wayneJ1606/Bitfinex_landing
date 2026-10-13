from __future__ import annotations

from bitfinex_lending.backtesting import BacktestResult
from bitfinex_lending.decision_support import build_decision_support
from bitfinex_lending.models import ModelEvaluation, ModelPrediction, ModelStatus, ModelingResult


def test_selects_best_model_and_requires_human_review() -> None:
    result = ModelingResult(
        statuses=(ModelStatus("fUSD", "trained", 168, 168, 168, "ok"),),
        evaluations=(
            ModelEvaluation("r", "fUSD", "baseline_previous", 134, 34, "a", "b", "c", "d", 0.2, 0.3, 0.1),
            ModelEvaluation("r", "fUSD", "decision_tree", 134, 34, "a", "b", "c", "d", 0.1, 0.2, 0.2),
        ),
        predictions=(
            ModelPrediction("r", "fUSD", "2026-01-01T00:00:00+00:00", "baseline_previous", 0.1, 0.11, -0.01),
            ModelPrediction("r", "fUSD", "2026-01-01T00:00:00+00:00", "decision_tree", 0.2, 0.21, -0.01),
            ModelPrediction("r", "fUSD", "2026-01-02T00:00:00+00:00", "decision_tree", 0.3, 0.31, -0.01),
        ),
    )
    backtests = (BacktestResult("fUSD", "decision_tree", 2, 2, 1, 0.5, 0.5, 1.0, 1, 0.03, 0.1),)
    row = build_decision_support(result, backtests)[0]
    assert (row.selected_model, row.latest_prediction, row.baseline_prediction) == ("decision_tree", 0.3, 0.1)
    assert 0.11 <= row.observation_low <= row.observation_high <= 0.31
    assert row.human_review_required is True
    assert row.no_automatic_trading is True


def test_insufficient_status_is_explicit() -> None:
    result = ModelingResult((ModelStatus("fBTC", "insufficient_data", 10, 8, 168, "requires more"),), (), ())
    row = build_decision_support(result, ())[0]
    assert (row.status, row.selected_model, row.limitation) == ("insufficient_data", None, "requires more")
