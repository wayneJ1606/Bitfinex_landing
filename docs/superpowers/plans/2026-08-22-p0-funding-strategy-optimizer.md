# P0 Funding Strategy Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, read-only Bitfinex funding optimizer that compares 1,000–10,000 USDT allocations over 30 days and produces an honest highest-return recommendation plus a downside-stable alternative.

**Architecture:** Keep the existing collectors and next-rate model, but add a separate P0 pipeline with focused modules for official interest math, normalized hourly market history, historical fill statistics, capital allocation, walk-forward evaluation, atomic outputs, and a static local dashboard. The daily pipeline reads local files only, never calls authenticated write endpoints, and promotes a new `latest` result only after every output succeeds.

**Tech Stack:** Python 3.11+, standard-library dataclasses/Decimal/CSV/JSON/HTML, existing scikit-learn model outputs, pytest 8, PowerShell Windows Task Scheduler.

## Global Constraints

- USDT is mandatory; `fUST` is the Bitfinex API symbol and must display as `USDT`, never as the UST asset.
- BTC and ETH produce results only when their own data gates pass; otherwise output `insufficient_data`.
- Public visible offers use a fixed 15% fee; hidden offers and LEO discounts are out of scope.
- Capital levels are exactly 1,000 through 10,000 USDT in 1,000-unit increments, with at most ten concurrent tranches.
- Candidate periods are exactly 2, 5, 10, and 30 days.
- Repricing waits are exactly 1, 3, 6, 12, and 24 hours.
- Rate candidates are the 10th, 25th, 50th, 75th, and 90th percentiles calculated from past-only data.
- Formal status requires 60 continuous days, at least 90% hourly coverage, no public gap over 6 hours, and at least 30 evaluable observations per strategy cell.
- Walk-forward evaluation starts with a 30-day historical window and never reads future data for a decision.
- Primary ranking is 30-day ending capital; the stable alternative maximizes the 10th-percentile 30-day net profit.
- Outputs are read-only research results, not investment advice, and no module may submit, modify, or cancel an order.
- Private raw data and complete offer identifiers remain local and never appear in report, dashboard, or GitHub-safe outputs.

---

## File Responsibility Map

- `bitfinex_lending/config.py`: public funding-book market list, including `fUST`.
- `bitfinex_lending/p0_economics.py`: authoritative Decimal interest, fee, tranche, and compounding rules.
- `bitfinex_lending/p0_market_history.py`: normalize daily public CSV files into hourly observations without treating `fUSD` as USDT.
- `bitfinex_lending/p0_fill_statistics.py`: past-only rate quantiles, fill/wait/capacity statistics, and optional private calibration.
- `bitfinex_lending/p0_strategy_optimizer.py`: allocate 1,000-unit tranches and choose highest-return/stable portfolios.
- `bitfinex_lending/p0_walk_forward.py`: chronological evaluation, three baselines, and with/without prediction comparison.
- `bitfinex_lending/p0_strategy_output.py`: atomic CSV/JSON/Markdown/status publishing and last-good preservation.
- `bitfinex_lending/p0_dashboard.py`: generate one static local HTML interface from dashboard JSON.
- `bitfinex_lending/p0_strategy_pipeline.py`: one read-only CLI orchestration boundary.
- `scripts/install-p0-strategy-analysis.ps1`: preview or register the daily 10:00 Asia/Taipei task.
- `docs/P0_STRATEGY_OPTIMIZER.md`: operator instructions and result interpretation.

---

### Task 1: Add USDT funding-book collection

**Files:**
- Modify: `bitfinex_lending/config.py`
- Modify: `tests/test_local_stable_collector.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: existing `Settings.markets` used by `run_collection()`.
- Produces: hourly `data/raw/YYYY/MM/DD/fUST.csv` rows with `market=fUST`.

- [ ] **Step 1: Write failing collection configuration tests**

```python
from bitfinex_lending.config import Settings


def test_default_markets_include_usdt_without_removing_existing_assets() -> None:
    assert Settings().markets == ("fUSD", "fUST", "fBTC", "fETH")
```

Extend the existing collector test client assertion so one run must request `fUST` exactly once and export a `MarketResult` for it.

- [ ] **Step 2: Run the focused tests and confirm the missing market failure**

Run: `python -m pytest tests/test_local_stable_collector.py tests/test_main.py -q`

Expected: FAIL because `Settings().markets` does not contain `fUST`.

- [ ] **Step 3: Add `fUST` to the canonical funding-book list**

```python
@dataclass(frozen=True)
class Settings:
    markets: tuple[str, ...] = ("fUSD", "fUST", "fBTC", "fETH")
