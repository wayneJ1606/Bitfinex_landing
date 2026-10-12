# Backtesting Implementation Plan

> **Status (2026-10-12):** Implemented and verified; retained as historical implementation documentation.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic, offline backtest for validation predictions and export the business metrics listed in `todo.md`.

**Architecture:** Backtesting consumes `ModelPrediction` rows only, so it cannot place orders or access private APIs. Each prediction is a signal when the predicted rate meets a configured threshold; a fill occurs when the actual next rate also meets that threshold. Metrics are computed independently per market/model and exported as UTF-8 CSV.

**Tech Stack:** Python 3.11, dataclasses, standard-library CSV, pytest.

## Global Constraints

- Use validation predictions only; never use training rows.
- Use fixed defaults: notional capital 1000.0, allocation fraction 0.10, threshold 0.0, hourly observations.
- Clearly label all outputs as simulated and not investment advice.
- No API calls, credentials, order submission, or account operations.

### Task 1: Backtest engine

**Files:** Create `bitfinex_lending/backtesting.py`, `tests/test_backtesting.py`.

- Add configuration and result dataclasses.
- Implement chronological per-market/model simulation.
- Calculate signal count, fills, fill rate, capital utilization, average wait hours, maximum consecutive misses, total simulated return, and annualized simulated return.
- Reject invalid configuration and non-finite predictions.

### Task 2: CSV export and pipeline integration

**Files:** Create `bitfinex_lending/backtesting_csv.py`, `tests/test_backtesting_csv.py`, modify `bitfinex_lending/modeling.py`.

- Export `backtest_results.csv` atomically.
- Run backtest after prediction export and expose the output path in `ModelingRunSummary` and CLI output.

### Task 3: Documentation and verification

- Update `todo.md` and `progress.md` only for completed backtest items.
- Run focused and full offline tests.
- Rebuild current modeling outputs and inspect the CSV header and row count.
