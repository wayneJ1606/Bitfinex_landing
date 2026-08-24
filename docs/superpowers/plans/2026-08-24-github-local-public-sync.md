# GitHub Local Public Data Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate local public Bitfinex data from GitHub Actions data, safely publish the approved code and documents, and synchronize local public data to the default GitHub branch every Monday at 10:00 Asia/Taipei without exposing private account data.

**Architecture:** Keep GitHub Actions output at `data/raw/`, route the local public collector to `data/local_public/raw/` and `data/local_public/market/`, and keep private output under ignored `data/account/`. A preview-first Python sync command creates a temporary isolated clone, copies only approved public paths, validates a sanitized manifest, and pushes with bounded retries; a Windows scheduled task invokes it weekly with `StartWhenAvailable`.

**Tech Stack:** Python 3.11+, pathlib/csv/json/hashlib/subprocess/tempfile, pytest 8, PowerShell 5+, Windows Task Scheduler, Git.

## Global Constraints

- GitHub Actions continues to write only `data/raw/`; do not relocate its historical data in this plan.
- Local public output is limited to `data/local_public/raw/`, `data/local_public/market/`, and sanitized `data/local_public/metadata/`.
- Begin the one-time local history migration at UTC date `2026-08-16`.
- Never publish `.env`, credentials, `data/account/`, private metadata, private identifiers, raw private payloads, SQLite, logs, locks, or temporary files.
- Never use `git add .` or stage the whole `data/` directory.
- Target the GitHub default branch and preserve hourly collection when synchronization fails.
- Schedule synchronization every Monday at 10:00 Asia/Taipei with `StartWhenAvailable`, `IgnoreNew`, and bounded retries.
- Do not merge GitHub and local observations into one modeling dataset in this plan.
- Treat the design and this plan as temporary construction records; after verified completion, record durable facts in `progress.md` and `todo.md`, then delete both temporary files.

---

## File Responsibility Map

- `.gitignore`: permanent private/runtime exclusions and local archive exclusion.
- `bitfinex_lending/local_stable_collector.py`: local-only Settings factory and existing hourly collection entry point.
- `bitfinex_lending/public_data_separation.py`: copy, verify, manifest, and recoverable archival of pre-separation public files.
- `bitfinex_lending/public_git_sync.py`: allowlisted temporary-clone synchronization and sanitized status output.
- `scripts/install-minimal-local-collector.ps1`: existing local collector registration, unchanged command but verified against the new local roots.
- `scripts/install-public-github-sync.ps1`: preview-first weekly scheduled-task registration.
- `docs/PUBLIC_GITHUB_SYNC.md`: durable operator instructions retained after temporary documents are removed.
- `tests/test_repository_privacy_contract.py`: repository exclusion contract.
- `tests/test_public_data_separation.py`: migration and collision behavior.
- `tests/test_public_git_sync.py`: allowlist, privacy, no-op, retry, and local bare-remote integration tests.
- `tests/test_public_sync_scheduler_script.py`: weekly scheduler contract.
- `progress.md`, `todo.md`: durable completion record and remaining merge work.

---

### Task 1: Lock the repository privacy boundary

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `tests/test_repository_privacy_contract.py`

**Interfaces:**
- Produces: a permanent denylist used by every later staging and synchronization task.
- Consumes: no earlier task output.

- [ ] **Step 1: Write the failing privacy contract tests**

```python
from pathlib import Path


def test_private_and_runtime_paths_are_ignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    for rule in (
        "data/account/",
        "data/archive/",
        "data/metadata/account_collector_status.json",
        "data/metadata/private_collection_status.json",
        "data/metadata/collector_runs/**/private.csv",
        "data/metadata/public_git_sync_status.json",
        "data/local_public/**/*.tmp",
    ):
        assert rule in text


def test_env_example_names_readonly_variables_without_values() -> None:
    lines = Path(".env.example").read_text(encoding="utf-8").splitlines()
    assert lines == [
        "BITFINEX_READONLY_API_KEY=",
        "BITFINEX_READONLY_API_SECRET=",
    ]
```

