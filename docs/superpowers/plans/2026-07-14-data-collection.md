# Bitfinex Data Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested, one-shot Python collector that fetches `fUSD`, `fBTC`, and `fETH` funding books, persists results and logs in SQLite, and exports successful snapshots to UTF-8 CSV.

**Architecture:** A small `bitfinex_lending` package separates HTTP access, parsing, persistence, CSV export, orchestration, and the command-line entry point. Each market is processed independently under one run ID; SQLite is the audit source of truth and CSV is an atomic per-market export.

**Tech Stack:** Python 3.11+, requests, sqlite3, csv, dataclasses, pathlib, pytest

## Global Constraints

- The program is one-shot and is invoked with `python -m bitfinex_lending`; scheduling remains the responsibility of Windows Task Scheduler.
- Markets are processed in this exact order: `fUSD`, `fBTC`, `fETH`.
- No private API key, account access, order placement, lending action, feature engineering, modeling, or backtesting.
- Timestamps are timezone-aware UTC ISO 8601 strings.
- Default tests must not access the network; the live smoke test is marked `integration`.
- A failed market does not stop later markets; any failed market produces process exit code `1`.

---

## File Map

- `pyproject.toml`: package metadata, dependencies, pytest configuration, and default integration-test exclusion.
- `bitfinex_lending/config.py`: immutable runtime settings and defaults.
- `bitfinex_lending/models.py`: shared immutable data records and result types.
- `bitfinex_lending/parser.py`: strict funding-book row validation and conversion.
- `bitfinex_lending/client.py`: public HTTP transport and stable client exceptions.
- `bitfinex_lending/storage.py`: SQLite schema and transactional writes.
- `bitfinex_lending/csv_export.py`: atomic CSV creation.
- `bitfinex_lending/runner.py`: per-run orchestration and summary.
- `bitfinex_lending/__main__.py`: production dependency assembly and process exit.
- `tests/`: unit and integration tests matching the modules above.

### Task 1: Package foundation and strict parser

**Files:**
- Create: `pyproject.toml`
- Create: `bitfinex_lending/__init__.py`
- Create: `bitfinex_lending/config.py`
- Create: `bitfinex_lending/models.py`
- Create: `bitfinex_lending/parser.py`
- Create: `tests/test_parser.py`

**Interfaces:**
- Produces: `Settings`, `FundingBookRow`, `ParseError`, and `parse_book(payload, market, run_id, fetched_at) -> tuple[FundingBookRow, ...]`.

- [ ] **Step 1: Add packaging and test configuration**

Create `pyproject.toml` with Python `>=3.11`, runtime dependency `requests>=2.32,<3`, test dependency `pytest>=8,<9`, package discovery for `bitfinex_lending*`, an `integration` marker, and `addopts = "-m 'not integration'"`.

- [ ] **Step 2: Write parser tests first**

Cover an offer and demand row, preservation of market/run/time, empty payload, non-list root, wrong row length, booleans/non-numeric values, non-integral `period` or `count`, and zero amount. Assert invalid cases raise `ParseError` with stable messages.

```python
rows = parse_book(
    [[0.0002, 2, 3, 10.5], [0.0003, 7, 1, -4.0]],
    market="fUSD",
    run_id="run-1",
    fetched_at="2026-07-14T12:00:00+00:00",
)
assert [row.side for row in rows] == ["offer", "demand"]
```

- [ ] **Step 3: Run RED verification**

Run: `python -m pytest tests/test_parser.py -v`

Expected: collection fails because `bitfinex_lending.parser` does not exist.

- [ ] **Step 4: Implement minimal records, settings, and parser**

Use frozen dataclasses. `Settings` defaults to the three markets, `https://api-pub.bitfinex.com/v2`, `P0`, length `25`, timeout `10.0`, database `data/bitfinex_lending.sqlite3`, and CSV directory `data/csv`. Reject booleans, require integral `period` and `count`, and classify positive/negative amount.

```python
def parse_book(payload: object, market: str, run_id: str, fetched_at: str) -> tuple[FundingBookRow, ...]:
    if not isinstance(payload, list):
        raise ParseError("book payload must be a list")
    return tuple(_parse_row(row, market, run_id, fetched_at) for row in payload)
```

- [ ] **Step 5: Run GREEN verification**

Run: `python -m pytest tests/test_parser.py -v`

Expected: all parser tests pass.

- [ ] **Step 6: Commit checkpoint if Git is available**

Run: `git add pyproject.toml bitfinex_lending tests/test_parser.py && git commit -m "feat: add funding book parser"`

If Git is still unavailable, record the checkpoint in the final handoff and continue without fabricating a commit.

### Task 2: Public Bitfinex HTTP client

