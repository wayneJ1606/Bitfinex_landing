# Automated Feature Engineering and Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild deterministic modeling features from repository raw CSV files every day and, once each market has 168 valid observations, automatically evaluate two baselines and linear regression on an ordered 80%／20% time split.

**Architecture:** Add a strict raw-CSV loader that feeds the existing pure feature calculator, then add a separate pure modeling boundary that returns status, evaluation, and prediction records. A command assembles the loader, calculator, trainer, and atomic CSV exporters; a daily GitHub Actions workflow runs tests and the command before committing only `data/modeling`.

**Tech Stack:** Python 3.11+, standard-library `csv`/`datetime`/`pathlib`, scikit-learn, pytest 8, GitHub Actions.

## Global Constraints

- Cloud input is exclusively `data/raw/YYYY/MM/DD/{fUSD,fBTC,fETH}.csv`; GitHub modeling must not read runner-local SQLite.
- Raw headers are exactly `run_id,market,rate,period,count,amount,side,fetched_at`; malformed input fails the whole command.
- Markets are exactly `fUSD`, `fBTC`, and `fETH`; timestamps are timezone-aware ISO 8601 normalized to UTC.
- Exact duplicate source rows are removed; conflicting `(run_id, market)` timestamps are errors.
- Existing feature formulas remain unchanged and amount-based calculations use `abs(amount)`.
- Modeling eligibility is calculated after removing rows with any null predictor or target; each market requires exactly 168 eligible rows.
- Split each market chronologically with `train_size = floor(n * 0.8)` and never shuffle.
- Models are exactly `baseline_mean`, `baseline_previous`, and `linear_regression`; all use identical validation rows.
- Output files are exactly `data/modeling/modeling_features.csv`, `model_status.csv`, `model_evaluations.csv`, and `predictions.csv`.
- Insufficient markets do not block trained markets; any parsing, training, metric, or output error returns nonzero and the workflow commits nothing.
- Daily schedule is `18:37 UTC`, supports `workflow_dispatch`, uses Python 3.11, `contents: write`, the built-in token, and the same concurrency group as collection.
- Collector installation remains lightweight; scikit-learn belongs to the `modeling` optional dependency group.
- No decision tree, XGBoost, backtesting, binary model artifact, authenticated API, or trading behavior.

## File Structure

- Create `bitfinex_lending/raw_csv.py`: strict recursive loading, type parsing, UTC normalization, consistency checks, and exact-row deduplication.
- Create `tests/test_raw_csv.py`: valid multi-day loading plus every input validation contract.
- Create `bitfinex_lending/model_training.py`: eligibility filtering, thresholding, chronological split, predictions, and metrics.
- Create `tests/test_model_training.py`: 167/168 boundary, leakage-safe baselines, linear regression, metric and market-isolation behavior.
- Modify `bitfinex_lending/models.py`: add immutable status, evaluation, prediction, and aggregate result records.
- Create `bitfinex_lending/modeling_csv.py`: atomic, fixed-schema exports for status/evaluation/predictions.
- Create `bitfinex_lending/modeling.py`: command orchestration from raw CSV to all four outputs.
- Create `tests/test_modeling_csv.py` and `tests/test_modeling.py`: output and command contracts.
- Modify `pyproject.toml`: add `modeling` optional dependency.
- Modify `.github/workflows/collect-funding-books.yml`: use the shared write-workflow concurrency group.
- Create `.github/workflows/build-modeling-dataset.yml` and `tests/test_modeling_workflow.py`.
- Modify `README.md`, `progress.md`, and `todo.md`: operation, limits, and acceptance evidence.

---

### Task 1: Strict Repository Raw-CSV Loader

**Files:**
- Create: `bitfinex_lending/raw_csv.py`
- Create: `tests/test_raw_csv.py`

**Interfaces:**
- Consumes: repository raw root `Path` and `FundingBookRow`.
- Produces: `RawCsvError` and `load_raw_snapshots(root: Path) -> tuple[FundingBookRow, ...]`.

- [x] **Step 1: Write failing valid-load and deduplication tests**

