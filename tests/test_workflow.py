from pathlib import Path


WORKFLOW = Path(".github/workflows/collect-funding-books.yml")


def test_collection_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "17 * * * *"' in text
    assert "workflow_dispatch:" in text
    assert "contents: write" in text
    assert "cancel-in-progress: false" in text
    assert "uses: actions/checkout@v6" in text
    assert "uses: actions/setup-python@v6" in text
    assert "python-version: '3.11'" in text
    assert "python -m bitfinex_lending" in text
    assert "continue-on-error: true" in text
    assert "git add data/raw" in text
    assert "git diff --cached --quiet" in text
    assert "git pull --rebase" in text
    assert "git push" in text
    assert "steps.collect.outcome" in text
