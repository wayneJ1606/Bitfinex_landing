# Dashboard 2.1 USDT Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a separate USDT-only Dashboard 2.1 with period-specific comparison baselines.

**Architecture:** Add a new self-contained exporter that consumes the existing canonical payload without changing it. Extend the experimental pipeline to publish the new file beside both existing Dashboard versions.

**Tech Stack:** Python 3.13, self-contained HTML/CSS/JavaScript, pytest

## Global Constraints

- Preserve `dashboard.html` and `dashboard_readable_zh.html` unchanged.
- Add `dashboard_readable_zh_v2_1.html`.
- Do not change models, proxy formulas, collectors, schedulers, private data, `progress.md`, or `todo.md`.
- Keep the output offline, read-only, and free of authenticated API endpoints.

---

### Task 1: Add the USDT-only 2.1 exporter

**Files:**
- Create: `bitfinex_lending/p0_usdt_strategy_dashboard_v2_1.py`
- Create: `tests/test_p0_usdt_strategy_dashboard_v2_1.py`

**Interfaces:**
- Consumes: canonical experimental payload.
- Produces: `period_baseline_ids(period_days: int) -> tuple[str, str]` and `export_usdt_strategy_dashboard_v2_1(payload: dict[str, object], output_path: Path) -> Path`.

- [ ] **Step 1: Write failing tests**

Assert the approved period mapping and independent output:

```python
assert period_baseline_ids(5) == ("q10-p5-w1", "q50-p5-w24")
assert period_baseline_ids(10) == ("q10-p10-w1", "q50-p10-w24")
assert path.name == "dashboard_readable_zh_v2_1.html"
assert "USDT 放貸候選策略" in html
assert 'id="asset"' not in html
assert "原生資產利率模型" not in html
assert "條件式理論收益" not in html
assert "q10-p5-w1" in html
assert "q50-p5-w24" in html
assert "q10-p10-w1" in html
assert "q50-p10-w24" in html
assert "fetch(" not in html
assert "/auth/w/" not in html
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest -q tests/test_p0_usdt_strategy_dashboard_v2_1.py`

Expected: import error because the new module is absent.

- [ ] **Step 3: Implement the exporter**

Validate periods against `(2, 5, 10, 30)`. Reuse `strategy_label` and `LIMITATION_ZH` from `p0_readable_dashboard`. Render only capital and period controls. In JavaScript derive the active baseline set from the selected period:

```javascript
const baselines=new Set([
  `q10-p${period.value}-w1`,
  `q50-p${period.value}-w24`
]);
const top=rows.slice(0,3);
const shown=[...top,...rows.filter(row=>baselines.has(row.strategy_id)&&!top.some(item=>item.strategy_id===row.strategy_id))];
```

Keep the existing Chinese limitations, Taiwan time, strategy translation, top-three ranking, close-result label, read-only warning, and safe embedded JSON escaping.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest -q tests/test_p0_usdt_strategy_dashboard_v2_1.py tests/test_p0_readable_dashboard.py`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add bitfinex_lending/p0_usdt_strategy_dashboard_v2_1.py tests/test_p0_usdt_strategy_dashboard_v2_1.py
git commit -m "feat: add USDT strategy dashboard 2.1"
```

### Task 2: Publish Dashboard 2.1 from the existing pipeline

**Files:**
- Modify: `bitfinex_lending/p0_experimental_pipeline.py`
- Modify: `tests/test_p0_experimental_pipeline.py`
- Create: `data/modeling/p0_experimental/latest/dashboard_readable_zh_v2_1.html`

**Interfaces:**
- Extend `ExperimentalPipelineSummary` with `dashboard_v2_1_path: Path`.
- Print `dashboard_v2_1=<path>` from the CLI.

- [ ] **Step 1: Extend pipeline tests first**

```python
assert summary.dashboard_v2_1_path == output / "dashboard_readable_zh_v2_1.html"
assert "USDT 放貸候選策略" in summary.dashboard_v2_1_path.read_text(encoding="utf-8")
```

Update the CLI fake summary with `dashboard_v2_1_path=Path("dashboard_readable_zh_v2_1.html")`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_p0_experimental_pipeline.py`

Expected: failure because the summary field and output are absent.

- [ ] **Step 3: Add the third output**

Call `export_usdt_strategy_dashboard_v2_1(payload, output_root / "dashboard_readable_zh_v2_1.html")`, return the path, and print it without changing the two existing exporters.

- [ ] **Step 4: Verify focused behavior**

Run: `python -m pytest -q tests/test_p0_usdt_strategy_dashboard_v2_1.py tests/test_p0_readable_dashboard.py tests/test_p0_experimental_dashboard.py tests/test_p0_experimental_pipeline.py tests/test_p0_experimental_payload.py`

Expected: all tests pass.

- [ ] **Step 5: Generate real output and verify preservation**

Record SHA-256 for both existing HTML files, run the pipeline against current local public/model data in an isolated worktree, then verify both hashes in the main workspace remain unchanged. Scan 2.1 for English limitations, private fields, `fetch(`, `XMLHttpRequest`, and `/auth/w/`.

- [ ] **Step 6: Run complete suite**

Run: `python -m pytest -q`

Expected: zero failures; the intentionally deselected integration test may remain deselected.

- [ ] **Step 7: Commit Task 2**

```powershell
git add bitfinex_lending/p0_experimental_pipeline.py tests/test_p0_experimental_pipeline.py data/modeling/p0_experimental/latest/dashboard_readable_zh_v2_1.html
git commit -m "feat: publish dashboard 2.1"
```