Create `tests/test_raw_csv.py` with a helper that writes exact-header CSV files and these assertions:

```python
def test_loads_multiple_days_in_utc_order_and_deduplicates_exact_rows(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    write_raw(root / "2026/07/22/fUSD.csv", [
        ["run-2", "fUSD", "0.0003", "7", "2", "-5", "demand", "2026-07-22T09:17:00+08:00"],
    ])
    duplicated = ["run-1", "fUSD", "0.0002", "2", "1", "10", "offer", "2026-07-21T13:17:00+00:00"]
    write_raw(root / "2026/07/21/fUSD.csv", [duplicated, duplicated])

    rows = load_raw_snapshots(root)

    assert len(rows) == 2
    assert [row.run_id for row in rows] == ["run-1", "run-2"]
    assert rows[1].fetched_at == "2026-07-22T01:17:00+00:00"
    assert rows[0].rate == 0.0002
    assert rows[0].period == 2
    assert rows[0].count == 1
```

Also assert a missing raw root returns `()`.

- [x] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_raw_csv.py -v`

Expected: collection fails because `bitfinex_lending.raw_csv` does not exist.

- [x] **Step 3: Implement deterministic loading and parsing**

Create `bitfinex_lending/raw_csv.py` with:

```python
RAW_FIELDS = ("run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at")
SUPPORTED_MARKETS = frozenset({"fUSD", "fBTC", "fETH"})

class RawCsvError(ValueError):
    pass

def load_raw_snapshots(root: Path) -> tuple[FundingBookRow, ...]:
    root = Path(root)
    if not root.exists():
        return ()
    parsed: list[tuple[datetime, FundingBookRow]] = []
    seen_rows: set[tuple[object, ...]] = set()
    run_times: dict[tuple[str, str], str] = {}
    for path in sorted(root.rglob("*.csv"), key=lambda item: item.as_posix()):
        for line_number, values in _read_rows(path, root):
            row, timestamp = _parse_row(values, path, root, line_number)
            run_key = (row.run_id, row.market)
            previous_time = run_times.setdefault(run_key, row.fetched_at)
            if previous_time != row.fetched_at:
                raise _csv_error(root, path, line_number, "run_id has conflicting fetched_at")
            row_key = (
                row.run_id, row.market, row.fetched_at, row.rate,
                row.period, row.count, row.amount, row.side,
            )
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                parsed.append((timestamp, row))
    return tuple(row for _, row in sorted(parsed, key=lambda item: (item[1].market, item[0], item[1].run_id, item[1].rate)))
