# GitHub Actions Automated Data Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect Bitfinex `fUSD`, `fBTC`, and `fETH` funding-book snapshots hourly on GitHub Actions and atomically append successful snapshots to daily, market-specific CSV files committed to the private repository.

**Architecture:** Add a focused daily CSV exporter behind the existing runner's `Exporter` callable, then select it from the existing CLI through `Settings.csv_directory`. A GitHub Actions workflow runs the CLI hourly, commits only `data/raw` changes with the repository-scoped `GITHUB_TOKEN`, preserves partial successes, and reports collection failures after attempting the data commit.

**Tech Stack:** Python 3.11+, standard-library `csv`/`datetime`/`pathlib`, pytest 8, GitHub Actions YAML, Bash/Git on `ubuntu-latest`.

## Global Constraints

- Markets are exactly `fUSD`, `fBTC`, and `fETH`.
- Schedule is hourly at minute 17 and also supports `workflow_dispatch`.
- Daily paths use UTC: `data/raw/YYYY/MM/DD/<market>.csv`.
- CSV columns remain exactly `run_id,market,rate,period,count,amount,side,fetched_at` in UTF-8 with one header.
- Updates are atomic and a repeated `run_id` for the same daily market file is a no-op.
- A failed market cannot erase prior CSV data; successful markets from a partial run must still be committed.
- SQLite remains local/ephemeral and is not committed by the workflow.
- Workflow authentication uses only the built-in `GITHUB_TOKEN` with `contents: write`; no Bitfinex key or personal access token.
- This feature does not train models, run backtests, use private account APIs, or place orders.

## File Structure

- Create `bitfinex_lending/daily_csv.py`: validate a homogeneous snapshot, derive its UTC daily path, deduplicate by `run_id`, and atomically rewrite the daily CSV with appended rows.
- Create `tests/test_daily_csv.py`: specify path selection, header/append behavior, deduplication, validation, and cleanup on write failure.
- Modify `bitfinex_lending/config.py`: make `data/raw` the collector's default CSV root.
- Modify `bitfinex_lending/__main__.py`: inject `append_daily_snapshot` into the existing collection runner.
- Modify `tests/test_main.py`: verify the CLI passes the daily exporter to the runner.
- Modify `.gitignore`: keep transient SQLite and temporary files ignored while allowing `data/raw/**/*.csv` to be tracked.
- Create `.github/workflows/collect-funding-books.yml`: schedule, run, commit/push, retry conflict once, and preserve a failing collection status.
- Create `tests/test_workflow.py`: guard the workflow's schedule, permissions, concurrency, collection, commit, and final failure propagation.
- Modify `README.md`: document GitHub setup, manual verification, UTC layout, free-minute expectation, and operational caveats.

---

### Task 1: Atomic Daily CSV Exporter

**Files:**
- Create: `bitfinex_lending/daily_csv.py`
- Create: `tests/test_daily_csv.py`

**Interfaces:**
- Consumes: `FundingBookRow` from `bitfinex_lending.models` and `FIELD_NAMES`, `CsvExportError` from `bitfinex_lending.csv_export`.
- Produces: `append_daily_snapshot(rows: Sequence[FundingBookRow], output_root: Path) -> Path` compatible with `runner.Exporter`.

- [ ] **Step 1: Write failing tests for UTC paths, appending, and one header**

