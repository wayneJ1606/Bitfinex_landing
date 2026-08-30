from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bitfinex_lending.p0_dashboard import DashboardDataError, export_dashboard


def _payload() -> dict[str, object]:
    return {
        "generated_at": "2026-10-01T02:00:00+00:00",
        "readiness_status": "insufficient_data",
        "status": "experimental",
        "limitations": ["研究用途，不構成投資建議", "成交機率為歷史估計"],
        "results": [
            {
                "asset": "USDT",
                "principal": "1000",
                "portfolio_type": "highest_return",
                "period_days": [2],
                "wait_hours": [1],
                "fill_probability": 0.8,
                "average_wait_hours": 0.5,
                "net_interest": "3.4",
                "ending_capital": "1003.4",
                "idle_fraction": 0.2,
                "net_profit_p10": "1.2",
            },
            {
                "asset": "USDT",
                "principal": "1000",
                "portfolio_type": "stable",
                "period_days": [2],
                "wait_hours": [1],
                "fill_probability": 0.9,
                "average_wait_hours": 0.4,
                "net_interest": "2.8",
                "ending_capital": "1002.8",
                "idle_fraction": 0.1,
                "net_profit_p10": "1.7",
            },
            {
                "asset": "USDT",
                "principal": "1000",
                "portfolio_type": "fixed_median",
                "period_days": [2],
                "wait_hours": [1],
                "fill_probability": 0.75,
                "average_wait_hours": 0.8,
                "net_interest": "2.5",
                "ending_capital": "1002.5",
                "idle_fraction": 0.25,
                "net_profit_p10": "0.9",
            },
        ],
    }


def _write_payload(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    source = tmp_path / "dashboard_data.json"
    source.write_text(
        json.dumps(_payload() if payload is None else payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return source


def test_dashboard_contains_only_approved_controls_and_read_only_copy(tmp_path: Path) -> None:
    path = export_dashboard(_write_payload(tmp_path), tmp_path)
    html = path.read_text(encoding="utf-8")

    assert path.name == "dashboard.html"
    assert 'id="capital"' in html
    assert 'value="1000"' in html and 'value="10000"' in html
    assert 'id="asset"' in html
    assert set(re.findall(r'data-period="(\d+)"', html)) == {"2", "5", "10", "30"}
    assert set(re.findall(r'data-wait="(\d+)"', html)) == {"1", "3", "6", "12", "24"}
    assert "本工具不會下單" in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "/auth/w/" not in html


def test_dashboard_embeds_canonical_data_and_required_sections(tmp_path: Path) -> None:
    path = export_dashboard(_write_payload(tmp_path), tmp_path)
    html = path.read_text(encoding="utf-8")

    assert 'id="dashboard-data"' in html
    assert "2026-10-01T02:00:00+00:00" in html
    assert '"ending_capital":"1003.4"' in html
    assert "資料尚未達正式門檻" in html
    assert "最高收益方案" in html and "較穩定替代方案" in html
    assert "基準策略比較" in html
    assert "最後成功資料時間" in html
    assert "資料可能已過期" in html
    assert "研究用途，不構成投資建議" in html


def test_dashboard_escapes_script_closing_text_inside_embedded_json(tmp_path: Path) -> None:
    payload = _payload()
    payload["limitations"] = ["請勿插入 </script><script>alert(1)</script>"]

    html = export_dashboard(_write_payload(tmp_path, payload), tmp_path).read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html


@pytest.mark.parametrize("payload", [{}, {"results": "not-a-list"}])
def test_dashboard_rejects_invalid_canonical_data(tmp_path: Path, payload: dict[str, object]) -> None:
    source = _write_payload(tmp_path, payload)

    with pytest.raises(DashboardDataError):
        export_dashboard(source, tmp_path)

    assert not (tmp_path / "dashboard.html").exists()
