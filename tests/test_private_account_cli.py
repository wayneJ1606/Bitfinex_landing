from bitfinex_lending import private_account_collector as module


def test_missing_credentials_fail_closed(monkeypatch, capsys):
    monkeypatch.delenv("BITFINEX_READONLY_API_KEY", raising=False)
    monkeypatch.delenv("BITFINEX_READONLY_API_SECRET", raising=False)

    assert module.main(["--dry-run"]) == 2
    assert "credentials" in capsys.readouterr().err.lower()


def test_dry_run_checks_permissions_without_collecting(monkeypatch, capsys):
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def check_permissions(self):
            calls.append("permissions")
            return ({"read": ["funding", "history"], "write": []},)

    monkeypatch.setenv("BITFINEX_READONLY_API_KEY", "key")
    monkeypatch.setenv("BITFINEX_READONLY_API_SECRET", "secret")
    monkeypatch.setattr(module, "ReadOnlyBitfinexClient", FakeClient)

    assert module.main(["--dry-run"]) == 0
    assert calls[0][1]["base_url"] == "https://api.bitfinex.com"
    assert calls[-1] == "permissions"
    assert "read-only permissions" in capsys.readouterr().out.lower()


def test_secret_value_is_not_printed_on_failure(monkeypatch, capsys):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def check_permissions(self):
            raise RuntimeError("permission check failed")

    monkeypatch.setenv("BITFINEX_READONLY_API_KEY", "key")
    monkeypatch.setenv("BITFINEX_READONLY_API_SECRET", "super-secret-value")
    monkeypatch.setattr(module, "ReadOnlyBitfinexClient", FailingClient)

    assert module.main(["--dry-run"]) == 1
    output = capsys.readouterr()
    assert "super-secret-value" not in output.out + output.err
