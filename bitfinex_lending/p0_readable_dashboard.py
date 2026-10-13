"""Export a separate, readable Traditional Chinese experimental Dashboard."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from html import escape
from pathlib import Path
import re


RATE_LABELS = {
    10: "低利率",
    25: "偏低利率",
    50: "中位利率",
    75: "偏高利率",
    90: "高利率",
}

LIMITATION_ZH = (
    "fUSD 的市場行為不能替代 fUST。",
    "顯示利率是歷史驗證區間的最近一期預測，不是即時未來預測。",
    "原生資產理論收益假設立即全額成交；fUST 區塊才包含公開成交代理與等待損失。",
    "公開市場價格碰到掛單利率，不代表個人掛單一定成交，因為無法得知排隊順位與可成交容量。",
    "成交代理假設資金維持借出至選定期限；實際借款人可能提前還款，使收益降低。",
    "收益已扣除公開放貸提供者 15% 手續費。",
    "USD／USDT 採明示的 1:1 近似顯示；BTC、ETH 仍以原生資產計算後再換算。",
)


def strategy_label(strategy_id: str) -> str:
    """Translate an approved qNN-pN-wN strategy ID without hiding its source ID."""
    matched = re.fullmatch(r"q(\d{2})-p(\d+)-w(\d+)", strategy_id)
    if matched is None:
        return strategy_id
    quantile, period, wait = (int(value) for value in matched.groups())
    rate = RATE_LABELS.get(quantile)
    if rate is None or period not in (2, 5, 10, 30) or wait not in (1, 3, 6, 12, 24):
        return strategy_id
    return f"{rate}｜借出 {period} 天｜最多等待 {wait} 小時"


def _taipei_display(value: object) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "時間資料無法辨識"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return "時間資料缺少時區"
    taipei = timezone(timedelta(hours=8), name="Asia/Taipei")
    return parsed.astimezone(taipei).strftime("%Y/%m/%d %H:%M")


def export_readable_dashboard(payload: dict[str, object], output_path: Path) -> Path:
    """Write a second self-contained Dashboard without touching the original file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    view_payload = deepcopy(payload)
    view_payload["limitations"] = list(LIMITATION_ZH)
    proxy = view_payload.get("public_fill_proxy")
    if isinstance(proxy, dict):
        candidates = proxy.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, dict):
                    candidate["display_name"] = strategy_label(
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
    generated = _taipei_display(view_payload.get("generated_at", ""))
    capitals = "".join(
        f'<option value="{value}">{value:,} USDT</option>'
        for value in range(1000, 10001, 1000)
    )
    estimates = view_payload.get("market_estimates", [])
    market_cards = "".join(
        f'<div class="status-card"><b>{escape(str(item.get("market", "")))}</b>'
        '<span class="good">已達最低建模門檻</span></div>'
        for item in estimates
        if isinstance(item, dict)
    )
    limitations = "".join(f"<li>{escape(item)}</li>" for item in LIMITATION_ZH)

    html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Bitfinex 放貸策略實驗室｜中文可讀版</title>
  <style>
    :root{{--ink:#17233c;--muted:#60708e;--paper:#f3f6fb;--card:#fff;--blue:#2257d6;--cyan:#168b95;--amber:#9a5a00;--line:#dce3ef;--green:#13795b}}
    *{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#edf3ff,#fafcff 48%,#eaf8f7);color:var(--ink);font-family:"Segoe UI","Noto Sans TC",sans-serif}}
    main{{max-width:1140px;margin:auto;padding:34px 22px 64px}} h1{{font-size:clamp(30px,5vw,48px);margin:6px 0 8px;letter-spacing:-.04em}} h2{{font-size:21px;margin:0 0 10px}} h3{{font-size:16px;margin:0 0 8px}} p{{line-height:1.65}}
    .sub,.hint{{color:var(--muted)}} .eyebrow{{color:var(--blue);font-weight:800;letter-spacing:.08em}} .badge{{display:inline-block;background:#fff2d9;color:#7d4900;border:1px solid #efc676;border-radius:999px;padding:7px 12px;font-weight:750}}
    header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}} .notice{{background:#17233c;color:white;border-radius:18px;padding:18px 22px;display:flex;justify-content:space-between;gap:18px;align-items:center}}
    .progress{{min-width:210px;text-align:right}} .bar{{height:7px;background:#ffffff2e;border-radius:9px;overflow:hidden;margin-top:7px}} .bar i{{display:block;height:100%;width:{progress:.3f}%;background:#49d3c7}}
    .card{{background:var(--card);border:1px solid #e1e7f0;border-radius:18px;padding:22px;box-shadow:0 10px 28px #21385b12;margin-top:18px}}
    .status-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}} .status-card{{border:1px solid var(--line);border-radius:13px;padding:14px;display:flex;justify-content:space-between;gap:8px}} .good{{color:var(--green);font-size:13px;font-weight:800}}
    .controls{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:18px}} label{{font-size:13px;color:var(--muted);font-weight:750}} select{{display:block;width:100%;margin-top:7px;border:1px solid var(--line);border-radius:12px;padding:12px;background:white;color:var(--ink);font-size:15px}}
    .grid{{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}} .metric{{font-size:34px;font-weight:850;margin:6px 0}} dl{{display:grid;grid-template-columns:1fr auto;gap:10px;margin:18px 0 0}} dt{{color:var(--muted)}} dd{{font-weight:750;margin:0;text-align:right}}
    .proxy-head{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}} .explain{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:18px}} .explain div{{background:#f5f8fc;border-radius:12px;padding:12px;font-size:13px;line-height:1.5}}
    .table-wrap{{overflow:auto;margin-top:18px}} table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}} th{{color:var(--muted);font-size:12px}} .strategy-name{{font-weight:800}} .strategy-code,.tag{{display:block;color:var(--muted);font-size:12px;margin-top:3px}} .tag{{color:var(--blue);font-weight:800}}
    .limits li{{color:#455572;margin:10px 0;line-height:1.6}} footer{{margin-top:22px;color:var(--muted);font-size:13px}}
    @media(max-width:760px){{header,.notice,.proxy-head{{display:block}}.badge,.progress{{margin-top:12px}}.progress{{text-align:left}}.controls,.grid,.status-grid,.explain{{grid-template-columns:1fr}}}}
  </style>
</head>
<body><main>
  <header><div><div class="eyebrow">中文可讀版｜唯讀研究工具</div><h1>Bitfinex 放貸策略實驗室</h1><p class="sub">先分清楚利率模型與成交代理，再比較可能收益。</p></div><span class="badge">實驗版，不會自動下單</span></header>
  <section class="notice"><div><strong>fUST 正式資料仍在蒐集</strong><div>目前只能顯示公開市場成交代理，不以 fUSD 取代 fUST 市場行為。</div></div><div class="progress"><b>{observed} / {required} 小時</b><div class="bar"><i></i></div></div></section>
  <section class="card"><div class="eyebrow">第一部分</div><h2>原生資產利率模型</h2><p class="hint">下列市場已達程式允許建模的最低門檻；這不等於已達正式投資可信度。</p><div class="status-grid">{market_cards}</div></section>
  <section class="controls">
    <label>本金（USDT 等值）<select id="capital">{capitals}</select></label>
    <label>原生資產市場<select id="asset"></select></label>
    <label>假設完整借出天數<select id="period"><option value="2">2 天</option><option value="5">5 天</option><option value="10">10 天</option><option value="30">30 天</option></select></label>
  </section>
  <section class="grid"><article class="card" id="result"></article><aside class="card"><h2>理論收益怎麼看？</h2><p>這一區使用最近一期歷史驗證利率，假設本金立即全額成交並持續借出，再扣除 15% 手續費。</p><p><b>它不是目前建議掛單利率，也沒有估算成交機率。</b></p></aside></section>
  <section class="card"><div class="proxy-head"><div><div class="eyebrow">第二部分</div><h2>fUST 公開市場成交代理</h2><p class="hint">用公開市場資料估算等待與資金閒置，不能證明個人掛單一定成交。</p></div><span class="badge">非常低可信度</span></div><div id="market-result"></div>
    <div class="explain"><div><b>候選日利率</b><br>依過去 24 小時利率分位點決定。</div><div><b>代理成交率</b><br>後續公開市場曾碰到該利率的比例。</div><div><b>最長等待</b><br>願意等待掛單成交的時間上限。</div><div><b>資金閒置</b><br>等待或未成交造成的空轉比例。</div></div>
    <div class="table-wrap"><table id="market-table"></table></div>
  </section>
  <section class="card limits"><h2>使用限制</h2><ul>{limitations}</ul></section>
  <footer>產生時間｜台灣時間：{generated} · 唯讀研究工具，不會下單</footer>
</main>
<script id="dashboard-data" type="application/json">{embedded}</script>
<script>
const data=JSON.parse(document.getElementById('dashboard-data').textContent);
const asset=document.getElementById('asset'),capital=document.getElementById('capital'),period=document.getElementById('period'),result=document.getElementById('result'),marketResult=document.getElementById('market-result'),marketTable=document.getElementById('market-table');
const safe=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const number=(value,digits=8)=>new Intl.NumberFormat('zh-TW',{{maximumFractionDigits:digits}}).format(Number(value));
const assets=[...new Set(data.scenarios.map(row=>row.asset))];
asset.innerHTML=assets.map(value=>`<option value="${{safe(value)}}">${{safe(value)}}</option>`).join('');
function render(){{
 const row=data.scenarios.find(item=>item.asset===asset.value&&item.capital_usdt===capital.value&&String(item.period_days)===period.value);
 if(!row){{result.innerHTML='<div class="hint">這個條件目前沒有可安全顯示的模型情境。</div>';return}}
 result.innerHTML=`<div class="eyebrow">條件式理論收益</div><h2>${{safe(row.asset)}} 原生資產結果</h2><div class="metric">+${{number(row.net_interest_native)}} ${{safe(row.asset)}}</div><div class="hint">約 +${{number(row.net_interest_usdt,2)}} USDT</div><dl><dt>模型驗證日利率</dt><dd>${{number(Number(row.daily_rate)*100,6)}}%</dd><dt>原生本金</dt><dd>${{number(row.principal_native)}} ${{safe(row.asset)}}</dd><dt>扣費後期末</dt><dd>${{number(row.ending_native)}} ${{safe(row.asset)}}</dd><dt>USDT 等值期末</dt><dd>${{number(row.ending_usdt,2)}} USDT</dd></dl>`;
}}
function renderMarket(){{
 const proxy=data.public_fill_proxy||{{status:'insufficient_data',candidates:[]}};
 const rows=(proxy.candidates||[]).filter(row=>String(row.period_days)===period.value).sort((a,b)=>Number(b.expected_30d_net_profit_per_1000)-Number(a.expected_30d_net_profit_per_1000));
 if(proxy.status!=='experimental'||!rows.length){{marketResult.innerHTML='<p class="hint">fUST 連續資料尚不足以產生成交代理比較。</p>';marketTable.innerHTML='';return}}
 const best=rows[0],scale=Number(capital.value)/1000,profit=Number(best.expected_30d_net_profit_per_1000)*scale;
 marketResult.innerHTML=`<div class="metric">+${{number(profit,2)}} USDT</div><div class="hint">目前樣本中最高的 30 天代理期望收益</div><dl><dt>策略</dt><dd>${{safe(best.display_name)}}</dd><dt>歷史候選日利率</dt><dd>${{number(Number(best.average_candidate_daily_rate)*100,6)}}%</dd><dt>公開成交代理率</dt><dd>${{number(Number(best.proxy_fill_probability)*100,1)}}%</dd><dt>成交時平均等待</dt><dd>${{number(best.average_success_wait_hours,1)}} 小時</dd><dt>估計資金閒置</dt><dd>${{number(Number(best.idle_fraction)*100,1)}}%</dd></dl>`;
 const baselines=new Set(Object.values(proxy.baselines||{{}})),top=rows.slice(0,3),shown=[...top,...rows.filter(row=>baselines.has(row.strategy_id)&&!top.some(item=>item.strategy_id===row.strategy_id))];
 marketTable.innerHTML='<thead><tr><th>候選策略</th><th>日利率</th><th>代理成交率</th><th>閒置</th><th>30 天期望收益</th></tr></thead><tbody>'+shown.map((row,index)=>{{const rowProfit=Number(row.expected_30d_net_profit_per_1000)*scale;const tags=[];if(index===0)tags.push('目前樣本最高');if(baselines.has(row.strategy_id))tags.push('比較基準');if(index>0&&profit-rowProfit<=0.01)tags.push('與第一名差異極小');return `<tr><td><span class="strategy-name">${{safe(row.display_name)}}</span><span class="strategy-code">${{safe(row.strategy_id)}}</span><span class="tag">${{tags.join('｜')}}</span></td><td>${{number(Number(row.average_candidate_daily_rate)*100,6)}}%</td><td>${{number(Number(row.proxy_fill_probability)*100,1)}}%</td><td>${{number(Number(row.idle_fraction)*100,1)}}%</td><td>${{number(rowProfit,2)}} USDT</td></tr>`}}).join('')+'</tbody>';
}}
asset.addEventListener('change',render);capital.addEventListener('change',()=>{{render();renderMarket()}});period.addEventListener('change',()=>{{render();renderMarket()}});render();renderMarket();
</script></body></html>"""

    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(html, encoding="utf-8", newline="\n")
    temporary.replace(output_path)
    return output_path
