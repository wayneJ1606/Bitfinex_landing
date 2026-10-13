from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .backtesting import BacktestResult


BACKTEST_FIELDS = (
    "market", "model_name", "observations", "signals", "fills", "fill_rate",
    "capital_utilization", "average_wait_hours", "max_consecutive_misses",
    "total_simulated_return", "simulated_annualized_return",
)


def export_backtest_results(results: Iterable[BacktestResult], output_directory: Path) -> Path:
    output_directory = Path(output_directory)
    target = output_directory / "backtest_results.csv"
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(BACKTEST_FIELDS)
            for result in sorted(results, key=lambda item: (item.market, item.model_name)):
                writer.writerow(tuple(getattr(result, field) for field in BACKTEST_FIELDS))
        temporary.replace(target)
    except (OSError, csv.Error) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"failed to export backtest_results.csv: {exc}") from exc
    return target
