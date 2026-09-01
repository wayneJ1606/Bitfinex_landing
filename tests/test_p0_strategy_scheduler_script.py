import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SCRIPT = Path("scripts/install-p0-strategy-analysis.ps1")


def test_p0_strategy_scheduler_contract_is_daily_preview_first_and_hidden() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for token in (
        "BitfinexP0StrategyAnalysis",
        "-m bitfinex_lending.p0_strategy_pipeline",
        "pythonw.exe",
        "New-ScheduledTaskTrigger -Daily",
        '10:00',
        "StartWhenAvailable",
        "IgnoreNew",
        "ExecutionTimeLimit (New-TimeSpan -Minutes 30)",
        "Interactive",
        "Limited",
        "registration=not_requested",
        "-Enable",
    ):
        assert token in text


def test_p0_strategy_scheduler_preview_reports_contract_without_registration() -> None:
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required for the Windows scheduler preview")

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-ProjectRoot",
            ".",
            "-PythonPath",
            sys.executable,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    json_text, registration = completed.stdout.rsplit("registration=", maxsplit=1)
    contract = json.loads(json_text)
    assert contract["task_name"] == "BitfinexP0StrategyAnalysis"
    assert contract["arguments"] == "-m bitfinex_lending.p0_strategy_pipeline"
    assert contract["local_time"] == "10:00"
    assert contract["multiple_instances"] == "IgnoreNew"
    assert contract["start_when_available"] is True
    assert contract["execution_limit_minutes"] == 30
    assert contract["enabled"] is False
    assert registration.strip() == "not_requested"


def test_p0_strategy_scheduler_contains_no_credentials_or_write_endpoints() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()

    for forbidden in (
        "api_key",
        "api_secret",
        "bitfinex_readonly_api_key",
        "bitfinex_readonly_api_secret",
        "/auth/w/",
        "funding/offer/submit",
    ):
        assert forbidden not in text
