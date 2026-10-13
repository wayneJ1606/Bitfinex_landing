"""Export the separate USDT-only readable experimental Dashboard 2.1."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import re


SUPPORTED_PERIODS = (2, 5, 10, 30)
RATE_LABELS = {
    10: "低利率",
    25: "偏低利率",
    50: "中位利率",
    75: "偏高利率",
    90: "高利率",
}

LIMITATIONS_ZH = (
    "本頁使用公開市場成交資料建立替代成交指標，不代表真實掛單一定成交。",
    "目前樣本仍少，結果僅供研究參考，不應直接作為投資或自動下單依據。",
    "候選策略是依歷史資料模擬；市場狀況改變時，過去表現可能無法延續。",
    "收益已依目前設定扣除 15% Bitfinex 放貸手續費，但未納入其他稅務或資金成本。",
    "本頁為唯讀離線檔案，不會連線至私人帳戶，也不具備下單功能。",
)


def period_baseline_ids(period_days: int) -> tuple[str, str]:
    """Return quick-fill and median-rate baseline IDs for an approved term."""
    if period_days not in SUPPORTED_PERIODS:
        raise ValueError(f"unsupported period: {period_days}")
    return f"q10-p{period_days}-w1", f"q50-p{period_days}-w24"


def _strategy_label(strategy_id: str) -> str:
    matched = re.fullmatch(r"q(\d{2})-p(\d+)-w(\d+)", strategy_id)
    if matched is None:
        return strategy_id
    quantile, period, wait = (int(value) for value in matched.groups())
    rate = RATE_LABELS.get(quantile)
    if rate is None or period not in SUPPORTED_PERIODS:
        return strategy_id
    return f"{rate}、借出 {period} 天、最多等待 {wait} 小時"


def _taipei_display(value: object) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "時間資料無法解析"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return "時間資料缺少時區"
    taipei = timezone(timedelta(hours=8), name="Asia/Taipei")
    return parsed.astimezone(taipei).strftime("%Y/%m/%d %H:%M")


def export_usdt_strategy_dashboard_v2_1(
    payload: dict[str, object], output_path: Path
) -> Path:
    """Write a separate self-contained Dashboard 2.1 without replacing older pages."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    view_payload = deepcopy(payload)
    proxy = view_payload.get("public_fill_proxy")
    if isinstance(proxy, dict):
        candidates = proxy.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, dict):
                    candidate["display_name"] = _strategy_label(
                        str(candidate.get("strategy_id", ""))
                    )

    embedded = json.dumps(
        view_payload, ensure_ascii=False, separators=(",", ":")
    ).replace("<", "\\u003c")
    usdt = view_payload.get("usdt_market", {})
    observed = usdt.get("observed_hours", 0) if isinstance(usdt, dict) else 0
    required = usdt.get("required_hours", 1440) if isinstance(usdt, dict) else 1440
    progress = min(
        100.0,
        (float(observed) / float(required) * 100.0) if required else 0.0,
    )
    capitals = "".join(
        f'<option value="{value}">{value:,} USDT</option>'
        for value in range(1000, 10001, 1000)
    )
    periods = "".join(
        f'<option value="{period}">{period} 天</option>' for period in SUPPORTED_PERIODS
    )
    limitations = "".join(f"<li>{escape(item)}</li>" for item in LIMITATIONS_ZH)
    generated = _taipei_display(view_payload.get("generated_at", ""))

    html = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bitfinex USDT 放貸策略 Dashboard 2.1</title>
