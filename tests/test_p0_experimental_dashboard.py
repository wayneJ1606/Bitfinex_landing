from __future__ import annotations

from pathlib import Path

from bitfinex_lending.p0_experimental_dashboard import export_experimental_dashboard


def test_dashboard_is_self_contained_read_only_and_shows_safety_boundary(tmp_path: Path) -> None:
    payload = {
        "schema_version": "p0-experimental-dashboard-v1",
        "status": "experimental",
        "generated_at": "2026-08-22T02:00:00+00:00",
        "market_estimates": [{"asset": "USD", "market": "fUSD", "model_name": "baseline_previous", "predicted_daily_rate": "0.001", "prediction_as_of": "2026-08-21T00:00:00+00:00", "rmse": "0.1"}],
        "scenarios": [{"asset": "USD", "market": "fUSD", "capital_usdt": "1000", "period_days": 2, "principal_native": "1000", "daily_rate": "0.001", "net_interest_native": "1.7", "ending_native": "1001.7", "net_interest_usdt": "1.7", "ending_usdt": "1001.7", "conversion_note": "USD/USDT 1:1"}],
        "usdt_market": {"status": "collecting", "observed_hours": 97, "required_hours": 1440, "recommendation_available": False},
        "public_fill_proxy": {
            "status": "experimental",
            "confidence": "very_low",
            "history_hours": 97,
            "lookback_hours": 24,
            "highest_expected_strategy_id": "q50-p2-w3",
            "baselines": {"quick_fill": "q10-p2-w1", "fixed_median": "q50-p2-w24"},
            "candidates": [
                {
                    "strategy_id": "q50-p2-w3",
                    "rate_quantile": "0.50",
                    "period_days": 2,
                    "wait_hours": 3,
                    "observations": 70,
                    "proxy_fills": 49,
                    "proxy_fill_probability": "0.7",
                    "average_success_wait_hours": "1.5",
                    "average_candidate_daily_rate": "0.001",
                    "expected_30d_net_profit_per_1000": "12.5",
                    "idle_fraction": "0.08",
                    "confidence": "very_low",
                    "method": "public_trade_high_proxy",
                }
            ],
            "method": "public_trade_high_proxy",
        },
        "limitations": ["fUSD market behavior is not used as a substitute for fUST market behavior."],
        "read_only": True,
        "automatic_trading": False,
    }

    path = export_experimental_dashboard(payload, tmp_path / "dashboard.html")
    html = path.read_text(encoding="utf-8")

    assert path.name == "dashboard.html"
    assert "實驗版" in html
    assert "唯讀研究工具，不會下單" in html
    assert "USDT 市場資料仍在蒐集" in html
    assert "97 / 1440 小時" in html
    assert 'id="capital"' in html
    assert 'id="asset"' in html
    assert 'id="period"' in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "/auth/w/" not in html
    assert "1001.7" in html
    assert "市場預期比較" in html
    assert "公開成交代理，不是個人掛單成交保證" in html
    assert "非常低可信度實驗值" in html
    assert 'id="market-result"' in html
    assert 'id="market-table"' in html
    assert "q50-p2-w3" in html


def test_dashboard_escapes_embedded_script_terminator(tmp_path: Path) -> None:
    payload = {
        "status": "experimental",
        "generated_at": "2026-08-22T02:00:00+00:00",
        "market_estimates": [],
        "scenarios": [],
        "usdt_market": {"status": "collecting", "observed_hours": 0, "required_hours": 1440, "recommendation_available": False},
        "public_fill_proxy": {"status": "insufficient_data", "candidates": []},
        "limitations": ["</script><script>alert(1)</script>"],
        "read_only": True,
        "automatic_trading": False,
    }
    html = export_experimental_dashboard(payload, tmp_path / "dashboard.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html
    assert "item.textContent=value" in html
    assert "innerHTML=data.limitations" not in html
