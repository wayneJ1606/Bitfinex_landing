from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

from bitfinex_lending.models import ModelingResult


STATUS_FIELDS = ("market", "status", "feature_rows", "valid_rows", "required_rows", "message")
EVALUATION_FIELDS = ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2")
PREDICTION_FIELDS = ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error")


class ModelingCsvError(RuntimeError):
    """Raised when a modeling-result CSV cannot be exported atomically."""


def _export(
    filename: str,
    fields: Sequence[str],
    rows: Iterable[Sequence[object]],
    output_directory: Path,
) -> Path:
    target = output_directory / filename
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows(rows)
        temporary.replace(target)
    except (OSError, csv.Error) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ModelingCsvError(f"failed to export {filename}: {exc}") from exc
    return target


def export_modeling_results(
    result: ModelingResult, output_directory: Path
) -> tuple[Path, Path, Path]:
    output_directory = Path(output_directory)
    status_path = _export(
        "model_status.csv",
        STATUS_FIELDS,
        (
            tuple(getattr(item, field) for field in STATUS_FIELDS)
            for item in sorted(result.statuses, key=lambda item: item.market)
        ),
        output_directory,
    )
    evaluation_path = _export(
        "model_evaluations.csv",
        EVALUATION_FIELDS,
        (
            tuple(getattr(item, field) for field in EVALUATION_FIELDS)
            for item in sorted(result.evaluations, key=lambda item: (item.market, item.model_name))
        ),
        output_directory,
    )
    prediction_path = _export(
        "predictions.csv",
        PREDICTION_FIELDS,
        (
            tuple(getattr(item, field) for field in PREDICTION_FIELDS)
            for item in sorted(result.predictions, key=lambda item: (item.market, item.model_name, item.feature_time))
        ),
        output_directory,
    )
    return status_path, evaluation_path, prediction_path
