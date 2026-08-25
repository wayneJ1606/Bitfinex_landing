from __future__ import annotations

from pathlib import Path

from bitfinex_lending.p0_readable_dashboard import (
    export_readable_dashboard,
    strategy_label,
)


def _payload() -> dict[str, object]:
    candidates = [
        {
            "strategy_id": "q90-p30-w24",
            "rate_quantile": "0.90",
            "period_days": 30,
            "wait_hours": 24,
            "observations": 120,
            "proxy_fills": 110,
            "proxy_fill_probability": "0.9167",
            "average_success_wait_hours": "1.3",
            "average_candidate_daily_rate": "0.000175",
            "expected_30d_net_profit_per_1000": "4.475",
            "idle_fraction": "0.018",
            "confidence": "very_low",
            "method": "public_trade_high_proxy",
        },
        {
            "strategy_id": "q75-p30-w24",
            "rate_quantile": "0.75",
            "period_days": 30,
            "wait_hours": 24,
            "observations": 120,
            "proxy_fills": 118,
            "proxy_fill_probability": "0.9833",
            "average_success_wait_hours": "1.1",
            "average_candidate_daily_rate": "0.000163",
            "expected_30d_net_profit_per_1000": "4.470",
            "idle_fraction": "0.016",
            "confidence": "very_low",
            "method": "public_trade_high_proxy",
        },
        {
            "strategy_id": "q10-p30-w1",
            "rate_quantile": "0.10",
            "period_days": 30,
            "wait_hours": 1,
            "observations": 143,
            "proxy_fills": 143,
            "proxy_fill_probability": "1",
            "average_success_wait_hours": "1",
            "average_candidate_daily_rate": "0.000106",
            "expected_30d_net_profit_per_1000": "2.71",
            "idle_fraction": "0.0014",
            "confidence": "very_low",
            "method": "public_trade_high_proxy",
        },
    ]
    return {
        "schema_version": "p0-experimental-dashboard-v2",
        "status": "experimental",
        "generated_at": "2026-08-25T14:06:06+00:00",
        "market_estimates": [
            {"asset": "BTC", "market": "fBTC"},
            {"asset": "ETH", "market": "fETH"},
            {"asset": "USD", "market": "fUSD"},
        ],
        "scenarios": [
            {
                "asset": "USD",
                "market": "fUSD",
                "capital_usdt": "1000",
                "period_days": 30,
                "principal_native": "1000",
                "daily_rate": "0.00019",
                "net_interest_native": "4.845",
                "ending_native": "1004.845",
                "net_interest_usdt": "4.845",
                "ending_usdt": "1004.845",
                "conversion_note": "USD/USDT 1:1",
            }
        ],
        "usdt_market": {
            "status": "collecting",
            "observed_hours": 168,
            "required_hours": 1440,
            "recommendation_available": False,
        },
        "public_fill_proxy": {
            "status": "experimental",
            "confidence": "very_low",
            "baselines": {"quick_fill": "q10-p30-w1"},
            "candidates": candidates,
        },
        "limitations": [
            "fUSD market behavior is not used as a substitute for fUST market behavior.",
            "Rates are the latest chronological validation predictions, not live forward forecasts.",
        ],
        "read_only": True,
        "automatic_trading": False,
    }


def test_strategy_label_translates_approved_strategy_ids() -> None:
    assert strategy_label("q90-p30-w24") == "高利率｜借出 30 天｜最多等待 24 小時"
    assert strategy_label("q50-p5-w3") == "中位利率｜借出 5 天｜最多等待 3 小時"
    assert strategy_label("custom") == "custom"


def test_readable_dashboard_is_separate_chinese_and_read_only(tmp_path: Path) -> None:
    original = tmp_path / "dashboard.html"
    original.write_bytes(b"ORIGINAL-DASHBOARD")
    original_before = original.read_bytes()

    readable = export_readable_dashboard(
        _payload(), tmp_path / "dashboard_readable_zh.html"
    )
    html = readable.read_text(encoding="utf-8")

    assert readable.name == "dashboard_readable_zh.html"
    assert original.read_bytes() == original_before
    assert "原生資產利率模型" in html
    assert "已達最低建模門檻" in html
    assert "fUST 公開市場成交代理" in html
    assert "非常低可信度" in html
    assert "高利率｜借出 30 天｜最多等待 24 小時" in html
    assert "目前樣本最高" in html
    assert "比較基準" in html
    assert "與第一名差異極小" in html
    assert "fUSD 的市場行為不能替代 fUST" in html
    assert "台灣時間：2026/08/25 22:06" in html
    assert "fUSD market behavior is not used" not in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "/auth/w/" not in html


def test_readable_dashboard_escapes_embedded_script_terminator(tmp_path: Path) -> None:
    payload = _payload()
    payload["scenarios"] = [{"asset": "</script><script>alert(1)</script>"}]
    html = export_readable_dashboard(
        payload, tmp_path / "dashboard_readable_zh.html"
    ).read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html
