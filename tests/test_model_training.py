from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math

import pytest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from bitfinex_lending.model_training import ModelTrainingError, evaluate_models
from bitfinex_lending.models import ModelingFeature


def _features(count: int, market: str = "fUSD") -> tuple[ModelingFeature, ...]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        current = 0.0001 + index * 0.000001
        rows.append(
            ModelingFeature(
                market=market,
                feature_time=(start + timedelta(hours=index)).isoformat(),
                hour=index % 24,
                day_of_week=(index // 24) % 7,
                avg_rate=current + 0.000002,
                weighted_avg_rate=current,
                min_rate=current - 0.000003,
                max_rate=current + 0.000004,
                total_amount=1000.0 + index * 3,
                avg_period=2.0 + index % 5,
                offer_count=10 + index % 4,
                demand_count=5 + index % 3,
                rate_spread=0.000007,
                previous_weighted_avg_rate=current - 0.000001,
                rate_change=0.000001,
                amount_change=3.0,
                target_next_weighted_avg_rate=(
                    current + 0.000001 + (index % 7) * 0.0000001
                ),
            )
        )
    return tuple(rows)


def test_threshold_and_market_isolation() -> None:
    run_at = "2026-07-22T00:00:00+00:00"
    trained = evaluate_models(_features(168), run_at=run_at)
    status = trained.statuses[0]
    assert status.status == "trained"
    assert (status.feature_rows, status.valid_rows, status.required_rows) == (168, 168, 168)
    assert {item.model_name for item in trained.evaluations} == {
        "baseline_mean",
        "baseline_previous",
        "linear_regression",
    }

    insufficient = evaluate_models(_features(167), run_at=run_at)
    assert insufficient.statuses[0].status == "insufficient_data"
    assert insufficient.evaluations == ()
    assert insufficient.predictions == ()

    mixed = evaluate_models(_features(168) + _features(10, "fBTC"), run_at=run_at)
    assert [(item.market, item.status) for item in mixed.statuses] == [
        ("fBTC", "insufficient_data"),
        ("fUSD", "trained"),
    ]
    assert {item.market for item in mixed.evaluations} == {"fUSD"}


def test_models_share_chronological_validation_and_leakage_safe_baselines() -> None:
    features = _features(168)
    result = evaluate_models(features, run_at="2026-07-22T00:00:00Z")
    assert {(item.train_rows, item.valid_rows) for item in result.evaluations} == {(134, 34)}

    by_model = {
        name: [item for item in result.predictions if item.model_name == name]
        for name in ("baseline_mean", "baseline_previous", "linear_regression")
    }
    expected_times = [item.feature_time for item in features[134:]]
    assert all([item.feature_time for item in rows] == expected_times for rows in by_model.values())

    train_mean = sum(item.target_next_weighted_avg_rate for item in features[:134]) / 134
    assert all(item.predicted_rate == pytest.approx(train_mean) for item in by_model["baseline_mean"])
    assert [item.predicted_rate for item in by_model["baseline_previous"]] == pytest.approx(
        [item.weighted_avg_rate for item in features[134:]]
    )
    assert all(
        item.prediction_error == pytest.approx(item.predicted_rate - item.actual_next_rate)
        for rows in by_model.values()
        for item in rows
    )


def test_metrics_match_independent_calculation() -> None:
    result = evaluate_models(_features(168), run_at="2026-07-22T00:00:00+00:00")
    evaluation = next(item for item in result.evaluations if item.model_name == "baseline_previous")
    predictions = [item for item in result.predictions if item.model_name == "baseline_previous"]
    actual = [item.actual_next_rate for item in predictions]
    predicted = [item.predicted_rate for item in predictions]
    assert evaluation.mae == pytest.approx(mean_absolute_error(actual, predicted))
    assert evaluation.rmse == pytest.approx(math.sqrt(mean_squared_error(actual, predicted)))
    assert evaluation.r2 == pytest.approx(r2_score(actual, predicted))
    assert evaluation.train_start < evaluation.train_end < evaluation.valid_start < evaluation.valid_end


@pytest.mark.parametrize("run_at", ["not-a-time", "2026-07-22T00:00:00"])
def test_rejects_invalid_run_at(run_at: str) -> None:
    with pytest.raises(ModelTrainingError, match="run_at"):
        evaluate_models(_features(168), run_at=run_at)


@pytest.mark.parametrize(
    ("field", "value"),
    [("avg_rate", math.inf), ("target_next_weighted_avg_rate", math.nan)],
)
def test_rejects_non_finite_model_values(field: str, value: float) -> None:
    rows = list(_features(168))
    rows[5] = replace(rows[5], **{field: value})
    with pytest.raises(ModelTrainingError, match="finite"):
        evaluate_models(rows, run_at="2026-07-22T00:00:00Z")


def test_rejects_non_finite_r2_for_constant_validation_targets() -> None:
    rows = list(_features(168))
    for index in range(134, 168):
        rows[index] = replace(rows[index], target_next_weighted_avg_rate=0.1)
    with pytest.raises(ModelTrainingError, match="finite"):
        evaluate_models(rows, run_at="2026-07-22T00:00:00Z")