Create `tests/test_daily_csv.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.csv_export import CsvExportError
from bitfinex_lending.daily_csv import append_daily_snapshot
from bitfinex_lending.models import FundingBookRow


def make_rows(
    run_id: str = "run-1",
    market: str = "fUSD",
    fetched_at: str = "2026-07-21T13:17:00+00:00",
) -> tuple[FundingBookRow, ...]:
    return (
        FundingBookRow(run_id, market, 0.0002, 2, 3, 10.5, "offer", fetched_at),
        FundingBookRow(run_id, market, 0.0003, 7, 1, -4.0, "demand", fetched_at),
    )


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def test_append_daily_snapshot_uses_utc_daily_market_path(tmp_path: Path) -> None:
    path = append_daily_snapshot(
        make_rows(fetched_at="2026-07-22T01:17:00+12:00"), tmp_path
    )

    assert path == tmp_path / "2026" / "07" / "21" / "fUSD.csv"
    assert read_csv(path)[0] == [
        "run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"
    ]
    assert len(read_csv(path)) == 3


def test_append_daily_snapshot_appends_without_repeating_header(tmp_path: Path) -> None:
    path = append_daily_snapshot(make_rows("run-1"), tmp_path)
    append_daily_snapshot(
        make_rows("run-2", fetched_at="2026-07-21T14:17:00+00:00"), tmp_path
    )

    content = read_csv(path)
    assert len(content) == 5
    assert sum(row and row[0] == "run_id" for row in content) == 1
    assert {row[0] for row in content[1:]} == {"run-1", "run-2"}
```

- [ ] **Step 2: Run the focused tests and verify the missing module failure**

Run: `python -m pytest tests/test_daily_csv.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'bitfinex_lending.daily_csv'`.

- [ ] **Step 3: Implement path derivation and atomic append**

Create `bitfinex_lending/daily_csv.py`:

```python
from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .csv_export import FIELD_NAMES, CsvExportError
from .models import FundingBookRow


def _validate_rows(rows: Sequence[FundingBookRow]) -> FundingBookRow:
    if not rows:
        raise ValueError("daily CSV export requires at least one row")
    first = rows[0]
    if any(row.run_id != first.run_id or row.market != first.market for row in rows):
        raise ValueError("daily CSV rows must share run_id and market")
    return first


def _utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("fetched_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _serialize(rows: Sequence[FundingBookRow]) -> list[tuple[object, ...]]:
    return [
        (
            row.run_id,
            row.market,
            row.rate,
            row.period,
            row.count,
            row.amount,
            row.side,
            row.fetched_at,
        )
        for row in rows
    ]


def append_daily_snapshot(
    rows: Sequence[FundingBookRow], output_root: Path
) -> Path:
    first = _validate_rows(rows)
    observed_at = _utc_date(first.fetched_at)
    target = Path(output_root) / observed_at.strftime("%Y/%m/%d") / f"{first.market}.csv"
    temporary = target.with_suffix(".csv.tmp")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing: list[list[str]] = []
        if target.exists():
            with target.open(encoding="utf-8", newline="") as stream:
                existing = list(csv.reader(stream))
            if any(row and row[0] == first.run_id for row in existing[1:]):
                return target

        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            if existing:
                writer.writerows(existing)
            else:
                writer.writerow(FIELD_NAMES)
            writer.writerows(_serialize(rows))
        temporary.replace(target)
    except (OSError, csv.Error) as error:
        temporary.unlink(missing_ok=True)
        raise CsvExportError(f"failed to append daily CSV: {error}") from error
    return target
```

- [ ] **Step 4: Run the focused tests and verify both pass**

Run: `python -m pytest tests/test_daily_csv.py -v`

Expected: `2 passed`.

- [ ] **Step 5: Add failing tests for retry deduplication and validation**

Append to `tests/test_daily_csv.py`:

```python
def test_append_daily_snapshot_deduplicates_same_run_id(tmp_path: Path) -> None:
    path = append_daily_snapshot(make_rows("same-run"), tmp_path)
    append_daily_snapshot(make_rows("same-run"), tmp_path)

    assert len(read_csv(path)) == 3


def test_append_daily_snapshot_rejects_empty_mixed_and_naive_rows(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one row"):
        append_daily_snapshot((), tmp_path)

    mixed = list(make_rows())
    mixed[1] = FundingBookRow(**{**mixed[1].__dict__, "market": "fBTC"})
    with pytest.raises(ValueError, match="share run_id and market"):
        append_daily_snapshot(tuple(mixed), tmp_path)

    with pytest.raises(ValueError, match="include a timezone"):
        append_daily_snapshot(make_rows(fetched_at="2026-07-21T13:17:00"), tmp_path)


def test_append_daily_snapshot_removes_temporary_file_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(CsvExportError, match="failed to append daily CSV"):
        append_daily_snapshot(make_rows(), tmp_path)
    assert list(tmp_path.rglob("*.tmp")) == []
```

