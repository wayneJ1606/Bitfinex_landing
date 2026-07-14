from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .config import Settings
from .feature_calculation import FeatureCalculationError, calculate_features
from .feature_csv import FeatureCsvError, export_modeling_features
from .models import FundingBookRow, ModelingFeature
from .storage import Storage, StorageError


@dataclass(frozen=True)
class FeatureRunSummary:
    source_row_count: int
    feature_count: int
    csv_path: Path


def run_feature_pipeline(
    storage: Storage,
    exporter: Callable[[Sequence[ModelingFeature], Path], Path],
    output_directory: Path,
    calculator: Callable[
        [Sequence[FundingBookRow]], tuple[ModelingFeature, ...]
    ] = calculate_features,
) -> FeatureRunSummary:
    snapshots = storage.load_snapshots()
    features = calculator(snapshots)
    storage.replace_features(features)
    csv_path = exporter(features, output_directory)
    return FeatureRunSummary(len(snapshots), len(features), csv_path)


def build_dependencies(settings: Settings) -> Storage:
    return Storage(settings.database_path)


def main(settings: Settings | None = None) -> int:
    settings = settings or Settings()
    try:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        settings.csv_directory.mkdir(parents=True, exist_ok=True)
        storage = build_dependencies(settings)
        storage.initialize()
        summary = run_feature_pipeline(
            storage, export_modeling_features, settings.csv_directory
        )
    except (OSError, StorageError, FeatureCalculationError, FeatureCsvError) as error:
        print(f"fatal: {error}", file=sys.stderr)
        return 1

    print(
        f"source_rows={summary.source_row_count} "
        f"features={summary.feature_count} csv={summary.csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
