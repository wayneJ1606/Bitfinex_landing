import csv
import json
import sqlite3
from pathlib import Path

import pytest

from bitfinex_lending.account_storage import AccountStorage, AccountStorageError


def test_initialize_creates_account_files_and_database(tmp_path):
    storage = AccountStorage(tmp_path / "account")

    storage.initialize()

    assert (tmp_path / "account").is_dir()
    assert (tmp_path / "account" / "account_events.sqlite3").exists()


def test_append_snapshot_writes_normalized_csv_and_deduplicates_same_event(tmp_path):
    storage = AccountStorage(tmp_path / "account")
    storage.initialize()
    rows = [{"id": 123, "symbol": "fUSD", "amount": "10", "status": "ACTIVE"}]

    first = storage.append_snapshot(
        "funding_offers", "2026-08-16T12:00:00+08:00", rows
    )
    second = storage.append_snapshot(
        "funding_offers", "2026-08-16T12:00:00+08:00", rows
    )

    assert first == 1
    assert second == 0
    with (tmp_path / "account" / "funding_offers" / "2026" / "08" / "16.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == 1
    assert records[0]["event_id"] == "123"
    assert json.loads(records[0]["raw_payload"])["status"] == "ACTIVE"

    with sqlite3.connect(tmp_path / "account" / "account_events.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM account_events").fetchone()[0] == 1


def test_same_historical_event_collected_twice_is_stored_once_with_collection_metadata(tmp_path):
    storage = AccountStorage(tmp_path / "account")
    storage.initialize()
    row = {"id": 123, "amount": "10"}

    assert storage.append_snapshot("funding_offers", "2026-08-16T12:00:00Z", [row]) == 1
    assert storage.append_snapshot("funding_offers", "2026-08-16T12:05:00Z", [row]) == 0

    with sqlite3.connect(tmp_path / "account" / "account_events.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM account_events").fetchone()[0] == 1
        assert connection.execute(
            "SELECT collected_at, last_collected_at FROM account_events"
        ).fetchone() == ("2026-08-16T12:00:00Z", "2026-08-16T12:05:00Z")


def test_initialize_migrates_legacy_collection_time_duplicates_to_one_event(tmp_path):
    root = tmp_path / "account"
    root.mkdir()
    database_path = root / "account_events.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE account_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL,
                event_key TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                source_timestamp TEXT NOT NULL,
                source_endpoint TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            );
            INSERT INTO account_events VALUES
                (1, 'funding_offers', 'first', '123', '2026-08-16T12:00:00Z', '', '/v2/auth/r/funding/offers', 'account-v1', '{"id":123}'),
                (2, 'funding_offers', 'second', '123', '2026-08-16T12:05:00Z', '', '/v2/auth/r/funding/offers', 'account-v1', '{"id":123}');
            """
        )

    AccountStorage(root).initialize()

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT collected_at, last_collected_at FROM account_events"
        ).fetchone() == ("2026-08-16T12:00:00Z", "2026-08-16T12:05:00Z")
        assert "idx_account_events_dataset_time" in {
            row[1] for row in connection.execute("PRAGMA index_list(account_events)")
        }


def test_list_payload_gets_stable_identifier_and_status_is_atomic(tmp_path):
    storage = AccountStorage(tmp_path / "account")
    storage.initialize()

    assert storage.append_snapshot("funding_trades", "2026-08-16T12:00:00Z", [[456, "fUSD", 10]]) == 1
    storage.write_status({"status": "success", "row_counts": {"funding_trades": 1}})

    with (tmp_path / "account" / "funding_trades" / "2026" / "08" / "16.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        records = list(csv.DictReader(handle))
    assert records[0]["event_id"] == "456"
    status = json.loads((tmp_path / "metadata" / "account_collector_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "success"


def test_funding_offer_history_has_separate_dataset(tmp_path):
    storage = AccountStorage(tmp_path / "account")
    storage.initialize()

    assert storage.append_snapshot(
        "funding_offers_history",
        "2026-08-18T12:00:00Z",
        [[789, "fUST", 1000, 2000, 160, 160, "LIMIT", None, None, 0, "EXECUTED"]],
    ) == 1
    assert (
        tmp_path / "account" / "funding_offers_history" / "2026" / "08" / "18.csv"
    ).exists()


def test_account_partition_uses_utc_date(tmp_path):
    storage = AccountStorage(tmp_path / "account")
    storage.initialize()

    storage.append_snapshot(
        "funding_offers", "2026-08-16T00:30:00+08:00", [{"id": 1}]
    )

    assert (
        tmp_path / "account" / "funding_offers" / "2026" / "08" / "15.csv"
    ).exists()


def test_csv_is_rebuilt_from_committed_sqlite_after_materialization_failure(tmp_path, monkeypatch):
    storage = AccountStorage(tmp_path / "account")
    row = {"id": 123, "amount": "10"}
    original_replace = Path.replace
    failed = False

    def fail_once(source, target):
        nonlocal failed
        if source.suffix == ".tmp" and not failed:
            failed = True
            raise OSError("simulated CSV replacement failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_once)

    with pytest.raises(AccountStorageError, match="failed to append"):
        storage.append_snapshot("funding_offers", "2026-08-16T12:00:00Z", [row])

    assert storage.append_snapshot("funding_offers", "2026-08-16T12:00:00Z", [row]) == 0
    with (tmp_path / "account" / "funding_offers" / "2026" / "08" / "16.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 1
