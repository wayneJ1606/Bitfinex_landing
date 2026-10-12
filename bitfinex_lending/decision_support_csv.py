from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .decision_support import DecisionSupportRow


FIELDS = tuple(DecisionSupportRow.__dataclass_fields__)


def export_decision_support(rows: Iterable[DecisionSupportRow], output_directory: Path) -> tuple[Path, Path]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    csv_path = output_directory / "decision_support.csv"
    temporary = csv_path.with_suffix(".csv.tmp")
    rows = tuple(sorted(rows, key=lambda item: item.market))
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            for row in rows:
                writer.writerow(tuple(getattr(row, field) for field in FIELDS))
        temporary.replace(csv_path)
    except (OSError, csv.Error) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"failed to export decision_support.csv: {exc}") from exc
    markdown_path = output_directory / "decision_support.md"
    lines = [
        "# 決策輔助摘要", "", "本文件僅供研究與人工確認，不構成投資建議；系統不會自動下單或操作帳戶。", "",
        "| 市場 | 狀態 | 選用模型 | 最新驗證集預測 | 建議觀察區間 | baseline | 成交率 | 平均等待（小時） |", "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        interval = "—" if row.observation_low is None else f"{row.observation_low:.8g}–{row.observation_high:.8g}"
        lines.append(f"| {row.market} | {row.status} | {row.selected_model or '—'} | {row.latest_prediction if row.latest_prediction is not None else '—'} | {interval} | {row.baseline_prediction if row.baseline_prediction is not None else '—'} | {row.fill_rate if row.fill_rate is not None else '—'} | {row.average_wait_hours if row.average_wait_hours is not None else '—'} |")
    lines.extend(["", "## 限制", ""])
    for row in rows:
        lines.append(f"- **{row.market}：** {row.limitation}；需人工確認：`{row.human_review_required}`；不自動下單：`{row.no_automatic_trading}`。")
    markdown_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return csv_path, markdown_path