```

Implement concrete helpers `_csv_error(root, path, line_number, reason)`, `_read_rows(path, root)`, `_utc_timestamp(value)`, `_parse_float(value, field)`, `_parse_int(value, field)`, and `_parse_row(values, path, root, line_number)`. `_read_rows` reads the first row with `csv.reader`, verifies `tuple(header) == RAW_FIELDS` and `len(set(header)) == len(header)`, and yields `(line_number, dict(zip(RAW_FIELDS, row, strict=True)))`. Catch `UnicodeDecodeError`, `OSError`, `csv.Error`, and conversion errors and raise `RawCsvError` with `invalid raw CSV <relative-path> row <number>: <reason>`.

- [x] **Step 4: Write failing validation matrix**

Add parameterized tests that separately assert `RawCsvError` for:

```python
[
    ("missing field", ["run_id", "market"]),
    ("extra field", [*RAW_FIELDS, "extra"]),
    ("duplicate field", [*RAW_FIELDS, "market"]),
    ("unsupported market", row(market="fDOGE")),
    ("path market does not match row", row(market="fBTC"), "fUSD.csv"),
    ("timestamp must include timezone", row(fetched_at="2026-07-21T13:17:00")),
    ("rate must be finite", row(rate="nan")),
    ("period must be positive", row(period="0")),
    ("count must be nonnegative", row(count="-1")),
    ("amount must not be zero", row(amount="0")),
    ("offer amount must be positive", row(side="offer", amount="-1")),
    ("demand amount must be negative", row(side="demand", amount="1")),
]
```

Add focused tests for invalid UTF-8 and for one `(run_id, market)` appearing with two different normalized timestamps.

- [x] **Step 5: Complete validation and run GREEN verification**

Run: `python -m pytest tests/test_raw_csv.py -v`

Expected: all raw-loader tests pass with pristine output.

- [x] **Step 6: Run feature integration regression**

Run: `python -m pytest tests/test_raw_csv.py tests/test_feature_calculation.py -v`

Expected: loader and existing feature-calculation tests pass.

- [x] **Step 7: Commit**

```bash
git add bitfinex_lending/raw_csv.py tests/test_raw_csv.py
git commit -m "feat: load repository funding CSVs"
```

---

### Task 2: Thresholded Baselines and Linear Regression

**Files:**
- Modify: `pyproject.toml`
- Modify: `bitfinex_lending/models.py`
- Create: `bitfinex_lending/model_training.py`
- Create: `tests/test_model_training.py`

**Interfaces:**
- Consumes: `Sequence[ModelingFeature]`, timezone-aware `run_at`, and `required_rows` defaulting to `168`.
- Produces: `ModelStatus`, `ModelEvaluation`, `ModelPrediction`, `ModelingResult`, `ModelTrainingError`, `PREDICTOR_FIELDS`, and `evaluate_models(features, run_at, required_rows=168) -> ModelingResult`.

- [x] **Step 1: Add and install the modeling dependency**

In `pyproject.toml`, add the separately installable optional group without changing collector dependencies:

```toml
[project.optional-dependencies]
test = ["pytest>=8,<9"]
modeling = ["scikit-learn>=1.9,<2"]
```

Run: `python -m pip install -e ".[test,modeling]"`

Expected: installation succeeds and `python -c "import sklearn; print(sklearn.__version__)"` reports a version in `[1.9, 2)`.

- [x] **Step 2: Add failing 167/168 threshold and market-isolation tests**

Create 168 chronological eligible `ModelingFeature` rows with a deterministic target. Assert:

```python
result = evaluate_models(features_168, run_at="2026-07-22T00:00:00+00:00")
status = result.statuses[0]
assert status.status == "trained"
assert status.valid_rows == 168
assert status.required_rows == 168
assert len(result.evaluations) == 3
assert {item.model_name for item in result.evaluations} == {
    "baseline_mean", "baseline_previous", "linear_regression"
}

insufficient = evaluate_models(features_168[:-1], run_at="2026-07-22T00:00:00+00:00")
assert insufficient.statuses[0].status == "insufficient_data"
assert insufficient.evaluations == ()
assert insufficient.predictions == ()
```

Combine 168 eligible `fUSD` rows and 10 `fBTC` rows; assert USD trains while BTC remains insufficient.

- [x] **Step 3: Run RED verification**

Run: `python -m pytest tests/test_model_training.py -v`

Expected: imports fail because modeling result records and `model_training` do not exist.

- [x] **Step 4: Add result records and eligibility boundary**

Append frozen dataclasses to `models.py`:

```python
@dataclass(frozen=True)
class ModelStatus:
    market: str
    status: Literal["insufficient_data", "trained"]
    feature_rows: int
    valid_rows: int
    required_rows: int
    message: str

@dataclass(frozen=True)
class ModelEvaluation:
    run_at: str
    market: str
    model_name: str
    train_rows: int
    valid_rows: int
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    mae: float
    rmse: float
    r2: float

@dataclass(frozen=True)
class ModelPrediction:
    run_at: str
    market: str
    feature_time: str
    model_name: str
    predicted_rate: float
    actual_next_rate: float
    prediction_error: float

@dataclass(frozen=True)
class ModelingResult:
    statuses: tuple[ModelStatus, ...]
    evaluations: tuple[ModelEvaluation, ...]
    predictions: tuple[ModelPrediction, ...]
