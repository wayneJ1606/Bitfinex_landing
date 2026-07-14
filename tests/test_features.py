from __future__ import annotations

from pathlib import Path

import pytest

import bitfinex_lending.features as feature_cli
from bitfinex_lending.config import Settings
from bitfinex_lending.feature_calculation import FeatureCalculationError
from bitfinex_lending.feature_csv import FeatureCsvError
from bitfinex_lending.models import FundingBookRow
from bitfinex_lending.storage import StorageError


def snapshot() -> FundingBookRow:
    return FundingBookRow(
        "run-1", "fUSD", 0.0002, 2, 3, 10.0, "offer", "2026-07-14T10:00:00+00:00"
    )


class FakeStorage:
    def __init__(self, rows=(), failure: Exception | None = None) -> None:
        self.rows = tuple(rows)
        self.failure = failure
        self.events: list[str] = []
        self.replaced = None
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True
        if self.failure:
            raise self.failure

    def load_snapshots(self):
        self.events.append("load_snapshots")
        if self.failure:
            raise self.failure
        return self.rows

    def replace_features(self, features):
        self.events.append("replace_features")
        self.replaced = features


def test_pipeline_loads_calculates_replaces_exports_and_returns_summary(tmp_path: Path) -> None:
    storage = FakeStorage([snapshot()])

    def calculator(rows):
        storage.events.append("calculate")
        assert rows == storage.rows
        return feature_cli.calculate_features(rows)

    def exporter(features, output_directory):
        storage.events.append("export")
        assert features == storage.replaced
        assert output_directory == tmp_path
        return tmp_path / "modeling_features.csv"

    summary = feature_cli.run_feature_pipeline(
        storage, exporter, tmp_path, calculator=calculator
    )

    assert storage.events == [
        "load_snapshots",
        "calculate",
        "replace_features",
        "export",
    ]
    assert summary.source_row_count == 1
    assert summary.feature_count == 1
    assert summary.csv_path == tmp_path / "modeling_features.csv"


def test_pipeline_empty_input_still_exports(tmp_path: Path) -> None:
    storage = FakeStorage()
    exported = []

    def exporter(features, output_directory):
        exported.append((features, output_directory))
        return tmp_path / "modeling_features.csv"

    summary = feature_cli.run_feature_pipeline(storage, exporter, tmp_path)

    assert storage.replaced == ()
    assert exported == [((), tmp_path)]
    assert summary.source_row_count == summary.feature_count == 0


@pytest.mark.parametrize(
    "error",
    [
        OSError("directory denied"),
        StorageError("database locked"),
        FeatureCalculationError("invalid snapshot"),
        FeatureCsvError("export failed"),
    ],
)
def test_main_reports_expected_errors(
    error: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        database_path=tmp_path / "db" / "features.sqlite3",
        csv_directory=tmp_path / "csv",
    )
    storage = FakeStorage()
    monkeypatch.setattr(feature_cli, "build_dependencies", lambda _: storage)
    monkeypatch.setattr(feature_cli, "run_feature_pipeline", lambda *args: (_ for _ in ()).throw(error))

    assert feature_cli.main(settings) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"fatal: {error}\n"


def test_main_creates_directories_initializes_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        database_path=tmp_path / "db" / "features.sqlite3",
        csv_directory=tmp_path / "csv",
    )
    storage = FakeStorage()
    csv_path = settings.csv_directory / "modeling_features.csv"
    summary = feature_cli.FeatureRunSummary(7, 3, csv_path)
    monkeypatch.setattr(feature_cli, "build_dependencies", lambda _: storage)
    monkeypatch.setattr(feature_cli, "run_feature_pipeline", lambda *args: summary)

    assert feature_cli.main(settings) == 0
    output = capsys.readouterr()
    assert storage.initialized
    assert settings.database_path.parent.is_dir()
    assert settings.csv_directory.is_dir()
    assert output.out == f"source_rows=7 features=3 csv={csv_path}\n"
    assert output.err == ""
