# Local Hourly Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Synchronize GitHub data locally and install a recoverable Windows collector that runs hourly at minute 47, pushes only collected raw data, and reports when 168 eligible feature rows are available.

**Architecture:** Put testable readiness and Git orchestration logic in focused Python modules. Keep Windows PowerShell scripts thin: bootstrap a dedicated clone and virtual environment, then register or remove one scheduled task. The developer checkout receives a one-time scoped data update, while scheduled collection always runs in the clean dedicated clone.

**Tech Stack:** Python 3.11, pytest, Git CLI, Windows Task Scheduler PowerShell cmdlets, existing `bitfinex_lending` collector.

## Global Constraints

- GitHub Actions continues at minute 17; the local task runs at minute 47 in `Asia/Taipei`.
- Never overwrite unrelated local commits, files, or uncommitted changes.
- Stage and commit only `data/raw`; never commit SQLite, logs, credentials, or developer changes.
- Preserve a successful local data commit when fetch, rebase, authentication, or push fails.
- Do not recollect while an earlier local data commit remains unsynchronized.
- Retry one rejected push after exactly one fetch/rebase attempt.
- Never synthesize snapshots for missed triggers and never access private Bitfinex APIs.
- Reaching 168 eligible rows is a technical training threshold, not proof of a reliable model.

## File Structure

- Create `bitfinex_lending/readiness.py`: count distinct raw snapshots and calculate eligible rows, remaining rows, and time estimate.
- Create `bitfinex_lending/local_collector.py`: lock, Git command boundary, pending-commit recovery, one collection, scoped commit/push, and sanitized operational logging.
- Create `scripts/install-local-collector.ps1`: clone/bootstrap a dedicated collector and register the minute-47 task.
- Create `scripts/remove-local-collector.ps1`: unregister only the named scheduled task.
- Create `tests/test_readiness.py`: readiness calculations and raw CSV counting.
- Create `tests/test_local_collector.py`: orchestration behavior using temporary local Git repositories and injected collector commands.
- Create `tests/test_local_collector_scripts.py`: static and dry-run checks for Windows task configuration.
- Modify `README.md`: installation, manual run, status, recovery, and removal instructions.
- Modify `progress.md` and `todo.md`: record delivery and remaining live acceptance work.

---

### Task 1: Scoped GitHub Data Synchronization

**Files:**
- Update from remote: `data/raw/**`
- Update from remote: `data/modeling/**`

**Interfaces:**
- Consumes: `origin/master:data/raw` and `origin/master:data/modeling`.
- Produces: a local data-only commit whose trees match `origin/master` at the fetched commit.

- [ ] **Step 1: Fetch and verify overwrite safety**

Run:

```powershell
git fetch --prune origin
git status --short -- data/raw data/modeling
git diff --quiet -- data/raw data/modeling
git diff --cached --quiet -- data/raw data/modeling
```

Expected: fetch exits 0 and both data-specific diff checks exit 0. If either diff check is nonzero, stop and report the paths rather than overwriting them.

- [ ] **Step 2: Update only the two data trees**

Run:

```powershell
git restore --source origin/master --worktree -- data/raw data/modeling
git diff --check -- data/raw data/modeling
git diff --stat -- data/raw data/modeling
```

Expected: only remote data changes appear; unrelated working-tree files are unchanged.

- [ ] **Step 3: Verify the synchronized snapshot counts**

Run a read-only CSV count grouped by `market` and distinct `run_id`; expected values must equal the current `origin/master` counts rather than a hard-coded historical number.

- [ ] **Step 4: Commit only synchronized data**

```powershell
git add data/raw data/modeling
git diff --cached --check
git commit -m "data: synchronize latest GitHub snapshots locally"
```

Expected: the commit contains only `data/raw/**` and `data/modeling/**`.

### Task 2: Feature Readiness Calculator

**Files:**
- Create: `bitfinex_lending/readiness.py`
- Create: `tests/test_readiness.py`

**Interfaces:**
- Produces: `ReadinessStatus(market, snapshots, eligible_rows, required_rows, remaining_snapshots, ideal_hours, expected_hours)`.
- Produces: `calculate_readiness(snapshot_count: int, required_rows: int = 168, combined_runs_per_day: float = 48.0, availability: float = 0.8) -> tuple[int, int, float, float]`.
- Produces: `read_raw_snapshot_counts(raw_directory: Path) -> dict[str, int]` counting unique `(market, run_id, fetched_at)` snapshots.

