from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from .models import ModelPrediction


def _scale(value: float, low: float, high: float, size: float, margin: float) -> float:
    if high == low:
        return size / 2
    return margin + (value - low) / (high - low) * (size - 2 * margin)


def export_prediction_charts(
    predictions: Iterable[ModelPrediction], output_directory: Path
) -> tuple[Path, ...]:
    grouped: dict[str, list[ModelPrediction]] = defaultdict(list)
    for row in predictions:
        grouped[row.market].append(row)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    width, height, margin = 1000, 500, 50
    for market in sorted(grouped):
        rows = sorted(grouped[market], key=lambda row: row.feature_time)
        timestamps = sorted({row.feature_time for row in rows})
        timestamp_index = {value: index for index, value in enumerate(timestamps)}
        actual_by_time: dict[str, float] = {}
        for row in rows:
            actual_by_time.setdefault(row.feature_time, row.actual_next_rate)
        values = [row.actual_next_rate for row in rows] + [row.predicted_rate for row in rows]
        low, high = min(values), max(values)
        models = sorted({row.model_name for row in rows})
        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]
        fragments = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
        fragments.append(f'<title>{escape(market)} actual and predicted rates</title>')
        fragments.append(f'<rect width="100%" height="100%" fill="white"/>')
        def points(model_rows: list[ModelPrediction]) -> str:
            return " ".join(
                f"{_scale(timestamp_index[row.feature_time], 0, max(1, len(timestamps)-1), width, margin):.2f},{height - _scale(row.predicted_rate, low, high, height, margin):.2f}"
                for row in model_rows
            )
        actual_timestamps = timestamps[:: max(1, len(timestamps) // 200)]
        actual_points = " ".join(
            f"{_scale(timestamp_index[value], 0, max(1, len(timestamps)-1), width, margin):.2f},{height - _scale(actual_by_time[value], low, high, height, margin):.2f}"
            for value in actual_timestamps
        )
        fragments.append(f'<polyline fill="none" stroke="#111" stroke-width="2" points="{actual_points}"/>')
        for index, model in enumerate(models):
            model_rows = [row for row in rows if row.model_name == model]
            fragments.append(f'<polyline fill="none" stroke="{colors[index % len(colors)]}" stroke-width="1.5" points="{points(model_rows)}"/>')
            fragments.append(f'<text x="{margin + index * 160}" y="25" fill="{colors[index % len(colors)]}">{escape(model)}</text>')
        fragments.append(f'<text x="{margin}" y="{height - 10}" fill="#111">actual</text></svg>')
        path = output_directory / f"prediction_{market}.svg"
        path.write_text("".join(fragments), encoding="utf-8", newline="\n")
        paths.append(path)
    return tuple(paths)
