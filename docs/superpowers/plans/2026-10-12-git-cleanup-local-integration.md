# Git Cleanup and Local Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every existing user artifact while separating verified source, tests, documentation, generated outputs, public runtime data, private data, and disposable tooling into safe Git boundaries before fast-forwarding local `master`.

**Architecture:** Treat the current dirty worktree as the source of truth and never use destructive cleanup or broad staging. Commit only reviewed allowlists; keep generated/runtime/private artifacts unstaged. Perform local `master` integration in a temporary worktree so the current worktree and its remaining local files stay untouched.

**Tech Stack:** Git, PowerShell, Python 3.11, pytest 8.4.

## Global Constraints

- Never stage `data/account/`, private collector history, `.env*`, credentials, API keys, account identifiers, or private API endpoint payloads.
- Never use `git add -A`, `git add .`, destructive reset, checkout-based cleanup, or recursive deletion.
- Do not push, fetch, pull, or otherwise change remote state; `origin/master` is outside this local integration.
- Preserve `data/local_public/`, generated modeling outputs, report drafts, screenshots, and disposable tooling unless a reviewed task explicitly names them.
- Every source commit must pass its focused tests; the final integrated `master` must pass the complete offline suite.

---

### Task 1: Repository guardrails and inventory

**Files:**
- Modify: `.gitignore`
- Create: `docs/superpowers/plans/2026-10-12-git-cleanup-local-integration.md`

**Interfaces:**
- Consumes: current dirty worktree and existing privacy rules.
- Produces: explicit ignore coverage for disposable `.codex_tmp/` and local Cloudflare notes, plus a reproducible cleanup plan.

- [ ] **Step 1:** Confirm the index is empty and record tracked, untracked, ignored, branch-topology, and privacy-scan evidence.
- [ ] **Step 2:** Add `.codex_tmp/`, `cloudflare tunnel 的相關資訊.txt`, and the exact private atomic `.tmp` sibling paths to `.gitignore`; do not ignore public runtime data globally because the existing public-sync workflow manages it separately.
- [ ] **Step 3:** Run `git check-ignore` for `.codex_tmp/`, the Cloudflare note, `.env`, and `data/account/`.
- [ ] **Step 4:** Review the exact staged diff and commit only `.gitignore` plus this plan with message `chore: harden local git cleanup boundaries`.

### Task 2: Model expansion source and tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `bitfinex_lending/model_training.py`
- Modify: `bitfinex_lending/modeling.py`
- Modify: `tests/test_model_training.py`
- Create: `bitfinex_lending/backtest_report.py`
- Create: `bitfinex_lending/backtesting.py`
- Create: `bitfinex_lending/backtesting_csv.py`
- Create: `bitfinex_lending/decision_support.py`
- Create: `bitfinex_lending/decision_support_csv.py`
- Create: `bitfinex_lending/model_report.py`
- Create: `bitfinex_lending/prediction_chart.py`
- Create: `tests/test_backtest_report.py`
- Create: `tests/test_backtesting.py`
- Create: `tests/test_backtesting_csv.py`
- Create: `tests/test_decision_support.py`
- Create: `tests/test_decision_support_csv.py`
- Create: `tests/test_model_report.py`
- Create: `tests/test_prediction_chart.py`

**Interfaces:**
- Consumes: existing modeling result dataclasses and CSV exporters.
- Produces: decision-tree/XGBoost evaluation, prediction SVGs, model report, backtest outputs, and decision-support outputs.

- [ ] **Step 1:** Review source/test diffs and confirm every new module has focused coverage.
- [ ] **Step 2:** Run the focused model, reporting, backtest, chart, decision-support, and workflow tests.
- [ ] **Step 3:** Stage only the exact source/test allowlist above; do not stage modeling CSV/SVG/Markdown outputs.
- [ ] **Step 4:** Inspect `git diff --cached --check` and `git diff --cached --stat`.
- [ ] **Step 5:** Commit with message `feat: expand modeling reports and decision support`.

