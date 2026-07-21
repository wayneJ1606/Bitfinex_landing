from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class FundingBookRow:
    run_id: str
    market: str
    rate: float
    period: int
    count: int
    amount: float
    side: Literal["offer", "demand"]
    fetched_at: str


@dataclass(frozen=True)
class ModelingFeature:
    market: str
    feature_time: str
    hour: int
    day_of_week: int
    avg_rate: float
    weighted_avg_rate: float
    min_rate: float
    max_rate: float
    total_amount: float
    avg_period: float
    offer_count: int
    demand_count: int
    rate_spread: float
    previous_weighted_avg_rate: float | None
    rate_change: float | None
    amount_change: float | None
    target_next_weighted_avg_rate: float | None


@dataclass(frozen=True)
class MarketResult:
    market: str
    status: Literal["success", "empty", "failed"]
    row_count: int
    message: str
    csv_path: Path | None = None


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    results: tuple[MarketResult, ...]

    @property
    def exit_code(self) -> int:
        return 1 if any(result.status == "failed" for result in self.results) else 0

    @property
    def warning_count(self) -> int:
        return sum(result.status == "empty" for result in self.results)


@dataclass(frozen=True)
class ModelStatus:
    market: str
    status: Literal["insufficient_data", "trained"]
    feature_rows: int
    valid_rows: int
    required_rows: int
    message: str


@dataclass(frozen=True)
class ModelEvaluation:
    run_at: str
    market: str
    model_name: str
    train_rows: int
    valid_rows: int
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    mae: float
    rmse: float
    r2: float


@dataclass(frozen=True)
class ModelPrediction:
    run_at: str
    market: str
    feature_time: str
    model_name: str
    predicted_rate: float
    actual_next_rate: float
    prediction_error: float


@dataclass(frozen=True)
class ModelingResult:
    statuses: tuple[ModelStatus, ...]
    evaluations: tuple[ModelEvaluation, ...]
    predictions: tuple[ModelPrediction, ...]