```

Do not rename `fUSD`; USD and USDT remain separate markets.

- [ ] **Step 4: Verify collection behavior**

Run: `python -m pytest tests/test_local_stable_collector.py tests/test_main.py -q`

Expected: PASS, including one `fUST` funding-book request.

- [ ] **Step 5: Commit the isolated collector change**

```powershell
git add bitfinex_lending/config.py tests/test_local_stable_collector.py tests/test_main.py
git commit -m "feat: collect USDT funding book snapshots"
```

---

### Task 2: Implement official interest and capital rules

**Files:**
- Create: `bitfinex_lending/p0_economics.py`
- Create: `tests/test_p0_economics.py`

**Interfaces:**
- Produces: `billable_seconds(actual_seconds, minimum_one_hour) -> int`, `gross_interest(principal, daily_rate, seconds) -> Decimal`, `net_interest(...) -> Decimal`, `capital_levels() -> tuple[Decimal, ...]`, and `split_capital(principal) -> tuple[Decimal, ...]`.
- Used by: optimizer, baselines, report validation.

- [ ] **Step 1: Write failing tests for the official example and boundaries**

```python
from decimal import Decimal
import pytest

from bitfinex_lending.p0_economics import (
    EconomicsError,
    capital_levels,
    gross_interest,
    net_interest,
    billable_seconds,
    split_capital,
)


def test_official_10000_usdt_example_uses_api_decimal_rate() -> None:
    assert gross_interest(Decimal("10000"), Decimal("0.0006"), 86400) == Decimal("6.0000")
    assert net_interest(Decimal("10000"), Decimal("0.0006"), 86400) == Decimal("5.100000")


def test_capital_grid_and_tranches_are_exact() -> None:
    assert capital_levels() == tuple(Decimal(index * 1000) for index in range(1, 11))
    assert split_capital(Decimal("3000")) == (Decimal("1000"),) * 3


def test_manual_return_minimum_can_bill_one_full_hour() -> None:
    assert billable_seconds(600, minimum_one_hour=True) == 3600
    assert billable_seconds(600, minimum_one_hour=False) == 600


@pytest.mark.parametrize("seconds", [-1, 0])
def test_interest_rejects_non_positive_duration(seconds: int) -> None:
    with pytest.raises(EconomicsError):
        net_interest(Decimal("1000"), Decimal("0.0002"), seconds)
```

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m pytest tests/test_p0_economics.py -q`

Expected: FAIL with `ModuleNotFoundError: bitfinex_lending.p0_economics`.

- [ ] **Step 3: Implement Decimal-safe economics**

```python
from decimal import Decimal

SECONDS_PER_DAY = Decimal("86400")
VISIBLE_PROVIDER_FEE = Decimal("0.15")
TRANCHE = Decimal("1000")


class EconomicsError(ValueError):
    pass


def _positive(value: Decimal, name: str) -> Decimal:
    number = Decimal(value)
    if not number.is_finite() or number <= 0:
        raise EconomicsError(f"{name} must be finite and greater than zero")
    return number


def gross_interest(principal: Decimal, daily_rate: Decimal, seconds: int) -> Decimal:
    amount = _positive(principal, "principal")
    rate = _positive(daily_rate, "daily_rate")
    if isinstance(seconds, bool) or seconds <= 0:
        raise EconomicsError("seconds must be greater than zero")
    return amount * rate * Decimal(seconds) / SECONDS_PER_DAY


def billable_seconds(actual_seconds: int, minimum_one_hour: bool) -> int:
    if isinstance(actual_seconds, bool) or actual_seconds <= 0:
        raise EconomicsError("actual_seconds must be greater than zero")
    return max(actual_seconds, 3600) if minimum_one_hour else actual_seconds


def net_interest(principal: Decimal, daily_rate: Decimal, seconds: int) -> Decimal:
    return gross_interest(principal, daily_rate, seconds) * (Decimal("1") - VISIBLE_PROVIDER_FEE)


def capital_levels() -> tuple[Decimal, ...]:
    return tuple(TRANCHE * index for index in range(1, 11))


def split_capital(principal: Decimal) -> tuple[Decimal, ...]:
    amount = _positive(principal, "principal")
    if amount not in capital_levels():
        raise EconomicsError("principal must be 1000 through 10000 in 1000-unit increments")
    return (TRANCHE,) * int(amount / TRANCHE)
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_p0_economics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_economics.py tests/test_p0_economics.py
git commit -m "feat: add official funding economics"
```

---

### Task 3: Normalize public hourly history and enforce data readiness

**Files:**
- Create: `bitfinex_lending/p0_market_history.py`
- Create: `tests/test_p0_market_history.py`
- Modify: `bitfinex_lending/p0_data_readiness.py`
- Modify: `tests/test_p0_data_readiness.py`

