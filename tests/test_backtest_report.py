from pathlib import Path

from bitfinex_lending.backtest_report import export_backtest_report
from bitfinex_lending.backtesting import BacktestResult


def test_export_backtest_report_contains_ranking_and_disclaimer(tmp_path: Path) -> None:
    rows = (BacktestResult("fUSD", "tree", 10, 8, 4, 0.5, 0.4, 2.0, 2, 0.01, 0.02),)
    path = export_backtest_report(rows, tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "fUSD" in content
    assert "tree" in content
    assert "實際收益" in content
