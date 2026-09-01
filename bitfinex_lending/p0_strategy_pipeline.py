"""Manual, read-only orchestration for the P0 funding strategy analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .models import ModelPrediction
from .p0_dashboard import export_dashboard
from .p0_economics import capital_levels
from .p0_fill_statistics import CandidateEstimate, estimate_candidates
from .p0_market_history import MarketHour, load_market_hours
from .p0_strategy_optimizer import OptimizerError, PortfolioResult, optimize_portfolios
from .p0_strategy_output import OutputPaths, publish_strategy_outputs
from .p0_walk_forward import WalkForwardError, _baseline_forecast, run_walk_forward


UTC = timezone.utc
FORMAL_HISTORY_HOURS = 1440.0
FORMAL_COVERAGE = 0.90
FORMAL_MAX_GAP_HOURS = 6.0
FORMAL_STRATEGY_OBSERVATIONS = 30


@dataclass(frozen=True)
class StrategyAnalysis:
    status: str
    readiness_status: str
    results: tuple[dict[str, object], ...]
    strategy_observations: tuple[tuple[str, int], ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class PipelineSummary:
    status: str
    dashboard_path: Path
    report_path: Path
    csv_path: Path
    status_path: Path


def _csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    if not path.exists():
        return ()
    with path.open(encoding="utf-8", newline="") as stream:
        return tuple(csv.DictReader(stream))


def _predictions(path: Path, api_symbol: str) -> tuple[ModelPrediction, ...]:
    output: list[ModelPrediction] = []
    for row in _csv_rows(path):
        if row.get("market") != api_symbol:
            continue
        try:
            output.append(
                ModelPrediction(
                    run_at=row["run_at"],
                    market=row["market"],
                    feature_time=row["feature_time"],
                    model_name=row["model_name"],
                    predicted_rate=float(row["predicted_rate"]),
                    actual_next_rate=float(row["actual_next_rate"]),
                    prediction_error=float(row["prediction_error"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(output)


def _history_metrics(rows: tuple[MarketHour, ...]) -> tuple[float, float, float]:
    if not rows:
        return 0.0, 0.0, math.inf
    hours = sorted({row.observed_at.replace(minute=0, second=0, microsecond=0) for row in rows})
    span_hours = (hours[-1] - hours[0]).total_seconds() / 3600
    expected_hours = max(1, math.floor(span_hours) + 1)
    coverage = len(hours) / expected_hours
    max_gap = max(
        ((right - left).total_seconds() / 3600 for left, right in zip(hours, hours[1:])),
        default=0.0,
    )
    return span_hours, coverage, max_gap


def _portfolio_row(
    portfolio: PortfolioResult,
    *,
    strategy_type: str,
    portfolio_type: str | None = None,
) -> dict[str, object]:
    legs = portfolio.legs
    fill_probability = sum(row.fill_probability for row in legs) / len(legs) if legs else 0.0
    average_wait = sum(row.expected_wait_hours for row in legs) / len(legs) if legs else 0.0
    return {
        "asset": portfolio.asset,
        "principal": str(portfolio.principal),
        "strategy_type": strategy_type,
        "portfolio_type": portfolio_type or portfolio.portfolio_type,
        "leg_count": len(legs),
        "daily_rates": [str(row.daily_rate) for row in legs],
        "period_days": sorted({row.period_days for row in legs}),
        "wait_hours": sorted({row.wait_hours for row in legs}),
        "fill_probability": round(fill_probability, 8),
        "average_wait_hours": round(average_wait, 8),
        "gross_interest": str(portfolio.gross_interest),
        "fee": str(portfolio.fee),
        "net_interest": str(portfolio.net_interest),
        "ending_capital": str(portfolio.ending_capital),
        "idle_fraction": round(portfolio.idle_fraction, 8),
        "net_profit_p10": str(portfolio.net_profit_p10),
    }


def _latest_prediction(
    predictions: Iterable[ModelPrediction],
    *,
    api_symbol: str,
    as_of: datetime,
) -> ModelPrediction | None:
    eligible: list[tuple[datetime, ModelPrediction]] = []
    for row in predictions:
        if row.market != api_symbol:
            continue
        try:
            observed_at = datetime.fromisoformat(row.feature_time.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            continue
        if observed_at.tzinfo is None or observed_at > as_of:
            continue
        eligible.append((observed_at.astimezone(UTC), row))
    return max(eligible, key=lambda item: item[0])[1] if eligible else None


def _append_current_rows(
    output: list[dict[str, object]],
    estimates: tuple[CandidateEstimate, ...],
    history: tuple[MarketHour, ...],
    predictions: tuple[ModelPrediction, ...],
) -> None:
    latest_frr = history[-1].frr
    for period_days in (2, 5, 10, 30):
        for wait_hours in (1, 3, 6, 12, 24):
            cell = tuple(
                row
                for row in estimates
                if row.period_days == period_days and row.wait_hours == wait_hours
            )
            if not cell:
                continue
            baselines = {
                "fixed_median": min(cell, key=lambda row: abs(row.rate_quantile - 0.50)),
                "quick_fill": min(cell, key=lambda row: abs(row.rate_quantile - 0.10)),
                "frr": min(cell, key=lambda row: abs(row.daily_rate - latest_frr)),
            }
            prediction = _latest_prediction(
                predictions,
                api_symbol=cell[0].api_symbol,
                as_of=cell[0].as_of,
            )
            predicted_cell = (
                tuple(row for row in cell if row.daily_rate <= prediction.predicted_rate)
                if prediction is not None
                else ()
            )
            if prediction is not None and not predicted_cell:
                lowest = min(row.daily_rate for row in cell)
                predicted_cell = tuple(row for row in cell if row.daily_rate == lowest)

            for principal in capital_levels():
                try:
                    highest, stable = optimize_portfolios(cell, principal)
                except OptimizerError:
                    highest = stable = None
                if highest is not None and stable is not None:
                    output.append(
                        _portfolio_row(highest, strategy_type="optimized_without_prediction")
                    )
                    output.append(
                        _portfolio_row(stable, strategy_type="optimized_without_prediction")
                    )
                for name, candidate in baselines.items():
                    baseline = _baseline_forecast(candidate, Decimal(principal))
                    output.append(
                        _portfolio_row(
                            baseline,
                            strategy_type=name,
                            portfolio_type=name,
                        )
                    )
                if predicted_cell:
                    try:
                        predicted_highest, predicted_stable = optimize_portfolios(
                            predicted_cell,
                            principal,
                        )
                    except OptimizerError:
                        continue
                    output.append(
                        _portfolio_row(
                            predicted_highest,
                            strategy_type="optimized_with_prediction",
                        )
                    )
                    output.append(
                        _portfolio_row(
                            predicted_stable,
                            strategy_type="optimized_with_prediction",
                        )
                    )


def build_strategy_analysis(
    history: Iterable[MarketHour],
    *,
    generated_at: datetime,
    predictions: Iterable[ModelPrediction] = (),
    private_matches: Iterable[Mapping[str, object]] = (),
    private_durations: Iterable[Mapping[str, object]] = (),
) -> StrategyAnalysis:
    """Build current P0 recommendations and evaluate whether they are formal."""
    rows = tuple(sorted(history, key=lambda row: row.observed_at))
    if not rows:
        return StrategyAnalysis(
            status="insufficient_data",
            readiness_status="insufficient_data",
            results=(),
            strategy_observations=(),
            limitations=("目前沒有可用的 USDT 公開市場資料。",),
        )
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must include a timezone")
    as_of = rows[-1].observed_at + timedelta(microseconds=1)
    estimates = estimate_candidates(
        rows,
        as_of,
        private_matches=private_matches,
        private_durations=private_durations,
    )
    output: list[dict[str, object]] = []
    prediction_rows = tuple(predictions)
    _append_current_rows(output, estimates, rows, prediction_rows)

    span_hours, coverage, max_gap = _history_metrics(rows)
    walk_forward_available = False
    if span_hours >= FORMAL_HISTORY_HOURS:
        try:
            run_walk_forward(
                rows,
                predictions=prediction_rows,
                private_matches=private_matches,
                private_durations=private_durations,
            )
            walk_forward_available = True
        except WalkForwardError:
            walk_forward_available = False
    min_observations = min((row.observations for row in estimates), default=0)
    formal = (
        span_hours >= FORMAL_HISTORY_HOURS
        and coverage >= FORMAL_COVERAGE
        and max_gap <= FORMAL_MAX_GAP_HOURS
        and min_observations >= FORMAL_STRATEGY_OBSERVATIONS
        and walk_forward_available
    )
    limitations = [
        "研究用途，不構成投資建議；本工具不會下單。",
        "公開市場成交代理不等於本人掛單真實成交，佇列順位仍可能影響結果。",
        "未滿 30 筆私人可比樣本時，成交與借出期間仍使用公開統計或名目期限。",
    ]
    if span_hours < FORMAL_HISTORY_HOURS:
        limitations.append(
            f"USDT 公開歷史目前約 {span_hours / 24:.1f} 天，尚未達正式 60 天門檻。"
        )
    if coverage < FORMAL_COVERAGE:
        limitations.append(f"每小時資料完整率約 {coverage:.1%}，低於正式 90% 門檻。")
    if max_gap > FORMAL_MAX_GAP_HOURS:
        limitations.append(f"最長公開資料缺口約 {max_gap:.1f} 小時，超過正式 6 小時門檻。")
    if not walk_forward_available:
        limitations.append("完整 walk-forward 驗證尚不可用；目前策略只可視為實驗估計。")
    if not prediction_rows:
        limitations.append("目前沒有可用的 fUST 利率預測，因此只顯示未使用預測的最佳化結果。")

    status = "formal" if formal else ("experimental" if output else "insufficient_data")
    return StrategyAnalysis(
        status=status,
        readiness_status="formal" if formal else "insufficient_data",
        results=tuple(output),
        strategy_observations=tuple(
            (row.strategy_id, row.observations) for row in estimates
        ),
        limitations=tuple(limitations),
    )


def _write_coverage(path: Path, rows: tuple[tuple[str, int], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("strategy_id", "observations"))
        writer.writerows(rows)
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _previous_last_success(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("last_success_at", "")) if isinstance(payload, dict) else ""


def _safe_error(error: Exception) -> str:
    message = str(error).replace("\r", " ").replace("\n", " ")[:500]
    return re.sub(
        r"(?i)(api[_ -]?key|secret|token|password)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        message,
    )


def _promote_latest(staged: Path, latest: Path) -> None:
    backup = latest.parent / f".latest-backup-{uuid.uuid4().hex}"
    if latest.exists():
        latest.replace(backup)
    try:
        staged.replace(latest)
    except Exception:
        if backup.exists() and not latest.exists():
            backup.replace(latest)
        raise
    if backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError:
            pass


def run_p0_strategy_pipeline(
    *,
    market_root: Path,
    raw_root: Path,
    account_root: Path,
    modeling_root: Path,
    output_root: Path,
    metadata_root: Path,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    history_loader: Callable[..., Iterable[MarketHour]] = load_market_hours,
    analysis_runner: Callable[..., StrategyAnalysis] = build_strategy_analysis,
    output_publisher: Callable[..., OutputPaths] = publish_strategy_outputs,
    dashboard_exporter: Callable[..., Path] = export_dashboard,
) -> PipelineSummary:
    """Run one manual P0 analysis; no scheduling or account writes are performed."""
    market_root = Path(market_root)
    raw_root = Path(raw_root)
    account_root = Path(account_root)
    modeling_root = Path(modeling_root)
    output_root = Path(output_root)
    metadata_root = Path(metadata_root)
    status_path = metadata_root / "p0_strategy_status.json"
    started_at = clock().astimezone(UTC)
    staging_root = output_root / f".pipeline-{uuid.uuid4().hex}"
    previous_success = _previous_last_success(status_path)
    try:
        history = tuple(
            history_loader(
                market_root,
                raw_root,
                "fUST",
                skip_incomplete=True,
            )
        )
        private_matches = _csv_rows(modeling_root / "p0_offer_trade_matches.csv")
        private_durations = _csv_rows(modeling_root / "p0_offer_lifecycle.csv")
        prediction_rows = _predictions(modeling_root / "predictions.csv", "fUST")
        analysis = analysis_runner(
            history,
            generated_at=started_at,
            predictions=prediction_rows,
            private_matches=private_matches,
            private_durations=private_durations,
        )
        _write_coverage(output_root / "strategy_coverage.csv", analysis.strategy_observations)
        payload = {
            "generated_at": started_at.isoformat(),
            "readiness_status": analysis.readiness_status,
            "limitations": list(analysis.limitations),
            "results": list(analysis.results),
        }
        paths = output_publisher(payload, staging_root)
        dashboard_path = dashboard_exporter(paths.json_path, paths.json_path.parent)
        required = (
            paths.csv_path,
            paths.report_path,
            paths.json_path,
            paths.status_path,
            dashboard_path,
        )
        if not all(path.exists() for path in required):
            raise RuntimeError("pipeline output validation failed")
        finished_at = clock().astimezone(UTC).isoformat()
        final_latest = output_root / "latest"
        _write_json_atomic(
            status_path,
            {
                "status": analysis.status,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at,
                "last_success_at": finished_at,
                "dashboard_path": str(final_latest / "dashboard.html"),
            },
        )
        _promote_latest(staging_root / "latest", final_latest)
        return PipelineSummary(
            status=analysis.status,
            dashboard_path=final_latest / "dashboard.html",
            report_path=final_latest / "report.md",
            csv_path=final_latest / "strategy_results.csv",
            status_path=status_path,
        )
    except Exception as error:
        _write_json_atomic(
            status_path,
            {
                "status": "failed",
                "started_at": started_at.isoformat(),
                "finished_at": clock().astimezone(UTC).isoformat(),
                "last_success_at": previous_success,
                "error": _safe_error(error),
            },
        )
        raise
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manually generate the local read-only P0 strategy dashboard"
    )
    parser.add_argument("--market-root", type=Path, default=Path("data/local_public/market"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/local_public/raw"))
    parser.add_argument("--account-root", type=Path, default=Path("data/account"))
    parser.add_argument("--modeling-root", type=Path, default=Path("data/modeling"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/modeling/p0_strategy"),
    )
    parser.add_argument("--metadata-root", type=Path, default=Path("data/metadata"))
    args = parser.parse_args()
    try:
        summary = run_p0_strategy_pipeline(
            market_root=args.market_root,
            raw_root=args.raw_root,
            account_root=args.account_root,
            modeling_root=args.modeling_root,
            output_root=args.output_root,
            metadata_root=args.metadata_root,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"failed: {_safe_error(error)}", file=sys.stderr)
        return 1
    print(f"status={summary.status}")
    print(f"dashboard={summary.dashboard_path}")
    print(f"report={summary.report_path}")
    print(f"csv={summary.csv_path}")
    print(f"metadata_status={summary.status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
