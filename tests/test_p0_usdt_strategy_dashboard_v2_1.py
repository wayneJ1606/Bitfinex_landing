from __future__ import annotations

from pathlib import Path

import pytest

from bitfinex_lending.p0_usdt_strategy_dashboard_v2_1 import (
    export_usdt_strategy_dashboard_v2_1,
    period_baseline_ids,
)


def _candidate(strategy_id: str, period_days: int, profit: str) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "rate_quantile": strategy_id[1:3],
        "period_days": period_days,
        "wait_hours": int(strategy_id.rsplit("w", 1)[1]),
        "observations": 120,
        "proxy_fills": 100,
        "proxy_fill_probability": "0.8333",
        "average_success_wait_hours": "1.5",
        "average_candidate_daily_rate": "0.00016",
        "expected_30d_net_profit_per_1000": profit,
        "idle_fraction": "0.02",
        "confidence": "very_low",
        "method": "public_trade_high_proxy",
    }


def _payload() -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for period in (2, 5, 10, 30):
        candidates.extend(
            (
                _candidate(f"q90-p{period}-w24", period, "4.50"),
                _candidate(f"q75-p{period}-w12", period, "4.40"),
                _candidate(f"q25-p{period}-w3", period, "4.30"),
                _candidate(f"q10-p{period}-w1", period, "2.70"),
                _candidate(f"q50-p{period}-w24", period, "4.00"),
            )
        )
    return {
        "schema_version": "p0-experimental-dashboard-v2",
        "status": "experimental",
        "generated_at": "2026-08-25T14:06:06+00:00",
        "usdt_market": {
            "status": "collecting",
            "observed_hours": 168,
            "required_hours": 1440,
        },
        "public_fill_proxy": {
            "status": "experimental",
            "confidence": "very_low",
            "candidates": candidates,
        },
        "limitations": [],
        "read_only": True,
        "automatic_trading": False,
    }


@pytest.mark.parametrize("period", (2, 5, 10, 30))
def test_period_baseline_ids_are_specific_to_selected_period(period: int) -> None:
    assert period_baseline_ids(period) == (
        f"q10-p{period}-w1",
        f"q50-p{period}-w24",
    )


def test_period_baseline_ids_reject_unknown_period() -> None:
    with pytest.raises(ValueError, match="unsupported period"):
        period_baseline_ids(7)


def test_v2_1_is_separate_usdt_only_and_read_only(tmp_path: Path) -> None:
    original = tmp_path / "dashboard.html"
    readable_v2 = tmp_path / "dashboard_readable_zh.html"
    original.write_bytes(b"ORIGINAL")
    readable_v2.write_bytes(b"READABLE-V2")

    output = export_usdt_strategy_dashboard_v2_1(
        _payload(), tmp_path / "dashboard_readable_zh_v2_1.html"
    )
    html = output.read_text(encoding="utf-8")

    assert output.name == "dashboard_readable_zh_v2_1.html"
    assert original.read_bytes() == b"ORIGINAL"
    assert readable_v2.read_bytes() == b"READABLE-V2"
    assert "USDT 放貸候選策略" in html
    assert "本金" in html
    assert "借出天數" in html
    assert 'id="asset"' not in html
    assert "原生資產利率模型" not in html
    assert "條件式理論收益" not in html
    for period in (2, 5, 10, 30):
        assert f"q10-p{period}-w1" in html
        assert f"q50-p{period}-w24" in html
    assert "快速成交基準" in html
    assert "中位利率基準" in html
    assert "僅供研究參考" in html
    assert "2026/08/25 22:06" in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "/auth/w/" not in html


def test_v2_1_escapes_embedded_script_terminator(tmp_path: Path) -> None:
    payload = _payload()
    payload["public_fill_proxy"]["candidates"][0]["strategy_id"] = (  # type: ignore[index]
        "</script><script>alert(1)</script>"
    )

    html = export_usdt_strategy_dashboard_v2_1(
        payload, tmp_path / "dashboard_readable_zh_v2_1.html"
    ).read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html
