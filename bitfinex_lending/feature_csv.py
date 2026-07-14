from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import ModelingFeature


FIELD_NAMES = (
    "market",
    "feature_time",
    "hour",
    "day_of_week",
    "avg_rate",
    "weighted_avg_rate",
    "min_rate",
    "max_rate",
    "total_amount",
    "avg_period",
    "offer_count",
    "demand_count",
    "rate_spread",
    "previous_weighted_avg_rate",
    "rate_change",
    "amount_change",
    "target_next_weighted_avg_rate",
)


class FeatureCsvError(RuntimeError):
    """Raised when the modeling-feature CSV cannot be exported atomically."""


def _utc_feature_time(feature: ModelingFeature) -> datetime:
    return datetime.fromisoformat(feature.feature_time).astimezone(timezone.utc)


def _csv_row(feature: ModelingFeature) -> tuple[object, ...]:
    return tuple(
        "" if value is None else value
        for value in (
            feature.market,
            feature.feature_time,
            feature.hour,
            feature.day_of_week,
            feature.avg_rate,
            feature.weighted_avg_rate,
            feature.min_rate,
            feature.max_rate,
            feature.total_amount,
            feature.avg_period,
            feature.offer_count,
            feature.demand_count,
            feature.rate_spread,
            feature.previous_weighted_avg_rate,
            feature.rate_change,
            feature.amount_change,
            feature.target_next_weighted_avg_rate,
        )
    )


def export_modeling_features(
    features: Sequence[ModelingFeature], output_directory: Path
) -> Path:
    output_directory = Path(output_directory)
    target_path = output_directory / "modeling_features.csv"
    temporary_path = target_path.with_suffix(".csv.tmp")
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        ordered_features = sorted(
            features, key=lambda feature: (feature.market, _utc_feature_time(feature))
        )
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELD_NAMES)
            writer.writerows(_csv_row(feature) for feature in ordered_features)
        temporary_path.replace(target_path)
    except (OSError, csv.Error) as error:
        temporary_path.unlink(missing_ok=True)
        raise FeatureCsvError(
            f"failed to export modeling features CSV: {error}"
        ) from error
    return target_path
