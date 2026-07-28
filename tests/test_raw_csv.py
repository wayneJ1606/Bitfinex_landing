from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.raw_csv import RAW_FIELDS, RawCsvError, load_raw_snapshots


def write_raw(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(RAW_FIELDS)
        writer.writerows(rows)


def raw_row(**overrides: str) -> list[str]:
    values = {
        "run_id": "run-1",
        "market": "fUSD",
        "rate": "0.0002",
        "period": "2",
        "count": "1",
        "amount": "10",
        "side": "offer",
        "fetched_at": "2026-07-21T13:17:00+00:00",
    }
    values.update(overrides)
    return [values[field] for field in RAW_FIELDS]


def write_with_header(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def test_loads_multiple_days_in_utc_order_and_deduplicates_exact_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    write_raw(
        root / "2026/07/22/fUSD.csv",
        [
            [
                "run-2",
                "fUSD",
                "0.0003",
                "7",
                "2",
                "-5",
                "demand",
                "2026-07-22T09:17:00+08:00",
            ],
        ],
    )
    duplicated = [
        "run-1",
        "fUSD",
        "0.0002",
        "2",
        "1",
        "10",
        "offer",
        "2026-07-21T13:17:00+00:00",
    ]
    write_raw(root / "2026/07/21/fUSD.csv", [duplicated, duplicated])

    rows = load_raw_snapshots(root)

    assert len(rows) == 2
    assert [row.run_id for row in rows] == ["run-1", "run-2"]
    assert rows[1].fetched_at == "2026-07-22T01:17:00+00:00"
    assert rows[0].rate == 0.0002
    assert rows[0].period == 2
    assert rows[0].count == 1


def test_missing_raw_root_returns_empty_tuple(tmp_path: Path) -> None:
    assert load_raw_snapshots(tmp_path / "missing") == ()


def test_existing_raw_root_must_be_a_directory(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(RawCsvError, match="raw root must be a directory"):
        load_raw_snapshots(root)


@pytest.mark.parametrize("method_name", ["exists", "is_dir"])
def test_converts_root_inspection_oserror_to_raw_csv_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method_name: str
) -> None:
    root = tmp_path / "raw"
    root.mkdir()

    def fail_inspection(path: Path) -> bool:
        if path == root:
            raise OSError("inspection denied")
        return True

    monkeypatch.setattr(Path, method_name, fail_inspection)

    with pytest.raises(RawCsvError, match="inspection denied") as raised:
        load_raw_snapshots(root)

    assert isinstance(raised.value.__cause__, OSError)


def test_converts_recursive_discovery_oserror_to_raw_csv_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "raw"
    root.mkdir()

    def fail_discovery(path: Path, pattern: str):
        assert path == root
        assert pattern == "*.csv"
        yield root / "2026/07/21/fUSD.csv"
        raise OSError("discovery denied")

    monkeypatch.setattr(Path, "rglob", fail_discovery)

    with pytest.raises(RawCsvError, match="discovery denied") as raised:
        load_raw_snapshots(root)

    assert isinstance(raised.value.__cause__, OSError)


@pytest.mark.parametrize(
    "relative_path",
    [
        "fUSD.csv",
        "archive/fUSD.csv",
        "26/07/21/fUSD.csv",
        "2026/7/21/fUSD.csv",
        "2026/07/1/fUSD.csv",
        "2026/13/21/fUSD.csv",
        "2026/02/30/fUSD.csv",
        "archive/2026/07/21/fUSD.csv",
    ],
)
def test_rejects_csv_outside_strict_daily_market_path(
    tmp_path: Path, relative_path: str
) -> None:
    root = tmp_path / "raw"
    write_raw(root / relative_path, [raw_row()])

    with pytest.raises(
        RawCsvError, match=r"path must match YYYY/MM/DD/<supported-market>\.csv"
    ):
        load_raw_snapshots(root)


@pytest.mark.parametrize(
    ("reason", "header", "values", "filename"),
    [
        ("missing field", ["run_id", "market"], ["run-1", "fUSD"], "fUSD.csv"),
        ("extra field", [*RAW_FIELDS, "extra"], [*raw_row(), "x"], "fUSD.csv"),
        (
            "duplicate field",
            [*RAW_FIELDS, "market"],
            [*raw_row(), "fUSD"],
            "fUSD.csv",
        ),
        ("unsupported market", list(RAW_FIELDS), raw_row(market="fDOGE"), "fDOGE.csv"),
        (
            "path market does not match row",
            list(RAW_FIELDS),
            raw_row(market="fBTC"),
            "fUSD.csv",
        ),
        (
            "timestamp must include timezone",
            list(RAW_FIELDS),
            raw_row(fetched_at="2026-07-21T13:17:00"),
            "fUSD.csv",
        ),
        ("rate must be finite", list(RAW_FIELDS), raw_row(rate="nan"), "fUSD.csv"),
        ("period must be positive", list(RAW_FIELDS), raw_row(period="0"), "fUSD.csv"),
        ("count must be nonnegative", list(RAW_FIELDS), raw_row(count="-1"), "fUSD.csv"),
        ("amount must not be zero", list(RAW_FIELDS), raw_row(amount="0"), "fUSD.csv"),
        (
            "offer amount must be positive",
            list(RAW_FIELDS),
            raw_row(side="offer", amount="-1"),
            "fUSD.csv",
        ),
        (
            "demand amount must be negative",
            list(RAW_FIELDS),
            raw_row(side="demand", amount="1"),
            "fUSD.csv",
        ),
    ],
)
def test_rejects_invalid_raw_csv(
    tmp_path: Path,
    reason: str,
    header: list[str],
    values: list[str],
    filename: str,
) -> None:
    root = tmp_path / "raw"
    write_with_header(root / "2026/07/21" / filename, header, [values])

    with pytest.raises(RawCsvError, match=reason):
        load_raw_snapshots(root)


def test_rejects_invalid_utf8(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    path = root / "2026/07/21/fUSD.csv"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"run_id,market\n\xff")

    with pytest.raises(RawCsvError, match="invalid UTF-8"):
        load_raw_snapshots(root)


def test_rejects_conflicting_normalized_timestamps_for_run_and_market(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    write_raw(
        root / "2026/07/21/fUSD.csv",
        [
            raw_row(fetched_at="2026-07-21T13:17:00+00:00"),
            raw_row(rate="0.0003", fetched_at="2026-07-21T14:17:00+00:00"),
        ],
    )

    with pytest.raises(RawCsvError, match="run_id has conflicting fetched_at"):
        load_raw_snapshots(root)