- [ ] **Step 2: Run the tests and confirm the missing rules/file failure**

Run: `python -m pytest tests/test_repository_privacy_contract.py -q`

Expected: FAIL because `data/archive/`, the sync status rule, or `.env.example` is absent.

- [ ] **Step 3: Add the exact ignore rules and empty example variables**

Append to `.gitignore`:

```gitignore
# Local public-data synchronization runtime
data/archive/
data/metadata/public_git_sync_status.json
data/local_public/**/*.tmp
data/local_public/**/*.lock
```

Create `.env.example` with the two empty variable declarations from Step 1 and no sample secrets.

- [ ] **Step 4: Verify Git ignore behavior, including real private paths**

Run:

```powershell
python -m pytest tests/test_repository_privacy_contract.py -q
git check-ignore data/account/account_events.sqlite3 data/metadata/private_collection_status.json .env
```

Expected: tests PASS and all three paths are printed as ignored.

- [ ] **Step 5: Commit only the privacy contract**

```powershell
git add .gitignore .env.example tests/test_repository_privacy_contract.py
git diff --cached --check
git commit -m "chore: lock private data out of Git"
```

---

### Task 2: Route the local public collector to its own roots

**Files:**
- Modify: `bitfinex_lending/local_stable_collector.py`
- Modify: `tests/test_local_stable_collector.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Produces: `local_public_settings() -> Settings`.
- Preserves: `Settings().csv_directory == Path("data/raw")` for GitHub Actions and `python -m bitfinex_lending`.

- [ ] **Step 1: Write failing path-separation tests**

```python
from pathlib import Path

from bitfinex_lending.config import Settings
from bitfinex_lending.local_stable_collector import local_public_settings


def test_default_settings_remain_the_github_actions_roots() -> None:
    assert Settings().csv_directory == Path("data/raw")
    assert Settings().market_directory == Path("data/market")


def test_local_collector_uses_source_specific_public_roots() -> None:
    settings = local_public_settings()
    assert settings.csv_directory == Path("data/local_public/raw")
    assert settings.market_directory == Path("data/local_public/market")
    assert settings.metadata_directory == Path("data/metadata")
```

- [ ] **Step 2: Run focused tests and confirm import failure**

Run: `python -m pytest tests/test_local_stable_collector.py tests/test_main.py -q`

Expected: FAIL because `local_public_settings` does not exist.

- [ ] **Step 3: Add the local-only Settings factory and use it in the CLI**

```python
def local_public_settings() -> Settings:
    return Settings(
        csv_directory=Path("data/local_public/raw"),
        market_directory=Path("data/local_public/market"),
    )
```

In `local_stable_collector.main`, replace `settings = Settings()` with `settings = local_public_settings()`. Do not change `config.Settings` defaults or `bitfinex_lending.__main__`.

- [ ] **Step 4: Verify both entry points remain separated**

Run: `python -m pytest tests/test_local_stable_collector.py tests/test_main.py tests/test_workflow.py -q`

Expected: PASS, including the assertion that the GitHub workflow still contains `git add data/raw`.

- [ ] **Step 5: Commit the isolated routing change**

```powershell
git add bitfinex_lending/local_stable_collector.py tests/test_local_stable_collector.py tests/test_main.py
git diff --cached --check
git commit -m "feat: separate local public collection paths"
```

---

### Task 3: Stage and verify public history from 2026-08-16

**Files:**
- Create: `bitfinex_lending/public_data_separation.py`
- Create: `tests/test_public_data_separation.py`

**Interfaces:**
- Produces: `SeparationSummary`, `stage_public_history(...)`, and `archive_verified_sources(...)`.
- CLI: `python -m bitfinex_lending.public_data_separation --data-root data --start-date 2026-08-16 [--archive-verified]`.
- Writes: `data/local_public/metadata/separation_manifest.json` containing only relative paths, sizes, row counts, SHA-256 hashes, and timestamps.

- [ ] **Step 1: Write failing copy, idempotence, and collision tests**

```python
from datetime import date
from pathlib import Path

