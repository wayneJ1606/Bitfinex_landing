from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.modeling_csv import (
    EVALUATION_FIELDS,
    PREDICTION_FIELDS,
    STATUS_FIELDS,
    ModelingCsvError,
    export_modeling_results,
)
from bitfinex_lending.models import ModelEvaluation, ModelingResult, ModelPrediction, ModelStatus


def _result(trained: bool = True) -> ModelingResult:
    statuses = (
        ModelStatus("fUSD", "trained" if trained else "insufficient_data", 168, 168 if trained else 2, 168, "message"),
    )
    if not trained:
        return ModelingResult(statuses, (), ())
    return ModelingResult(
        statuses,
        (ModelEvaluation("2026-07-22T00:00:00+00:00", "fUSD", "baseline_mean", 134, 34, "a", "b", "c", "d", 1.0, 2.0, 3.0),),
        (ModelPrediction("2026-07-22T00:00:00+00:00", "fUSD", "2026-07-21T00:00:00+00:00", "baseline_mean", 1.0, 2.0, -1.0),),
    )


def _read(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def test_exports_fixed_schemas_and_header_only_insufficient_files(tmp_path: Path) -> None:
    status, evaluation, prediction = export_modeling_results(_result(False), tmp_path)
    assert _read(status)[0] == list(STATUS_FIELDS)
    assert _read(evaluation) == [list(EVALUATION_FIELDS)]
    assert _read(prediction) == [list(PREDICTION_FIELDS)]


def test_exports_rows_and_atomically_replaces_existing_files(tmp_path: Path) -> None:
    old = tmp_path / "model_status.csv"
    old.write_text("old", encoding="utf-8")
    paths = export_modeling_results(_result(), tmp_path)
    assert [path.name for path in paths] == ["model_status.csv", "model_evaluations.csv", "predictions.csv"]
    assert _read(paths[0])[1][0:2] == ["fUSD", "trained"]
    assert _read(paths[1])[1][2] == "baseline_mean"
    assert _read(paths[2])[1][-1] == "-1.0"
    assert not list(tmp_path.glob("*.tmp"))


def test_replace_failure_preserves_error_and_cleans_temporary_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.replace

    def fail_status(path: Path, target: Path) -> Path:
        if path.name == "model_status.csv.tmp":
            raise OSError("replace failed")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail_status)
    with pytest.raises(ModelingCsvError, match="replace failed"):
        export_modeling_results(_result(), tmp_path)
    assert not (tmp_path / "model_status.csv.tmp").exists()
