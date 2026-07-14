# Bitfinex Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable batch pipeline that derives per-snapshot modeling features from SQLite, atomically replaces the derived table, and exports a stable UTF-8 CSV.

**Architecture:** Keep calculation pure and independent from collection. Extend the existing storage boundary for snapshot loading and transactional feature replacement, use a focused exporter for the complete modeling dataset, and expose a separate `python -m bitfinex_lending.features` command.

**Tech Stack:** Python 3.11+, dataclasses, datetime, sqlite3, csv, pathlib, pytest

## Global Constraints

- The existing `python -m bitfinex_lending` collection behavior must not change.
- SQLite `funding_book_snapshots` remains the source of truth.
- Feature rows are grouped by `(market, fetched_at)` and ordered by timezone-aware UTC time within each market.
- Amount-based calculations use `abs(amount)`.
- The derived table is rebuilt atomically; it is not incrementally appended.
- Empty source data is a successful no-op and still produces a header-only CSV.
- Default tests must not access the network.
- Modeling, evaluation, backtesting, and decision recommendations remain out of scope.
- If Git is unavailable, record each checkpoint in `progress.md` instead of fabricating commits.

---

## File Map

- `bitfinex_lending/models.py`: add immutable `ModelingFeature` record.
- `bitfinex_lending/feature_calculation.py`: pure grouping, validation, aggregation, lag, and target calculation.
- `bitfinex_lending/storage.py`: feature schema, source loading, atomic feature replacement, and ordered feature loading.
- `bitfinex_lending/feature_csv.py`: atomic header-stable modeling CSV export.
- `bitfinex_lending/features.py`: feature-pipeline orchestration and command entry point.
- `tests/test_feature_calculation.py`: pure feature and validation tests.
- `tests/test_feature_storage.py`: SQLite schema/rebuild/rollback tests.
- `tests/test_feature_csv.py`: CSV behavior tests.
- `tests/test_features.py`: pipeline and command tests.
- `README.md`, `todo.md`, `progress.md`: operator documentation and status.

### Task 1: Pure Feature Calculation

**Files:**
- Modify: `bitfinex_lending/models.py`
- Create: `bitfinex_lending/feature_calculation.py`
- Create: `tests/test_feature_calculation.py`

**Interfaces:**
- Consumes: `Sequence[FundingBookRow]`.
- Produces: frozen `ModelingFeature`, `FeatureCalculationError`, and `calculate_features(rows: Sequence[FundingBookRow]) -> tuple[ModelingFeature, ...]`.

- [ ] **Step 1: Write failing aggregation and chronology tests**

Create fixtures with two `fUSD` snapshots supplied out of order and one `fBTC` snapshot. Assert exact arithmetic means, `abs(amount)` weighted values and totals, UTC `hour`/`day_of_week`, summed source counts by side, spread, independent market ordering, lag fields, and next-period target:

```python
features = calculate_features(rows)
usd_first, usd_second, btc_only = features
assert [item.market for item in features] == ["fUSD", "fUSD", "fBTC"]
assert usd_first.weighted_avg_rate == pytest.approx(
    (0.0002 * 10.0 + 0.0004 * 30.0) / 40.0
)
assert usd_first.total_amount == 40.0
assert usd_first.offer_count == 2
assert usd_first.demand_count == 3
assert usd_first.previous_weighted_avg_rate is None
assert usd_first.target_next_weighted_avg_rate == usd_second.weighted_avg_rate
assert usd_second.rate_change == pytest.approx(
    usd_second.weighted_avg_rate - usd_first.weighted_avg_rate
)
assert btc_only.previous_weighted_avg_rate is None
assert btc_only.target_next_weighted_avg_rate is None
```

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_feature_calculation.py -v`

Expected: collection fails because `bitfinex_lending.feature_calculation` does not exist.

- [ ] **Step 3: Add the immutable feature record and minimal calculation**

Add all fields from the approved spec to `ModelingFeature`. In `feature_calculation.py`, group by `(market, fetched_at)`, parse with `datetime.fromisoformat`, reject naive timestamps, normalize ordering with `astimezone(timezone.utc)`, calculate current values, then use `dataclasses.replace` to populate adjacent lag and target fields per market.

```python
@dataclass(frozen=True)
class ModelingFeature:
    market: str
    feature_time: str
    hour: int
    day_of_week: int
    avg_rate: float
    weighted_avg_rate: float
    min_rate: float
    max_rate: float
    total_amount: float
    avg_period: float
    offer_count: int
    demand_count: int
    rate_spread: float
    previous_weighted_avg_rate: float | None
    rate_change: float | None
    amount_change: float | None
    target_next_weighted_avg_rate: float | None
