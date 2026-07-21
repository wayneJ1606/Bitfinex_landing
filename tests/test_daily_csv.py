from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.csv_export import CsvExportError
from bitfinex_lending.daily_csv import append_daily_snapshot
from bitfinex_lending.models import FundingBookRow


def make_rows(
    run_id: str = "run-1",
    market: str = "fUSD",
    fetched_at: str = "2026-07-21T13:17:00+00:00",
) -> tuple[FundingBookRow, ...]:
    return (
        FundingBookRow(run_id, market, 0.0002, 2, 3, 10.5, "offer", fetched_at),
        FundingBookRow(run_id, market, 0.0003, 7, 1, -4.0, "demand", fetched_at),
    )


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def test_append_daily_snapshot_uses_utc_daily_market_path(tmp_path: Path) -> None:
    path = append_daily_snapshot(
        make_rows(fetched_at="2026-07-22T01:17:00+12:00"), tmp_path
    )

    assert path == tmp_path / "2026" / "07" / "21" / "fUSD.csv"
    assert read_csv(path)[0] == [
        "run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at"
    ]
    assert len(read_csv(path)) == 3


def test_append_daily_snapshot_appends_without_repeating_header(tmp_path: Path) -> None:
    path = append_daily_snapshot(make_rows("run-1"), tmp_path)
    append_daily_snapshot(
        make_rows("run-2", fetched_at="2026-07-21T14:17:00+00:00"), tmp_path
    )

    content = read_csv(path)
    assert len(content) == 5
    assert sum(row and row[0] == "run_id" for row in content) == 1
    assert {row[0] for row in content[1:]} == {"run-1", "run-2"}


def test_append_daily_snapshot_deduplicates_same_run_id(tmp_path: Path) -> None:
    path = append_daily_snapshot(make_rows("same-run"), tmp_path)
    append_daily_snapshot(make_rows("same-run"), tmp_path)

    assert len(read_csv(path)) == 3


def test_append_daily_snapshot_rejects_empty_mixed_and_naive_rows(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one row"):
        append_daily_snapshot((), tmp_path)

    mixed = list(make_rows())
    mixed[1] = FundingBookRow(**{**mixed[1].__dict__, "market": "fBTC"})
    with pytest.raises(ValueError, match="share run_id and market"):
        append_daily_snapshot(tuple(mixed), tmp_path)

    with pytest.raises(ValueError, match="include a timezone"):
        append_daily_snapshot(make_rows(fetched_at="2026-07-21T13:17:00"), tmp_path)


@pytest.mark.parametrize("market", ["fDOGE", "../escape", "fUSD/../../escape"])
def test_append_daily_snapshot_rejects_unsupported_and_path_like_markets(
    tmp_path: Path, market: str
) -> None:
    with pytest.raises(ValueError, match="supported market"):
        append_daily_snapshot(make_rows(market=market), tmp_path)


def test_append_daily_snapshot_rejects_rows_from_different_utc_dates(
    tmp_path: Path,
) -> None:
    mixed = list(make_rows())
    mixed[1] = FundingBookRow(
        **{**mixed[1].__dict__, "fetched_at": "2026-07-22T01:00:00+00:00"}
    )

    with pytest.raises(ValueError, match="same UTC date"):
        append_daily_snapshot(tuple(mixed), tmp_path)


def test_append_daily_snapshot_removes_temporary_file_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = append_daily_snapshot(make_rows("existing-run"), tmp_path)
    original = path.read_bytes()

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(CsvExportError, match="failed to append daily CSV"):
        append_daily_snapshot(make_rows("new-run"), tmp_path)
    assert path.read_bytes() == original
    assert list(tmp_path.rglob("*.tmp")) == []


def test_append_daily_snapshot_cleanup_failure_does_not_mask_export_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    def fail_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError("cleanup failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(CsvExportError, match="replace failed"):
        append_daily_snapshot(make_rows(), tmp_path)