**Interfaces:**
- Produces `MarketHour(observed_at, api_symbol, asset, frr, ask_rate, visible_demand_amount, traded_high, traded_volume, funding_amount_used)`.
- Produces `load_market_hours(market_root: Path, raw_root: Path, api_symbol: str) -> tuple[MarketHour, ...]`.
- Readiness consumes a strategy coverage CSV with `strategy_id,observations` and classifies private checks as diagnostics rather than blockers.

- [ ] **Step 1: Write failing loader tests with daily partitions**

```python
def _write_csv(path: Path, fields: tuple[str, ...], row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def _write_market_fixture(root: Path, market: str, collected_at: str) -> None:
    day = root / "market"
    suffix = Path("2026/08/01") / f"{market}.csv"
    _write_csv(
        day / "ticker" / suffix,
        ("collected_at", "market", "frr", "ask", "ask_size"),
        {"collected_at": collected_at, "market": market, "frr": 0.0002, "ask": 0.00021, "ask_size": 5000},
    )
    _write_csv(
        day / "funding_candles" / suffix,
        ("collected_at", "market", "mts", "high", "volume"),
        {"collected_at": collected_at, "market": market, "mts": 1785545220000, "high": 0.0003, "volume": 10000},
    )
    _write_csv(
        day / "funding_stats" / suffix,
        ("collected_at", "market", "mts", "funding_amount_used"),
        {"collected_at": collected_at, "market": market, "mts": 1785545220000, "funding_amount_used": 1000000},
    )
    _write_csv(
        root / "raw" / "2026" / "08" / "01" / f"{market}.csv",
        ("run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"),
        {"run_id": "r1", "market": market, "rate": 0.0002, "period": 2, "count": 1, "amount": -8000, "side": "demand", "fetched_at": collected_at},
    )


def test_loads_fust_as_usdt_and_never_substitutes_fusd(tmp_path: Path) -> None:
    _write_market_fixture(tmp_path, "fUST", "2026-08-01T00:47:00+00:00")
    _write_market_fixture(tmp_path, "fUSD", "2026-08-01T00:47:00+00:00")
    rows = load_market_hours(tmp_path / "market", tmp_path / "raw", "fUST")
    assert len(rows) == 1
    assert rows[0].api_symbol == "fUST"
    assert rows[0].asset == "USDT"
```

Add cases that reject naive timestamps, non-finite rates, duplicate hourly keys, and a missing ticker/candle pairing.

- [ ] **Step 2: Run the loader test and confirm import failure**

Run: `python -m pytest tests/test_p0_market_history.py -q`

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement the normalized immutable row and as-of joins**

```python
@dataclass(frozen=True)
class MarketHour:
    observed_at: datetime
    api_symbol: str
    asset: str
    frr: float
    ask_rate: float
    visible_demand_amount: float
    traded_high: float
    traded_volume: float
    funding_amount_used: float


ASSET_BY_SYMBOL = {"fUST": "USDT", "fBTC": "BTC", "fETH": "ETH"}
```

Load `ticker`, `funding_candles`, `funding_stats`, and raw funding-book rows recursively, deduplicate by stable keys, and join only observations from the same API symbol. For each ticker timestamp, use the latest candle/stat/book timestamp not later than the ticker and no more than 90 minutes old. `visible_demand_amount` is the sum of absolute raw-book amounts whose `side=demand`; never merge `fUSD` rows into `fUST`.

- [ ] **Step 4: Change formal readiness to public-data gates**

Extend `ReadinessConfig` with exact defaults:

```python
min_public_hours: float = 1440.0
min_strategy_observations: int = 30
max_public_gap_minutes: float = 360.0
```

The formal blocking checks are `public_history_duration`, `public_hourly_coverage`, `public_max_gap`, and `strategy_observations`. Keep private success, offer, trade, and alignment metrics under `diagnostics`; their failure must not change formal readiness.

- [ ] **Step 5: Verify readiness behavior**

Run: `python -m pytest tests/test_p0_market_history.py tests/test_p0_data_readiness.py -q`

Expected: PASS. A 60-day/90%-coverage fixture is `ready`; missing private events alone remains `ready`; any strategy cell below 30 observations is `not_ready`.

- [ ] **Step 6: Commit**

```powershell
git add bitfinex_lending/p0_market_history.py bitfinex_lending/p0_data_readiness.py tests/test_p0_market_history.py tests/test_p0_data_readiness.py
git commit -m "feat: normalize P0 market history and readiness"
```

---

### Task 4: Estimate rate candidates, fills, waits, and capacity

**Files:**
- Create: `bitfinex_lending/p0_fill_statistics.py`
- Create: `tests/test_p0_fill_statistics.py`

