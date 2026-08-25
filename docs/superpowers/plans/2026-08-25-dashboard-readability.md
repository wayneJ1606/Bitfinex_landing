# Dashboard Chinese Readability Variant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate Traditional Chinese readable Dashboard without changing or overwriting the existing Dashboard.

**Architecture:** Keep the canonical payload and original `export_experimental_dashboard` unchanged. Add a focused readable exporter, then make the experimental pipeline publish both HTML variants from the same in-memory payload.

**Tech Stack:** Python 3.13, self-contained HTML/CSS/JavaScript, pytest

## Global Constraints

- Preserve `data/modeling/p0_experimental/latest/dashboard.html` byte-for-byte when the readable exporter is called directly.
- Publish the new file as `data/modeling/p0_experimental/latest/dashboard_readable_zh.html`.
- Do not change models, calculations, collectors, schedulers, private-data handling, `progress.md`, or `todo.md`.
- Keep both Dashboards read-only, offline, and free of authenticated Bitfinex endpoints.

---

## File Responsibility Map

- Create `bitfinex_lending/p0_readable_dashboard.py`: strategy-name translation, Taiwan-time presentation, and readable HTML export only.
- Create `tests/test_p0_readable_dashboard.py`: readable-copy contract, Chinese copy, strategy labels, state separation, safety, and unchanged original-file assertions.
- Modify `bitfinex_lending/p0_experimental_pipeline.py`: publish and report both HTML files from one payload.
- Modify `tests/test_p0_experimental_pipeline.py`: assert both outputs exist and CLI summary exposes the readable path.

### Task 1: Build the independent readable Dashboard exporter

**Files:**
- Create: `bitfinex_lending/p0_readable_dashboard.py`
- Create: `tests/test_p0_readable_dashboard.py`

**Interfaces:**
- Consumes: `payload: dict[str, object]` produced by `build_experimental_payload`.
- Produces: `strategy_label(strategy_id: str) -> str` and `export_readable_dashboard(payload: dict[str, object], output_path: Path) -> Path`.

- [ ] **Step 1: Write failing tests**

Create a representative payload containing trained fUSD/fBTC/fETH estimates, one `q90-p30-w24` candidate, one baseline, seven English limitations, and safety flags. Assert:

```python
assert strategy_label("q90-p30-w24") == "高利率｜借出 30 天｜最多等待 24 小時"
assert readable.name == "dashboard_readable_zh.html"
assert original.read_bytes() == original_before
assert "原生資產利率模型" in html
assert "已達最低建模門檻" in html
assert "fUST 公開市場成交代理" in html
assert "非常低可信度" in html
assert "目前樣本最高" in html
assert "比較基準" in html
assert "與第一名差異極小" in html
assert "fUSD 的市場行為不能替代 fUST" in html
assert "台灣時間" in html
assert "fetch(" not in html
assert "/auth/w/" not in html
```

- [ ] **Step 2: Verify the new tests fail**

Run: `python -m pytest -q tests/test_p0_readable_dashboard.py`

Expected: FAIL because `bitfinex_lending.p0_readable_dashboard` does not exist.

- [ ] **Step 3: Implement the readable exporter**

Implement fixed mappings without changing payload values:

```python
RATE_LABELS = {10: "低利率", 25: "偏低利率", 50: "中位利率", 75: "偏高利率", 90: "高利率"}

LIMITATION_ZH = (
    "fUSD 的市場行為不能替代 fUST。",
    "顯示利率是歷史驗證區間的最近一期預測，不是即時未來預測。",
    "原生資產理論收益假設立即全額成交；fUST 區塊才包含公開成交代理與等待損失。",
    "公開市場價格碰到掛單利率，不代表個人掛單一定成交，因為無法得知排隊順位與可成交容量。",
    "成交代理假設資金維持借出至選定期限；實際借款人可能提前還款，使收益降低。",
    "收益已扣除公開放貸提供者 15% 手續費。",
    "USD／USDT 採明示的 1:1 近似顯示；BTC、ETH 仍以原生資產計算後再換算。",
)
```

