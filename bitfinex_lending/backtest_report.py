from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .backtesting import BacktestResult


def export_backtest_report(results: Iterable[BacktestResult], output_directory: Path) -> Path:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[BacktestResult]] = {}
    for result in results:
        grouped.setdefault(result.market, []).append(result)
    lines = [
        "# 回測結果解讀",
        "",
        "本報告只使用 validation predictions 的離線模擬；結果不代表實際成交或實際收益，也不是投資建議。",
        "",
    ]
    for market in sorted(grouped):
        ranked = sorted(grouped[market], key=lambda item: (-item.total_simulated_return, item.model_name))
        lines.extend([f"## {market}", "", "| 模型 | 信號 | 成交 | 成交率 | 資金利用率 | 平均等待（小時） | 模擬總收益 |", "|---|---:|---:|---:|---:|---:|---:|"])
        for item in ranked:
            lines.append(f"| `{item.model_name}` | {item.signals} | {item.fills} | {item.fill_rate:.8g} | {item.capital_utilization:.8g} | {item.average_wait_hours:.8g} | {item.total_simulated_return:.8g} |")
        lines.extend(["", f"目前依模擬總收益排序的第一名是 `{ranked[0].model_name}`；仍需人工確認門檻、成交假設與資料品質。", ""])
    lines.extend(["## 使用限制", "", "本回測未模擬滑價、深度、手續費、撤單、部分成交或市場中斷；不可直接轉換為真實交易策略。", ""])
    path = output_directory / "backtest_report.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