**Interfaces:**
- Consumes: chronological `MarketHour` rows, optional `p0_offer_trade_matches.csv` rows, and optional completed private credit/loan durations.
- Produces: `CandidateEstimate` rows for every 5 quantiles × 4 periods × 5 waits.
- Produces: `estimate_candidates(history, as_of, private_matches=(), private_durations=()) -> tuple[CandidateEstimate, ...]`.

- [ ] **Step 1: Write synthetic history tests**

```python
def hourly_history(days: int, end: str) -> tuple[MarketHour, ...]:
    end_at = datetime.fromisoformat(end)
    start = end_at - timedelta(days=days)
    return tuple(
        MarketHour(
            observed_at=start + timedelta(hours=index),
            api_symbol="fUST",
            asset="USDT",
            frr=0.0002,
            ask_rate=0.0002 + (index % 5) * 0.00001,
            visible_demand_amount=10_000.0,
            traded_high=0.0003,
            traded_volume=20_000.0,
            funding_amount_used=1_000_000.0,
        )
        for index in range(days * 24 + 1)
    )


def test_estimates_all_100_strategy_cells_from_past_only() -> None:
    history = hourly_history(days=35, end="2026-08-05T00:00:00+00:00")
    estimates = estimate_candidates(history, as_of=datetime.fromisoformat("2026-08-01T00:00:00+00:00"))
    assert len(estimates) == 5 * 4 * 5
    assert {item.period_days for item in estimates} == {2, 5, 10, 30}
    assert {item.wait_hours for item in estimates} == {1, 3, 6, 12, 24}
    assert all(item.training_end <= datetime.fromisoformat("2026-08-01T00:00:00+00:00") for item in estimates)
```

Add exact cases where a candidate fills only when a later candle high reaches the rate, `deployable_amount` is capped by executed volume and visible demand amount, and private samples below 30 set `calibration_status="insufficient_private_data"`.

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m pytest tests/test_p0_fill_statistics.py -q`

Expected: FAIL because the estimator does not exist.

- [ ] **Step 3: Define the estimator contract**

```python
RATE_QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)
PERIOD_DAYS = (2, 5, 10, 30)
WAIT_HOURS = (1, 3, 6, 12, 24)


@dataclass(frozen=True)
class CandidateEstimate:
    strategy_id: str
    api_symbol: str
    asset: str
    as_of: datetime
    rate_quantile: float
    daily_rate: float
    period_days: int
    wait_hours: int
    observations: int
    fills: int
    fill_probability: float
    average_wait_hours: float
    deployable_amount: float
    expected_duration_hours: float
    expected_net_profit_per_1000: float
    net_profit_p10_per_1000: float
    calibration_status: str
    duration_status: str
```

For each historical decision hour, a simulated visible offer fills at the first future candle within the wait window whose `traded_high >= candidate_rate`. Its deployable amount is `min(visible_demand_amount, traded_volume)` and its wait is the elapsed whole/fractional hours. Non-fills wait the full configured window. Calculate all rates from rows strictly before `as_of`.

When at least 30 comparable private outcomes exist, blend public and private fill counts with a fixed public prior weight of 30:

```python
calibrated = (public_probability * 30 + private_fills) / (30 + private_observations)
```

Below 30 private outcomes, retain the public probability and label the result `insufficient_private_data`.

Use completed private credit/loan lifecycle durations only when at least 30 comparable closed durations exist. Otherwise set `expected_duration_hours = period_days * 24`, label `duration_status="nominal_period_assumption"`, and propagate that limitation to every output; never imply that the borrower is guaranteed to keep funds for the full term.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_p0_fill_statistics.py -q`

Expected: PASS with exactly 100 cells per asset/as-of point.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_fill_statistics.py tests/test_p0_fill_statistics.py
git commit -m "feat: estimate historical funding fills"
```

---

### Task 5: Optimize tranches and model compounding

**Files:**
- Create: `bitfinex_lending/p0_strategy_optimizer.py`
- Create: `tests/test_p0_strategy_optimizer.py`

**Interfaces:**
- Consumes: `CandidateEstimate` rows and one approved capital level.
- Produces: `StrategyLeg` and `PortfolioResult` for `highest_return` and `stable_alternative`.
- Produces: `optimize_portfolios(estimates, principal, horizon_days=30) -> tuple[PortfolioResult, PortfolioResult]`.

- [ ] **Step 1: Write failing allocation tests**

```python
def candidate(
    strategy_id: str,
    *,
    expected: float,
    p10: float,
    deployable: float,
) -> CandidateEstimate:
    return CandidateEstimate(
        strategy_id=strategy_id,
        api_symbol="fUST",
        asset="USDT",
        as_of=datetime(2026, 8, 1, tzinfo=timezone.utc),
        rate_quantile=0.5,
        daily_rate=0.0002,
        period_days=2,
        wait_hours=1,
        observations=100,
        fills=80,
        fill_probability=0.8,
        average_wait_hours=0.5,
        deployable_amount=deployable,
        expected_duration_hours=48.0,
        expected_net_profit_per_1000=expected,
        net_profit_p10_per_1000=p10,
        calibration_status="public_only",
        duration_status="nominal_period_assumption",
    )