- [ ] **Step 1: Write failing boundary tests**

```python
import pytest
from bitfinex_lending.readiness import calculate_readiness

@pytest.mark.parametrize(
    ("snapshots", "eligible", "remaining"),
    [(0, 0, 170), (124, 122, 46), (169, 167, 1), (170, 168, 0)],
)
def test_calculate_readiness_boundaries(snapshots, eligible, remaining):
    result = calculate_readiness(snapshots)
    assert result[:2] == (eligible, remaining)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_readiness.py -q`

Expected: FAIL because `bitfinex_lending.readiness` does not exist.

- [ ] **Step 3: Implement minimal readiness arithmetic**

Implement eligibility as `max(snapshot_count - 2, 0)`, remaining snapshots as `max(required_rows - eligible, 0)`, ideal hours from 48 observations/day, and expected hours using 80% availability. Reject negative counts, nonpositive rates, and availability outside `(0, 1]`.

- [ ] **Step 4: Add failing raw CSV tests**

Create temporary UTC daily files with repeated book rows, duplicated rows, and two markets. Assert the reader counts unique snapshot keys rather than book depth rows and rejects missing required columns.

- [ ] **Step 5: Verify RED, implement strict CSV counting, then verify GREEN**

Run: `python -m pytest tests/test_readiness.py -q`

Expected after implementation: all readiness tests pass.

- [ ] **Step 6: Commit**

```powershell
git add bitfinex_lending/readiness.py tests/test_readiness.py
git commit -m "feat: calculate feature readiness from raw snapshots"
```

### Task 3: Recoverable Local Collector Orchestration

**Files:**
- Create: `bitfinex_lending/local_collector.py`
- Create: `tests/test_local_collector.py`

**Interfaces:**
- Produces: `CommandResult(returncode: int, stdout: str, stderr: str)`.
- Produces: `run_local_collection(repo: Path, log_directory: Path, collector_command: Sequence[str], remote_url: str, command_runner: CommandRunner) -> int`.
- Produces CLI: `python -m bitfinex_lending.local_collector --repo PATH --log-directory PATH --remote-url URL [--dry-run]`.

- [ ] **Step 1: Write failing tests for preflight and scoped staging**

Tests create a bare remote plus a clean temporary clone. Inject a collector command that appends one valid raw CSV snapshot. Assert the workflow validates `master` and `origin`, invokes `git add -- data/raw`, never stages another modified file, creates one `[skip ci]` commit, and pushes it.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_local_collector.py -q`

Expected: FAIL because the orchestration module does not exist.

- [ ] **Step 3: Implement command boundary, preflight, collect, commit, and push**

Use `subprocess.run(..., cwd=repo, capture_output=True, text=True, timeout=...)` without `shell=True`. Validate the resolved repository path, current branch `master`, and exact normalized `origin` URL. Refuse unrelated changes before collection. Stage only `data/raw`; use `git diff --cached --quiet` to skip empty commits.

- [ ] **Step 4: Add failing pending-commit and push-retry tests**

Cover these sequences with real temporary repositories and a deterministic failing command runner where necessary:

- local commit ahead of `origin/master` pushes before collection;
- failed pending push returns nonzero without calling the collector;
- first new push rejection triggers one `fetch origin`, one `rebase origin/master`, and one retry;
- second push failure leaves the local commit intact;
- rebase conflict stops without deleting raw data.

- [ ] **Step 5: Verify RED, implement bounded recovery, then verify GREEN**

Run: `python -m pytest tests/test_local_collector.py -q`

Expected after implementation: all orchestration tests pass.

- [ ] **Step 6: Add failing lock and logging tests**

Assert a held lock makes a second invocation exit without collection. Assert logs include scheduled/actual time, collector result, run ID when present, commit SHA, and push state while redacting URL user-info and strings matching `token`, `password`, or `authorization` values.

- [ ] **Step 7: Verify RED, implement OS-released file locking and sanitized rotating logs, then verify GREEN**

Use an opened lock file with `msvcrt.locking` on Windows and retain seven daily files covering at least 30 days through weekly rotation. Ensure exceptions pass through one sanitizer before logging.

- [ ] **Step 8: Add and test dry-run behavior**

`--dry-run` must validate repo/remote, report pending state and readiness, but must not fetch, collect, commit, rebase, or push.

Run: `python -m pytest tests/test_local_collector.py -q`

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add bitfinex_lending/local_collector.py tests/test_local_collector.py
git commit -m "feat: add recoverable local collection workflow"
```

