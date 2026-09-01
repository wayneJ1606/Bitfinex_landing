"""Generate a self-contained, read-only dashboard from canonical P0 results."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Mapping


class DashboardDataError(ValueError):
    """Raised when dashboard input is not a Task 7 canonical payload."""


def _load_payload(source: Path) -> dict[str, object]:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DashboardDataError(f"cannot read dashboard data: {exc}") from exc
    if not isinstance(payload, dict):
        raise DashboardDataError("dashboard data must be a JSON object")
    required = ("generated_at", "readiness_status", "results")
    if any(key not in payload for key in required):
        raise DashboardDataError("dashboard data is missing required fields")
    if not isinstance(payload["generated_at"], str) or not payload["generated_at"]:
        raise DashboardDataError("generated_at must be a non-empty string")
    if not isinstance(payload["readiness_status"], str):
        raise DashboardDataError("readiness_status must be a string")
    if not isinstance(payload["results"], list) or not all(
        isinstance(row, Mapping) for row in payload["results"]
    ):
        raise DashboardDataError("results must be a list of objects")
    limitations = payload.get("limitations", [])
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise DashboardDataError("limitations must be a list of strings")
    return payload


def _embedded_json(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return serialized.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _html(payload: Mapping[str, object]) -> str:
    capital_options = "".join(
        f'<option value="{amount}">{amount:,} USDT</option>'
        for amount in range(1000, 10001, 1000)
    )
    period_buttons = "".join(
        f'<button type="button" class="choice" data-period="{days}">{days} 天</button>'
        for days in (2, 5, 10, 30)
    )
    wait_buttons = "".join(
        f'<button type="button" class="choice" data-wait="{hours}">{hours} 小時</button>'
        for hours in (1, 3, 6, 12, 24)
    )
    data = _embedded_json(payload)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bitfinex 放貸策略 Dashboard</title>
  <style>
    :root {{ color-scheme: dark; --bg:#08111f; --panel:#111d2f; --line:#263854; --text:#eef5ff; --muted:#9eb0c8; --accent:#43d6a2; --warn:#ffcb6b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at top right,#153257 0,#08111f 45%); color:var(--text); font:15px/1.55 system-ui,"Microsoft JhengHei",sans-serif; }}
    main {{ width:min(1180px,calc(100% - 32px)); margin:32px auto 64px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; margin-bottom:22px; }}
    h1,h2,h3,p {{ margin-top:0; }} h1 {{ font-size:clamp(26px,4vw,42px); margin-bottom:8px; }} h2 {{ font-size:20px; }}
    .muted {{ color:var(--muted); }} .badge {{ padding:7px 12px; border:1px solid var(--line); border-radius:999px; white-space:nowrap; }}
    .banner {{ border:1px solid #8b692e; background:#332815; color:#ffe0a0; padding:12px 16px; border-radius:12px; margin-bottom:18px; }}
    .hidden {{ display:none; }} .panel {{ background:rgba(17,29,47,.94); border:1px solid var(--line); border-radius:16px; padding:20px; margin-bottom:18px; box-shadow:0 16px 40px rgba(0,0,0,.2); }}
    .controls {{ display:grid; grid-template-columns:repeat(2,minmax(180px,1fr)); gap:16px 24px; }}
    label,.label {{ display:block; color:var(--muted); margin-bottom:7px; }} select {{ width:100%; padding:10px 12px; border-radius:9px; border:1px solid var(--line); background:#0b1627; color:var(--text); }}
    .choices {{ display:flex; flex-wrap:wrap; gap:8px; }} .choice {{ padding:8px 12px; border-radius:9px; border:1px solid var(--line); background:#0b1627; color:var(--text); cursor:pointer; }}
    .choice.active {{ color:#04110d; border-color:var(--accent); background:var(--accent); font-weight:700; }}
    .cards {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }} .card {{ min-height:210px; }} .metric {{ font-size:28px; font-weight:800; color:var(--accent); }}
    .facts {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin-top:18px; }} .facts div {{ border-top:1px solid var(--line); padding-top:8px; }} .facts span {{ display:block; color:var(--muted); font-size:12px; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:10px; border-bottom:1px solid var(--line); text-align:right; }} th:first-child,td:first-child {{ text-align:left; }}
    .empty {{ color:var(--muted); padding:24px 0; }} ul {{ padding-left:22px; }}
    footer {{ color:var(--muted); text-align:center; margin-top:24px; }}
    @media (max-width:760px) {{ header {{ display:block; }} .badge {{ display:inline-block; margin-top:8px; }} .controls,.cards {{ grid-template-columns:1fr; }} table {{ font-size:12px; }} th,td {{ padding:8px 4px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div><h1>放貸策略比較</h1><p class="muted">比較實驗最佳化結果與簡單基準；所有內容均由本機資料產生。</p></div>
    <div id="readiness" class="badge">讀取狀態中</div>
  </header>
  <div id="status-banner" class="banner hidden" role="status"></div>

  <section class="panel controls" aria-label="策略篩選條件">
    <div><label for="capital">本金</label><select id="capital">{capital_options}</select></div>
    <div><label for="asset">資產</label><select id="asset"><option value="USDT">USDT</option><option value="BTC">BTC</option><option value="ETH">ETH</option></select></div>
    <div><span class="label">借出期限</span><div id="periods" class="choices">{period_buttons}</div></div>
    <div><span class="label">最長等待</span><div id="waits" class="choices">{wait_buttons}</div></div>
  </section>

  <section class="cards">
    <article class="panel card"><h2>最高收益方案</h2><div id="highest-return" class="empty">此條件沒有可用結果</div></article>
    <article class="panel card"><h2>較穩定替代方案</h2><div id="stable-return" class="empty">此條件沒有可用結果</div></article>
  </section>

  <section class="panel"><h2>基準策略比較</h2><div class="table-wrap"><table><thead><tr><th>策略</th><th>成交機率</th><th>平均等待</th><th>淨收益</th><th>期末本金</th></tr></thead><tbody id="baseline-body"></tbody></table><p id="baseline-empty" class="empty">此條件沒有基準結果</p></div></section>
  <section class="panel"><h2>資料狀態與限制</h2><p>最後成功資料時間：<strong id="last-success"></strong></p><ul id="limitations"></ul><p><strong>本工具不會下單</strong>，結果僅供研究與結案報告使用，不構成投資建議。</p></section>
  <footer>Bitfinex 放貸決策輔助系統 · 本機唯讀介面</footer>
</main>
<script id="dashboard-data" type="application/json">{data}</script>
<script>
(() => {{
  "use strict";
  const data = JSON.parse(document.getElementById("dashboard-data").textContent);
  const state = {{ period: 2, wait: 1 }};
  const byId = (id) => document.getElementById(id);
  const labels = {{ highest_return:"最高收益", stable_alternative:"較穩定", fixed_median:"固定中位利率", frr:"FRR 市場利率", quick_fill:"低利率快速成交", optimized_with_prediction:"使用預測", optimized_without_prediction:"不使用預測" }};
  const value = (row, key, suffix="") => row && row[key] !== undefined && row[key] !== "" ? String(row[key]) + suffix : "—";
  const includesNumber = (item, selected) => Array.isArray(item) ? item.map(Number).includes(selected) : Number(item) === selected;
  const matching = () => data.results.filter((row) => String(row.asset) === byId("asset").value && String(row.principal) === byId("capital").value && includesNumber(row.period_days, state.period) && includesNumber(row.wait_hours, state.wait));
  const renderCard = (target, row) => {{
    if (!row) {{ target.className="empty"; target.textContent="此條件沒有可用結果"; return; }}
    target.className="";
    target.replaceChildren();
    const amount=document.createElement("div"); amount.className="metric"; amount.textContent=value(row,"ending_capital");
    const caption=document.createElement("p"); caption.className="muted"; caption.textContent="30 天期末本金（原資產單位）";
    const facts=document.createElement("div"); facts.className="facts";
    [["淨收益",value(row,"net_interest")],["成交機率",value(row,"fill_probability")],["平均等待",value(row,"average_wait_hours"," 小時")],["閒置比例",value(row,"idle_fraction")]].forEach(([name,item]) => {{ const box=document.createElement("div"); const label=document.createElement("span"); label.textContent=name; const strong=document.createElement("strong"); strong.textContent=item; box.append(label,strong); facts.append(box); }});
    target.append(amount,caption,facts);
  }};
  const render = () => {{
    const rows=matching();
    const preferred=(portfolioType)=>rows.find((row)=>row.portfolio_type===portfolioType && row.strategy_type==="optimized_with_prediction") || rows.find((row)=>row.portfolio_type===portfolioType && row.strategy_type==="optimized_without_prediction") || rows.find((row)=>row.portfolio_type===portfolioType);
    renderCard(byId("highest-return"),preferred("highest_return"));
    renderCard(byId("stable-return"),preferred("stable_alternative") || preferred("stable"));
    const body=byId("baseline-body"); body.replaceChildren();
    rows.filter((row)=>!["stable","stable_alternative"].includes(row.portfolio_type) && (row.portfolio_type!=="highest_return" || String(row.strategy_type).startsWith("optimized_"))).forEach((row) => {{ const tr=document.createElement("tr"); [labels[row.strategy_type] || labels[row.portfolio_type] || row.strategy_type || row.portfolio_type,value(row,"fill_probability"),value(row,"average_wait_hours"," 小時"),value(row,"net_interest"),value(row,"ending_capital")].forEach((item)=>{{ const td=document.createElement("td"); td.textContent=item; tr.append(td); }}); body.append(tr); }});
    byId("baseline-empty").classList.toggle("hidden",body.children.length > 0);
  }};
  document.querySelectorAll("[data-period]").forEach((button) => button.addEventListener("click",()=>{{ state.period=Number(button.dataset.period); document.querySelectorAll("[data-period]").forEach((item)=>item.classList.toggle("active",item===button)); render(); }}));
  document.querySelectorAll("[data-wait]").forEach((button) => button.addEventListener("click",()=>{{ state.wait=Number(button.dataset.wait); document.querySelectorAll("[data-wait]").forEach((item)=>item.classList.toggle("active",item===button)); render(); }}));
  byId("capital").addEventListener("change",render); byId("asset").addEventListener("change",render);
  document.querySelector('[data-period="2"]').classList.add("active"); document.querySelector('[data-wait="1"]').classList.add("active");
  const formal=data.status==="formal" && data.readiness_status==="formal";
  const lastSuccess=String(data.last_success_at || data.generated_at);
  const lastSuccessMillis=Date.parse(lastSuccess);
  const stale=Number.isFinite(lastSuccessMillis) && Date.now()-lastSuccessMillis > 48*60*60*1000;
  byId("readiness").textContent=formal ? "正式資料" : "實驗結果";
  if (!formal || stale || data.error) {{
    const banner=byId("status-banner"); banner.classList.remove("hidden");
    banner.textContent=data.error ? "更新失敗，顯示上一個成功版本："+String(data.error) : stale ? "資料可能已過期：最後成功更新已超過 48 小時。" : "資料尚未達正式門檻；目前結果只能作為實驗參考。";
  }}
  byId("last-success").textContent=lastSuccess;
  (data.limitations || []).forEach((item)=>{{ const li=document.createElement("li"); li.textContent=String(item); byId("limitations").append(li); }});
  render();
}})();
</script>
</body>
</html>
"""


def export_dashboard(source: Path, output_dir: Path) -> Path:
    """Render Task 7 dashboard data to an offline HTML file."""
    source = Path(source)
    output_dir = Path(output_dir)
    payload = _load_payload(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "dashboard.html"
    temporary = output_dir / f".dashboard-{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(_html(payload), encoding="utf-8")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target