def test_3000_principal_selects_three_1000_tranches_with_capacity_limit() -> None:
    estimates = (
        candidate("high", expected=12, p10=2, deployable=2000),
        candidate("stable", expected=9, p10=6, deployable=5000),
    )
    highest, stable = optimize_portfolios(estimates, Decimal("3000"))
    assert sum(leg.starting_principal for leg in highest.legs) == Decimal("3000")
    assert [leg.strategy_id for leg in highest.legs].count("high") == 2
    assert stable.portfolio_type == "stable_alternative"
    assert all(leg.strategy_id == "stable" for leg in stable.legs)
```

Add tests for 1,000 and 10,000 capital, 15% fee inclusion, idle time, returned principal and interest reinvestment, and rejection of non-approved capital.

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m pytest tests/test_p0_strategy_optimizer.py -q`

Expected: FAIL because the optimizer module is absent.

- [ ] **Step 3: Define portfolio result types**

```python
@dataclass(frozen=True)
class StrategyLeg:
    strategy_id: str
    starting_principal: Decimal
    daily_rate: Decimal
    period_days: int
    wait_hours: int
    fill_probability: float
    expected_wait_hours: float
    expected_net_interest: Decimal
    expected_ending_capital: Decimal


@dataclass(frozen=True)
class PortfolioResult:
    asset: str
    principal: Decimal
    portfolio_type: str
    legs: tuple[StrategyLeg, ...]
    gross_interest: Decimal
    fee: Decimal
    net_interest: Decimal
    ending_capital: Decimal
    idle_fraction: float
    net_profit_p10: Decimal
```

For each candidate, calculate one expected cycle as:

```text
cycle_hours = fill_probability × (average_wait_hours + expected_duration_hours)
              + (1 - fill_probability) × wait_hours
profit_per_cycle = fill_probability × net_interest(1000, daily_rate, round(expected_duration_hours × 3600))
```

Repeat complete expected cycles within 720 hours; add returned principal and interest before the next cycle. Convert `deployable_amount` into `floor(deployable_amount / 1000)` available slots. Select highest expected ending capital for the primary portfolio and highest `net_profit_p10_per_1000` for the stable portfolio until all tranches are assigned.

- [ ] **Step 4: Verify optimizer tests**

Run: `python -m pytest tests/test_p0_economics.py tests/test_p0_strategy_optimizer.py -q`

Expected: PASS with no portfolio exceeding market capacity or ten legs.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_strategy_optimizer.py tests/test_p0_strategy_optimizer.py
git commit -m "feat: optimize P0 funding allocations"
```

---

### Task 6: Add walk-forward evaluation and fair baselines

**Files:**
- Create: `bitfinex_lending/p0_walk_forward.py`
- Create: `tests/test_p0_walk_forward.py`
- Modify: `bitfinex_lending/p0_fixed_baselines.py`
- Modify: `tests/test_p0_fixed_baselines.py`

**Interfaces:**
- Consumes: normalized market history, optional `ModelPrediction` rows, and optional private matches.
- Produces: `WalkForwardResult` rows and strategy-cell observation coverage.
- Baselines: `fixed_median` = q50/2-day/24-hour; `frr` = current FRR/2-day/1-hour; `quick_fill` = q10/2-day/1-hour.

- [ ] **Step 1: Replace stale baseline defaults in tests**

```python
assert DEFAULT_PRINCIPALS == tuple(float(index * 1000) for index in range(1, 11))
assert DEFAULT_PERIODS == (2, 5, 10, 30)
assert DEFAULT_QUANTILES == (0.10, 0.25, 0.50, 0.75, 0.90)
```

Remove assertions that treat 160 USDT, 7 days, or 15 days as P0 defaults.

- [ ] **Step 2: Write walk-forward leakage and baseline tests**

```python
def hourly_history(days: int) -> tuple[MarketHour, ...]:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    return tuple(
        MarketHour(
            observed_at=start + timedelta(hours=index),
            api_symbol="fUST",
            asset="USDT",
            frr=0.0002,
            ask_rate=0.0002,
            visible_demand_amount=20_000.0,
            traded_high=0.0003,
            traded_volume=50_000.0,
            funding_amount_used=1_000_000.0,
        )
        for index in range(days * 24 + 1)
    )


