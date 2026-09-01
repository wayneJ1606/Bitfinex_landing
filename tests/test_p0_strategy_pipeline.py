from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import bitfinex_lending.p0_strategy_pipeline as pipeline
from bitfinex_lending.p0_market_history import MarketHour
from bitfinex_lending.p0_strategy_output import OutputPaths
from bitfinex_lending.p0_strategy_pipeline import (
    PipelineSummary,
    StrategyAnalysis,
    build_strategy_analysis,
    run_p0_strategy_pipeline,
)


UTC = timezone.utc


def _analysis() -> StrategyAnalysis:
    return StrategyAnalysis(
        status="experimental",
        readiness_status="insufficient_data",
        results=(
            {
                "asset": "USDT",
                "principal": "1000",
                "strategy_type": "optimized_without_prediction",
                "portfolio_type": "highest_return",
                "leg_count": 1,
                "daily_rates": ["0.0002"],
                "period_days": [2],
                "wait_hours": [1],
                "fill_probability": 0.8,
                "average_wait_hours": 0.5,
                "gross_interest": "4",
                "fee": "0.6",
                "net_interest": "3.4",
                "ending_capital": "1003.4",
                "idle_fraction": 0.2,
                "net_profit_p10": "1.2",
            },
        ),
        strategy_observations=(("q10-p2-w1", 20),),
        limitations=("資料未滿 60 天",),
    )


