from __future__ import annotations

from pathlib import Path

import pytest

from bitfinex_lending import modeling
from bitfinex_lending.models import ModelStatus, ModelingResult
from bitfinex_lending.modeling import ModelingRunSummary, ModelingSettings
from bitfinex_lending.raw_csv import RawCsvError


def _result() -> ModelingResult:
    return ModelingResult(
        statuses=(
            ModelStatus("fUSD", "insufficient_data", 2, 0, 168, "requires more data"),
        ),
        evaluations=(),
        predictions=(),
    )


def test_pipeline_calls_each_boundary_in_order(tmp_path: Path) -> None:
    events: list[str] = []
    raw_root = tmp_path / "raw"
    output_root = tmp_path / "modeling"
    rows = (object(), object(), object())
    features = (object(), object())
    result = _result()

    def loader(path: Path):
        events.append("load")
        assert path == raw_root
        return rows

    def calculator(source):
        events.append("calculate")
        assert source is rows
        return features

    def evaluator(source, run_at: str, required_rows: int):
        events.append("evaluate")
        assert source is features
        assert run_at == "2026-07-22T00:00:00+00:00"
        assert required_rows == 168
        return result

    def feature_exporter(source, path: Path):
        events.append("features_csv")
        assert source is features
        return path / "modeling_features.csv"

    def result_exporter(source, path: Path):
        events.append("results_csv")
        assert source is result
        return (
            path / "model_status.csv",
            path / "model_evaluations.csv",
            path / "predictions.csv",
        )

    summary = modeling.run_modeling_pipeline(
        raw_root,
        output_root,
        run_at="2026-07-22T00:00:00+00:00",
        loader=loader,
        calculator=calculator,
        evaluator=evaluator,
        feature_exporter=feature_exporter,
        result_exporter=result_exporter,
    )

    assert events == ["load", "calculate", "evaluate", "features_csv", "results_csv"]
    assert summary.source_rows == 3
    assert summary.feature_rows == 2
    assert summary.result is result


def test_main_reports_insufficient_data_and_all_output_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output_root = tmp_path / "modeling"
    summary = ModelingRunSummary(
        source_rows=3,
        feature_rows=2,
        result=_result(),
        feature_path=output_root / "modeling_features.csv",
        status_path=output_root / "model_status.csv",
        evaluation_path=output_root / "model_evaluations.csv",
        prediction_path=output_root / "predictions.csv",
    )
    monkeypatch.setattr(modeling, "run_modeling_pipeline", lambda *args, **kwargs: summary)

    assert modeling.main(ModelingSettings(tmp_path / "raw", output_root)) == 0
    output = capsys.readouterr()
    assert "fUSD insufficient_data feature_rows=2 valid_rows=0 required_rows=168" in output.out
    for path in (
        summary.feature_path,
        summary.status_path,
        summary.evaluation_path,
        summary.prediction_path,
    ):
        assert str(path) in output.out
    assert output.err == ""


@pytest.mark.parametrize(
    "error",
    [
        OSError("disk full"),
        RawCsvError("bad raw data"),
    ],
)
def test_main_returns_one_and_prints_fatal_for_expected_errors(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(modeling, "run_modeling_pipeline", fail)
    assert modeling.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"fatal: {error}\n"
