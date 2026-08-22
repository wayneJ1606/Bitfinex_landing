from __future__ import annotations

import csv
import json
from pathlib import Path

from bitfinex_lending.p0_experimental_pipeline import run_experimental_pipeline


def write_csv(path: Path, fields: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def test_pipeline_publishes_canonical_json_and_dashboard_without_private_inputs(tmp_path: Path) -> None:
    modeling, market, output = tmp_path / "modeling", tmp_path / "market", tmp_path / "output"
    write_csv(
        modeling / "model_evaluations.csv",
        ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2"),
        (("2026-08-22T00:00:00+00:00", "fUSD", "baseline_previous", 100, 20, "a", "b", "c", "d", 0.1, 0.2, 0.3),),
    )
    write_csv(
        modeling / "predictions.csv",
        ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error"),
        (("2026-08-22T00:00:00+00:00", "fUSD", "2026-08-21T00:00:00+00:00", "baseline_previous", "0.001", "0.0011", "-0.0001"),),
    )

    summary = run_experimental_pipeline(
        modeling_root=modeling,
        market_root=market,
        output_root=output,
        generated_at="2026-08-22T02:00:00+00:00",
    )

    assert summary.status == "experimental"
    assert summary.json_path == output / "dashboard_data.json"
    assert summary.dashboard_path == output / "dashboard.html"
    payload = json.loads(summary.json_path.read_text(encoding="utf-8"))
    assert payload["read_only"] is True
    assert payload["automatic_trading"] is False
    assert payload["scenarios"]
    assert "1001.7" in summary.dashboard_path.read_text(encoding="utf-8")
    assert not list(output.glob("*.tmp"))