<style>
:root{{--ink:#17233c;--muted:#62718c;--paper:#f2f6fc;--card:#fff;--blue:#2458d3;--line:#dce4f0;--green:#13795b;--amber:#925600}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#edf3ff,#fbfcff 50%,#eaf8f7);color:var(--ink);font-family:"Segoe UI","Noto Sans TC",sans-serif}}
main{{max-width:1120px;margin:auto;padding:34px 22px 60px}}h1{{font-size:clamp(30px,5vw,46px);margin:7px 0}}h2{{font-size:22px;margin:0 0 8px}}p{{line-height:1.65}}.eyebrow{{color:var(--blue);font-weight:800;letter-spacing:.07em}}.sub,.hint{{color:var(--muted)}}
.notice,.card{{border-radius:18px;padding:21px;margin-top:18px}}.notice{{background:#17233c;color:#fff;display:flex;justify-content:space-between;gap:20px}}.progress{{min-width:210px;text-align:right}}.bar{{height:7px;background:#ffffff30;border-radius:9px;overflow:hidden;margin-top:8px}}.bar i{{display:block;width:{progress:.3f}%;height:100%;background:#49d3c7}}
.card{{background:var(--card);border:1px solid #e0e7f1;box-shadow:0 10px 28px #21385b12}}.controls{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}label{{color:var(--muted);font-size:13px;font-weight:750}}select{{display:block;width:100%;margin-top:7px;padding:12px;border:1px solid var(--line);border-radius:12px;background:#fff;font-size:15px;color:var(--ink)}}
.summary{{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}}.metric{{font-size:35px;font-weight:850;margin:8px 0}}dl{{display:grid;grid-template-columns:1fr auto;gap:10px;margin:15px 0 0}}dt{{color:var(--muted)}}dd{{font-weight:750;margin:0;text-align:right}}.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#fff2d9;border:1px solid #efc676;color:#754500;font-size:13px;font-weight:800}}
.table-wrap{{overflow:auto;margin-top:18px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}th{{font-size:12px;color:var(--muted)}}.name{{font-weight:800}}.code,.tags{{display:block;margin-top:3px;font-size:12px;color:var(--muted)}}.tags{{color:var(--blue);font-weight:800}}.explain{{background:#f5f8fc;border-radius:13px;padding:14px;line-height:1.65}}.limits li{{margin:9px 0;line-height:1.6;color:#455572}}footer{{margin-top:22px;color:var(--muted);font-size:13px}}
@media(max-width:720px){{.notice,.summary{{display:block}}.progress{{text-align:left;margin-top:12px}}.controls{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><div class="eyebrow">唯讀研究版・Dashboard 2.1</div><h1>USDT 放貸候選策略</h1><p class="sub">比較不同掛單利率、借出天數與等待時間，在歷史市場替代指標下的預期結果。</p></header>
<section class="notice"><div><strong>fUST 資料仍在累積</strong><div>目前結果可先協助整理結案報告，但可信度仍低，不能視為實際投資保證。</div></div><div class="progress"><b>{observed} / {required} 小時</b><div class="bar"><i></i></div></div></section>
<section class="card controls"><label>本金<select id="capital">{capitals}</select></label><label>借出天數<select id="period">{periods}</select></label></section>
<section class="card"><div class="summary"><div><div class="eyebrow">市場預期比較</div><h2>目前排名第一的候選策略</h2><div id="best"></div></div><div class="explain"><b>這裡比較的是什麼？</b><br>系統先依所選借出天數篩選策略，再比較歷史替代成交機率、等待時間、閒置比例與扣費後 30 天預期收益。排名前三以外，固定補列同天數的「快速成交基準」與「中位利率基準」，方便判斷複雜策略是否真的優於簡單做法。</div></div><div class="table-wrap"><table id="strategy-table"></table></div></section>
<section class="card limits"><h2>使用限制</h2><ul>{limitations}</ul></section>
<footer>資料產生時間（台灣）：{generated}・本頁不會連線或下單</footer>
</main><script id="dashboard-data" type="application/json">{embedded}</script>
<script>
const data=JSON.parse(document.getElementById('dashboard-data').textContent);
const capital=document.getElementById('capital'),period=document.getElementById('period'),best=document.getElementById('best'),table=document.getElementById('strategy-table');
const safe=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const number=(v,d=2)=>new Intl.NumberFormat('zh-TW',{{maximumFractionDigits:d}}).format(Number(v));
function render(){{
 const proxy=data.public_fill_proxy||{{status:'insufficient_data',candidates:[]}};
 const rows=(proxy.candidates||[]).filter(r=>String(r.period_days)===period.value).sort((a,b)=>Number(b.expected_30d_net_profit_per_1000)-Number(a.expected_30d_net_profit_per_1000));
 if(proxy.status!=='experimental'||!rows.length){{best.innerHTML='<p class="hint">目前沒有這個天數可比較的策略資料。</p>';table.innerHTML='';return;}}
 const scale=Number(capital.value)/1000,leader=rows[0],leaderProfit=Number(leader.expected_30d_net_profit_per_1000)*scale;
 best.innerHTML=`<div class="metric">+${{number(leaderProfit)}} USDT</div><div class="hint">扣費後 30 天預期收益</div><dl><dt>策略</dt><dd>${{safe(leader.display_name)}}</dd><dt>替代成交機率</dt><dd>${{number(Number(leader.proxy_fill_probability)*100,1)}}%</dd><dt>平均等待</dt><dd>${{number(leader.average_success_wait_hours,1)}} 小時</dd><dt>閒置比例</dt><dd>${{number(Number(leader.idle_fraction)*100,1)}}%</dd></dl>`;
 const quick=`q10-p${{period.value}}-w1`,median=`q50-p${{period.value}}-w24`,baselineNames=new Map([[quick,'快速成交基準'],[median,'中位利率基準']]);
 const top=rows.slice(0,3),shown=[...top,...rows.filter(r=>baselineNames.has(r.strategy_id)&&!top.some(t=>t.strategy_id===r.strategy_id))];
 table.innerHTML='<thead><tr><th>候選策略</th><th>每日利率</th><th>替代成交機率</th><th>閒置比例</th><th>30 天預期收益</th></tr></thead><tbody>'+shown.map((r,index)=>{{const tags=[];if(index===0)tags.push('目前排名第一');if(baselineNames.has(r.strategy_id))tags.push(baselineNames.get(r.strategy_id));const profit=Number(r.expected_30d_net_profit_per_1000)*scale;return `<tr><td><span class="name">${{safe(r.display_name)}}</span><span class="code">${{safe(r.strategy_id)}}</span><span class="tags">${{tags.join('・')}}</span></td><td>${{number(Number(r.average_candidate_daily_rate)*100,6)}}%</td><td>${{number(Number(r.proxy_fill_probability)*100,1)}}%</td><td>${{number(Number(r.idle_fraction)*100,1)}}%</td><td>${{number(profit)}} USDT</td></tr>`}}).join('')+'</tbody>';
}}
capital.addEventListener('change',render);period.addEventListener('change',render);render();
</script></body></html>"""

    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(html, encoding="utf-8", newline="\n")
    temporary.replace(output_path)
    return output_path