```

- [ ] **Step 4: Write failing validation tests**

Assert `FeatureCalculationError` for an invalid ISO timestamp, a timestamp without UTC offset, zero total absolute amount, zero amount row, non-finite numeric values, side/amount mismatch, negative `count`, and inconsistent metadata inside one snapshot. Assert an empty input returns `()`.

- [ ] **Step 5: Implement stable validation messages**

Use messages prefixed with `invalid snapshot <market> at <fetched_at>:` and explicitly validate finite rates/amounts, positive periods, nonnegative counts, nonzero amounts, and `offer`/positive or `demand`/negative agreement before aggregation.

- [ ] **Step 6: Run GREEN verification**

Run: `python -m pytest tests/test_feature_calculation.py -v`

Expected: all feature-calculation tests pass.

- [ ] **Step 7: Run regression verification and checkpoint**

Run: `python -m pytest tests/test_parser.py tests/test_feature_calculation.py -v`

Expected: all selected tests pass. If Git is available, commit with `feat: calculate modeling features`; otherwise note the checkpoint for project tracking.

### Task 2: Transactional Feature Storage

**Files:**
- Modify: `bitfinex_lending/storage.py`
- Create: `tests/test_feature_storage.py`

**Interfaces:**
- Consumes: `Sequence[ModelingFeature]`.
- Produces: `Storage.load_snapshots() -> tuple[FundingBookRow, ...]`, `Storage.replace_features(features) -> None`, and `Storage.load_features() -> tuple[ModelingFeature, ...]`.

- [ ] **Step 1: Write failing schema and source-loading tests**

Initialize a temporary database and assert `modeling_features` has every approved column plus `UNIQUE (market, feature_time)`. Insert snapshots out of order and assert `load_snapshots()` returns `FundingBookRow` values ordered by market, UTC text time, and source `id`.

- [ ] **Step 2: Write failing rebuild and rollback tests**

Call `replace_features()` twice and assert stale rows disappear, current rows do not duplicate, nullable fields round-trip through `load_features()`, and ordering is stable. Inject an invalid duplicate feature key in the second rebuild and assert the previous dataset remains intact.

- [ ] **Step 3: Run RED verification**

Run: `python -m pytest tests/test_feature_storage.py -v`

Expected: tests fail because the feature schema and storage methods are absent.

- [ ] **Step 4: Extend the schema and implement storage methods**

Add `modeling_features` with numeric checks, nullable lag/target columns, and the unique key. Convert SQL rows explicitly to dataclasses. Rebuild within one connection context:

```python
with self._connect() as connection:
    connection.execute("DELETE FROM modeling_features")
    connection.executemany(
        """INSERT INTO modeling_features (
            market, feature_time, hour, day_of_week, avg_rate,
            weighted_avg_rate, min_rate, max_rate, total_amount,
            avg_period, offer_count, demand_count, rate_spread,
            previous_weighted_avg_rate, rate_change, amount_change,
            target_next_weighted_avg_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        feature_parameter_rows,
    )
```

Wrap `sqlite3.Error` in operation-specific `StorageError` messages.

- [ ] **Step 5: Run GREEN and regression verification**

Run: `python -m pytest tests/test_feature_storage.py tests/test_storage.py -v`

Expected: all tests pass, including rollback and all existing collector storage tests.

- [ ] **Step 6: Checkpoint**

If Git is available, commit with `feat: persist modeling features`; otherwise note the checkpoint for project tracking.

### Task 3: Atomic Modeling CSV

**Files:**
- Create: `bitfinex_lending/feature_csv.py`
- Create: `tests/test_feature_csv.py`

**Interfaces:**
- Consumes: `Sequence[ModelingFeature]` and an output directory.
- Produces: `export_modeling_features(features: Sequence[ModelingFeature], output_directory: Path) -> Path` and `FeatureCsvError`.

- [ ] **Step 1: Write failing CSV tests**

Assert the exact header below, stable input ordering by market/time, empty strings for `None`, UTF-8 output at `modeling_features.csv`, header-only output for empty input, directory creation, atomic replacement, and `.tmp` cleanup after an injected replacement failure.

```python
FIELD_NAMES = (
    "market", "feature_time", "hour", "day_of_week", "avg_rate",
    "weighted_avg_rate", "min_rate", "max_rate", "total_amount",
    "avg_period", "offer_count", "demand_count", "rate_spread",
    "previous_weighted_avg_rate", "rate_change", "amount_change",
    "target_next_weighted_avg_rate",
)
```

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_feature_csv.py -v`

Expected: collection fails because `bitfinex_lending.feature_csv` does not exist.

- [ ] **Step 3: Implement atomic export**

Sort rows by `(market, parsed UTC feature_time)`, create the output directory, write with `encoding="utf-8"` and `newline=""`, and replace the target using `Path.replace`. Convert `None` to `""`. On `OSError` or `csv.Error`, remove the temporary file and raise `FeatureCsvError`.

- [ ] **Step 4: Run GREEN and regression verification**

Run: `python -m pytest tests/test_feature_csv.py tests/test_csv_export.py -v`

Expected: all tests pass and no temporary files remain.

- [ ] **Step 5: Checkpoint**

If Git is available, commit with `feat: export modeling feature dataset`; otherwise note the checkpoint for project tracking.

### Task 4: Pipeline Command, Documentation, and Status

**Files:**
- Create: `bitfinex_lending/features.py`
- Create: `tests/test_features.py`
- Modify: `README.md`
- Modify: `todo.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: `Settings`, `Storage`, `calculate_features`, and `export_modeling_features`.
- Produces: `FeatureRunSummary`, `run_feature_pipeline(storage, exporter, output_directory) -> FeatureRunSummary`, and `main(settings: Settings | None = None) -> int`.

- [ ] **Step 1: Write failing pipeline tests**

Use fakes to assert the exact sequence `load_snapshots`, calculate, `replace_features`, export; summary source/feature counts and output path; and empty-input success with a header-only export. Assert calculation, storage, and export errors are propagated to the command boundary.

- [ ] **Step 2: Write failing command tests**

Patch only `build_dependencies`/pipeline assembly. Assert configured directories are created, success prints `source_rows=<n> features=<n> csv=<path>` to stdout and returns `0`, while `OSError`, `StorageError`, `FeatureCalculationError`, and `FeatureCsvError` print `fatal: <message>` to stderr and return `1`.

- [ ] **Step 3: Run RED verification**

Run: `python -m pytest tests/test_features.py -v`

Expected: collection fails because `bitfinex_lending.features` does not exist.

- [ ] **Step 4: Implement pipeline and module command**

Use a frozen summary record and keep dependency assembly patchable:

```python
@dataclass(frozen=True)
class FeatureRunSummary:
    source_row_count: int
    feature_count: int
    csv_path: Path

def run_feature_pipeline(storage, exporter, output_directory):
    snapshots = storage.load_snapshots()
    features = calculate_features(snapshots)
    storage.replace_features(features)
    csv_path = exporter(features, output_directory)
    return FeatureRunSummary(len(snapshots), len(features), csv_path)
```

`main()` builds `Settings` and `Storage`, initializes storage, runs the pipeline, prints one summary line, and uses `raise SystemExit(main())` under the module guard.

- [ ] **Step 5: Run GREEN and the full unit suite**

Run: `python -m pytest tests/test_features.py -v`

Run: `python -m pytest -v`

Expected: every unit test passes and the integration smoke test remains deselected.

- [ ] **Step 6: Document operation and update tracking**

Add `python -m bitfinex_lending.features`, output location, nullable first/last fields, full-rebuild semantics, and data-volume caveat to `README.md`. Mark the implemented `modeling_features`, feature columns, and modeling-feature CSV items complete in `todo.md`. Add verification evidence and make model baselines the next milestone in `progress.md`.

- [ ] **Step 7: Run production-path verification**

Run: `python -m bitfinex_lending.features`

Run a read-only SQLite query for feature counts per market and inspect the CSV header. Expected with the current database: one feature row for each market observation time; first/last nullable fields reflect available history; CSV and SQLite counts match.

- [ ] **Step 8: Run final verification and checkpoint**

Run: `python -m pytest -v`

Expected: all unit tests pass with the integration test deselected. If Git is available, commit with `feat: add feature engineering pipeline`; otherwise record all four checkpoints in the final handoff.
