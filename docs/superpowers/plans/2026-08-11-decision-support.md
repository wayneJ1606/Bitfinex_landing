# Decision Support Output Implementation Plan

> **Status (2026-10-12):** Implemented and verified; retained as historical implementation documentation.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended; see plan) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert model and backtest outputs into a transparent, human-review decision-support report without placing orders.

**Architecture:** Select the lowest-validation-RMSE model per market, use its latest validation prediction, derive a descriptive 10th–90th percentile observation range, and join matching backtest metrics. Insufficient markets still receive an explicit limited-status row.

**Tech Stack:** Python 3.11 dataclasses, CSV/Markdown standard library, pytest.

## Global Constraints

- Output is informational only and must state human confirmation and no automatic trading.
- Never invent predictions for insufficient markets.
- Do not use private APIs, credentials, or order operations.
- Use deterministic sorting and UTF-8 atomic CSV output.

### Task 1: Decision-support calculation

**Files:** Create `bitfinex_lending/decision_support.py`, `tests/test_decision_support.py`.

- Define a row containing market, selected model, latest prediction, observation range, baseline prediction, backtest metrics, limitation, and safety flags.
- Select best model by lowest RMSE, tie-breaking by model name.
- Return explicit limited rows for `insufficient_data` statuses.

### Task 2: CSV and Markdown outputs

**Files:** Create `bitfinex_lending/decision_support_csv.py`, `tests/test_decision_support_csv.py`.

- Export `decision_support.csv` atomically.
- Export `decision_support.md` with tables and mandatory safety disclaimer.

### Task 3: Pipeline integration and verification

**Files:** Modify `bitfinex_lending/modeling.py`.

- Generate decision-support outputs after model evaluation and backtest.
- Run the full offline test suite and rebuild current outputs.
- Update `todo.md` and `progress.md` for completed decision-support items.