### Task 3: P0 private-data preparation source and tests

**Files:**
- Create: `bitfinex_lending/p0_alignment.py`
- Create: `bitfinex_lending/p0_offer_lifecycle.py`
- Create: `tests/test_p0_alignment.py`
- Create: `tests/test_p0_offer_lifecycle.py`
- Create: `docs/P0_DATA_QUALITY_CHECK_2026-08-18.md`
- Create: `docs/P0_PREPARATION_SPEC.md`
- Create: `docs/superpowers/plans/2026-08-16-private-funding-collector.md`
- Create: `docs/superpowers/specs/2026-08-16-private-funding-collector-design.md`

**Interfaces:**
- Consumes: sanitized public/private event representations.
- Produces: lifecycle and UTC-alignment tooling without publishing private account rows.

- [ ] **Step 1:** Review files for private values and private endpoint payloads; permit documentation names but no secret values.
- [ ] **Step 2:** Run `tests/test_p0_alignment.py`, `tests/test_p0_offer_lifecycle.py`, and the repository privacy-contract test.
- [ ] **Step 3:** Stage only the exact allowlist and inspect the cached diff.
- [ ] **Step 4:** Commit with message `feat: prepare private funding data alignment`.

### Task 4: Documentation and Task 10 handoff

**Files:**
- Modify: `docs/P0_EXECUTION_CHECKLIST.md`
- Modify: `progress.md`
- Modify: `todo.md`
- Create: `docs/MODEL_NEXT_LAYER_PLAN.md`
- Create: `docs/superpowers/plans/2026-08-11-backtesting.md`
- Create: `docs/superpowers/plans/2026-08-11-decision-support.md`
- Create: `docs/superpowers/plans/2026-08-11-model-expansion.md`

**Interfaces:**
- Consumes: verified Task 10 evidence and model-expansion implementation.
- Produces: accurate current handoff while retaining historical entries.

- [ ] **Step 1:** Review documentation for stale statements versus intentionally historical entries.
- [ ] **Step 2:** Stage reviewed documentation hunks only; do not sweep unrelated README, motion-video, report-draft, or screenshot changes into this commit.
- [ ] **Step 3:** Run Markdown privacy scan and `git diff --cached --check`.
- [ ] **Step 4:** Commit with message `docs: record verified modeling and P0 handoff`.

### Task 5: Preserve local-only and unfinished artifacts

**Files:**
- Keep unstaged: `data/local_public/`, `data/metadata/`, `data/modeling/`, `deliverables/`, `作業繳交截圖/`, `README.md`, motion-video documents, report-generation scripts, report-draft status, and the tracked deletion/renamed local note.

**Interfaces:**
- Consumes: remaining worktree changes.
- Produces: an explicit residual inventory with no data loss.

- [ ] **Step 1:** Confirm private paths remain ignored and no sensitive file is staged.
- [ ] **Step 2:** Record the remaining `git status --short` without deleting, stashing, or overwriting anything.
- [ ] **Step 3:** Confirm all committed files are reproducible source/tests/docs rather than runtime account data.

### Task 6: Local master integration

**Files:**
- Create temporarily: `.worktrees/local-master-integration/`

**Interfaces:**
- Consumes: reviewed commits on `codex/git-safety-review-20260822`.
- Produces: local `master` fast-forwarded to the verified feature branch, with the dirty source worktree preserved.

- [ ] **Step 1:** Verify `master` remains an ancestor of the feature branch and the feature branch index is empty.
- [ ] **Step 2:** Create a temporary ignored worktree on local `master`; do not pull or contact `origin`.
- [ ] **Step 3:** Fast-forward local `master` to `codex/git-safety-review-20260822`.
- [ ] **Step 4:** Run the complete offline suite from the integrated worktree using the project virtual environment.
- [ ] **Step 5:** Remove only the temporary integration worktree after the test succeeds; do not delete the feature branch while the preserved dirty worktree uses it.
- [ ] **Step 6:** Report local integration separately from the still-divergent `origin/master`; do not push.
