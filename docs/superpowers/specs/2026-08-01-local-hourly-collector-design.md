# Local Hourly Collector and GitHub Synchronization Design

**Status:** Approved for implementation

## Goal

Synchronize the latest GitHub-hosted Bitfinex raw and modeling data into the
developer checkout, then add a reliable Windows collector that captures one
snapshot per market at minute 47 of every hour. GitHub Actions continues to run
at minute 17, so the two collectors provide approximately two observations per
hour without intentionally collecting at the same instant.

The local collector must preserve successfully collected data when GitHub is
temporarily unavailable. It must never place offers, access a private Bitfinex
account, or fabricate snapshots for missed hours.

## Data Synchronization into the Developer Checkout

The first synchronization updates only `data/raw` and `data/modeling` from
`origin/master`. It does not merge or overwrite unrelated source code,
documentation, local commits, or uncommitted files. Before updating, the process
must verify that neither data directory contains local modifications that would
be overwritten. If it does, synchronization stops and reports the affected
paths.

This scoped synchronization is necessary because the developer checkout is
currently ahead of and behind `origin/master` and contains unrelated local
changes. The scheduled collector must not use this checkout.

## Collector Workspace

Use a dedicated clean clone outside the developer checkout. The installation
script accepts its absolute location instead of embedding a user-specific path.
The clone uses the repository's configured `origin` and works directly with
`master`; it contains no development changes.

Keeping collection isolated prevents normal coding, documentation edits, and
untracked files from blocking an hourly run. Git credentials remain managed by
Git Credential Manager and must not be written to scripts or logs.

## Hourly Workflow

Windows Task Scheduler starts the orchestration script at minute 47 of every
hour in `Asia/Taipei`. The task starts when available after a missed trigger,
does not launch a second instance while one is running, and stops a hung run
after ten minutes.

For each invocation, the orchestration script performs these steps:

1. Acquire a single-instance lock.
2. Validate the dedicated clone, branch, and expected remote.
3. If a previous local data commit is not yet on GitHub, try to synchronize it
   before collecting again.
4. Fetch `origin/master` and integrate it with a bounded rebase.
5. Run `python -m bitfinex_lending` once.
6. Preserve all successfully written local CSV rows even if later Git commands
   fail.
7. Stage only `data/raw`, and create a `[skip ci]` data commit when content was
   added.
8. Push the commit. On a rejected push, fetch and rebase once, then retry once.
9. Write the outcome and health information to a local rotating log.
10. Release the lock and return a meaningful exit code.

If a previous commit remains unsynchronized after the bounded retry, the run
does not collect another snapshot. This keeps the pending state simple and
prevents an unbounded local queue. The next scheduled invocation retries it.

## Failure and Recovery Rules

- Bitfinex failure: retain per-market failure records and return nonzero; do not
  create a data commit when no raw data changed.
- Partial market success: retain and commit successful markets; report the task
  as degraded/nonzero.
- GitHub network or authentication failure after collection: retain the local
  commit and mark it pending; do not recollect the same scheduled run.
- Non-fast-forward push: fetch, rebase, and retry once. On conflict, stop and
  preserve recoverable state for operator attention.
- Process overlap: the second process exits without collecting.
- Missed trigger or powered-off computer: collect one current snapshot when the
  task next runs; never backfill synthetic historical timestamps.

Logs contain timestamps, run ID, per-market status, collector exit code, commit
SHA, push result, and sanitized errors. They contain no tokens or credentials
and are retained for at least 30 days.

## Components

- A PowerShell orchestration script owns locking, Git synchronization, invoking
  the existing Python collector, bounded retry, and logging.
- A PowerShell installation script validates Python/Git paths and creates or
  updates the Windows scheduled task for minute 47.
- A removal script unregisters only the named task; it does not delete collected
  data or the dedicated clone.
- Pure helper functions expose decisions such as pending-commit detection and
  feature-readiness estimation so they can be tested without network access or
  Task Scheduler.
- Operator documentation explains installation, credentials, manual execution,
  status inspection, recovery, and removal.

The Python market-fetching and CSV behavior remain in the existing
`bitfinex_lending` package. The PowerShell layer does not duplicate API parsing
or feature calculation.

## Feature Readiness Estimate

The training code requires 168 eligible rows per market. Because the first
snapshot lacks lag fields and the last lacks a next-period target, at least 170
snapshots per market are required to produce 168 eligible rows.

At the latest inspected GitHub state, each market has 124 raw snapshots, which
would produce approximately 122 eligible rows after rebuilding. Therefore each
market needs 46 additional successful snapshots.

With GitHub collecting at minute 17 and the local computer collecting at minute
47, ideal operation produces 48 snapshots per day. Under ideal operation, the
threshold is reached about 23 hours after both schedules are active. A more
realistic estimate using 80% combined availability is about 29 hours. The status
must be recomputed from actual distinct snapshot times after synchronization;
calendar estimates are advisory, not acceptance evidence.

Reaching 168 eligible rows starts the first technical model evaluation. It does
not establish production reliability. Longer histories remain necessary before
interpreting model performance as decision support.

## Testing and Acceptance

Implementation follows test-driven development. Automated tests must cover:

- exact minute-47 task configuration generation;
- scoped staging of `data/raw` only;
- pending local commit detection;
- no recollection while an earlier commit remains pending;
- one bounded fetch/rebase/push retry;
- preservation of data and commit state after simulated push failure;
- single-instance lock behavior;
- readiness calculation at 124, 169, and 170 snapshots; and
- sanitized logging without credentials.

Acceptance also requires:

- all existing offline Python tests passing;
- a dry run of the orchestration logic without calling Bitfinex or pushing;
- one explicit live collection approved by the operator;
- successful scheduled-task inspection showing minute 47 and no-overlap policy;
- verification that the developer checkout's unrelated changes remain intact;
- confirmation that GitHub and local snapshots both appear in the rebuilt data;
  and
- a documented recovery exercise for a simulated unavailable GitHub remote.

## Out of Scope

- Automatic lending or trading.
- Historical backfilling of missed funding-book snapshots.
- Running model training every hour; the existing daily workflow remains the
  automatic rebuild path.
- Notifications beyond local logs and Task Scheduler history.
- Refactoring unrelated collection or modeling code.
