from __future__ import annotations

from pathlib import Path

import pytest

import bitfinex_lending.__main__ as cli
from bitfinex_lending.config import Settings
from bitfinex_lending.daily_csv import append_daily_snapshot
from bitfinex_lending.models import MarketResult, RunSummary
from bitfinex_lending.storage import StorageError


class FakeStorage:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.initialized = False

    def initialize(self) -> None:
        if self.failure:
            raise self.failure
        self.initialized = True


def test_main_initializes_storage_creates_directories_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        database_path=tmp_path / "db" / "collector.sqlite3",
        csv_directory=tmp_path / "exports",
    )
    storage = FakeStorage()
    summary = RunSummary(
        run_id="run-1",
        results=(
            MarketResult("fUSD", "success", 2, "Fetched and stored 2 rows"),
            MarketResult("fBTC", "empty", 0, "Bitfinex returned an empty book"),
            MarketResult("fETH", "failed", 0, "request timed out"),
        ),
    )
    captured: dict[str, object] = {}

    def fake_run_collection(*args: object, **kwargs: object) -> RunSummary:
        captured["exporter"] = args[3]
        return summary

    monkeypatch.setattr(cli, "build_dependencies", lambda _: (object(), storage))
    monkeypatch.setattr(cli, "run_collection", fake_run_collection)

    exit_code = cli.main(settings)

    output = capsys.readouterr()
    assert exit_code == 1
    assert storage.initialized
    assert settings.database_path.parent.is_dir()
    assert settings.csv_directory.is_dir()
    assert captured["exporter"] is append_daily_snapshot
    assert "run_id=run-1" in output.out
    assert "fUSD success rows=2" in output.out
    assert "fBTC empty rows=0" in output.out
    assert "fETH failed rows=0" in output.out
    assert "success=1 empty=1 failed=1" in output.out
    assert output.err == ""


def test_main_reports_fatal_storage_error_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        csv_directory=tmp_path / "csv",
    )
    storage = FakeStorage(StorageError("database is locked"))
    monkeypatch.setattr(cli, "build_dependencies", lambda _: (object(), storage))

    assert cli.main(settings) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "fatal: database is locked\n"