import pytest

from bitfinex_lending.public_data_separation import (
    SeparationError,
    stage_public_history,
)


def test_stages_only_public_files_on_or_after_start_date(tmp_path: Path) -> None:
    old = tmp_path / "data/raw/2026/08/15/fUST.csv"
    new = tmp_path / "data/raw/2026/08/16/fUST.csv"
    market = tmp_path / "data/market/ticker/2026/08/16/fUST.csv"
    for path in (old, new, market):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("header\nrow\n", encoding="utf-8")
    summary = stage_public_history(tmp_path / "data", date(2026, 8, 16))
    assert summary.file_count == 2
    assert not (tmp_path / "data/local_public/raw/2026/08/15/fUST.csv").exists()
    assert (tmp_path / "data/local_public/raw/2026/08/16/fUST.csv").exists()
    assert (tmp_path / "data/local_public/market/ticker/2026/08/16/fUST.csv").exists()


def test_rejects_a_different_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "data/raw/2026/08/16/fUST.csv"
    target = tmp_path / "data/local_public/raw/2026/08/16/fUST.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("source", encoding="utf-8")
    target.write_text("different", encoding="utf-8")
    with pytest.raises(SeparationError, match="collision"):
        stage_public_history(tmp_path / "data", date(2026, 8, 16))
```

Add one test that rerunning identical input produces zero changed files and one test that manifest JSON contains no absolute path or `account` key.

- [ ] **Step 2: Run tests and confirm the module is absent**

Run: `python -m pytest tests/test_public_data_separation.py -q`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement atomic copy and exact verification**

```python
@dataclass(frozen=True)
class SeparationSummary:
    file_count: int
    changed_count: int
    total_bytes: int
    total_rows: int
    manifest_path: Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
