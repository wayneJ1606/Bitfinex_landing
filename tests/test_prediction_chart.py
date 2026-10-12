from pathlib import Path
import re

from bitfinex_lending.models import ModelPrediction
from bitfinex_lending.prediction_chart import export_prediction_charts


def test_export_prediction_charts_writes_svg_per_market(tmp_path: Path) -> None:
    rows = (
        ModelPrediction("2026-01-01T00:00:00+00:00", "fUSD", "2026-01-01T01:00:00+00:00", "baseline_mean", 1.0, 1.1, -0.1),
        ModelPrediction("2026-01-01T00:00:00+00:00", "fUSD", "2026-01-01T02:00:00+00:00", "decision_tree", 1.2, 1.3, -0.1),
    )
    paths = export_prediction_charts(rows, tmp_path)
    assert paths == (tmp_path / "prediction_fUSD.svg",)
    content = paths[0].read_text(encoding="utf-8")
    assert content.startswith("<svg")
    assert "baseline_mean" in content
    assert "actual" in content


def test_all_chart_series_share_the_same_timestamp_axis(tmp_path: Path) -> None:
    rows = tuple(
        ModelPrediction(
            "2026-01-01T00:00:00+00:00",
            "fUSD",
            f"2026-01-01T0{hour}:00:00+00:00",
            model,
            float(hour),
            float(hour),
            0.0,
        )
        for model in ("baseline_mean", "decision_tree")
        for hour in (1, 2, 3)
    )

    content = export_prediction_charts(rows, tmp_path)[0].read_text(encoding="utf-8")
    series = re.findall(r'<polyline[^>]+points="([^"]+)"', content)

    assert len(series) == 3
    assert all(points.split()[0].startswith("50.00,") for points in series)
    assert all(points.split()[-1].startswith("950.00,") for points in series)
