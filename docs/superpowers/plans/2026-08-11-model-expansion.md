# Model Expansion Implementation Plan

> **Status (2026-10-12):** Implemented and verified; retained as historical implementation documentation.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing modeling pipeline with a decision-tree model, optional XGBoost support, prediction comparison charts, and a reproducible result interpretation report.

**Architecture:** Keep chronological splitting and leakage-safe baselines unchanged. Add tree estimators beside the existing estimators, detect XGBoost at runtime without making the base install fail, and export a dependency-free SVG chart plus Markdown interpretation from the already exported result objects.

**Tech Stack:** Python 3.11, scikit-learn, optional xgboost, pytest, standard-library SVG/Markdown writers.

## Global Constraints

- Preserve the 168 eligible-row threshold and chronological 80/20 split.
- Never report an unavailable optional model as trained.
- Keep outputs atomic and UTF-8 encoded.
- Do not add live API calls, trading, or backtesting in this batch.

### Task 1: Model estimators

**Files:** `bitfinex_lending/model_training.py`, `tests/test_model_training.py`

- Add `decision_tree` using `DecisionTreeRegressor(random_state=42, max_depth=5, min_samples_leaf=2)`.
- Add `xgboost` only when importable, using deterministic conservative parameters.
- Keep unavailable XGBoost out of evaluations and identify it in the trained status message.
- Test tree output and optional-model behavior without requiring xgboost installation.

### Task 2: Prediction comparison chart

**Files:** Create `bitfinex_lending/prediction_chart.py`, `tests/test_prediction_chart.py`, modify `bitfinex_lending/modeling.py`.

- Export one UTF-8 SVG per market from validation predictions.
- Include actual and predicted series, model labels, and a stable filename.
- Wire chart paths into the run summary and CLI output.

### Task 3: Model interpretation report

**Files:** Create `bitfinex_lending/model_report.py`, `tests/test_model_report.py`, modify `bitfinex_lending/modeling.py`.

- Export Markdown summarizing status, MAE/RMSE/R2, best model per market, and limitations.
- State explicitly when XGBoost is unavailable or when data is insufficient.
- Wire the report path into the run summary and CLI output.

### Task 4: Verification and documentation

- Run focused tests, then the complete offline suite.
- Update `todo.md` only for items actually completed in this batch.
- Record current environment limitation if XGBoost is not installed.
