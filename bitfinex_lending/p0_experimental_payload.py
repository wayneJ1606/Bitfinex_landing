"""Build the canonical JSON-safe payload for the experimental dashboard."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from .p0_experimental import NativeMarketEstimate, build_native_scenarios
from .p0_public_fill_proxy import (
    PublicFundingHour,
    estimate_public_fill_proxy,
    load_fust_public_hours,
)


ASSET_BY_MARKET = {"fUSD": "USD", "fBTC": "BTC", "fETH": "ETH"}
PRICE_MARKET_BY_FUNDING = {"fBTC": "tBTCUSD", "fETH": "tETHUSD"}
FORMAL_USDT_HOURS = 1440


class ExperimentalPayloadError(ValueError):
    """Raised when local model artifacts cannot be interpreted safely."""


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _decimal(value: str, field: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ExperimentalPayloadError(f"{field} must be a decimal") from error
    if not number.is_finite():
        raise ExperimentalPayloadError(f"{field} must be finite")
    return number


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ExperimentalPayloadError(f"{field} must be ISO 8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExperimentalPayloadError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def _latest_price(market_root: Path, price_market: str) -> tuple[Decimal, str] | None:
    candidates: list[tuple[datetime, Decimal, str]] = []
    for path in sorted((market_root / "prices").rglob(f"{price_market}.csv")) if (market_root / "prices").exists() else ():
        for row in _csv_rows(path):
            if row.get("market") != price_market:
                continue
            timestamp_text = row.get("collected_at", "")
            try:
                timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            except ValueError as error:
                raise ExperimentalPayloadError("price collected_at must be ISO 8601") from error
            if timestamp.tzinfo is None:
                raise ExperimentalPayloadError("price collected_at must include timezone")
            price = _decimal(row.get("last_price", ""), "last_price")
            if price <= 0:
                raise ExperimentalPayloadError("last_price must be greater than zero")
            candidates.append((timestamp.astimezone(timezone.utc), price, timestamp_text))
    if not candidates:
        return None
    _, price, timestamp_text = max(candidates, key=lambda item: item[0])
    return price, timestamp_text


def _usdt_observed_hours(market_root: Path) -> int:
    hours: set[datetime] = set()
    ticker_root = market_root / "ticker"
    for path in sorted(ticker_root.rglob("fUST.csv")) if ticker_root.exists() else ():
        for row in _csv_rows(path):
            if row.get("market") != "fUST":
                continue
            try:
                timestamp = datetime.fromisoformat(row.get("collected_at", "").replace("Z", "+00:00"))
            except ValueError as error:
                raise ExperimentalPayloadError("fUST collected_at must be ISO 8601") from error
            if timestamp.tzinfo is None:
                raise ExperimentalPayloadError("fUST collected_at must include timezone")
            hours.add(timestamp.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))
    return len(hours)


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _continuous_tail(hours: tuple[PublicFundingHour, ...]) -> tuple[PublicFundingHour, ...]:
    if not hours:
        return ()
    start = len(hours) - 1
    while start > 0 and hours[start].observed_at - hours[start - 1].observed_at == timedelta(hours=1):
        start -= 1
    return hours[start:]


def _public_fill_payload(market_root: Path, periods: tuple[int, ...]) -> dict[str, object]:
    paired = load_fust_public_hours(market_root)
    continuous = _continuous_tail(paired)
    if len(continuous) < 26:
        return {
            "status": "insufficient_data",
            "confidence": "very_low",
            "history_hours": len(continuous),
            "lookback_hours": 24,
            "highest_expected_strategy_id": "",
            "baselines": {},
            "candidates": [],
            "method": "public_trade_high_proxy",
        }
    candidates = estimate_public_fill_proxy(continuous, periods=periods)
    if not candidates:
        return {
            "status": "insufficient_data",
            "confidence": "very_low",
            "history_hours": len(continuous),
            "lookback_hours": 24,
            "highest_expected_strategy_id": "",
            "baselines": {},
            "candidates": [],
            "method": "public_trade_high_proxy",
        }
    highest = max(
        candidates,
        key=lambda row: (row.expected_30d_net_profit_per_1000, row.proxy_fill_probability, row.strategy_id),
    )
    baselines: dict[str, str] = {}
    candidate_ids = {row.strategy_id for row in candidates}
    if "q10-p2-w1" in candidate_ids:
        baselines["quick_fill"] = "q10-p2-w1"
    if "q50-p2-w24" in candidate_ids:
        baselines["fixed_median"] = "q50-p2-w24"
    return {
        "status": "experimental",
        "confidence": "very_low",
        "history_hours": len(continuous),
        "lookback_hours": 24,
        "highest_expected_strategy_id": highest.strategy_id,
        "baselines": baselines,
        "candidates": [asdict(row) for row in candidates],
        "method": "public_trade_high_proxy",
    }


def build_experimental_payload(
    modeling_root: Path,
    market_root: Path,
    *,
    generated_at: str,
    capitals_usdt: Iterable[int] = range(1000, 10001, 1000),
    periods: Iterable[int] = (2, 5, 10, 30),
) -> dict[str, object]:
    """Combine validation predictions and native conversions without fill inference."""
    modeling_root, market_root = Path(modeling_root), Path(market_root)
    evaluations = _csv_rows(modeling_root / "model_evaluations.csv")
    predictions = _csv_rows(modeling_root / "predictions.csv")

    latest_run_by_market: dict[str, datetime] = {}
    for row in evaluations:
        market = row.get("market", "")
        if market not in ASSET_BY_MARKET:
            continue
        run_at = _timestamp(row.get("run_at", ""), "run_at")
        if market not in latest_run_by_market or run_at > latest_run_by_market[market]:
            latest_run_by_market[market] = run_at

    best: dict[str, dict[str, str]] = {}
    for row in evaluations:
        market = row.get("market", "")
        if market not in ASSET_BY_MARKET:
            continue
        if _timestamp(row.get("run_at", ""), "run_at") != latest_run_by_market[market]:
            continue
        rmse = _decimal(row.get("rmse", ""), "rmse")
        if rmse < 0:
            raise ExperimentalPayloadError("rmse must be nonnegative")
        previous = best.get(market)
        if previous is None or rmse < _decimal(previous["rmse"], "rmse"):
            best[market] = row

    estimates: list[NativeMarketEstimate] = []
    skipped: list[str] = []
    for market in sorted(best):
        evaluation = best[market]
        matches = [
            row for row in predictions
            if row.get("market") == market and row.get("model_name") == evaluation.get("model_name")
            and _timestamp(row.get("run_at", ""), "run_at")
            == _timestamp(evaluation.get("run_at", ""), "run_at")
        ]
        if not matches:
            skipped.append(f"{market}: no validation prediction for selected model")
            continue
        latest = max(matches, key=lambda row: _timestamp(row.get("feature_time", ""), "feature_time"))
        predicted_rate = _decimal(latest.get("predicted_rate", ""), "predicted_rate")
        if predicted_rate <= 0:
            skipped.append(f"{market}: latest validation rate is not positive")
            continue
        if market == "fUSD":
            conversion, conversion_at = Decimal("1"), generated_at
            note = "USD/USDT display uses an explicit 1:1 approximation"
        else:
            price = _latest_price(market_root, PRICE_MARKET_BY_FUNDING[market])
            if price is None:
                skipped.append(f"{market}: no local USD spot price for USDT-equivalent display")
                continue
            conversion, conversion_at = price
            note = f"{PRICE_MARKET_BY_FUNDING[market]} local last price; USD/USDT assumed 1:1 for display"
        estimates.append(
            NativeMarketEstimate(
                asset=ASSET_BY_MARKET[market],
                market=market,
                model_name=evaluation["model_name"],
                predicted_daily_rate=predicted_rate,
                prediction_as_of=latest["feature_time"],
                rmse=_decimal(evaluation["rmse"], "rmse"),
                native_to_usdt=conversion,
                conversion_as_of=conversion_at,
                conversion_note=note,
            )
        )

    period_values = tuple(periods)
    scenarios = build_native_scenarios(
        tuple(estimates),
        capitals_usdt=tuple(Decimal(value) for value in capitals_usdt),
        periods=period_values,
    )
    observed_hours = _usdt_observed_hours(market_root)
    public_fill_proxy = _public_fill_payload(market_root, period_values)
    payload = {
        "schema_version": "p0-experimental-dashboard-v2",
        "status": "experimental",
        "generated_at": generated_at,
        "market_estimates": [asdict(item) for item in estimates],
        "scenarios": [asdict(item) for item in scenarios],
        "usdt_market": {
            "status": "collecting" if observed_hours < FORMAL_USDT_HOURS else "awaiting_formal_validation",
            "observed_hours": observed_hours,
            "required_hours": FORMAL_USDT_HOURS,
            "recommendation_available": False,
        },
        "public_fill_proxy": public_fill_proxy,
        "limitations": [
            "fUSD market behavior is not used as a substitute for fUST market behavior.",
            "Rates are the latest chronological validation predictions, not live forward forecasts.",
            "Native-asset theoretical scenarios assume immediate full matching; the separate fUST market comparison includes a public trade-high fill proxy and waiting loss.",
            "A public candle touching a rate does not prove an individual offer filled because queue position and available capacity are unknown.",
            "A successful proxy assumes funding remains open for the selected term; actual funding may be repaid early and earn less.",
            "The 15% public funding provider fee is deducted.",
            "USD values use an explicit 1:1 USD/USDT display approximation; BTC and ETH remain calculated in their native assets.",
            *skipped,
        ],
        "read_only": True,
        "automatic_trading": False,
    }
    return _json_safe(payload)  # type: ignore[return-value]