- [ ] **Step 6: Run exporter tests and verify all edge cases pass**

Run: `python -m pytest tests/test_daily_csv.py -v`

Expected: `5 passed`.

- [ ] **Step 7: Commit the exporter**

```bash
git add bitfinex_lending/daily_csv.py tests/test_daily_csv.py
git commit -m "feat: append snapshots to daily market CSVs"
```

---

### Task 2: Select the Daily Exporter from the CLI

**Files:**
- Modify: `bitfinex_lending/config.py`
- Modify: `bitfinex_lending/__main__.py`
- Modify: `tests/test_main.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `append_daily_snapshot(rows, output_root) -> Path` from Task 1 and the existing `run_collection(...) -> RunSummary`.
- Produces: default `Settings.csv_directory == Path("data/raw")`; `main()` passes `append_daily_snapshot` as the runner exporter.

- [ ] **Step 1: Write a failing CLI wiring assertion**

In `tests/test_main.py`, add `from bitfinex_lending.daily_csv import append_daily_snapshot`, replace the `run_collection` monkeypatch in `test_main_initializes_storage_creates_directories_and_prints_summary` with a capturing fake, and assert the exporter:

```python
    captured: dict[str, object] = {}

    def fake_run_collection(*args: object, **kwargs: object) -> RunSummary:
        captured["exporter"] = args[3]
        return summary

    monkeypatch.setattr(cli, "run_collection", fake_run_collection)

    exit_code = cli.main(settings)

    assert captured["exporter"] is append_daily_snapshot
```

Retain all existing assertions in that test.

- [ ] **Step 2: Run the CLI test and verify it fails**

Run: `python -m pytest tests/test_main.py::test_main_initializes_storage_creates_directories_and_prints_summary -v`

Expected: FAIL because the captured exporter is still `export_snapshot`.

- [ ] **Step 3: Switch the CLI and default path**

In `bitfinex_lending/__main__.py`, replace:

```python
from .csv_export import export_snapshot
```

with:

```python
from .daily_csv import append_daily_snapshot
```

and pass `append_daily_snapshot` as the fourth argument to `run_collection`.

In `bitfinex_lending/config.py`, change:

```python
    csv_directory: Path = Path("data/raw")
```

In `.gitignore`, keep the existing `data/csv/*.csv` rule for legacy/generated feature files and add:

```gitignore
data/raw/**/*.tmp
```

Do not ignore `data/raw/**/*.csv`.

- [ ] **Step 4: Run CLI, runner, exporter, and config tests**

Run: `python -m pytest tests/test_main.py tests/test_runner.py tests/test_csv_export.py tests/test_daily_csv.py -v`

Expected: all selected tests pass.

- [ ] **Step 5: Run the complete offline suite**

Run: `python -m pytest -q`

Expected: all tests pass with the live integration test deselected.

- [ ] **Step 6: Commit CLI integration**

```bash
git add bitfinex_lending/config.py bitfinex_lending/__main__.py tests/test_main.py .gitignore
git commit -m "feat: use daily CSV output for collection"
```

---

### Task 3: GitHub Actions Collection Workflow

**Files:**
- Create: `.github/workflows/collect-funding-books.yml`
- Create: `tests/test_workflow.py`

**Interfaces:**
- Consumes: `python -m bitfinex_lending`, which returns nonzero for any failed market but writes successful market CSVs before returning.
- Produces: an hourly/manual GitHub Actions workflow that commits `data/raw`, retries a push conflict once, and finally propagates collection failure.

- [ ] **Step 1: Write a failing workflow contract test**

Create `tests/test_workflow.py`:

```python
from pathlib import Path


WORKFLOW = Path(".github/workflows/collect-funding-books.yml")