```

Select only `raw/YYYY/MM/DD/*.csv` dates on or after the given start date and every CSV below the four approved market dataset directories. Copy to a `.tmp` sibling, verify size and SHA-256, then use `Path.replace`. Reject symlinks, non-CSV files, path traversal, and differing existing destinations. Write the manifest atomically.

Add an argparse entry point that defaults to copy-and-verify only. `--archive-verified` must require the manifest created by the current data state and the explicit tracked-path guard; it may never silently archive tracked GitHub files.

- [ ] **Step 4: Implement recoverable archival with tracked-file protection**

`archive_verified_sources(data_root, manifest_path, archive_root, tracked_paths)` must move only source files whose current hash still equals the manifest, refuse every path present in `tracked_paths`, preserve relative paths under `data/archive/local-public-pre-separation-20260824/`, and never delete the archive.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_public_data_separation.py -q`

Expected: PASS for copy, idempotence, collision, privacy, and recoverable archive cases.

- [ ] **Step 6: Commit**

```powershell
git add bitfinex_lending/public_data_separation.py tests/test_public_data_separation.py
git diff --cached --check
git commit -m "feat: stage source-separated public history"
```

---

### Task 4: Build the allowlisted temporary-clone Git sync command

**Files:**
- Create: `bitfinex_lending/public_git_sync.py`
- Create: `tests/test_public_git_sync.py`

**Interfaces:**
- CLI: `python -m bitfinex_lending.public_git_sync [--project-root PATH] [--branch master] [--push]`.
- Produces: `SyncSummary(status, file_count, total_bytes, commit_sha, attempts)` and local-only `data/metadata/public_git_sync_status.json`.

- [ ] **Step 1: Write failing allowlist and privacy tests**

```python
from pathlib import Path

import pytest

from bitfinex_lending.public_git_sync import SyncError, collect_public_files


def test_collects_only_three_approved_public_subtrees(tmp_path: Path) -> None:
    approved = tmp_path / "data/local_public/raw/2026/08/16/fUST.csv"
    private = tmp_path / "data/account/funding_trades/2026/08/16.csv"
    for path in (approved, private):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    assert collect_public_files(tmp_path) == (approved,)


def test_rejects_private_field_names_in_public_csv(tmp_path: Path) -> None:
    path = tmp_path / "data/local_public/raw/2026/08/16/fUST.csv"
    path.parent.mkdir(parents=True)
    path.write_text("offer_id,raw_payload\n1,secret\n", encoding="utf-8")
    with pytest.raises(SyncError, match="forbidden public fields"):
        collect_public_files(tmp_path)
```

Also test rejection of `.env`, symlinks, `..`, absolute manifest paths, SQLite extensions, and files outside `raw`, `market`, or sanitized `metadata`.

- [ ] **Step 2: Write a local bare-remote integration test**

Create a temporary bare Git remote and seed its `master` branch. Run `synchronize(..., push=True)` against it and assert the pushed commit contains only `data/local_public/**`; rerun without changes and assert `status == "no_changes"`. Add a fake first push failure and assert attempts stop at three.

- [ ] **Step 3: Run tests and confirm import failure**

Run: `python -m pytest tests/test_public_git_sync.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 4: Implement the sync boundary**

```python
APPROVED_PREFIXES = (
    Path("data/local_public/raw"),
    Path("data/local_public/market"),
    Path("data/local_public/metadata"),
)
FORBIDDEN_FIELDS = {"api_key", "api_secret", "offer_id", "event_id", "raw_payload"}


@dataclass(frozen=True)
class SyncSummary:
    status: str
    file_count: int
    total_bytes: int
    commit_sha: str | None
    attempts: int
```

Use `tempfile.TemporaryDirectory`, obtain the existing `origin` URL with `git remote get-url origin`, clone the requested branch, copy validated files, generate `sync_manifest.json`, and run Git commands as argument lists with `shell=False`. Stage only the three exact approved prefixes. If `git diff --cached --quiet` succeeds, return `no_changes`. Otherwise commit, execute `git pull --rebase origin <branch>`, and push with at most three attempts.

- [ ] **Step 5: Make preview the default**

Without `--push`, validate and print the intended branch, file count, byte count, source roots, and `push=false`; do not clone, commit, or contact the network. With `--push`, write a sanitized success/failure status locally using an atomic replace.

- [ ] **Step 6: Run integration and privacy tests**

Run: `python -m pytest tests/test_public_git_sync.py tests/test_repository_privacy_contract.py -q`

Expected: PASS with the temporary local bare remote and no network dependency.

- [ ] **Step 7: Commit**

```powershell
git add bitfinex_lending/public_git_sync.py tests/test_public_git_sync.py
git diff --cached --check
git commit -m "feat: add allowlisted public Git sync"
```

---

### Task 5: Add the Monday 10:00 preview-first scheduler

**Files:**
- Create: `scripts/install-public-github-sync.ps1`
- Create: `tests/test_public_sync_scheduler_script.py`
- Create: `docs/PUBLIC_GITHUB_SYNC.md`

**Interfaces:**
- Scheduled task: `BitfinexPublicGitHubSync`.
- Command: `pythonw.exe -m bitfinex_lending.public_git_sync --project-root <root> --branch master --push`.

- [ ] **Step 1: Write failing scheduler contract tests**

```python
from pathlib import Path


SCRIPT = Path("scripts/install-public-github-sync.ps1")


def test_public_sync_schedule_is_weekly_preview_first_and_hidden() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "BitfinexPublicGitHubSync",
        "-Weekly",
        "-DaysOfWeek Monday",
        '10:00',
        "StartWhenAvailable",
        "IgnoreNew",
        "pythonw.exe",
        "--push",
        "registration=not_requested",
        "-Enable",
    ):
        assert token in text
```

Add assertions that the script contains no API variable names, account paths, `git add .`, or embedded GitHub token.

- [ ] **Step 2: Run the test and confirm the script is absent**

Run: `python -m pytest tests/test_public_sync_scheduler_script.py -q`

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Implement preview-first registration**

Follow the existing collector installer pattern: resolve `ProjectRoot` and Python, prefer `pythonw.exe`, emit JSON containing task name, command, branch, Monday, 10:00, `StartWhenAvailable`, `IgnoreNew`, interactive limited principal, and a 30-minute execution limit. Register and enable only when `-Enable` is present.

- [ ] **Step 4: Write durable operator documentation**

Document preview, one-time manual preview/push, scheduler preview/enable, status path, source directory meanings, retry behavior, and these permanent warnings: private data never syncs; code/doc changes are not part of the weekly data job; synchronization failure does not stop collection.

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest tests/test_public_sync_scheduler_script.py tests/test_private_scheduler_script.py -q`

Expected: PASS.

```powershell
git add scripts/install-public-github-sync.ps1 tests/test_public_sync_scheduler_script.py docs/PUBLIC_GITHUB_SYNC.md
git diff --cached --check
git commit -m "feat: schedule weekly public GitHub sync"
```

---

### Task 6: Publish the approved collector, Dashboard, and linked-document source

**Files:**
- Public collector review set: `.github/workflows/collect-funding-books.yml`, `bitfinex_lending/__main__.py`, `bitfinex_lending/client.py`, `bitfinex_lending/config.py`, `bitfinex_lending/models.py`, `bitfinex_lending/parser.py`, `bitfinex_lending/runner.py`, `bitfinex_lending/storage.py`, `bitfinex_lending/csv_export.py`, `bitfinex_lending/daily_csv.py`, `bitfinex_lending/partitioned_csv.py`, `bitfinex_lending/market_collector.py`, `bitfinex_lending/local_stable_collector.py`, `bitfinex_lending/collector_run_history.py`, `scripts/install-minimal-local-collector.ps1`, `docs/LOCAL_STABLE_COLLECTOR.md`, `tests/test_client.py`, `tests/test_parser.py`, `tests/test_runner.py`, `tests/test_storage.py`, `tests/test_csv_export.py`, `tests/test_daily_csv.py`, `tests/test_market_collector.py`, `tests/test_local_stable_collector.py`, `tests/test_collector_run_history.py`, `tests/test_main.py`, and `tests/test_workflow.py`.
- Private collector review set: `bitfinex_lending/private_client.py`, `bitfinex_lending/account_storage.py`, `bitfinex_lending/private_account_collector.py`, `scripts/install-private-account-collector.ps1`, `docs/PRIVATE_ACCOUNT_COLLECTOR.md`, `docs/PRIVATE_ACCOUNT_COLLECTION_STATUS.md`, `tests/test_private_client.py`, `tests/test_account_storage.py`, `tests/test_private_account_collector.py`, `tests/test_private_account_cli.py`, and `tests/test_private_scheduler_script.py`.
- Document review set: `progress.md`, `todo.md`, `PROJECT_DIRECTION.md`, `PROJECT_STATUS_SUMMARY.md`, `strategy_optimization_goals.md`, `docs/P0_EXECUTION_CHECKLIST.md`, `docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md`, and `docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md`.
- Dashboard review set: `bitfinex_lending/p0_experimental.py`, `bitfinex_lending/p0_experimental_dashboard.py`, `bitfinex_lending/p0_experimental_payload.py`, `bitfinex_lending/p0_experimental_pipeline.py`, `bitfinex_lending/p0_public_fill_proxy.py`, `tests/test_p0_experimental.py`, `tests/test_p0_experimental_dashboard.py`, `tests/test_p0_experimental_payload.py`, `tests/test_p0_experimental_pipeline.py`, `tests/test_p0_public_fill_proxy.py`, `data/modeling/p0_experimental/latest/dashboard.html`, and `data/modeling/p0_experimental/latest/dashboard_data.json`.

**Interfaces:**
- Produces: reviewable source and working relative Markdown links on the default GitHub branch.
- Excludes: every runtime account file and unapproved generated modeling artifact.

- [ ] **Step 1: Create an isolated integration worktree from the freshly fetched default branch**

Run the `using-git-worktrees` workflow. Fetch `origin`, create `codex/github-public-sync` from `origin/master`, and do not merge the dirty development worktree wholesale.

Expected: the integration worktree starts clean and tracks the current remote default branch.

- [ ] **Step 2: Bring in reviewed commits and source batches**

Cherry-pick only previously verified collector prerequisites and commits `14c5afa`, `f9f66e9`, and `302bce6` when they are not already ancestors. For uncommitted collector/source files, copy and stage exact filenames in separate public-collector, private-collector, and document batches. Inspect `git diff --cached --name-status` before every commit.

- [ ] **Step 3: Verify linked Markdown files exist**

Run:

```powershell
@'
import re
from pathlib import Path
for source in (Path("progress.md"), Path("todo.md")):
    for target in re.findall(r"\]\(([^)#]+\.md)\)", source.read_text(encoding="utf-8")):
        path = source.parent / target
        if not path.exists():
            raise SystemExit(f"missing link: {source} -> {target}")
print("linked_markdown=ok")
'@ | python -
```

Expected: `linked_markdown=ok`.

- [ ] **Step 4: Inspect privacy and staged scope before each source push**

Run:

```powershell
git diff --cached --check
git diff --cached --name-status
git status --short --ignored data/account .env data/metadata/private_collection_status.json
```

Expected: private paths are ignored and absent from the staged list. Review staged text for real credentials and private identifiers; fake test values are allowed only inside tests.

For the two generated Dashboard files, additionally run:

```powershell
rg -n "api_key|api_secret|offer_id|event_id|raw_payload|/auth/w/" data/modeling/p0_experimental/latest/dashboard.html data/modeling/p0_experimental/latest/dashboard_data.json
```

Expected: no matches. If any match exists, do not publish either generated file until the payload exporter removes it.

- [ ] **Step 5: Run the complete offline suite**

Run: `python -m pytest -q`

Expected: all offline tests pass and only the configured live test is deselected.

- [ ] **Step 6: Commit and push the reviewed source batches**

Use specific messages such as `feat: publish local public collector`, `feat: publish readonly private collector`, and `docs: publish current project records`. Do not use `git add .`. Rebase the clean integration branch on the current `origin/master`, rerun the full tests and privacy checks, then push without force. If GitHub Actions advances the branch, repeat fetch/rebase with bounded attempts.

---

### Task 7: Perform the first verified public-data synchronization

**Files:**
- Create through the migration command: `data/local_public/raw/**`, `data/local_public/market/**`, and `data/local_public/metadata/separation_manifest.json`.
- Preserve locally: `data/archive/local-public-pre-separation-20260824/**`.

**Interfaces:**
- Consumes: Task 3 migration and Task 4 sync CLI.
- Produces: the first public-data commit on `origin/master` and a local sanitized status.

- [ ] **Step 1: Stop only the local public collector task for the migration window**

Confirm the exact task name is `BitfinexLocalStableCollector`, disable it temporarily, and leave `BitfinexPrivateAccountCollector` running. Record the start time. Do not stop either collector process by killing Python globally.

- [ ] **Step 2: Stage the historical public data**

Run the separation CLI with project data root and start date `2026-08-16`. Before archival, run `git ls-files data/raw/2026/08/16 data/raw/2026/08/17 data/raw/2026/08/18 data/raw/2026/08/19 data/raw/2026/08/20 data/raw/2026/08/21 data/raw/2026/08/22 data/raw/2026/08/23 data/raw/2026/08/24` and pass every tracked result to the archival guard.

Expected: copies and manifest verify; tracked GitHub files are never moved.

- [ ] **Step 3: Archive only verified untracked source duplicates**

Resolve every source and archive destination under the project `data` root, call `archive_verified_sources`, then rerun manifest verification. Keep the archive local and ignored. If any hash changed after staging, stop and re-run collection separation rather than moving it.

- [ ] **Step 4: Re-enable and test the local collector**

Enable `BitfinexLocalStableCollector`, trigger one run, and confirm the new run updates `data/local_public/raw/` and `data/local_public/market/` while leaving `data/raw/` unchanged.

- [ ] **Step 5: Preview the GitHub data synchronization**

Run: `python -m bitfinex_lending.public_git_sync --project-root . --branch master`

Expected: `push=false`, only approved public roots, a nonzero file count, and no network mutation.

- [ ] **Step 6: Obtain explicit user approval, then push the first data batch**

Run only after approval: `python -m bitfinex_lending.public_git_sync --project-root . --branch master --push`

Expected: `status=success` or `status=no_changes`; never `partial`. Inspect the resulting GitHub commit tree and confirm it contains only `data/local_public/**`.

---

### Task 8: Register and verify the weekly sync

**Files:**
- Uses: `scripts/install-public-github-sync.ps1`.

**Interfaces:**
- Produces: enabled `BitfinexPublicGitHubSync` Windows task.

- [ ] **Step 1: Preview the scheduler**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-public-github-sync.ps1 -ProjectRoot .
```

Expected: Monday 10:00, `registration=not_requested`, `StartWhenAvailable=true`, `IgnoreNew`, and `pythonw.exe` when available.

- [ ] **Step 2: Obtain explicit user approval and enable the scheduler**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-public-github-sync.ps1 -ProjectRoot . -Enable
```

Expected: `registration=enabled` for `BitfinexPublicGitHubSync`.

- [ ] **Step 3: Trigger one no-change verification run**

Expected: the task finishes successfully, does not create an empty commit, and writes a local sanitized `status=no_changes` without opening a console window.

- [ ] **Step 4: Verify collection independence**

Confirm the public and private collectors remain enabled and continue updating their respective local paths even if a sync run is deliberately made to fail against an invalid test remote.

---

### Task 9: Record durable results and remove temporary construction files

**Files:**
- Modify: `progress.md`
- Modify: `todo.md`
- Delete: `docs/superpowers/specs/2026-08-24-github-local-public-sync-design.md`
- Delete: `docs/superpowers/plans/2026-08-24-github-local-public-sync.md`

**Interfaces:**
- Produces: the final long-lived handoff with no redundant temporary sync documents.

- [ ] **Step 1: Capture verified facts**

Record the actual source date range, file/row/byte counts, hashes or manifest path, GitHub commit IDs, scheduler state, full test count, privacy scan result, retained operator document, and the still-deferred two-source merge work.

- [ ] **Step 2: Update project records**

In `progress.md`, add one dated completion entry. In `todo.md`, mark path separation, first public sync, collector source publication, linked-document publication, and weekly schedule complete; leave GitHub/local merge and conflict rules unchecked.

- [ ] **Step 3: Confirm the durable handoff is sufficient**

Verify `docs/PUBLIC_GITHUB_SYNC.md`, `progress.md`, and `todo.md` contain every operational fact needed to inspect status and continue work. Check their relative links.

- [ ] **Step 4: Delete both temporary construction documents**

Use `apply_patch` to delete the confirmed design and this implementation plan only after Steps 1–3 pass. Do not delete the durable operator document.

- [ ] **Step 5: Run final verification**

Run:

```powershell
python -m pytest -q
git diff --check
git status --short --ignored data/account .env
```

Expected: all offline tests pass; private paths remain ignored; the final staged set contains only verified code, public data, durable documents, and deletion of the two temporary construction files.

- [ ] **Step 6: Commit and push the final records**

```powershell
git add progress.md todo.md docs/PUBLIC_GITHUB_SYNC.md docs/superpowers/specs/2026-08-24-github-local-public-sync-design.md docs/superpowers/plans/2026-08-24-github-local-public-sync.md
git diff --cached --check
git commit -m "docs: record public GitHub sync completion"
git pull --rebase origin master
git push origin master
```

Expected: the default branch contains durable completion records and operator instructions, while the temporary design and plan are absent from the final working tree.
