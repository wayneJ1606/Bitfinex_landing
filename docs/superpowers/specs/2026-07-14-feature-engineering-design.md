# Bitfinex Feature Engineering Design

## Goal

Build a repeatable batch feature-engineering pipeline that reads persisted funding-book snapshots, calculates one feature row per market and observation time, stores the results in SQLite, and exports a UTF-8 modeling dataset CSV.

This milestone does not train models, run backtests, fabricate historical observations, or modify the existing data-collection command.

## Architecture

The pipeline uses SQLite `funding_book_snapshots` as its source of truth. Feature calculation remains independent from collection so formulas can be changed and the full derived dataset rebuilt deterministically.

The implementation has four boundaries:

- Snapshot loading reads normalized rows ordered by market and UTC observation time.
- Pure feature calculation groups rows into snapshots and derives current, lagged, and next-period values.
- Storage initializes and atomically replaces the complete derived feature dataset.
- A dedicated command runs the batch job and exports the complete `modeling_features` table to CSV.

The existing `python -m bitfinex_lending` collector remains unchanged. Feature generation is invoked separately with `python -m bitfinex_lending.features`.

## Feature Semantics

One feature row represents one `(market, fetched_at)` snapshot. Rows are ordered independently within each market using timezone-aware UTC timestamps.

The pipeline calculates:

- `market`: funding market identifier.
- `feature_time`: the snapshot's `fetched_at` value.
- `hour`: UTC hour from `feature_time`.
- `day_of_week`: UTC weekday where Monday is `0` and Sunday is `6`.
- `avg_rate`: arithmetic mean of all book-row rates.
- `weighted_avg_rate`: mean rate weighted by `abs(amount)`.
- `min_rate` and `max_rate`: extrema across the snapshot.
- `total_amount`: sum of `abs(amount)` so demand does not cancel supply.
- `avg_period`: arithmetic mean of book-row periods.
- `offer_count`: sum of the source `count` values for offer rows.
- `demand_count`: sum of the source `count` values for demand rows.
- `rate_spread`: `max_rate - min_rate`.
- `previous_weighted_avg_rate`: prior snapshot's weighted average for the same market.
- `rate_change`: current minus previous weighted average rate.
- `amount_change`: current minus previous total amount.
- `target_next_weighted_avg_rate`: next snapshot's weighted average for the same market.

For the first snapshot in a market, previous-period fields are `NULL`. For the last snapshot, the target is `NULL`. Such rows remain useful for current market observation; downstream model training must exclude rows whose target is `NULL`.

An empty source database produces no feature rows and is a successful no-op. A malformed timestamp, a zero total absolute amount, or an invalid source row is a feature-generation error rather than silently producing a misleading value.

## SQLite Schema and Rebuild Behavior

Add `modeling_features` with the columns specified in `requirements_design.md`. The pair `(market, feature_time)` is unique.

Feature generation uses a database transaction. Within that transaction it replaces the derived dataset from the currently persisted snapshots, ensuring removed or corrected snapshots cannot leave stale feature rows. A failure rolls back the entire feature update.

This full-rebuild approach is intentional for the MVP: it is deterministic, simple to validate, and appropriate for the current local data volume. Incremental recomputation is deferred until data size demonstrates a need.

## CSV Export

After a successful database update, export the complete `modeling_features` table to:

```text
data/csv/modeling_features.csv
```

The file uses UTF-8, a stable header matching the SQLite column names except the internal `id`, and rows ordered by `market`, then `feature_time`. Export uses a temporary file followed by atomic replacement. Nullable lag and target values are written as empty CSV fields.

If CSV export fails, the command returns a nonzero exit status and reports the error. The already committed feature table remains valid and can be exported again without recomputing source data.

## Command Behavior

`python -m bitfinex_lending.features` uses the default database and CSV locations from `Settings`. It initializes the feature table, loads snapshots, calculates and saves features, exports the CSV, and prints a concise summary containing source snapshot count, generated feature count, and output path.

Exit code `0` means the feature table and CSV represent the current source data, including the empty-source case. Exit code `1` means loading, calculation, persistence, or export failed. Errors are reported without exposing secrets or stack traces in normal command output.

## Testing

Development follows test-driven development.

- Pure calculation tests cover aggregation formulas, absolute-amount weighting, UTC calendar fields, market isolation, chronological ordering, lag values, next-period targets, and single-snapshot nullable fields.
- Validation tests cover malformed timestamps and invalid or zero-weight source data.
- Storage tests cover schema, atomic full rebuild, uniqueness, stale-row removal, and rollback.
- CSV tests cover exact header/order, UTF-8 output, nullable fields, empty datasets, atomic replacement, and temporary-file cleanup.
- Command tests cover successful summaries, empty input, configured paths, and nonzero failure behavior.
- The full existing unit suite must remain green and must not access the network.

## Scope Boundary

This milestone ends after verified feature persistence and CSV export. Baselines, regression models, XGBoost, evaluation metrics, backtesting, decision recommendations, authenticated APIs, and automatic lending remain out of scope.