def test_walk_forward_uses_30_days_before_each_decision_and_scores_complete_outcomes() -> None:
    rows = hourly_history(days=61)
    result = run_walk_forward(rows, predictions=(), private_matches=())
    assert result.training_start == rows[0].observed_at
    assert result.first_decision_at >= rows[0].observed_at + timedelta(days=30)
    assert result.last_decision_at <= rows[-1].observed_at - timedelta(days=30)
    assert {row.strategy_type for row in result.results} >= {
        "fixed_median", "frr", "quick_fill", "optimized_without_prediction"
    }
```

Add a future outlier after a decision and assert it cannot change that decision's candidate quantiles. Add prediction rows and assert both `optimized_with_prediction` and `optimized_without_prediction` exist.

- [ ] **Step 3: Implement daily walk-forward decisions**

```python
@dataclass(frozen=True)
class WalkForwardResult:
    asset: str
    generated_at: datetime
    training_start: datetime
    first_decision_at: datetime
    last_decision_at: datetime
    results: tuple[PortfolioResult, ...]
    strategy_observations: tuple[tuple[str, int], ...]
```

Evaluate one decision per UTC day corresponding to 10:00 Asia/Taipei (02:00 UTC). Require 30 full prior days and 30 full future days. The prediction-assisted variant may select only candidate rates at or below the predicted next rate; if none qualify, use the lowest candidate and record the fallback. The unassisted variant evaluates all candidates.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_p0_fixed_baselines.py tests/test_p0_walk_forward.py -q`

Expected: PASS; no decision changes when only later unavailable data changes.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_fixed_baselines.py bitfinex_lending/p0_walk_forward.py tests/test_p0_fixed_baselines.py tests/test_p0_walk_forward.py
git commit -m "feat: add P0 walk-forward comparisons"
```

---

### Task 7: Publish consistent CSV, Markdown, JSON, and failure status

**Files:**
- Create: `bitfinex_lending/p0_strategy_output.py`
- Create: `tests/test_p0_strategy_output.py`

**Interfaces:**
- Consumes: one sanitized canonical `dict[str, object]` built from `WalkForwardResult`, readiness, and current BTC/USDT and ETH/USDT prices.
- Produces atomically under `data/modeling/p0_strategy/latest/`: `strategy_results.csv`, `report.md`, `dashboard_data.json`, `status.json`.
- Failure updates only `data/metadata/p0_strategy_status.json` and preserves the prior `latest` directory.
- Produces `OutputPaths(csv_path: Path, report_path: Path, json_path: Path, status_path: Path)` from `publish_strategy_outputs(payload, output_root)`.

- [ ] **Step 1: Write cross-format consistency and privacy tests**

```python
def test_publish_uses_one_canonical_payload_for_all_formats(tmp_path: Path) -> None:
    payload = {
        "generated_at": "2026-10-01T02:00:00+00:00",
        "readiness_status": "formal",
        "limitations": ["研究用途，不構成投資建議"],
        "results": [{
            "asset": "USDT",
            "principal": "1000",
            "portfolio_type": "highest_return",
            "leg_count": 1,
            "daily_rates": ["0.0002"],
            "period_days": [2],
            "wait_hours": [1],
            "fill_probability": 0.8,
            "average_wait_hours": 0.5,
            "gross_interest": "4.0",
            "fee": "0.6",
            "net_interest": "3.4",
            "ending_capital": "1003.4",
            "idle_fraction": 0.2,
            "net_profit_p10": "1.2",
        }],
    }
    paths = publish_strategy_outputs(payload, tmp_path)
    csv_rows = list(csv.DictReader(paths.csv_path.open(encoding="utf-8")))
    dashboard = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert csv_rows[0]["ending_capital"] == dashboard["results"][0]["ending_capital"]
    assert csv_rows[0]["asset"] == "USDT"
    assert "fUST" not in paths.report_path.read_text(encoding="utf-8")
```

Add tests that no output key contains `api_key`, `offer_id`, `event_id`, or `raw_payload`, and that a forced write failure leaves the previous `latest` byte-for-byte unchanged.

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m pytest tests/test_p0_strategy_output.py -q`

Expected: FAIL because the output publisher is absent.

- [ ] **Step 3: Implement one canonical serializable payload**

```python
SAFE_RESULT_FIELDS = (
    "asset", "principal", "portfolio_type", "leg_count", "daily_rates",
    "period_days", "wait_hours", "fill_probability", "average_wait_hours",
    "gross_interest", "fee", "net_interest", "ending_capital",
    "idle_fraction", "net_profit_p10", "readiness_status", "limitations",
)
```

Write all four artifacts into a sibling temporary directory, reopen and validate them, then replace `latest` only after every artifact succeeds. Use `status="experimental"` unless all formal gates pass. Markdown must explain the three baselines, with/without-model comparison, annualized conversion warning, and an honest conclusion when optimization loses.