```

In `model_training.py`, define the exact `PREDICTOR_FIELDS` from the spec, group by market, order by parsed UTC `feature_time`, remove any row with null predictor/target, and return insufficient statuses before importing/training estimators.

- [x] **Step 5: Add failing leakage-safe model and metric tests**

Assert:

- `train_rows == floor(168 * 0.8) == 134` and `valid_rows == 34`.
- `baseline_mean` prediction equals only the first 134 targets' mean.
- `baseline_previous` prediction equals validation `weighted_avg_rate`.
- all three models predict exactly the same 34 feature times.
- `prediction_error == predicted_rate - actual_next_rate`.
- evaluation MAE/RMSE/R² match independently calculated expected values.
- naive or invalid `run_at`, non-finite predictors/targets, and non-finite R² raise `ModelTrainingError`.

- [x] **Step 6: Implement the models and common evaluation path**

Implement one `_evaluate_predictions` helper using `mean_absolute_error`, `mean_squared_error`, and `r2_score`; calculate RMSE with `math.sqrt(mean_squared_error(...))`. Fit `LinearRegression` only on the chronological training matrix. Convert NumPy/scikit values to built-in `float` and reject non-finite metrics.

Use the same ordered validation feature list for all prediction records. Sort statuses by market and outputs by `(market, model_name, feature_time)`.

- [x] **Step 7: Run GREEN and full model tests**

Run: `python -m pytest tests/test_model_training.py -v`

Expected: all model tests pass.

Run: `python -m pytest tests/test_feature_calculation.py tests/test_model_training.py -v`

Expected: existing feature behavior and new training behavior both pass.

- [x] **Step 8: Commit**

```bash
git add pyproject.toml bitfinex_lending/models.py bitfinex_lending/model_training.py tests/test_model_training.py
git commit -m "feat: evaluate baseline and linear models"
```

---

### Task 3: Modeling CSV Outputs and Command

**Files:**
- Create: `bitfinex_lending/modeling_csv.py`
- Create: `bitfinex_lending/modeling.py`
- Create: `tests/test_modeling_csv.py`
- Create: `tests/test_modeling.py`

**Interfaces:**
- Consumes: `load_raw_snapshots`, `calculate_features`, `evaluate_models`, and `export_modeling_features`.
- Produces: `ModelingCsvError`, `export_modeling_results(result: ModelingResult, output_directory: Path) -> tuple[Path, Path, Path]`, `ModelingRunSummary`, `run_modeling_pipeline(raw_root: Path, output_root: Path, run_at: str, *, loader=load_raw_snapshots, calculator=calculate_features, evaluator=evaluate_models, feature_exporter=export_modeling_features, result_exporter=export_modeling_results) -> ModelingRunSummary`, and CLI `main(settings: ModelingSettings | None = None) -> int` where frozen `ModelingSettings` defaults to `Path("data/raw")`, `Path("data/modeling")`, and `168` required rows.

- [x] **Step 1: Write failing fixed-schema and atomic output tests**

In `tests/test_modeling_csv.py`, construct a `ModelingResult` and assert exact schemas:

```python
STATUS_FIELDS = ("market", "status", "feature_rows", "valid_rows", "required_rows", "message")
EVALUATION_FIELDS = ("run_at", "market", "model_name", "train_rows", "valid_rows", "train_start", "train_end", "valid_start", "valid_end", "mae", "rmse", "r2")
PREDICTION_FIELDS = ("run_at", "market", "feature_time", "model_name", "predicted_rate", "actual_next_rate", "prediction_error")
```

Assert stable sorting, UTF-8, header-only evaluation/prediction files for insufficient data, atomic replacement, and `.tmp` cleanup after injected `Path.replace` failure.

- [x] **Step 2: Run CSV RED verification**

Run: `python -m pytest tests/test_modeling_csv.py -v`

Expected: module import fails.

- [x] **Step 3: Implement focused atomic exporters**

Create `modeling_csv.py` with a shared private `_export(filename, fields, rows, output_directory)` that creates the directory, writes `filename.tmp`, and atomically replaces the target. Export status, evaluation, and prediction files only; `modeling_features.csv` remains owned by the existing `feature_csv.py` boundary.

Catch `OSError` and `csv.Error`, perform best-effort temp cleanup without masking the original exception, and raise `ModelingCsvError`.

- [x] **Step 4: Write failing pipeline and CLI tests**

In `tests/test_modeling.py`, inject loader, calculator, evaluator, and exporters and assert call order plus summary:

```python
summary = run_modeling_pipeline(
    raw_root,
    output_root,
    run_at="2026-07-22T00:00:00+00:00",
    loader=fake_loader,
    calculator=fake_calculator,
    evaluator=fake_evaluator,
    feature_exporter=fake_feature_exporter,
    result_exporter=fake_result_exporter,
)
assert events == ["load", "calculate", "evaluate", "features_csv", "results_csv"]
assert summary.source_rows == 3
assert summary.feature_rows == 2
```

Assert `main()` defaults to `data/raw` and `data/modeling`, prints one line per market and all four paths, returns `0` for all-insufficient results, and returns `1` with `fatal:` for `OSError`, `RawCsvError`, `FeatureCalculationError`, `ModelTrainingError`, `FeatureCsvError`, or `ModelingCsvError`.

- [x] **Step 5: Implement command orchestration**

Create `modeling.py` with:

```python
@dataclass(frozen=True)
class ModelingSettings:
    raw_root: Path = Path("data/raw")
    output_root: Path = Path("data/modeling")
    required_rows: int = 168

