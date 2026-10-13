from pathlib import Path

from bitfinex_lending.backtesting import BacktestResult
from bitfinex_lending.backtesting_csv import export_backtest_results


def test_export_backtest_results_writes_utf8_csv(tmp_path: Path) -> None:
    result = (BacktestResult("fUSD", "tree", 2, 1, 1, 0.5, 0.1, 3.0, 2, 0.01, 0.02),)
    path = export_backtest_results(result, tmp_path)
    assert path.name == "backtest_results.csv"
    assert "simulated_annualized_return" in path.read_text(encoding="utf-8").splitlines()[0]
    assert "fUSD,tree" in path.read_text(encoding="utf-8")
