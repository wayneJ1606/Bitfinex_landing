from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest

from bitfinex_lending.models import FundingBookRow
from bitfinex_lending.storage import Storage, StorageError


STARTED = "2026-07-14T12:00:00+00:00"
FINISHED = "2026-07-14T12:00:01+00:00"


def make_row(*, side: str = "offer", amount: float = 10.0) -> FundingBookRow:
    return FundingBookRow(
        run_id="run-1",
        market="fUSD",
        rate=0.0002,
        period=2,
        count=1,
        amount=amount,
        side=cast(object, side),
        fetched_at=STARTED,
    )


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_initialize_creates_required_tables_and_columns(tmp_path: Path) -> None:
    database = tmp_path / "collector.sqlite3"
    Storage(database).initialize()

    with connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        snapshot_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(funding_book_snapshots)")
        }

    assert {"funding_book_snapshots", "crawl_logs", "error_logs"} <= tables
    assert {
        "run_id",
        "market",
        "rate",
        "period",
        "count",
        "amount",
        "side",
        "fetched_at",
    } <= snapshot_columns


def test_record_success_writes_snapshots_and_crawl_log_atomically(tmp_path: Path) -> None:
    database = tmp_path / "collector.sqlite3"
    storage = Storage(database)
    storage.initialize()
    rows = (make_row(), make_row(side="demand", amount=-4.0))

    storage.record_success(rows, started_at=STARTED, finished_at=FINISHED)

    with connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM funding_book_snapshots"
        ).fetchone()[0] == 2
        log = connection.execute(
            "SELECT status, row_count, message FROM crawl_logs"
        ).fetchone()
    assert tuple(log) == ("success", 2, "Fetched and stored 2 rows")


def test_record_empty_writes_only_empty_crawl_log(tmp_path: Path) -> None:
    database = tmp_path / "collector.sqlite3"
    storage = Storage(database)
    storage.initialize()

    storage.record_empty("run-1", "fUSD", STARTED, FINISHED)

    with connect(database) as connection:
        snapshot_count = connection.execute(
            "SELECT COUNT(*) FROM funding_book_snapshots"
        ).fetchone()[0]
        log = connection.execute(
            "SELECT status, row_count FROM crawl_logs"
        ).fetchone()
    assert snapshot_count == 0
    assert tuple(log) == ("empty", 0)


def test_record_failure_writes_crawl_and_error_logs(tmp_path: Path) -> None:
    database = tmp_path / "collector.sqlite3"
    storage = Storage(database)
    storage.initialize()

    storage.record_failure(
        "run-1",
        "fUSD",
        STARTED,
        FINISHED,
        "network_error",
        "request timed out",
    )

    with connect(database) as connection:
        crawl = connection.execute(
            "SELECT status, row_count, message FROM crawl_logs"
        ).fetchone()
        error = connection.execute(
            "SELECT error_type, message, occurred_at FROM error_logs"
        ).fetchone()
    assert tuple(crawl) == ("failed", 0, "request timed out")
    assert tuple(error) == ("network_error", "request timed out", FINISHED)


def test_record_success_rolls_back_all_rows_on_constraint_failure(tmp_path: Path) -> None:
    database = tmp_path / "collector.sqlite3"
    storage = Storage(database)
    storage.initialize()

    with pytest.raises(StorageError, match="failed to record successful crawl"):
        storage.record_success(
            (make_row(), make_row(side="unknown")),
            started_at=STARTED,
            finished_at=FINISHED,
        )

    with connect(database) as connection:
        snapshots = connection.execute(
            "SELECT COUNT(*) FROM funding_book_snapshots"
        ).fetchone()[0]
        logs = connection.execute("SELECT COUNT(*) FROM crawl_logs").fetchone()[0]
    assert snapshots == 0
    assert logs == 0