### Task 4: Windows Task Installation and Removal

**Files:**
- Create: `scripts/install-local-collector.ps1`
- Create: `scripts/remove-local-collector.ps1`
- Create: `tests/test_local_collector_scripts.py`

**Interfaces:**
- Installer parameters: `RepositoryUrl`, `CollectorRoot`, `TaskName = "Bitfinex Local Funding Collector"`, `Minute = 47`, and `-WhatIf`.
- Removal parameters: `TaskName = "Bitfinex Local Funding Collector"` and `-WhatIf`.
- Scheduled action: `<CollectorRoot>\.venv\Scripts\python.exe -m bitfinex_lending.local_collector --repo <CollectorRoot> --log-directory <CollectorRoot>\logs --remote-url <RepositoryUrl>`.

- [ ] **Step 1: Write failing script-contract tests**

Tests invoke PowerShell with `-WhatIf` and assert JSON output contains minute 47, a one-hour repetition interval, ten-minute execution limit, `IgnoreNew` multiple-instance policy, the dedicated Python executable, and no task mutation. Assert minute values outside `0..59` fail.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_local_collector_scripts.py -q`

Expected: FAIL because the scripts do not exist.

- [ ] **Step 3: Implement installer bootstrap and task registration**

Validate absolute `CollectorRoot`, clone only when `.git` is absent, verify the existing clone's `origin`, create `.venv`, install `-e .`, calculate the next local `HH:47`, create an hourly repetition trigger, set `StartWhenAvailable`, `ExecutionTimeLimit` ten minutes, and `MultipleInstances IgnoreNew`, then register the task. `-WhatIf` emits the computed contract as JSON and performs no clone, package install, or registration.

- [ ] **Step 4: Implement safe removal and verify GREEN**

Removal unregisters only the exact task name after confirmation semantics; it never removes `CollectorRoot`, logs, commits, or raw data.

Run: `python -m pytest tests/test_local_collector_scripts.py -q`

Expected: all script tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts/install-local-collector.ps1 scripts/remove-local-collector.ps1 tests/test_local_collector_scripts.py
git commit -m "feat: install minute-47 Windows collector task"
```

### Task 5: Documentation, Full Verification, and Deployment

**Files:**
- Modify: `README.md`
- Modify: `progress.md`
- Modify: `todo.md`

**Interfaces:**
- Consumes the CLI and script contracts from Tasks 2–4.
- Produces operator commands for install, dry run, manual collection, task inspection, pending-push recovery, readiness inspection, and removal.

- [ ] **Step 1: Document exact operator workflow**

Document prerequisites (Windows, Python 3.11+, Git Credential Manager, stable network), why the collector uses a dedicated clone, the minute-17/minute-47 split, and commands whose `-CollectorRoot` and `-RepositoryUrl` arguments are supplied explicitly by the operator. State that the computer must be awake and that missed snapshots cannot be backfilled.

- [ ] **Step 2: Record project status accurately**

Mark code/tests complete only after verification. Keep live Bitfinex collection, actual task registration, and observation of the first scheduled run unchecked until each is separately evidenced.

- [ ] **Step 3: Run complete offline verification**

```powershell
python -m pytest -q
git diff --check
python -m bitfinex_lending.local_collector --repo . --log-directory .test-tmp-local-collector-logs --remote-url https://github.com/wayneJ1606/Bitfinex_landing.git --dry-run
```

Expected: all offline tests pass, diff check exits 0, and dry run reports state without modifying Git history or raw data.

- [ ] **Step 4: Inspect the final diff and commit documentation**

```powershell
git status --short
git diff -- README.md progress.md todo.md
git add README.md progress.md todo.md
git commit -m "docs: explain local collector operation and recovery"
```

- [ ] **Step 5: Request deployment approvals at the point of mutation**

Ask separately before cloning outside the workspace, registering the Windows scheduled task, performing a live Bitfinex collection, or pushing commits to GitHub. Do not treat code completion as deployment completion.

- [ ] **Step 6: Verify deployed task and recompute readiness**

After approval, inspect `Get-ScheduledTask`/`Get-ScheduledTaskInfo`, verify the next run is at minute 47 and policy is `IgnoreNew`, perform one live run, confirm all three markets appear, and calculate the estimate from current distinct snapshot counts rather than the historical 124-row baseline.
