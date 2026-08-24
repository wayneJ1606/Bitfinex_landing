from pathlib import Path


SCRIPT = Path("scripts/install-private-account-collector.ps1")


def test_private_scheduler_script_has_safe_defaults_and_five_minute_trigger():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "BitfinexPrivateAccountCollector" in content
    assert "New-TimeSpan -Minutes 5" in content
    assert "MultipleInstances" in content
    assert "IgnoreNew" in content
    assert "Interactive" in content
    assert "Limited" in content
    assert "-Enable" in content
    assert "Register-ScheduledTask" in content
    assert "pythonw.exe" in content


def test_private_scheduler_script_does_not_contain_credentials_or_write_endpoints():
    content = SCRIPT.read_text(encoding="utf-8").lower()

    assert "api_secret" not in content
    assert "super-secret" not in content
    assert "/auth/w/order/submit" not in content
    assert "/auth/w/funding/offer/submit" not in content
