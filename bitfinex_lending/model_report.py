from __future__ import annotations

from pathlib import Path

from .models import ModelingResult


def export_model_report(result: ModelingResult, output_directory: Path) -> Path:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 模型結果解讀",
        "",
        "本報告使用時間順序 80/20 切分；結果僅供研究與人工確認，不代表收益保證，也不會執行下單。",
        "",
    ]
    evaluations_by_market: dict[str, list] = {}
    for evaluation in result.evaluations:
        evaluations_by_market.setdefault(evaluation.market, []).append(evaluation)
    for status in result.statuses:
        lines.extend([f"## {status.market}", "", f"- 狀態：`{status.status}`", f"- 有效資料：{status.valid_rows}/{status.required_rows}"])
        if status.status != "trained":
            lines.extend([f"- 限制：{status.message}", ""])
            continue
        evaluations = sorted(evaluations_by_market.get(status.market, []), key=lambda item: item.rmse)
        if evaluations:
            best = evaluations[0]
            lines.extend([f"- **best（依 RMSE）**：`{best.model_name}`", "", "| 模型 | MAE | RMSE | R² |", "|---|---:|---:|---:|"])
            lines.extend(f"| `{item.model_name}` | {item.mae:.8g} | {item.rmse:.8g} | {item.r2:.8g} |" for item in evaluations)
        lines.extend(["", "- 解讀限制：驗證集樣本仍有限，模型比較不等同於未來績效；需人工確認資料品質與市場狀況。", ""])
    if any("xgboost unavailable" in status.message for status in result.statuses):
        lines.extend(["## 執行環境限制", "", "目前環境未安裝 `xgboost`，因此未將 XGBoost 視為已訓練模型；安裝 modeling 額外依賴後重新執行即可。", ""])
    path = output_directory / "model_report.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