@dataclass(frozen=True)
class ModelingRunSummary:
    source_rows: int
    feature_rows: int
    result: ModelingResult
    feature_path: Path
    status_path: Path
    evaluation_path: Path
    prediction_path: Path
```

`run_modeling_pipeline` loads all raw rows, calculates all features in memory, evaluates models, writes `modeling_features.csv`, then writes the three result CSVs. `main()` uses `datetime.now(timezone.utc).isoformat()`, catches the specified domain errors, and is exposed through `python -m bitfinex_lending.modeling`.

- [x] **Step 6: Run GREEN and integration tests**

Run: `python -m pytest tests/test_modeling_csv.py tests/test_modeling.py -v`

Expected: all output and command tests pass.

Run: `python -m pytest tests/test_raw_csv.py tests/test_feature_calculation.py tests/test_model_training.py tests/test_modeling_csv.py tests/test_modeling.py -v`

Expected: complete raw-to-model pipeline test set passes.

- [x] **Step 7: Commit**

```bash
git add bitfinex_lending/modeling_csv.py bitfinex_lending/modeling.py tests/test_modeling_csv.py tests/test_modeling.py
git commit -m "feat: add modeling dataset command"
```

---

### Task 4: Dependencies and Daily GitHub Workflow

**Files:**
- Modify: `.github/workflows/collect-funding-books.yml`
- Create: `.github/workflows/build-modeling-dataset.yml`
- Create: `tests/test_modeling_workflow.py`

**Interfaces:**
- Consumes: `python -m bitfinex_lending.modeling` from Task 3.
- Produces: a write-capable daily/manual workflow serialized with collection and using the `modeling` optional dependency delivered by Task 2.

- [x] **Step 1: Write failing dependency and workflow contract tests**

Create `tests/test_modeling_workflow.py` and assert:

```python
workflow = Path(".github/workflows/build-modeling-dataset.yml").read_text(encoding="utf-8")
collector = Path(".github/workflows/collect-funding-books.yml").read_text(encoding="utf-8")
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
assert workflow.index("python -m pytest") < workflow.index("python -m bitfinex_lending.modeling")
assert "git add data/modeling" in workflow
assert "git pull --rebase" in workflow
assert "git push" in workflow
assert "--force" not in workflow
```

- [x] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_modeling_workflow.py -v`

Expected: missing workflow and shared-concurrency assertions fail.

- [x] **Step 3: Share concurrency and create workflow**

Change the collector group to `bitfinex-repository-writer`. Create `.github/workflows/build-modeling-dataset.yml` mirroring the reviewed collector patterns with:

```yaml
name: Build Bitfinex modeling dataset
on:
  schedule:
    - cron: "37 18 * * *"
  workflow_dispatch:
permissions:
  contents: write
concurrency:
  group: bitfinex-repository-writer
  cancel-in-progress: false
```