**Files:**
- Create: `bitfinex_lending/client.py`
- Create: `tests/test_client.py`

**Interfaces:**
- Consumes: API settings from `Settings`.
- Produces: `BitfinexClient.fetch_book(market) -> object` and `ClientError(code, message)` where code is one of `network_error`, `http_error`, `invalid_json`.

- [ ] **Step 1: Write client tests first**

Use a small fake session/response rather than the network. Verify exact URL, query parameter `len=25`, timeout forwarding, valid JSON return, request exception conversion, non-2xx conversion, and JSON decoding conversion.

```python
payload = client.fetch_book("fUSD")
assert payload == [[0.0002, 2, 1, 10.0]]
assert session.calls == [("https://api-pub.bitfinex.com/v2/book/fUSD/P0", {"len": 25}, 10.0)]
```

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_client.py -v`

Expected: collection fails because `bitfinex_lending.client` does not exist.

- [ ] **Step 3: Implement the client**

Inject a `requests.Session`-compatible object, call `get(url, params={"len": length}, timeout=timeout)`, call `raise_for_status()`, and convert only `requests.RequestException` and JSON decode failures into stable `ClientError` values.

- [ ] **Step 4: Run GREEN and regression verification**

Run: `python -m pytest tests/test_client.py tests/test_parser.py -v`

Expected: all tests pass without warnings.

- [ ] **Step 5: Commit checkpoint if Git is available**

Run: `git add bitfinex_lending/client.py tests/test_client.py && git commit -m "feat: add Bitfinex public API client"`

### Task 3: Transactional SQLite storage

**Files:**
- Create: `bitfinex_lending/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `FundingBookRow` records and run/market timestamps.
- Produces: `Storage.initialize()`, `record_success(rows, ...)`, `record_empty(...)`, `record_failure(...)`, and `StorageError`.

- [ ] **Step 1: Write schema and write-path tests first**

Against a real temporary SQLite file, verify all three tables and required columns, atomic success insertion, empty crawl log without snapshots, failed crawl/error records, and rollback when a row violates a constraint.

```python
storage.record_success(rows, started_at=started, finished_at=finished)
assert connection.execute("SELECT COUNT(*) FROM funding_book_snapshots").fetchone()[0] == 2
assert connection.execute("SELECT status, row_count FROM crawl_logs").fetchone() == ("success", 2)
```

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_storage.py -v`

Expected: collection fails because `bitfinex_lending.storage` does not exist.

- [ ] **Step 3: Implement schema and transaction methods**

Create the exact three tables in the approved design. Add checks for `side IN ('offer','demand')`, `status IN ('success','empty','failed')`, and nonnegative row counts. Open a new sqlite connection per operation, enable foreign keys, use the connection context manager for commit/rollback, and wrap sqlite errors as `StorageError`.

- [ ] **Step 4: Run GREEN and regression verification**

Run: `python -m pytest tests/test_storage.py tests/test_parser.py -v`

Expected: all tests pass and the rollback test leaves no partial snapshots.

- [ ] **Step 5: Commit checkpoint if Git is available**

Run: `git add bitfinex_lending/storage.py tests/test_storage.py && git commit -m "feat: persist collection results in SQLite"`

### Task 4: Atomic UTF-8 CSV export

**Files:**
- Create: `bitfinex_lending/csv_export.py`
- Create: `tests/test_csv_export.py`

**Interfaces:**
- Consumes: one non-empty tuple of `FundingBookRow` values for one market.
- Produces: `export_snapshot(rows, output_dir) -> Path` and `CsvExportError`.

- [ ] **Step 1: Write CSV tests first**

Verify exact column order, UTF-8 content, market/run/timestamp-based unique filename, returned path, target-directory creation, and cleanup of `.tmp` files after an injected replacement failure.

```python
path = export_snapshot(rows, tmp_path)
with path.open(encoding="utf-8", newline="") as stream:
    assert next(csv.reader(stream)) == [
        "run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"
    ]
```

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest tests/test_csv_export.py -v`

Expected: collection fails because `bitfinex_lending.csv_export` does not exist.

- [ ] **Step 3: Implement atomic export**

Require non-empty rows from one market/run, sanitize timestamp characters for Windows filenames, write with `newline=""` and `encoding="utf-8"`, then call `Path.replace`. On any exception, delete the temporary file and raise `CsvExportError`.

- [ ] **Step 4: Run GREEN and regression verification**

Run: `python -m pytest tests/test_csv_export.py tests/test_parser.py -v`

Expected: all tests pass and no temporary files remain.

- [ ] **Step 5: Commit checkpoint if Git is available**

