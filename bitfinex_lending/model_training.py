from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Sequence
import warnings

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from bitfinex_lending.models import (
    ModelEvaluation,
    ModelingFeature,
    ModelingResult,
    ModelPrediction,
    ModelStatus,
)


PREDICTOR_FIELDS = (
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
)


class ModelTrainingError(ValueError):
    """Raised when trustworthy model evaluation cannot be produced."""


def _utc(value: str, field: str) -> tuple[datetime, str]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ModelTrainingError(f"{field} must be a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ModelTrainingError(f"{field} must include a timezone offset")
    normalized = parsed.astimezone(timezone.utc)
    return normalized, normalized.isoformat()


def _eligible(feature: ModelingFeature) -> bool:
    values = [getattr(feature, field) for field in PREDICTOR_FIELDS]
    values.append(feature.target_next_weighted_avg_rate)
    if any(value is None for value in values):
        return False
    if any(not math.isfinite(float(value)) for value in values):
        raise ModelTrainingError(
            f"model values must be finite for {feature.market} at {feature.feature_time}"
        )
    return True


def _matrix(features: Sequence[ModelingFeature]) -> list[list[float]]:
    return [[float(getattr(feature, field)) for field in PREDICTOR_FIELDS] for feature in features]


def _evaluate_predictions(
    *,
    run_at: str,
    market: str,
    model_name: str,
    train: Sequence[ModelingFeature],
    validation: Sequence[ModelingFeature],
    predicted: Sequence[float],
) -> tuple[ModelEvaluation, tuple[ModelPrediction, ...]]:
    actual = [float(item.target_next_weighted_avg_rate) for item in validation]
    predicted_values = [float(value) for value in predicted]
    mae = float(mean_absolute_error(actual, predicted_values))
    rmse = float(math.sqrt(mean_squared_error(actual, predicted_values)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r2 = float(r2_score(actual, predicted_values, force_finite=False))
    if not all(math.isfinite(value) for value in (mae, rmse, r2, *predicted_values)):
        raise ModelTrainingError(f"{market} {model_name} metrics and predictions must be finite")
    evaluation = ModelEvaluation(
        run_at=run_at,
        market=market,
        model_name=model_name,
        train_rows=len(train),
        valid_rows=len(validation),
        train_start=train[0].feature_time,
        train_end=train[-1].feature_time,
        valid_start=validation[0].feature_time,
        valid_end=validation[-1].feature_time,
        mae=mae,
        rmse=rmse,
        r2=r2,
    )
    predictions = tuple(
        ModelPrediction(
            run_at=run_at,
            market=market,
            feature_time=feature.feature_time,
            model_name=model_name,
            predicted_rate=value,
            actual_next_rate=actual_rate,
            prediction_error=value - actual_rate,
        )
        for feature, value, actual_rate in zip(
            validation, predicted_values, actual, strict=True
        )
    )
    return evaluation, predictions


def evaluate_models(
    features: Sequence[ModelingFeature],
    run_at: str,
    required_rows: int = 168,
) -> ModelingResult:
    """Evaluate fixed models independently per market on chronological data."""
    _, normalized_run_at = _utc(run_at, "run_at")
    if required_rows < 2:
        raise ModelTrainingError("required_rows must be at least 2")

    grouped: dict[str, list[tuple[datetime, ModelingFeature]]] = defaultdict(list)
    for feature in features:
        timestamp, normalized_time = _utc(feature.feature_time, "feature_time")
        normalized = feature
        if normalized_time != feature.feature_time:
            from dataclasses import replace

            normalized = replace(feature, feature_time=normalized_time)
        grouped[feature.market].append((timestamp, normalized))

    statuses: list[ModelStatus] = []
    evaluations: list[ModelEvaluation] = []
    predictions: list[ModelPrediction] = []
    for market in sorted(grouped):
        ordered = [item[1] for item in sorted(grouped[market], key=lambda item: item[0])]
        eligible = [item for item in ordered if _eligible(item)]
        if len(eligible) < required_rows:
            statuses.append(
                ModelStatus(
                    market=market,
                    status="insufficient_data",
                    feature_rows=len(ordered),
                    valid_rows=len(eligible),
                    required_rows=required_rows,
                    message=f"requires {required_rows} eligible rows; found {len(eligible)}",
                )
            )
            continue

        train_size = math.floor(len(eligible) * 0.8)
        train, validation = eligible[:train_size], eligible[train_size:]
        if not train or not validation:
            raise ModelTrainingError(f"{market} chronological split must be non-empty")
        train_targets = [float(item.target_next_weighted_avg_rate) for item in train]
        prediction_sets = {
            "baseline_mean": [sum(train_targets) / len(train_targets)] * len(validation),
            "baseline_previous": [float(item.weighted_avg_rate) for item in validation],
        }
        estimator = LinearRegression().fit(_matrix(train), train_targets)
        prediction_sets["linear_regression"] = estimator.predict(_matrix(validation)).tolist()

        for model_name, predicted in prediction_sets.items():
            evaluation, model_predictions = _evaluate_predictions(
                run_at=normalized_run_at,
                market=market,
                model_name=model_name,
                train=train,
                validation=validation,
                predicted=predicted,
            )
            evaluations.append(evaluation)
            predictions.extend(model_predictions)
        statuses.append(
            ModelStatus(
                market=market,
                status="trained",
                feature_rows=len(ordered),
                valid_rows=len(eligible),
                required_rows=required_rows,
                message="evaluated baseline_mean, baseline_previous, and linear_regression",
            )
        )

    return ModelingResult(
        statuses=tuple(statuses),
        evaluations=tuple(sorted(evaluations, key=lambda item: (item.market, item.model_name))),
        predictions=tuple(
            sorted(predictions, key=lambda item: (item.market, item.model_name, item.feature_time))
        ),
    )
