"""Export a self-contained, read-only Traditional Chinese dashboard."""

from __future__ import annotations

import json
from pathlib import Path


def export_experimental_dashboard(payload: dict[str, object], output_path: Path) -> Path:
    """Write a static dashboard whose JavaScript only filters embedded data."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    usdt = payload.get("usdt_market", {})
    observed = usdt.get("observed_hours", 0) if isinstance(usdt, dict) else 0
    required = usdt.get("required_hours", 1440) if isinstance(usdt, dict) else 1440
    progress = min(100.0, (float(observed) / float(required) * 100.0) if required else 0.0)
    generated_at = str(payload.get("generated_at", ""))
    capitals = "".join(f'<option value="{value}">{value:,} USDT</option>' for value in range(1000, 10001, 1000))
    html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Bitfinex 放貸策略實驗室</title>
  <style>
    :root{{--ink:#17233c;--muted:#60708e;--paper:#f3f6fb;--card:#fff;--blue:#2257d6;--cyan:#1f9eb5;--amber:#b66a00;--line:#dce3ef}}
    *{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#eef3ff,#f8fafc 46%,#eaf8f7);color:var(--ink);font-family:"Segoe UI","Noto Sans TC",sans-serif}}
    main{{max-width:1120px;margin:auto;padding:36px 22px 64px}} header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:24px}}
    h1{{font-size:clamp(28px,5vw,48px);letter-spacing:-.04em;margin:6px 0 8px}} h2{{font-size:18px;margin:0 0 14px}} p{{line-height:1.65}}
    .eyebrow{{color:var(--blue);font-weight:800;letter-spacing:.12em}} .badge{{background:#fff2d9;color:#8b5100;border:1px solid #f0c77e;border-radius:999px;padding:8px 13px;font-weight:750;white-space:nowrap}}
    .notice{{background:#17233c;color:white;border-radius:18px;padding:18px 22px;display:flex;justify-content:space-between;gap:18px;align-items:center;box-shadow:0 14px 35px #1a315226}}
    .notice strong{{display:block;margin-bottom:5px}} .progress{{min-width:190px;text-align:right;font-variant-numeric:tabular-nums}} .bar{{height:7px;background:#ffffff2e;border-radius:9px;overflow:hidden;margin-top:7px}} .bar i{{display:block;height:100%;background:#49d3c7;width:{progress:.3f}%}}
    .controls{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}} label{{font-size:13px;color:var(--muted);font-weight:700}} select{{display:block;width:100%;margin-top:7px;border:1px solid var(--line);border-radius:12px;padding:12px;background:white;color:var(--ink);font-size:15px}}
    .grid{{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}} .card{{background:var(--card);border:1px solid #e4e9f2;border-radius:18px;padding:22px;box-shadow:0 10px 28px #21385b12}}
    .metric{{font-size:34px;font-weight:800;letter-spacing:-.03em;margin:6px 0}} .sub{{color:var(--muted)}} dl{{display:grid;grid-template-columns:1fr auto;gap:11px;margin:20px 0 0}} dt{{color:var(--muted)}} dd{{font-weight:700;margin:0;font-variant-numeric:tabular-nums}}
    .market{{margin-top:18px}} .market-head{{display:flex;justify-content:space-between;gap:16px;align-items:start}} .market-head p{{margin:0;color:var(--muted)}}
    .table-wrap{{overflow:auto;margin-top:18px}} table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{padding:11px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}} th{{color:var(--muted);font-size:12px}}
    .limits{{margin-top:18px}} .limits li{{color:#4d5d78;margin:8px 0;line-height:1.5}} .empty{{padding:28px 0;color:var(--muted)}} footer{{margin-top:22px;color:var(--muted);font-size:13px}}
    @media(max-width:720px){{header,.notice{{display:block}}.badge{{display:inline-block;margin-top:12px}}.progress{{text-align:left;margin-top:14px}}.controls,.grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body><main>
  <header><div><div class="eyebrow">BITFINEX FUNDING · DASHBOARD-FIRST</div><h1>放貸策略實驗室</h1><p class="sub">先看得懂產品，再逐步補足可靠性。所有數字均保留原生資產計算。</p></div><span class="badge">實驗版 · 資料尚未達正式門檻</span></header>
  <section class="notice"><div><strong>USDT 市場資料仍在蒐集</strong><span>不以 fUSD 的成交機率、等待時間或市場行為代替 fUST。</span></div><div class="progress"><b>{observed} / {required} 小時</b><div class="bar"><i></i></div></div></section>
  <section class="controls">
    <label>本金（USDT 等值）<select id="capital">{capitals}</select></label>
    <label>原生資產市場<select id="asset"></select></label>
    <label>假設完整借出天數<select id="period"><option value="2">2 天</option><option value="5">5 天</option><option value="10">10 天</option><option value="30">30 天</option></select></label>
  </section>
  <section class="grid"><article class="card" id="result"></article><aside class="card"><h2>這個數字代表什麼？</h2><p>採用既有模型在歷史驗證區間的最近一筆利率估計，假設本金立即全額成交，並在所選天數內持續借出，再扣除 15% 手續費。</p><p><b>它不是成交機率模型，也不是目前建議掛單利率。</b></p></aside></section>
  <section class="card market"><div class="market-head"><div><div class="eyebrow">fUST PUBLIC MARKET PROXY</div><h2>市場預期比較</h2><p>公開成交代理，不是個人掛單成交保證。數值已計入等待、未成交與本金閒置。</p></div><span class="badge">非常低可信度實驗值</span></div><div id="market-result"></div><div class="table-wrap"><table id="market-table"></table></div></section>
  <section class="card limits"><h2>使用限制</h2><ul id="limitations"></ul></section>
  <footer>產生時間：{generated_at} · 唯讀研究工具，不會下單</footer>
</main>
<script id="dashboard-data" type="application/json">{embedded}</script>
<script>
const data=JSON.parse(document.getElementById('dashboard-data').textContent);
const asset=document.getElementById('asset'),capital=document.getElementById('capital'),period=document.getElementById('period'),result=document.getElementById('result');
const marketResult=document.getElementById('market-result'),marketTable=document.getElementById('market-table');
const assets=[...new Set(data.scenarios.map(row=>row.asset))];
asset.innerHTML=assets.map(value=>`<option value="${{value}}">${{value}}</option>`).join('');
const limitList=document.getElementById('limitations');
data.limitations.forEach(value=>{{const item=document.createElement('li');item.textContent=value;limitList.append(item)}});
function number(value,digits=8){{return new Intl.NumberFormat('zh-TW',{{maximumFractionDigits:digits}}).format(Number(value))}}
function render(){{
 const row=data.scenarios.find(item=>item.asset===asset.value&&item.capital_usdt===capital.value&&String(item.period_days)===period.value);
 if(!row){{result.innerHTML='<div class="empty">這個市場目前沒有可安全顯示的模型情境。</div>';return}}
 result.innerHTML=`<div class="eyebrow">條件式收益情境</div><h2>${{row.asset}} 原生資產結果</h2><div class="metric">+${{number(row.net_interest_native)}} ${{row.asset}}</div><div class="sub">約 +${{number(row.net_interest_usdt,2)}} USDT（僅供直觀顯示）</div><dl><dt>模型驗證利率（日）</dt><dd>${{number(Number(row.daily_rate)*100,6)}}%</dd><dt>原生本金</dt><dd>${{number(row.principal_native)}} ${{row.asset}}</dd><dt>扣費後期末</dt><dd>${{number(row.ending_native)}} ${{row.asset}}</dd><dt>USDT 等值期末</dt><dd>${{number(row.ending_usdt,2)}} USDT</dd><dt>換算說明</dt><dd>${{row.conversion_note}}</dd></dl>`;
}}
function renderMarket(){{
 const proxy=data.public_fill_proxy||{{status:'insufficient_data',candidates:[]}};
 const rows=(proxy.candidates||[]).filter(row=>String(row.period_days)===period.value).sort((a,b)=>Number(b.expected_30d_net_profit_per_1000)-Number(a.expected_30d_net_profit_per_1000));
 if(proxy.status!=='experimental'||!rows.length){{marketResult.innerHTML='<div class="empty">fUST 連續資料尚不足以產生成交代理比較。</div>';marketTable.innerHTML='';return}}
 const best=rows[0],scale=Number(capital.value)/1000,profit=Number(best.expected_30d_net_profit_per_1000)*scale;
 marketResult.innerHTML=`<div class="metric">+${{number(profit,2)}} USDT</div><div class="sub">目前樣本中最高的 30 天代理期望收益；策略 ${{best.strategy_id}}</div><dl><dt>歷史候選日利率</dt><dd>${{number(Number(best.average_candidate_daily_rate)*100,6)}}%</dd><dt>公開成交代理機率</dt><dd>${{number(Number(best.proxy_fill_probability)*100,1)}}%</dd><dt>成交時平均等待</dt><dd>${{number(best.average_success_wait_hours,1)}} 小時</dd><dt>估計閒置比例</dt><dd>${{number(Number(best.idle_fraction)*100,1)}}%</dd><dt>可評估歷史時點</dt><dd>${{best.observations}} 筆</dd></dl>`;
 const baselines=new Set(Object.values(proxy.baselines||{{}})),top=rows.slice(0,5),shown=[...top,...rows.filter(row=>baselines.has(row.strategy_id)&&!top.some(item=>item.strategy_id===row.strategy_id))];
 marketTable.innerHTML='<thead><tr><th>候選策略</th><th>日利率</th><th>最長等待</th><th>代理成交率</th><th>閒置</th><th>30 天期望收益</th></tr></thead><tbody>'+shown.map(row=>`<tr><td>${{row.strategy_id}}${{baselines.has(row.strategy_id)?'（基準）':''}}</td><td>${{number(Number(row.average_candidate_daily_rate)*100,6)}}%</td><td>${{row.wait_hours}} 小時</td><td>${{number(Number(row.proxy_fill_probability)*100,1)}}%</td><td>${{number(Number(row.idle_fraction)*100,1)}}%</td><td>${{number(Number(row.expected_30d_net_profit_per_1000)*scale,2)}} USDT</td></tr>`).join('')+'</tbody>';
}}
asset.addEventListener('change',render); capital.addEventListener('change',()=>{{render();renderMarket()}}); period.addEventListener('change',()=>{{render();renderMarket()}}); render(); renderMarket();
</script></body></html>"""
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(html, encoding="utf-8", newline="\n")
    temporary.replace(output_path)
    return output_path
