from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.csv_export import CsvExportError, export_snapshot
from bitfinex_lending.models import FundingBookRow


def make_rows() -> tuple[FundingBookRow, ...]:
    return (
        FundingBookRow(
            run_id="run-1",
            market="fUSD",
            rate=0.0002,
            period=2,
            count=3,
            amount=10.5,
            side="offer",
            fetched_at="2026-07-14T12:00:00+00:00",
        ),
        FundingBookRow(
            run_id="run-1",
            market="fUSD",
            rate=0.0003,
            period=7,
            count=1,
            amount=-4.0,
            side="demand",
            fetched_at="2026-07-14T12:00:00+00:00",
        ),
    )


def test_export_snapshot_writes_expected_utf8_csv(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "csv"

    path = export_snapshot(make_rows(), output_dir)

    assert path.parent == output_dir
    assert path.name == "2026-07-14T12-00-00_00-00_fUSD_run-1.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        content = list(csv.reader(stream))
    assert content[0] == [
        "run_id",
        "market",
        "rate",
        "period",
        "count",
        "amount",
        "side",
        "fetched_at",
    ]
    assert content[1] == [
        "run-1",
        "fUSD",
        "0.0002",
        "2",
        "3",
        "10.5",
        "offer",
        "2026-07-14T12:00:00+00:00",
    ]
    assert list(output_dir.glob("*.tmp")) == []


def test_export_snapshot_rejects_empty_or_mixed_rows(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one row"):
        export_snapshot((), tmp_path)

    mixed = list(make_rows())
    mixed[1] = FundingBookRow(**{**mixed[1].__dict__, "market": "fBTC"})
    with pytest.raises(ValueError, match="share run_id and market"):
        export_snapshot(tuple(mixed), tmp_path)


def test_export_snapshot_removes_temporary_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(CsvExportError, match="failed to export CSV"):
        export_snapshot(make_rows(), tmp_path)

    assert list(tmp_path.iterdir()) == []