For BTC and ETH, convert each USDT benchmark into asset units using the first eligible walk-forward price, keep all interest calculations in that asset, and show a separate current-USDT estimate using the latest local `tBTCUSD` or `tETHUSD` row together with its timestamp. Never mix the converted USDT estimate into the asset-denominated return calculation.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_p0_strategy_output.py -q`

Expected: PASS, including last-good preservation.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_strategy_output.py tests/test_p0_strategy_output.py
git commit -m "feat: publish atomic P0 strategy results"
```

---

### Task 8: Generate the local read-only dashboard

**Files:**
- Create: `bitfinex_lending/p0_dashboard.py`
- Create: `tests/test_p0_dashboard.py`

**Interfaces:**
- Consumes: `dashboard_data.json` produced by Task 7.
- Produces: `data/modeling/p0_strategy/latest/dashboard.html` with no API client and no write actions.

- [ ] **Step 1: Write HTML contract tests**

```python
def test_dashboard_contains_only_approved_controls_and_read_only_copy(tmp_path: Path) -> None:
    source = tmp_path / "dashboard_data.json"
    source.write_text(
        json.dumps({"readiness_status": "experimental", "results": []}),
        encoding="utf-8",
    )
    path = export_dashboard(source, tmp_path)
    html = path.read_text(encoding="utf-8")
    assert 'id="capital"' in html
    assert 'value="1000"' in html and 'value="10000"' in html
    assert set(re.findall(r'data-period="(\d+)"', html)) == {"2", "5", "10", "30"}
    assert set(re.findall(r'data-wait="(\d+)"', html)) == {"1", "3", "6", "12", "24"}
    assert "本工具不會下單" in html
    assert "fetch(" not in html and "/auth/w/" not in html
```

- [ ] **Step 2: Run the test and confirm import failure**

Run: `python -m pytest tests/test_p0_dashboard.py -q`

Expected: FAIL because the dashboard exporter is absent.

- [ ] **Step 3: Implement a self-contained static dashboard**

Generate UTF-8 HTML with embedded canonical JSON, Traditional Chinese labels, capital/asset/period/wait selectors, highest-return and stable cards, baseline comparison table, readiness badge, last-success time, stale/error banner, and limitations. JavaScript may only filter and render embedded data; it must not use network requests, credentials, or Bitfinex endpoints.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_p0_dashboard.py tests/test_p0_strategy_output.py -q`

Expected: PASS and all displayed numeric values originate from dashboard JSON.

- [ ] **Step 5: Commit**

```powershell
git add bitfinex_lending/p0_dashboard.py tests/test_p0_dashboard.py
git commit -m "feat: add read-only P0 dashboard"
```

---

### Task 9: Orchestrate the daily pipeline and Windows schedule

**Files:**
- Create: `bitfinex_lending/p0_strategy_pipeline.py`
- Create: `tests/test_p0_strategy_pipeline.py`
- Create: `scripts/install-p0-strategy-analysis.ps1`
- Create: `tests/test_p0_strategy_scheduler_script.py`
- Create: `docs/P0_STRATEGY_OPTIMIZER.md`

**Interfaces:**
- CLI: `python -m bitfinex_lending.p0_strategy_pipeline`.
- Scheduled task: `BitfinexP0StrategyAnalysis`, daily at local 10:00, `pythonw.exe`, interactive limited principal, `IgnoreNew`, 30-minute execution limit.
- Produces `PipelineSummary(status: str, dashboard_path: Path, report_path: Path, csv_path: Path, status_path: Path)`.

- [ ] **Step 1: Write an end-to-end pipeline test with dependency injection**

```python
def test_pipeline_publishes_dashboard_after_all_read_only_stages(tmp_path: Path) -> None:
    calls: list[str] = []

    def load_history(*args: object) -> tuple[object, ...]:
        calls.append("load")
        return ()

    def evaluate(*args: object) -> object:
        calls.append("walk_forward")
        return object()

    def publish(*args: object) -> object:
        calls.append("publish")
        latest = tmp_path / "modeling" / "p0_strategy" / "latest"
        latest.mkdir(parents=True)
        for name in ("report.md", "strategy_results.csv", "dashboard_data.json", "status.json"):
            (latest / name).write_text("{}", encoding="utf-8")
        return OutputPaths(
            csv_path=latest / "strategy_results.csv",
            report_path=latest / "report.md",
            json_path=latest / "dashboard_data.json",
            status_path=latest / "status.json",
        )

    def dashboard(*args: object) -> Path:
        calls.append("dashboard")
        path = tmp_path / "modeling" / "p0_strategy" / "latest" / "dashboard.html"
        path.write_text("<html></html>", encoding="utf-8")
        return path

    summary = run_p0_strategy_pipeline(
        market_root=tmp_path / "market",
        raw_root=tmp_path / "raw",
        account_root=tmp_path / "account",
        output_root=tmp_path / "modeling" / "p0_strategy",
        metadata_root=tmp_path / "metadata",
        clock=lambda: datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc),
        history_loader=load_history,
        walk_forward_runner=evaluate,
        output_publisher=publish,
        dashboard_exporter=dashboard,
    )
    assert summary.status in {"formal", "experimental"}
    assert summary.dashboard_path.name == "dashboard.html"
    assert calls == ["load", "walk_forward", "publish", "dashboard"]