def test_collection_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "17 * * * *"' in text
    assert "workflow_dispatch:" in text
    assert "contents: write" in text
    assert "cancel-in-progress: false" in text
    assert "python-version: '3.11'" in text
    assert "python -m bitfinex_lending" in text
    assert "continue-on-error: true" in text
    assert "git add data/raw" in text
    assert "git diff --cached --quiet" in text
    assert "git pull --rebase" in text
    assert "git push" in text
    assert "steps.collect.outcome" in text
```

- [ ] **Step 2: Run the workflow test and verify the missing file failure**

Run: `python -m pytest tests/test_workflow.py -v`

Expected: FAIL with `FileNotFoundError` for `.github/workflows/collect-funding-books.yml`.

- [ ] **Step 3: Create the scheduled workflow**

Create `.github/workflows/collect-funding-books.yml`:

```yaml
name: Collect Bitfinex funding books

on:
  schedule:
    - cron: "17 * * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: bitfinex-funding-collection
  cancel-in-progress: false

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip

      - name: Install collector
        run: python -m pip install -e .

      - name: Collect funding books
        id: collect
        continue-on-error: true
        run: python -m bitfinex_lending

      - name: Commit collected CSV data
        id: commit
        shell: bash
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data/raw
          if git diff --cached --quiet; then
            echo "No new CSV data to commit"
            exit 0
          fi
          collected_at="$(date -u +'%Y-%m-%dT%H:%MZ')"
          git commit -m "data: collect funding books at ${collected_at} [skip ci]"
          if ! git push; then
            git pull --rebase origin "${GITHUB_REF_NAME}"
            git push
          fi

      - name: Propagate collection failure
        if: steps.collect.outcome != 'success'
        shell: bash
        run: |
          echo "Collection reported one or more failed markets" >&2
          exit 1
```

- [ ] **Step 4: Run the workflow contract test**

Run: `python -m pytest tests/test_workflow.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Verify YAML syntax with Ruby's built-in parser on the runner-compatible file**

Run: `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/collect-funding-books.yml'); puts 'valid yaml'"`

Expected: `valid yaml`. If Ruby is unavailable locally, record that and rely on the contract test plus GitHub's workflow parser during `workflow_dispatch`; do not add a project dependency solely for YAML parsing.

- [ ] **Step 6: Run the complete offline suite**

Run: `python -m pytest -q`

Expected: all tests pass with one integration test deselected.

- [ ] **Step 7: Commit the workflow**

```bash
git add .github/workflows/collect-funding-books.yml tests/test_workflow.py
git commit -m "ci: collect Bitfinex funding books hourly"
```

---

### Task 4: Operations Documentation and Local Verification

**Files:**
- Modify: `README.md`
- Modify: `progress.md`
- Modify: `todo.md`

**Interfaces:**
- Consumes: workflow and daily path delivered by Tasks 1-3.
- Produces: exact repository setup and verification instructions, plus updated project progress.

- [ ] **Step 1: Add GitHub Actions operating instructions to README**

Append this section to `README.md`:

```markdown
## GitHub Actions 每小時自動收集

Repository 使用 `.github/workflows/collect-funding-books.yml`，在每小時第 17 分鐘（UTC）抓取 `fUSD`、`fBTC`、`fETH`，也可從 GitHub 的 **Actions → Collect Bitfinex funding books → Run workflow** 手動執行。

資料依 UTC 日期追加到：

```text
data/raw/YYYY/MM/DD/fUSD.csv
data/raw/YYYY/MM/DD/fBTC.csv
data/raw/YYYY/MM/DD/fETH.csv
```

啟用步驟：

1. 將 repository 設為 private 並推送 default branch。
2. 到 **Settings → Actions → General → Workflow permissions**，允許 **Read and write permissions**。
3. 到 Actions 頁面手動執行一次 workflow。
4. 確認工作完成後出現 `data: collect funding books ... [skip ci]` commit。
5. 再執行一次，確認當日 CSV 追加資料且只有一列標頭。

workflow 使用 Bitfinex public endpoint，不需要 API key 或 GitHub secret。private repository 的 GitHub Free 帳戶目前包含每月 Actions 分鐘額度；此排程約執行 720 次/月，仍應每月從 **Settings → Billing and licensing** 檢查實際用量。

GitHub scheduled workflow 可能延遲，資料時間以 CSV 的 `fetched_at` 為準。SQLite 是 runner 內的暫存記錄，不會提交；可在分析環境由 repo 中的 CSV 重建資料庫。
```

