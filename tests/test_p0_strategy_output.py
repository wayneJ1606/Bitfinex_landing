from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import bitfinex_lending.p0_strategy_output as strategy_output
from bitfinex_lending.p0_strategy_output import OutputPrivacyError, publish_strategy_outputs


def payload() -> dict[str, object]:
    return {
        "generated_at": "2026-10-01T02:00:00+00:00",
        "readiness_status": "formal",
        "limitations": ["研究用途，不構成投資建議"],
        "results": [
            {
                "asset": "USDT",
                "principal": "1000",
                "portfolio_type": "highest_return",
                "leg_count": 1,
                "daily_rates": ["0.0002"],
                "period_days": [2],
                "wait_hours": [1],
                "fill_probability": 0.8,
                "average_wait_hours": 0.5,
                "gross_interest": "4.0",
                "fee": "0.6",
                "net_interest": "3.4",
                "ending_capital": "1003.4",
                "idle_fraction": 0.2,
                "net_profit_p10": "1.2",
            }
        ],
    }


def test_publish_uses_one_canonical_payload_for_all_formats(tmp_path: Path) -> None:
    paths = publish_strategy_outputs(payload(), tmp_path)

    csv_rows = list(csv.DictReader(paths.csv_path.open(encoding="utf-8", newline="")))
    dashboard = json.loads(paths.json_path.read_text(encoding="utf-8"))
    status = json.loads(paths.status_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert csv_rows[0]["ending_capital"] == dashboard["results"][0]["ending_capital"]
    assert csv_rows[0]["asset"] == "USDT"
    assert status["status"] == "formal"
    assert "fUST" not in report
    assert "固定歷史中位利率" in report
    assert "有使用預測" in report and "未使用預測" in report
    assert "年化" in report and "不構成投資建議" in report


@pytest.mark.parametrize("forbidden", ["api_key", "offer_id", "event_id", "raw_payload"])
def test_rejects_private_or_identifying_keys_recursively(
    tmp_path: Path,
    forbidden: str,
) -> None:
    unsafe = payload()
    unsafe["results"][0][forbidden] = "secret-value"

    with pytest.raises(OutputPrivacyError, match=forbidden):
        publish_strategy_outputs(unsafe, tmp_path)

    assert not (tmp_path / "latest").exists()


def test_non_formal_readiness_is_published_as_experimental(tmp_path: Path) -> None:
    experimental = payload()
    experimental["readiness_status"] = "insufficient_data"

    paths = publish_strategy_outputs(experimental, tmp_path)

    status = json.loads(paths.status_path.read_text(encoding="utf-8"))
    dashboard = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert status["status"] == "experimental"
    assert dashboard["status"] == "experimental"


def test_strategy_and_portfolio_types_survive_every_machine_readable_output(
    tmp_path: Path,
) -> None:
    compatible = payload()
    compatible["results"][0]["strategy_type"] = "optimized_without_prediction"
    compatible["results"][0]["portfolio_type"] = "stable_alternative"

    paths = publish_strategy_outputs(compatible, tmp_path)

    csv_rows = list(csv.DictReader(paths.csv_path.open(encoding="utf-8", newline="")))
    dashboard = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert csv_rows[0]["strategy_type"] == "optimized_without_prediction"
    assert dashboard["results"][0]["strategy_type"] == "optimized_without_prediction"
    assert dashboard["results"][0]["portfolio_type"] == "stable_alternative"
    assert "optimized_without_prediction" in paths.report_path.read_text(encoding="utf-8")


def test_forced_write_failure_preserves_previous_latest_byte_for_byte(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    latest = tmp_path / "latest"
    latest.mkdir()
    previous = {
        "strategy_results.csv": b"old-csv\n",
        "report.md": "舊報告".encode(),
        "dashboard_data.json": b'{"old":true}\n',
        "status.json": b'{"status":"formal"}\n',
    }
    for name, content in previous.items():
        (latest / name).write_bytes(content)

    def fail_report(*args: object, **kwargs: object) -> None:
        raise OSError("forced report failure")

    monkeypatch.setattr(strategy_output, "_write_report", fail_report)

    with pytest.raises(OSError, match="forced report failure"):
        publish_strategy_outputs(payload(), tmp_path)

    assert {name: (latest / name).read_bytes() for name in previous} == previous
    assert not tuple(tmp_path.glob(".staging-*"))


def test_backup_cleanup_lock_does_not_turn_success_into_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish_strategy_outputs(payload(), tmp_path)
    real_rmtree = strategy_output.shutil.rmtree

    def locked_backup(path: Path, *args: object, **kwargs: object) -> None:
        if Path(path).name.startswith(".latest-backup-"):
            raise PermissionError("backup is locked")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(strategy_output.shutil, "rmtree", locked_backup)
    updated = payload()
    updated["generated_at"] = "2026-10-02T02:00:00+00:00"

    paths = publish_strategy_outputs(updated, tmp_path)

    dashboard = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert dashboard["generated_at"] == "2026-10-02T02:00:00+00:00"
