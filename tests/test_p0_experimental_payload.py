from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bitfinex_lending.p0_experimental_payload import build_experimental_payload


def write_csv(path: Path, fields: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def test_payload_uses_native_models_and_never_substitutes_fusd_for_fust(tmp_path: Path) -> None:
    modeling = tmp_path / "modeling"
    market = tmp_path / "market"
    write_csv(
        modeling / "model_evaluations.csv",
        ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2"),
        (
            ("2026-08-22T00:00:00+00:00", "fUSD", "baseline_previous", 100, 20, "a", "b", "c", "d", 0.1, 0.2, 0.3),
            ("2026-08-22T00:00:00+00:00", "fUSD", "linear_regression", 100, 20, "a", "b", "c", "d", 0.1, 0.1, 0.3),
            ("2026-08-22T00:00:00+00:00", "fUST", "linear_regression", 100, 20, "a", "b", "c", "d", 0.1, 0.01, 0.3),
        ),
    )
    write_csv(
        modeling / "predictions.csv",
        ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error"),
        (
            ("2026-08-22T00:00:00+00:00", "fUSD", "2026-08-21T00:00:00+00:00", "linear_regression", "0.001", "0.0011", "-0.0001"),
            ("2026-08-22T00:00:00+00:00", "fUST", "2026-08-21T00:00:00+00:00", "linear_regression", "0.009", "0.0091", "-0.0001"),
        ),
    )
    write_csv(
        market / "ticker" / "2026" / "08" / "22" / "fUST.csv",
        ("collected_at", "market", "frr", "ask"),
        (
            ("2026-08-22T00:47:00+00:00", "fUST", 0.1, 0.1),
            ("2026-08-22T01:47:00+00:00", "fUST", 0.1, 0.1),
        ),
    )

    payload = build_experimental_payload(
        modeling,
        market,
        generated_at="2026-08-22T02:00:00+00:00",
        capitals_usdt=(1000,),
        periods=(2,),
    )

    assert payload["status"] == "experimental"
    assert {row["market"] for row in payload["market_estimates"]} == {"fUSD"}
    assert payload["market_estimates"][0]["model_name"] == "linear_regression"
    assert payload["usdt_market"]["status"] == "collecting"
    assert payload["usdt_market"]["observed_hours"] == 2
    assert payload["usdt_market"]["required_hours"] == 1440
    assert payload["public_fill_proxy"]["status"] == "insufficient_data"
    assert all(row["market"] != "fUST" for row in payload["scenarios"])
    assert any("fUSD" in note and "fUST" in note for note in payload["limitations"])


def test_payload_converts_btc_principal_and_interest_with_latest_local_price(tmp_path: Path) -> None:
    modeling = tmp_path / "modeling"
    market = tmp_path / "market"
    write_csv(
        modeling / "model_evaluations.csv",
        ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2"),
        (("2026-08-22T00:00:00+00:00", "fBTC", "baseline_previous", 100, 20, "a", "b", "c", "d", 0.1, 0.2, 0.3),),
    )
    write_csv(
        modeling / "predictions.csv",
        ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error"),
        (("2026-08-22T00:00:00+00:00", "fBTC", "2026-08-21T00:00:00+00:00", "baseline_previous", "0.001", "0.0011", "-0.0001"),),
    )
    write_csv(
        market / "prices" / "2026" / "08" / "22" / "tBTCUSD.csv",
        ("collected_at", "market", "bid", "bid_size", "daily_change", "daily_change_perc", "last_price"),
        (
            ("2026-08-22T00:47:00+00:00", "tBTCUSD", 49990, 1, 0, 0, 50000),
            ("2026-08-22T01:47:00+00:00", "tBTCUSD", 50990, 1, 0, 0, 51000),
        ),
    )

    payload = build_experimental_payload(
        modeling,
        market,
        generated_at="2026-08-22T02:00:00+00:00",
        capitals_usdt=(1000,),
        periods=(2,),
    )

    estimate = payload["market_estimates"][0]
    scenario = payload["scenarios"][0]
    assert estimate["native_to_usdt"] == "51000"
    assert estimate["conversion_as_of"] == "2026-08-22T01:47:00+00:00"
    assert scenario["principal_native"] == "0.01960784313725490196078431373"
    assert Decimal(scenario["net_interest_usdt"]) == pytest.approx(Decimal("1.7"))


def test_payload_adds_low_confidence_fust_market_comparison(tmp_path: Path) -> None:
    modeling = tmp_path / "modeling"
    market = tmp_path / "market"
    write_csv(
        modeling / "model_evaluations.csv",
        ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2"),
        (),
    )
    write_csv(
        modeling / "predictions.csv",
        ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error"),
        (),
    )
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    ticker_rows = tuple(
        ((start + timedelta(hours=index, minutes=47)).isoformat(), "fUST", "0.001")
        for index in range(170)
    )
    candle_rows = tuple(
        ((start + timedelta(hours=index, minutes=47)).isoformat(), "fUST", "0.001")
        for index in range(170)
    )
    write_csv(
        market / "ticker" / "2026" / "08" / "01" / "fUST.csv",
        ("collected_at", "market", "ask"),
        ticker_rows,
    )
    write_csv(
        market / "funding_candles" / "2026" / "08" / "01" / "fUST.csv",
        ("collected_at", "market", "high"),
        candle_rows,
    )

    payload = build_experimental_payload(
        modeling,
        market,
        generated_at="2026-08-22T02:00:00+00:00",
        capitals_usdt=(1000,),
        periods=(2,),
    )

    proxy = payload["public_fill_proxy"]
    assert payload["schema_version"] == "p0-experimental-dashboard-v2"
    assert proxy["status"] == "experimental"
    assert proxy["confidence"] == "very_low"
    assert proxy["history_hours"] == 170
    assert proxy["highest_expected_strategy_id"]
    assert proxy["baselines"] == {
        "quick_fill": "q10-p2-w1",
        "fixed_median": "q50-p2-w24",
    }
    assert {row["wait_hours"] for row in proxy["candidates"]} == {1, 3, 6, 12, 24}
    assert all(row["method"] == "public_trade_high_proxy" for row in proxy["candidates"])
    assert any("repaid early" in note for note in payload["limitations"])


def test_payload_selects_best_model_and_prediction_from_same_latest_run(tmp_path: Path) -> None:
    modeling = tmp_path / "modeling"
    write_csv(
        modeling / "model_evaluations.csv",
        ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2"),
        (
            ("2026-08-01T00:00:00+00:00", "fUSD", "baseline_previous", 100, 20, "a", "b", "c", "d", 0.1, 0.001, 0.3),
            ("2026-08-22T00:00:00+00:00", "fUSD", "linear_regression", 100, 20, "a", "b", "c", "d", 0.1, 0.2, 0.3),
        ),
    )
    write_csv(
        modeling / "predictions.csv",
        ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error"),
        (
            ("2026-08-01T00:00:00+00:00", "fUSD", "2026-08-10T00:00:00+00:00", "baseline_previous", "0.009", "0.0091", "-0.0001"),
            ("2026-08-22T00:00:00+00:00", "fUSD", "2026-08-21T00:00:00+00:00", "linear_regression", "0.002", "0.0021", "-0.0001"),
        ),
    )

    payload = build_experimental_payload(
        modeling,
        tmp_path / "market",
        generated_at="2026-08-22T02:00:00+00:00",
        capitals_usdt=(1000,),
        periods=(2,),
    )

    estimate = payload["market_estimates"][0]
    assert estimate["model_name"] == "linear_regression"
    assert estimate["predicted_daily_rate"] == "0.002"
    assert estimate["prediction_as_of"] == "2026-08-21T00:00:00+00:00"