Use `ubuntu-latest`, timeout 10 minutes, `actions/checkout@v6` with full history, `actions/setup-python@v6`, install `.[test,modeling]`, run `python -m pytest -q`, then `python -m bitfinex_lending.modeling`. Configure the Actions bot identity, stage only `data/modeling`, skip empty commits, commit `data: rebuild modeling dataset at <UTC> [skip ci]`, and retry one rejected push with pull/rebase. Do not use `continue-on-error` for tests or modeling.

- [x] **Step 4: Run workflow GREEN and full suite**

Run: `python -m pytest tests/test_workflow.py tests/test_modeling_workflow.py -v`

Expected: both workflow contracts pass.

Run: `python -m pytest -q`

Expected: all offline tests pass; the live integration test remains deselected.

- [x] **Step 5: Commit**

```bash
git add .github/workflows/collect-funding-books.yml .github/workflows/build-modeling-dataset.yml tests/test_modeling_workflow.py
git commit -m "ci: build modeling dataset daily"
```

---

### Task 5: Documentation, Local Production Verification, and GitHub Acceptance

**Files:**
- Modify: `README.md`
- Modify: `progress.md`
- Modify: `todo.md`
- Generated and tracked: `data/modeling/*.csv`

**Interfaces:**
- Consumes: completed command and workflow from Tasks 1-4.
- Produces: operator documentation, current insufficient-data outputs, and remote acceptance evidence.

- [x] **Step 1: Document command, schedule, outputs, and limits**

Add a README section documenting:

```powershell
python -m pip install -e ".[test,modeling]"
python -m bitfinex_lending.modeling
```

Describe the four `data/modeling` files, 168 eligible-row threshold, 80%／20% chronological split, three first-stage models, daily `18:37 UTC` schedule, manual workflow trigger, research-only status, and absence of automatic orders or guaranteed returns.

- [x] **Step 2: Update project tracking without premature claims**

In `todo.md`, mark raw-CSV ingestion, automated feature rebuild, two baselines, linear regression, MAE/RMSE/R², fixed evaluation/prediction CSVs, and daily workflow implementation complete. Add unchecked remote checks for manual workflow success and first scheduled run.

In `progress.md`, record the actual final test count and local command results. Do not claim trained models while current markets remain below 168 eligible rows.

- [x] **Step 3: Run local production path**

Run:

```powershell
python -m bitfinex_lending.modeling
```

Expected with the current repository data: three markets appear in `model_status.csv` with `insufficient_data`; `modeling_features.csv` contains current snapshots; evaluation and prediction files contain headers only.

Read all four CSVs and verify exact headers, market counts, one row per market status, and no raw-file modification.

- [x] **Step 4: Run final local verification and commit generated outputs**

Run:

```powershell
python -m pytest -q
git diff --check
git status --short
```

Expected: all offline tests pass, integration remains deselected, and only intended documentation plus `data/modeling` outputs are modified/untracked.

Commit:

```bash
git add README.md progress.md todo.md data/modeling
git commit -m "docs: deliver automated feature modeling"
```

- [x] **Step 5: Push and manually run the daily workflow**

Push the reviewed branch/default branch according to the selected finishing workflow. On GitHub, run **Build Bitfinex modeling dataset** with `workflow_dispatch`.

Expected: tests and modeling succeed; a `[skip ci]` modeling-data commit is created only if outputs differ; `data/raw` is unchanged.

- [x] **Step 6: Record GitHub evidence**

Record the manual run URL/ID, data commit SHA or no-change result, market statuses, and actual job duration in `progress.md`. Check the manual GitHub acceptance item in `todo.md`, commit, and push. Leave the scheduled-run item unchecked until an actual `schedule` event succeeds.

- [ ] **Step 7: Observe one scheduled run**

After the next `18:37 UTC` trigger, verify event `schedule`, successful tests/modeling, allowed scheduling delay, output consistency, and absence of unintended file changes. Record its run URL/ID and check the final scheduled acceptance item.