Parse only approved IDs matching `qNN-pN-wN`; unknown IDs remain visible as their original code. Convert `generated_at` to `Asia/Taipei` for visible text. Embed the canonical payload safely by replacing `<` with `\\u003c`. Render the top-three strategies plus missing baselines, show Chinese labels with the raw strategy ID as secondary text, and mark nominal profit differences up to `0.01 USDT` per selected principal as「與第一名差異極小」.

- [ ] **Step 4: Verify focused tests pass**

Run: `python -m pytest -q tests/test_p0_readable_dashboard.py tests/test_p0_experimental_dashboard.py`

Expected: all tests PASS and the original exporter regression suite remains green.

- [ ] **Step 5: Commit the isolated exporter**

```powershell
git add bitfinex_lending/p0_readable_dashboard.py tests/test_p0_readable_dashboard.py
git commit -m "feat: add readable Chinese dashboard variant"
```

### Task 2: Publish both Dashboard versions from the existing pipeline

**Files:**
- Modify: `bitfinex_lending/p0_experimental_pipeline.py`
- Modify: `tests/test_p0_experimental_pipeline.py`

**Interfaces:**
- Consumes: `export_readable_dashboard(payload, output_root / "dashboard_readable_zh.html")`.
- Produces: `ExperimentalPipelineSummary.readable_dashboard_path: Path` and CLI line `readable_dashboard=<path>`.

- [ ] **Step 1: Extend pipeline tests first**

Add assertions:

```python
assert summary.dashboard_path == output / "dashboard.html"
assert summary.readable_dashboard_path == output / "dashboard_readable_zh.html"
assert summary.dashboard_path.read_text(encoding="utf-8") != summary.readable_dashboard_path.read_text(encoding="utf-8")
assert "使用限制" in summary.readable_dashboard_path.read_text(encoding="utf-8")
```

Update the CLI fake summary with `readable_dashboard_path=Path("dashboard_readable_zh.html")`.

- [ ] **Step 2: Verify the pipeline test fails**

Run: `python -m pytest -q tests/test_p0_experimental_pipeline.py`

Expected: FAIL because `readable_dashboard_path` is absent.

- [ ] **Step 3: Add the second output without replacing the original**

Import `export_readable_dashboard`, add `readable_dashboard_path: Path` to `ExperimentalPipelineSummary`, call both exporters sequentially with different output names, return both paths, and print:

```python
print(f"dashboard={summary.dashboard_path}")
print(f"readable_dashboard={summary.readable_dashboard_path}")
```

- [ ] **Step 4: Verify focused and safety tests**

Run: `python -m pytest -q tests/test_p0_readable_dashboard.py tests/test_p0_experimental_dashboard.py tests/test_p0_experimental_pipeline.py tests/test_p0_experimental_payload.py`

Expected: all tests PASS.

- [ ] **Step 5: Generate and inspect the real outputs**

Record the SHA-256 of the existing `dashboard.html`, run `python -m bitfinex_lending.p0_experimental_pipeline`, then confirm:

- `dashboard.html` still exists.
- `dashboard_readable_zh.html` exists and contains no visible English limitation sentences.
- The old Dashboard SHA-256 is unchanged when only the readable exporter is rerun directly.
- Both files contain no `fetch(`, `XMLHttpRequest`, `/auth/w/`, API key, or API secret.

- [ ] **Step 6: Run the complete offline test suite**

Run: `python -m pytest -q`

Expected: zero failures; the existing intentionally deselected test may remain deselected.

- [ ] **Step 7: Commit the pipeline integration**

```powershell
git add bitfinex_lending/p0_experimental_pipeline.py tests/test_p0_experimental_pipeline.py data/modeling/p0_experimental/latest/dashboard_readable_zh.html
git commit -m "feat: publish both dashboard variants"
```
