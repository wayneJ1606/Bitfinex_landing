"""Atomic, privacy-safe publication of canonical P0 strategy results."""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SAFE_RESULT_FIELDS = (
    "asset",
    "principal",
    "portfolio_type",
    "leg_count",
    "daily_rates",
    "period_days",
    "wait_hours",
    "fill_probability",
    "average_wait_hours",
    "gross_interest",
    "fee",
    "net_interest",
    "ending_capital",
    "idle_fraction",
    "net_profit_p10",
)
FORBIDDEN_KEYS = ("api_key", "offer_id", "event_id", "raw_payload")


class OutputPrivacyError(ValueError):
    """Raised when a canonical payload contains private or identifying fields."""


class OutputValidationError(ValueError):
    """Raised when a canonical payload cannot produce consistent artifacts."""


@dataclass(frozen=True)
class OutputPaths:
    csv_path: Path
    report_path: Path
    json_path: Path
    status_path: Path


def _check_private_keys(value: object, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()
            if any(forbidden in name for forbidden in FORBIDDEN_KEYS):
                raise OutputPrivacyError(f"forbidden output key {key!r} at {path}: {name}")
            _check_private_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _check_private_keys(child, f"{path}[{index}]")


def _display_safe(value: object) -> object:
    if isinstance(value, str):
        return "USDT" if value == "fUST" else value
    if isinstance(value, Mapping):
        return {str(key): _display_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_display_safe(child) for child in value]
    return value


def _canonical_payload(payload: Mapping[str, object]) -> dict[str, object]:
    _check_private_keys(payload)
    generated_at = payload.get("generated_at")
    readiness = payload.get("readiness_status")
    limitations = payload.get("limitations", [])
    results = payload.get("results")
    if not isinstance(generated_at, str) or not generated_at:
        raise OutputValidationError("generated_at must be a non-empty string")
    if not isinstance(readiness, str) or not readiness:
        raise OutputValidationError("readiness_status must be a non-empty string")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise OutputValidationError("limitations must be a list of strings")
    if not isinstance(results, list) or not all(isinstance(item, Mapping) for item in results):
        raise OutputValidationError("results must be a list of mappings")

    safe_results = [
        {
            field: _display_safe(row[field])
            for field in SAFE_RESULT_FIELDS
            if field in row
        }
        for row in results
    ]
    status = "formal" if readiness == "formal" else "experimental"
    canonical: dict[str, object] = {
        "generated_at": generated_at,
        "readiness_status": readiness,
        "status": status,
        "limitations": list(limitations),
        "results": safe_results,
    }
    if "current_prices" in payload:
        canonical["current_prices"] = _display_safe(payload["current_prices"])
    return canonical


def _csv_value(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _write_csv(path: Path, payload: Mapping[str, object]) -> None:
    fields = (*SAFE_RESULT_FIELDS, "readiness_status", "limitations")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in payload["results"]:
            row = {field: _csv_value(result.get(field, "")) for field in SAFE_RESULT_FIELDS}
            row["readiness_status"] = payload["readiness_status"]
            row["limitations"] = _csv_value(payload["limitations"])
            writer.writerow(row)


def _write_report(path: Path, payload: Mapping[str, object]) -> None:
    lines = [
        "# P0 放貸策略回測報告",
        "",
        f"產生時間：{payload['generated_at']}",
        f"結果狀態：{payload['status']}",
        "",
        "## 比較方式",
        "",
        "本報告比較固定歷史中位利率、FRR 市場利率、偏低利率快速成交三種基準。",
        "同時比較有使用預測與未使用預測的最佳化策略；若最佳化未勝過簡單基準，也會如實保留結論。",
        "",
        "## 結果",
        "",
        "| 資產 | 本金 | 組合 | 淨利息 | 期末本金 | 閒置比例 |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            "| {asset} | {principal} | {portfolio_type} | {net_interest} | {ending_capital} | {idle_fraction} |".format(
                asset=row.get("asset", ""),
                principal=row.get("principal", ""),
                portfolio_type=row.get("portfolio_type", ""),
                net_interest=row.get("net_interest", ""),
                ending_capital=row.get("ending_capital", ""),
                idle_fraction=row.get("idle_fraction", ""),
            )
        )
    lines.extend(
        [
            "",
            "## 使用限制",
            "",
            "年化數字只是期間換算，不能視為未來保證報酬。",
            *(f"- {item}" for item in payload["limitations"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_staging(staging: Path, expected_rows: int) -> None:
    dashboard = json.loads((staging / "dashboard_data.json").read_text(encoding="utf-8"))
    status = json.loads((staging / "status.json").read_text(encoding="utf-8"))
    with (staging / "strategy_results.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != expected_rows or len(dashboard.get("results", [])) != expected_rows:
        raise OutputValidationError("published result counts are inconsistent")
    if status.get("status") != dashboard.get("status"):
        raise OutputValidationError("published statuses are inconsistent")


def publish_strategy_outputs(
    payload: Mapping[str, object],
    output_root: Path,
) -> OutputPaths:
    """Publish four mutually consistent files without damaging the last good set."""
    canonical = _canonical_payload(payload)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = output_root / f".staging-{token}"
    latest = output_root / "latest"
    backup = output_root / f".latest-backup-{token}"
    staging.mkdir()
    try:
        _write_csv(staging / "strategy_results.csv", canonical)
        _write_report(staging / "report.md", canonical)
        _write_json(staging / "dashboard_data.json", canonical)
        _write_json(
            staging / "status.json",
            {
                "status": canonical["status"],
                "generated_at": canonical["generated_at"],
                "result_count": len(canonical["results"]),
            },
        )
        _validate_staging(staging, len(canonical["results"]))

        if latest.exists():
            latest.replace(backup)
        try:
            staging.replace(latest)
        except Exception:
            if backup.exists() and not latest.exists():
                backup.replace(latest)
            raise
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError:
                # Publication already succeeded; a locked backup remains recoverable.
                pass
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return OutputPaths(
        csv_path=latest / "strategy_results.csv",
        report_path=latest / "report.md",
        json_path=latest / "dashboard_data.json",
        status_path=latest / "status.json",
    )
