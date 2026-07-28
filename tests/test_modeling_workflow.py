from pathlib import Path


def test_modeling_workflow_contract() -> None:
    workflow = Path(
        ".github/workflows/build-modeling-dataset.yml"
    ).read_text(encoding="utf-8")
    collector = Path(
        ".github/workflows/collect-funding-books.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "37 18 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: write" in workflow
    assert "group: bitfinex-repository-writer" in workflow
    assert "group: bitfinex-repository-writer" in collector
    assert "cancel-in-progress: false" in workflow
    assert "uses: actions/checkout@v6" in workflow
    assert "uses: actions/setup-python@v6" in workflow
    assert "python-version: '3.11'" in workflow
    assert 'pip install -e ".[test,modeling]"' in workflow
    assert workflow.index("python -m pytest") < workflow.index(
        "python -m bitfinex_lending.modeling"
    )
    assert "git add data/modeling" in workflow
    assert "git pull --rebase" in workflow
    assert "git push" in workflow
    assert "--force" not in workflow
    assert "continue-on-error" not in workflow