- [ ] **Step 2: Record the delivered milestone**

At the top of `progress.md`, add a dated section stating that the hourly workflow, UTC daily CSV exporter, partial-success commit behavior, deduplication, and manual trigger are implemented. Include the final offline test count obtained in Task 3 rather than predicting a number.

In `todo.md`, add and check these concrete items under a new `2026-07-21 GitHub Actions 自動收集` section:

```markdown
- [x] 建立 UTC 每日、每市場 CSV 追加輸出
- [x] 建立同一 run ID 去重與原子檔案更新
- [x] 建立每小時第 17 分鐘 GitHub Actions 排程
- [x] 建立 workflow 手動執行入口
- [x] 建立成功資料自動 commit 與 push
- [x] 建立部分失敗仍保存成功市場資料的流程
- [ ] 在 GitHub private repository 啟用 workflow 寫入權限
- [ ] 從 GitHub Actions 手動執行並確認自動 commit
- [ ] 觀察至少一次 scheduled run
```

- [ ] **Step 3: Run final local verification**

Run:

```bash
python -m pytest -q
git diff --check
git status --short
```

Expected: all offline tests pass with the integration test deselected; `git diff --check` prints nothing; status lists only the intended README/progress/todo changes.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md progress.md todo.md
git commit -m "docs: explain automated GitHub collection"
```

---

### Task 5: GitHub Deployment Acceptance

**Files:**
- No repository file changes expected unless GitHub validation reveals a defect.

**Interfaces:**
- Consumes: pushed default branch containing Tasks 1-4.
- Produces: evidence that repository permissions, manual execution, automatic commit, append behavior, and scheduled execution work on GitHub.

- [ ] **Step 1: Push the implementation commits to the private GitHub repository**

Run: `git push origin master`

Expected: Git reports the new commits pushed to the repository's default branch. If the default branch is not `master`, push the current branch and set it as default before continuing.

- [ ] **Step 2: Enable the minimum workflow permission**

In GitHub, open **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**, and save. Do not create a PAT or Bitfinex secret.

- [ ] **Step 3: Run the workflow manually**

Open **Actions → Collect Bitfinex funding books → Run workflow**, select the default branch, and run it.

Expected: the collection and commit steps complete, and the default branch receives one `[skip ci]` data commit containing `data/raw/<UTC date>/fUSD.csv`, `fBTC.csv`, and `fETH.csv`. If a market is temporarily unavailable, successful market files are still committed and the final workflow status is failure.

- [ ] **Step 4: Run it a second time and inspect append semantics**

Trigger the workflow again after the first completes.

Expected: the same UTC daily files gain rows with a new `run_id`; each file still contains exactly one header and the earlier rows remain unchanged.

- [ ] **Step 5: Observe one scheduled run**

Wait for the next hour's minute 17 run and inspect its actual `fetched_at` values.

Expected: the scheduled job starts without local-machine involvement and commits another snapshot. A small scheduling delay is acceptable.

- [ ] **Step 6: Record remote acceptance results**

Update `progress.md` with the manual run URL or run ID, scheduled run URL or run ID, UTC paths created, and any measured GitHub Actions billable minutes. Check the remaining three GitHub Actions items in `todo.md`, then commit:

```bash
git add progress.md todo.md
git commit -m "docs: record GitHub collection acceptance"
git push origin master
```

Expected: the final documentation commit is visible on GitHub and the project has evidence for both manual and scheduled execution.
