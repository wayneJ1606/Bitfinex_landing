from pathlib import Path

from bitfinex_lending.decision_support import DecisionSupportRow
from bitfinex_lending.decision_support_csv import export_decision_support


def _row(market: str) -> DecisionSupportRow:
    return DecisionSupportRow(
        market, "trained", "tree", 0.2, 0.1, 0.3, 0.15, 0.2, 2.0,
        "ok", True, True,
    )


def test_export_decision_support_writes_csv_and_markdown(tmp_path: Path) -> None:
    rows = (_row("fUSD"),)
    csv_path, markdown_path = export_decision_support(rows, tmp_path)
    assert csv_path.exists() and markdown_path.exists()
    assert "human_review_required" in csv_path.read_text(encoding="utf-8").splitlines()[0]
    content = markdown_path.read_text(encoding="utf-8")
    assert "人工確認" in content
    assert "不自動下單" in content


def test_markdown_keeps_multiple_markets_inside_one_table(tmp_path: Path) -> None:
    _, markdown_path = export_decision_support(
        (_row("fBTC"), _row("fUSD")), tmp_path
    )
    content = markdown_path.read_text(encoding="utf-8")
    table, limitations = content.split("\n\n## 限制", maxsplit=1)

    assert "| fBTC |" in table
    assert "| fUSD |" in table
    assert "最新驗證集預測" in table
    assert "fBTC" in limitations
    assert "fUSD" in limitations
