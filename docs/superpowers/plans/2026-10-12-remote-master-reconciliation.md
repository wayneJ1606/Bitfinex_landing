# Remote Master Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a tested local integration candidate that combines the current GitHub public-data history with the completed local application code, without exposing private data or changing the remote repository.

**Architecture:** Create an isolated branch from the freshly fetched `origin/master`, merge local `master`, and resolve conflicts by ownership: GitHub keeps authoritative public collection data, while local `master` keeps the newer application, tests, and verified progress documents. Validate repository privacy and the entire offline suite before offering any push or pull-request action.

**Tech Stack:** Git worktrees, PowerShell, Python 3.11, pytest.

## Global Constraints

- Do not push, force-push, delete, or rewrite `origin/master` while executing this plan.
- Preserve the dirty primary workspace and every uncommitted local data/report file.
- Use the fetched `origin/master` tip as the public-data authority.
- Use local `master` as the source-code, test, and completed-documentation authority.
- Never stage `data/account/**`, `data/metadata/**`, credentials, temporary files, or private raw payloads.
- Create backup refs before any merge and use only an ignored `.worktrees/` path.
- The candidate is complete only when the privacy contract and full offline test suite pass without warnings.

---

### Task 1: Freeze inputs and create the isolated candidate

**Files:**
- Create: `docs/superpowers/plans/2026-10-12-remote-master-reconciliation.md`
- Create worktree: `.worktrees/remote-master-reconciliation`

**Interfaces:**
- Consumes: `origin/master`, local `master`, and the verified commit IDs recorded before work begins.
- Produces: branch `codex/remote-master-reconciliation-20261012` checked out in an isolated worktree.

- [ ] **Step 1: Commit this plan and advance local `master` to it**

Run:

```powershell
git add -- docs/superpowers/plans/2026-10-12-remote-master-reconciliation.md
git commit -m "docs: plan remote master reconciliation"
git branch -f master HEAD
```

Expected: only this plan is committed; `master` and the current local feature branch point to the plan commit.

- [ ] **Step 2: Record immutable backup refs**

Run:

```powershell
git branch backup/pre-remote-reconcile-local-20261012 master
git branch backup/pre-remote-reconcile-origin-20261012 origin/master
```

Expected: both branch refs are created without moving `master` or `origin/master`.

- [ ] **Step 3: Verify the worktree directory is ignored**

Run:

```powershell
git check-ignore -q .worktrees
```

Expected: exit code `0`.

- [ ] **Step 4: Create the candidate from the remote tip**

Run:

```powershell
git worktree add .worktrees/remote-master-reconciliation -b codex/remote-master-reconciliation-20261012 origin/master
```

Expected: the new branch points exactly to the fetched remote tip and the primary workspace remains untouched.

### Task 2: Merge with an explicit ownership matrix

**Files:**
- Resolve manually: `.gitignore`
- Keep local `master`: `bitfinex_lending/**`, `tests/**`, `docs/**`, `scripts/**`, `pyproject.toml`, `progress.md`, `todo.md`, and top-level project documentation
- Keep `origin/master`: `data/local_public/**`, `data/raw/**`, and conflicting generated `data/modeling/*.csv`

**Interfaces:**
- Consumes: the candidate branch from Task 1 and local `master`.
- Produces: one merge commit with both histories and no unmerged paths.

- [ ] **Step 1: Start the no-commit merge**

Run inside the candidate worktree:

```powershell
git merge --no-ff --no-commit master
```

Expected: Git reports conflicts; no merge commit is created yet.

- [ ] **Step 2: Resolve generated/public data conflicts from the remote side**

Because the candidate starts from `origin/master`, run:

```powershell
git checkout --ours -- data/raw data/modeling/model_evaluations.csv data/modeling/model_status.csv data/modeling/modeling_features.csv data/modeling/predictions.csv
git add -- data/raw data/modeling/model_evaluations.csv data/modeling/model_status.csv data/modeling/modeling_features.csv data/modeling/predictions.csv
```

Expected: all legacy raw-data and generated-model conflicts use the current GitHub snapshot.

- [ ] **Step 3: Resolve code, tests, and verified documentation from local master**

Resolve the known code, test, and documentation conflicts explicitly:

```powershell
git checkout --theirs -- bitfinex_lending/p0_experimental_pipeline.py bitfinex_lending/p0_market_history.py bitfinex_lending/public_git_sync.py docs/P0_EXECUTION_CHECKLIST.md docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md progress.md tests/test_p0_experimental_pipeline.py tests/test_p0_market_history.py tests/test_public_git_sync.py todo.md
git add -- bitfinex_lending/p0_experimental_pipeline.py bitfinex_lending/p0_market_history.py bitfinex_lending/public_git_sync.py docs/P0_EXECUTION_CHECKLIST.md docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md progress.md tests/test_p0_experimental_pipeline.py tests/test_p0_market_history.py tests/test_public_git_sync.py todo.md
```

Expected: newer P0, modeling, dashboard, Windows encoding, tests, and completion records are retained.

- [ ] **Step 4: Resolve `.gitignore` as a union**

Keep the remote public-data rules and the local protections for `.codex_tmp/`, the Cloudflare note, and exact private temporary paths. Remove every conflict marker, then run:

```powershell
git add -- .gitignore
git diff --check
git diff --name-only --diff-filter=U
```

Expected: `git diff --check` succeeds and the unmerged-path command prints nothing.

- [ ] **Step 5: Inspect and commit the merge**

Run:

```powershell
git status --short
git diff --cached --check
git commit -m "merge: reconcile public data history with local application"
```

Expected: a two-parent merge commit; no private or primary-workspace-only files are included.

### Task 3: Validate privacy, behavior, and history

**Files:**
- Test: `tests/test_repository_privacy_contract.py`
- Test: all `tests/`

**Interfaces:**
- Consumes: the merge commit from Task 2.
- Produces: an evidence-backed, push-ready local candidate or a documented failure requiring correction.

- [ ] **Step 1: Verify merge ancestry and repository state**

Run:

```powershell
git merge-base --is-ancestor origin/master HEAD
git merge-base --is-ancestor master HEAD
git status --porcelain
```

Expected: both ancestry checks return `0`; status is clean.

- [ ] **Step 2: Run the privacy contract**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -q --basetemp='..\..\.codex_tmp\pytest-remote-privacy' tests/test_repository_privacy_contract.py
```

Expected: all privacy-contract tests pass.

- [ ] **Step 3: Run the complete offline suite**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -q --basetemp='..\..\.codex_tmp\pytest-remote-reconcile'
```

Expected: at least `372 passed, 1 deselected`, with no warnings or failures.

- [ ] **Step 4: Re-fetch and confirm remote stability**

Run from the primary repository:

```powershell
git fetch origin
git rev-list --left-right --count codex/remote-master-reconciliation-20261012...origin/master
```

Expected: if new automated data commits appeared, merge `origin/master` into the candidate and repeat Steps 1–3; otherwise the remote-side count is `0`.

### Task 4: Handoff without remote mutation

**Files:** None.

**Interfaces:**
- Consumes: the fully verified candidate.
- Produces: a clear user choice for remote publication.

- [ ] **Step 1: Report the candidate commit and verification evidence**

Include the candidate SHA, both parent SHAs, test totals, privacy result, and whether `origin/master` advanced during validation.

- [ ] **Step 2: Offer publication choices**

Offer only these safe next actions:

1. Push the candidate to a new branch and create/review a pull request.
2. Keep the verified candidate local for later.

Direct push to `origin/master` and every form of force-push remain out of scope unless the user explicitly authorizes them after reviewing the candidate.
