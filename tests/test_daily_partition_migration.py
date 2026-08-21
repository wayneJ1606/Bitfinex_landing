from __future__ import annotations

import csv
from pathlib import Path

import pytest

import bitfinex_lending.daily_partition_migration as migration
from bitfinex_lending.daily_partition_migration import (
    MigrationError,
    delete_verified_backup,
    migrate_staged_files,
    stage_legacy_files,
    verify_staged_migration,
)


ACCOUNT_HEADER = (
    "event_id",
    "collected_at",
    "source_timestamp",
    "source_endpoint",
    "schema_version",
    "raw_payload",
)
MARKET_HEADER = ("collected_at", "market", "frr")


def _write(path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def test_stage_migrate_and_verify_preserves_rows_in_utc_daily_files(tmp_path: Path) -> None:
    data = tmp_path / "data"
    backup = data / "archive" / "daily-partition-test"
    account_row = ("1", "2026-08-16T00:30:00+08:00", "1", "/private", "v1", "[]")
    market_row = ("2026-08-16T00:30:00+08:00", "fUST", "0.0002")
    _write(data / "account" / "funding_offers.csv", ACCOUNT_HEADER, [account_row])
    _write(data / "market" / "ticker" / "fUST.csv", MARKET_HEADER, [market_row])
    _write(
        data / "account" / "funding_offers" / "2026" / "08" / "15.csv",
        ACCOUNT_HEADER,
        [account_row],
    )
    (data / "account" / "account_events.sqlite3").write_bytes(b"db")

    staged = stage_legacy_files(data, backup)
    summary = migrate_staged_files(backup, data)
    verified = verify_staged_migration(backup, data)

    assert len(staged) == 2
    assert not (data / "account" / "funding_offers.csv").exists()
    assert (data / "account" / "account_events.sqlite3").exists()
    assert summary.source_rows == 2
    assert summary.inserted_rows == 1
    assert summary.duplicate_rows == 1
    assert verified == summary.source_rows
    assert (data / "account" / "funding_offers" / "2026" / "08" / "15.csv").exists()
    assert (data / "market" / "ticker" / "2026" / "08" / "15" / "fUST.csv").exists()


def test_delete_backup_requires_successful_verification(tmp_path: Path) -> None:
    data = tmp_path / "data"
    backup = data / "archive" / "daily-partition-test"
    row = ("1", "2026-08-16T12:00:00Z", "1", "/private", "v1", "[]")
    _write(data / "account" / "funding_offers.csv", ACCOUNT_HEADER, [row])
    stage_legacy_files(data, backup)

    with pytest.raises(MigrationError):
        delete_verified_backup(backup, data)
    assert backup.exists()

    migrate_staged_files(backup, data)
    deleted_rows = delete_verified_backup(backup, data)

    assert deleted_rows == 1
    assert not backup.exists()


def test_stage_rolls_back_every_source_when_the_nth_move_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    backup = data / "archive" / "daily-partition-test"
    first_source = data / "account" / "funding_offers.csv"
    second_source = data / "account" / "funding_trades.csv"
    row = ("1", "2026-08-16T12:00:00Z", "1", "/private", "v1", "[]")
    _write(first_source, ACCOUNT_HEADER, [row])
    _write(second_source, ACCOUNT_HEADER, [row])

    original_replace = Path.replace
    moves = 0

    def fail_second_move(source: Path, destination: Path) -> Path:
        nonlocal moves
        moves += 1
        if moves == 2:
            raise OSError("injected second move failure")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_second_move)

    with pytest.raises(MigrationError, match="injected second move failure"):
        migration.stage_legacy_files(data, backup)

    assert first_source.exists()
    assert second_source.exists()
    assert not (backup / "account" / "funding_offers.csv").exists()
    assert not (backup / "account" / "funding_trades.csv").exists()
    assert not (backup / "manifest.json").exists()

    monkeypatch.setattr(Path, "replace", original_replace)
    assert stage_legacy_files(data, backup) == (
        backup / "account" / "funding_offers.csv",
        backup / "account" / "funding_trades.csv",
    )


def test_stage_rolls_back_every_source_when_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    backup = data / "archive" / "daily-partition-test"
    first_source = data / "account" / "funding_offers.csv"
    second_source = data / "account" / "funding_trades.csv"
    row = ("1", "2026-08-16T12:00:00Z", "1", "/private", "v1", "[]")
    _write(first_source, ACCOUNT_HEADER, [row])
    _write(second_source, ACCOUNT_HEADER, [row])

    original_write_text = Path.write_text

    def fail_manifest_write(path: Path, *args: object, **kwargs: object) -> int:
        if path == backup / "manifest.json.staging":
            raise OSError("injected manifest write failure")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_manifest_write)

    with pytest.raises(MigrationError, match="injected manifest write failure"):
        migration.stage_legacy_files(data, backup)

    assert first_source.exists()
    assert second_source.exists()
    assert not (backup / "account" / "funding_offers.csv").exists()
    assert not (backup / "account" / "funding_trades.csv").exists()
    assert not (backup / "manifest.json").exists()

    monkeypatch.setattr(Path, "write_text", original_write_text)
    assert stage_legacy_files(data, backup) == (
        backup / "account" / "funding_offers.csv",
        backup / "account" / "funding_trades.csv",
    )


def test_stage_refuses_to_overwrite_a_source_created_during_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    backup = data / "archive" / "daily-partition-test"
    first_source = data / "account" / "funding_offers.csv"
    second_source = data / "account" / "funding_trades.csv"
    row = ("1", "2026-08-16T12:00:00Z", "1", "/private", "v1", "[]")
    _write(first_source, ACCOUNT_HEADER, [row])
    _write(second_source, ACCOUNT_HEADER, [row])

    original_replace = Path.replace

    def create_source_then_fail(source: Path, destination: Path) -> Path:
        if source == second_source:
            _write(first_source, ACCOUNT_HEADER, [("unrelated", *row[1:])])
            raise OSError("injected second move failure")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", create_source_then_fail)

    with pytest.raises(MigrationError, match="refusing to overwrite source during rollback"):
        migration.stage_legacy_files(data, backup)

    assert first_source.exists()
    assert first_source.read_text(encoding="utf-8").count("unrelated") == 1
    assert second_source.exists()
    assert (backup / "account" / "funding_offers.csv").exists()
    assert not (backup / "manifest.json").exists()
