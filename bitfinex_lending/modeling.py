from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from .feature_calculation import FeatureCalculationError, calculate_features
from .feature_csv import FeatureCsvError, export_modeling_features
from .model_training import ModelTrainingError, evaluate_models
from .modeling_csv import ModelingCsvError, export_modeling_results
from .models import FundingBookRow, ModelingFeature, ModelingResult
from .raw_csv import RawCsvError, load_raw_snapshots


@dataclass(frozen=True)
class ModelingSettings:
    raw_root: Path = Path("data/raw")
    output_root: Path = Path("data/modeling")
    required_rows: int = 168


@dataclass(frozen=True)
class ModelingRunSummary:
    source_rows: int
    feature_rows: int
    result: ModelingResult
    feature_path: Path
    status_path: Path
    evaluation_path: Path
    prediction_path: Path


def run_modeling_pipeline(
    raw_root: Path,
    output_root: Path,
    run_at: str,
    *,
    required_rows: int = 168,
    loader: Callable[[Path], Sequence[FundingBookRow]] = load_raw_snapshots,
    calculator: Callable[[Sequence[FundingBookRow]], Sequence[ModelingFeature]] = calculate_features,
    evaluator: Callable[[Sequence[ModelingFeature], str, int], ModelingResult] = evaluate_models,
    feature_exporter: Callable[[Sequence[ModelingFeature], Path], Path] = export_modeling_features,
    result_exporter: Callable[[ModelingResult, Path], tuple[Path, Path, Path]] = export_modeling_results,
) -> ModelingRunSummary:
    rows = loader(Path(raw_root))
    features = calculator(rows)
    result = evaluator(features, run_at, required_rows)
    feature_path = feature_exporter(features, Path(output_root))
    status_path, evaluation_path, prediction_path = result_exporter(
        result, Path(output_root)
    )
    return ModelingRunSummary(
        source_rows=len(rows),
        feature_rows=len(features),
        result=result,
        feature_path=feature_path,
        status_path=status_path,
        evaluation_path=evaluation_path,
        prediction_path=prediction_path,
    )


def main(settings: ModelingSettings | None = None) -> int:
    settings = settings or ModelingSettings()
    try:
        summary = run_modeling_pipeline(
            settings.raw_root,
            settings.output_root,
            datetime.now(timezone.utc).isoformat(),
            required_rows=settings.required_rows,
        )
    except (
        OSError,
        RawCsvError,
        FeatureCalculationError,
        ModelTrainingError,
        FeatureCsvError,
        ModelingCsvError,
    ) as error:
        print(f"fatal: {error}", file=sys.stderr)
        return 1

    print(f"source_rows={summary.source_rows} feature_rows={summary.feature_rows}")
    for status in summary.result.statuses:
        print(
            f"{status.market} {status.status} feature_rows={status.feature_rows} "
            f"valid_rows={status.valid_rows} required_rows={status.required_rows} "
            f"message={status.message}"
        )
    for path in (
        summary.feature_path,
        summary.status_path,
        summary.evaluation_path,
        summary.prediction_path,
    ):
        print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