def test_manual_pipeline_promotes_dashboard_only_after_all_read_only_stages(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def load_history(*args: object, **kwargs: object) -> tuple[object, ...]:
        calls.append("load")
        assert kwargs["skip_incomplete"] is True
        return (object(),)

    def analyze(*args: object, **kwargs: object) -> StrategyAnalysis:
        calls.append("analyze")
        return _analysis()

    def publish(payload: object, output_root: Path) -> OutputPaths:
        calls.append("publish")
        latest = Path(output_root) / "latest"
        latest.mkdir(parents=True)
        (latest / "strategy_results.csv").write_text("ok\n", encoding="utf-8")
        (latest / "report.md").write_text("ok\n", encoding="utf-8")
        (latest / "dashboard_data.json").write_text("{}\n", encoding="utf-8")
        (latest / "status.json").write_text("{}\n", encoding="utf-8")
        return OutputPaths(
            csv_path=latest / "strategy_results.csv",
            report_path=latest / "report.md",
            json_path=latest / "dashboard_data.json",
            status_path=latest / "status.json",
        )

    def dashboard(source: Path, output_dir: Path) -> Path:
        calls.append("dashboard")
        path = Path(output_dir) / "dashboard.html"
        path.write_text("<html></html>", encoding="utf-8")
        return path

    summary = run_p0_strategy_pipeline(
        market_root=tmp_path / "market",
        raw_root=tmp_path / "raw",
        account_root=tmp_path / "account",
        modeling_root=tmp_path / "modeling",
        output_root=tmp_path / "modeling" / "p0_strategy",
        metadata_root=tmp_path / "metadata",
        clock=lambda: datetime(2026, 10, 1, 2, 0, tzinfo=UTC),
        history_loader=load_history,
        analysis_runner=analyze,
        output_publisher=publish,
        dashboard_exporter=dashboard,
    )

    assert summary.status == "experimental"
    assert summary.dashboard_path == tmp_path / "modeling" / "p0_strategy" / "latest" / "dashboard.html"
    assert summary.report_path.exists() and summary.csv_path.exists()
    assert calls == ["load", "analyze", "publish", "dashboard"]
    assert not tuple((tmp_path / "modeling" / "p0_strategy").glob(".pipeline-*"))


def test_manual_pipeline_failure_preserves_last_good_and_sanitizes_status(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "modeling" / "p0_strategy"
    latest = output_root / "latest"
    latest.mkdir(parents=True)
    (latest / "dashboard.html").write_text("last-good", encoding="utf-8")

    def publish(payload: object, output_root: Path) -> OutputPaths:
        staged = Path(output_root) / "latest"
        staged.mkdir(parents=True)
        for name in ("strategy_results.csv", "report.md", "dashboard_data.json", "status.json"):
            (staged / name).write_text("new", encoding="utf-8")
        return OutputPaths(
            csv_path=staged / "strategy_results.csv",
            report_path=staged / "report.md",
            json_path=staged / "dashboard_data.json",
            status_path=staged / "status.json",
        )

    def fail_dashboard(*args: object) -> Path:
        raise RuntimeError("api_key=private-value")

    with pytest.raises(RuntimeError):
        run_p0_strategy_pipeline(
            market_root=tmp_path / "market",
            raw_root=tmp_path / "raw",
            account_root=tmp_path / "account",
            modeling_root=tmp_path / "modeling",
            output_root=output_root,
            metadata_root=tmp_path / "metadata",
            history_loader=lambda *args, **kwargs: (object(),),
            analysis_runner=lambda *args, **kwargs: _analysis(),
            output_publisher=publish,
            dashboard_exporter=fail_dashboard,
        )

    assert (latest / "dashboard.html").read_text(encoding="utf-8") == "last-good"
    status = json.loads((tmp_path / "metadata" / "p0_strategy_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert "private-value" not in status["error"]


def test_success_status_write_must_finish_before_last_good_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "modeling" / "p0_strategy"
    latest = output_root / "latest"
    latest.mkdir(parents=True)
    (latest / "dashboard.html").write_text("last-good", encoding="utf-8")
    real_write_status = pipeline._write_json_atomic

    def fail_success_status(path: Path, payload: dict[str, object]) -> None:
        if payload.get("status") != "failed":
            raise OSError("status disk failure")
        real_write_status(path, payload)

    monkeypatch.setattr(pipeline, "_write_json_atomic", fail_success_status)

    with pytest.raises(OSError, match="status disk failure"):
        run_p0_strategy_pipeline(
            market_root=tmp_path / "market",
            raw_root=tmp_path / "raw",
            account_root=tmp_path / "account",
            modeling_root=tmp_path / "modeling",
            output_root=output_root,
            metadata_root=tmp_path / "metadata",
            history_loader=lambda *args, **kwargs: (object(),),
            analysis_runner=lambda *args, **kwargs: _analysis(),
        )

    assert (latest / "dashboard.html").read_text(encoding="utf-8") == "last-good"


def _hourly_history(hours: int = 72) -> tuple[MarketHour, ...]:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    return tuple(
        MarketHour(
            observed_at=start + timedelta(hours=index),
            api_symbol="fUST",
            asset="USDT",
            frr=0.0002,
            ask_rate=0.00018 + (index % 5) * 0.00001,
            visible_demand_amount=20_000.0,
            traded_high=0.0003,
            traded_volume=20_000.0,
            funding_amount_used=1_000_000.0,
        )
        for index in range(hours + 1)
    )


def test_short_history_still_produces_honest_experimental_current_strategies() -> None:
    analysis = build_strategy_analysis(
        _hourly_history(),
        generated_at=datetime(2026, 8, 4, 2, 0, tzinfo=UTC),
    )

    assert analysis.status == "experimental"
    assert analysis.readiness_status == "insufficient_data"
    assert {row["portfolio_type"] for row in analysis.results} >= {
        "highest_return",
        "stable_alternative",
        "fixed_median",
        "frr",
        "quick_fill",
    }
    assert {row["principal"] for row in analysis.results} >= {"1000", "10000"}
    assert any("60 天" in item for item in analysis.limitations)


def test_cli_is_manual_only_and_defaults_to_source_separated_local_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(**kwargs: object) -> PipelineSummary:
        captured.update(kwargs)
        latest = Path("data/modeling/p0_strategy/latest")
        return PipelineSummary(
            status="experimental",
            dashboard_path=latest / "dashboard.html",
            report_path=latest / "report.md",
            csv_path=latest / "strategy_results.csv",
            status_path=Path("data/metadata/p0_strategy_status.json"),
        )

    monkeypatch.setattr(pipeline, "run_p0_strategy_pipeline", fake_run)
    monkeypatch.setattr(sys, "argv", ["p0_strategy_pipeline"])

    assert pipeline.main() == 0
    assert captured["market_root"] == Path("data/local_public/market")
    assert captured["raw_root"] == Path("data/local_public/raw")
    assert "schedule" not in captured