Run: `git add bitfinex_lending/csv_export.py tests/test_csv_export.py && git commit -m "feat: export atomic funding snapshots"`

### Task 5: One-shot orchestration and CLI

**Files:**
- Modify: `bitfinex_lending/models.py`
- Create: `bitfinex_lending/runner.py`
- Create: `bitfinex_lending/__main__.py`
- Create: `tests/test_runner.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: client, parser, storage, exporter, settings, UUID factory, and UTC clock.
- Produces: `RunSummary`, `run_collection(...) -> RunSummary`, and `main() -> int`.

- [ ] **Step 1: Write runner tests first**

Verify exact market order, shared run ID, distinct UTC fetched times, success persistence/export, empty persistence without export, partial failure continuation, failed persistence, summary counts, exit code `0` for success/empty only, and exit code `1` for any failure.

```python
summary = run_collection(settings, client, storage, exporter, uuid_factory, clock)
assert client.markets == ["fUSD", "fBTC", "fETH"]
assert summary.exit_code == 1
assert [result.status for result in summary.results] == ["success", "failed", "success"]
```

- [ ] **Step 2: Run runner RED verification**

Run: `python -m pytest tests/test_runner.py -v`

Expected: collection fails because `bitfinex_lending.runner` does not exist.

- [ ] **Step 3: Implement orchestration**

Catch `ClientError`, `ParseError`, `CsvExportError`, and unexpected safe-to-report exceptions per market. Persist success only after CSV export succeeds so a CSV failure cannot be logged as success. If failure logging itself raises `StorageError`, re-raise it as a fatal run error.

- [ ] **Step 4: Run runner GREEN verification**

Run: `python -m pytest tests/test_runner.py -v`

Expected: all orchestration tests pass.

- [ ] **Step 5: Write CLI tests first**

Patch only the dependency-assembly boundary and verify stdout summary, stderr fatal errors, creation of configured data directories, and returned exit code.

- [ ] **Step 6: Run CLI RED verification**

Run: `python -m pytest tests/test_main.py -v`

Expected: collection fails because `bitfinex_lending.__main__` does not exist.

- [ ] **Step 7: Implement the CLI**

Construct default settings, requests session/client, storage, exporter, UUID factory, and UTC clock. Initialize storage before collection, print one concise line per market plus totals, and use `raise SystemExit(main())` under the module guard.

- [ ] **Step 8: Run GREEN and full unit suite**

Run: `python -m pytest -v`

Expected: all non-integration tests pass without network access.

- [ ] **Step 9: Commit checkpoint if Git is available**

Run: `git add bitfinex_lending tests/test_runner.py tests/test_main.py && git commit -m "feat: add one-shot collection command"`

### Task 6: Live API smoke test, documentation, and project status

**Files:**
- Create: `tests/integration/test_live_api.py`
- Create: `README.md`
- Modify: `todo.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: production `BitfinexClient` and parser.
- Produces: an opt-in live validation and operator instructions.

- [ ] **Step 1: Write the opt-in smoke test**

Mark it `pytest.mark.integration`, fetch `fUSD`, parse it, and assert every row has market `fUSD`, a valid side, and the requested fetched timestamp. This is the only test allowed to use the network.

- [ ] **Step 2: Verify default suite still excludes the smoke test**

Run: `python -m pytest -v`

Expected: all unit tests pass; the integration test is deselected.

- [ ] **Step 3: Run the live smoke test explicitly**

Run: `python -m pytest -m integration tests/integration/test_live_api.py -v`

Expected: pass when Bitfinex and the network are available. If unavailable, report the external failure without weakening the test.

- [ ] **Step 4: Document installation and operation**

Document virtual-environment creation, `python -m pip install -e .[test]`, unit tests, the opt-in smoke test, `python -m bitfinex_lending`, output locations, exit codes, and a Windows Task Scheduler example using the virtual environment's `python.exe` with the repository as the working directory.

- [ ] **Step 5: Update project tracking**

Mark only implemented and verified API exploration, project structure, request, parsing, error handling, timestamps, crawl/error logs, SQLite snapshot/log tables, and CSV snapshot items complete. Keep modeling, backtesting, and unimplemented storage tables open. Update `progress.md` with verification commands and the next milestone.

- [ ] **Step 6: Run final verification**

Run: `python -m pytest -v`

Run: `python -m bitfinex_lending`

Run a SQLite query that reports per-market snapshot and crawl-log counts for the generated run. Expected: tests pass; the live command attempts all three markets; successful markets have SQLite rows and CSV files; the command's exit code matches the per-market summary.

- [ ] **Step 7: Commit checkpoint if Git is available**

Run: `git add README.md tests/integration todo.md progress.md && git commit -m "docs: add collector operation guide"`