```

Use local fixtures only; the pipeline receives current price rows from `data/market/prices` and performs no network call.

- [ ] **Step 2: Write scheduler preview tests**

Assert preview JSON contains:

```text
task_name=BitfinexP0StrategyAnalysis
arguments=-m bitfinex_lending.p0_strategy_pipeline
local_time=10:00
multiple_instances=IgnoreNew
execution_limit_minutes=30
registration=not_requested
```

- [ ] **Step 3: Run tests and confirm both entry points are absent**

Run: `python -m pytest tests/test_p0_strategy_pipeline.py tests/test_p0_strategy_scheduler_script.py -q`

Expected: FAIL because the pipeline module and PowerShell script do not exist.

- [ ] **Step 4: Implement orchestration with a last-good error boundary**

The pipeline order is fixed: load public history → load optional private matches → run walk-forward → write strategy coverage → evaluate readiness → publish canonical outputs → generate dashboard. On any exception, atomically write `data/metadata/p0_strategy_status.json` with `status=failed`, `finished_at`, `last_success_at`, and a sanitized error message; do not touch `latest`.

- [ ] **Step 5: Implement preview-first scheduler registration**

Mirror the established collector scripts: resolve the project and Python path, prefer `pythonw.exe`, print the full contract when `-Enable` is absent, and register only with explicit `-Enable`. The trigger is daily at 10:00 local time and `StartWhenAvailable` is enabled.

- [ ] **Step 6: Write operator documentation**

Document these exact commands:

```powershell
python -m bitfinex_lending.p0_strategy_pipeline
powershell -ExecutionPolicy Bypass -File .\scripts\install-p0-strategy-analysis.ps1 -ProjectRoot .
powershell -ExecutionPolicy Bypass -File .\scripts\install-p0-strategy-analysis.ps1 -ProjectRoot . -Enable
```

Explain `formal`, `experimental`, `insufficient_data`, `failed`, and `stale`; identify `dashboard.html`, `report.md`, CSV, JSON, and status paths; repeat that the tool cannot place orders.

- [ ] **Step 7: Run focused and full verification**

Run:

```powershell
python -m pytest tests/test_p0_strategy_pipeline.py tests/test_p0_strategy_scheduler_script.py -q
python -m pytest -q
```

Expected: all offline tests pass; the live integration test remains deselected.

- [ ] **Step 8: Commit**

```powershell
git add bitfinex_lending/p0_strategy_pipeline.py tests/test_p0_strategy_pipeline.py scripts/install-p0-strategy-analysis.ps1 tests/test_p0_strategy_scheduler_script.py docs/P0_STRATEGY_OPTIMIZER.md
git commit -m "feat: schedule daily P0 strategy analysis"
```

---

### Task 10: Final production-path verification and project records

**Files:**
- Modify: `docs/P0_EXECUTION_CHECKLIST.md`
- Modify: `todo.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: one reproducible handoff with exact test counts, status, limitations, and next data checkpoint.

- [ ] **Step 1: Run the local production path once**

Run: `python -m bitfinex_lending.p0_strategy_pipeline`

Expected today: the command succeeds but reports `experimental` or `insufficient_data` until 60-day USDT gates pass. It must not invent a formal recommendation.

- [ ] **Step 2: Inspect cross-format equality and privacy**

Confirm the selected principal's `ending_capital`, `net_interest`, and strategy IDs match in CSV, JSON, Markdown, and dashboard. Search published files for `api_key`, `offer_id`, `event_id`, `raw_payload`, and `/auth/w/`; expect no matches.

- [ ] **Step 3: Run the complete offline suite**

Run: `python -m pytest -q`

Expected: all unit tests pass and exactly the configured live integration test is deselected.

- [ ] **Step 4: Update project tracking only with verified facts**

Mark a checklist item complete only when its exact test and output evidence exists. Record the current formal-data shortfall separately from functional completion. Do not rewrite historical progress entries; add a new dated entry.

- [ ] **Step 5: Commit the verified records**

```powershell
git add docs/P0_EXECUTION_CHECKLIST.md todo.md progress.md
git commit -m "docs: record P0 optimizer verification"
```
