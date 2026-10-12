from pathlib import Path

from bitfinex_lending.model_report import export_model_report
from bitfinex_lending.models import ModelEvaluation, ModelStatus, ModelingResult


def test_export_model_report_names_best_model_and_limitations(tmp_path: Path) -> None:
    result = ModelingResult(
        statuses=(ModelStatus("fUSD", "trained", 168, 168, 168, "evaluated"),),
        evaluations=(
            ModelEvaluation("2026-01-01T00:00:00+00:00", "fUSD", "baseline_mean", 134, 34, "a", "b", "c", "d", 0.2, 0.3, 0.4),
            ModelEvaluation("2026-01-01T00:00:00+00:00", "fUSD", "decision_tree", 134, 34, "a", "b", "c", "d", 0.1, 0.2, 0.5),
        ),
        predictions=(),
    )
    path = export_model_report(result, tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "decision_tree" in content
    assert "best" in content.lower()
    assert "人工確認" in content
