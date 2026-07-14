from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import FundingBookRow, ModelingFeature


SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_book_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market TEXT NOT NULL,
    rate REAL NOT NULL,
    period INTEGER NOT NULL,
    count INTEGER NOT NULL CHECK (count >= 0),
    amount REAL NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('offer', 'demand')),
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_run_market
    ON funding_book_snapshots (run_id, market);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'empty', 'failed')),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_crawl_logs_run_market
    ON crawl_logs (run_id, market);

CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    market TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_error_logs_run_market
    ON error_logs (run_id, market);

CREATE TABLE IF NOT EXISTS modeling_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    feature_time TEXT NOT NULL,
    hour INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    avg_rate REAL NOT NULL,
    weighted_avg_rate REAL NOT NULL,
    min_rate REAL NOT NULL,
    max_rate REAL NOT NULL CHECK (max_rate >= min_rate),
    total_amount REAL NOT NULL CHECK (total_amount >= 0),
    avg_period REAL NOT NULL CHECK (avg_period > 0),
    offer_count INTEGER NOT NULL CHECK (offer_count >= 0),
    demand_count INTEGER NOT NULL CHECK (demand_count >= 0),
    rate_spread REAL NOT NULL CHECK (rate_spread >= 0),
    previous_weighted_avg_rate REAL,
    rate_change REAL,
    amount_change REAL,
    target_next_weighted_avg_rate REAL,
    UNIQUE (market, feature_time)
);
"""


class StorageError(RuntimeError):
    """Raised when SQLite initialization or a transaction fails."""


def _utc_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed.astimezone(timezone.utc)


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript(SCHEMA)
        except (OSError, sqlite3.Error) as error:
            raise StorageError(f"failed to initialize database: {error}") from error

    def load_snapshots(self) -> tuple[FundingBookRow, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, run_id, market, rate, period, count, amount, side,
                           fetched_at
                    FROM funding_book_snapshots
                    """
                ).fetchall()
                rows.sort(key=lambda row: (row[2], _utc_instant(row[8]), row[0]))
        except (sqlite3.Error, ValueError) as error:
            raise StorageError(f"failed to load funding book snapshots: {error}") from error
        return tuple(FundingBookRow(*row[1:]) for row in rows)

    def replace_features(self, features: Sequence[ModelingFeature]) -> None:
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM modeling_features")
                connection.executemany(
                    """
                    INSERT INTO modeling_features (
                        market, feature_time, hour, day_of_week, avg_rate,
                        weighted_avg_rate, min_rate, max_rate, total_amount,
                        avg_period, offer_count, demand_count, rate_spread,
                        previous_weighted_avg_rate, rate_change, amount_change,
                        target_next_weighted_avg_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            item.market,
                            item.feature_time,
                            item.hour,
                            item.day_of_week,
                            item.avg_rate,
                            item.weighted_avg_rate,
                            item.min_rate,
                            item.max_rate,
                            item.total_amount,
                            item.avg_period,
                            item.offer_count,
                            item.demand_count,
                            item.rate_spread,
                            item.previous_weighted_avg_rate,
                            item.rate_change,
                            item.amount_change,
                            item.target_next_weighted_avg_rate,
                        )
                        for item in features
                    ],
                )
        except sqlite3.Error as error:
            raise StorageError(f"failed to replace modeling features: {error}") from error

    def load_features(self) -> tuple[ModelingFeature, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, market, feature_time, hour, day_of_week, avg_rate,
                           weighted_avg_rate, min_rate, max_rate, total_amount,
                           avg_period, offer_count, demand_count, rate_spread,
                           previous_weighted_avg_rate, rate_change, amount_change,
                           target_next_weighted_avg_rate
                    FROM modeling_features
                    """
                ).fetchall()
                rows.sort(key=lambda row: (row[1], _utc_instant(row[2]), row[0]))
        except (sqlite3.Error, ValueError) as error:
            raise StorageError(f"failed to load modeling features: {error}") from error
        return tuple(ModelingFeature(*row[1:]) for row in rows)

    def record_success(
        self,
        rows: Sequence[FundingBookRow],
        *,
        started_at: str,
        finished_at: str,
    ) -> None:
        if not rows:
            raise ValueError("successful crawl requires at least one row")
        first = rows[0]
        if any(row.run_id != first.run_id or row.market != first.market for row in rows):
            raise ValueError("successful crawl rows must share run_id and market")
        try:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT INTO funding_book_snapshots
                        (run_id, market, rate, period, count, amount, side, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.run_id,
                            row.market,
                            row.rate,
                            row.period,
                            row.count,
                            row.amount,
                            row.side,
                            row.fetched_at,
                        )
                        for row in rows
                    ],
                )
                connection.execute(
                    """
                    INSERT INTO crawl_logs
                        (run_id, market, started_at, finished_at, status, row_count, message)
                    VALUES (?, ?, ?, ?, 'success', ?, ?)
                    """,
                    (
                        first.run_id,
                        first.market,
                        started_at,
                        finished_at,
                        len(rows),
                        f"Fetched and stored {len(rows)} rows",
                    ),
                )
        except sqlite3.Error as error:
            raise StorageError(f"failed to record successful crawl: {error}") from error

    def record_empty(
        self,
        run_id: str,
        market: str,
        started_at: str,
        finished_at: str,
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO crawl_logs
                        (run_id, market, started_at, finished_at, status, row_count, message)
                    VALUES (?, ?, ?, ?, 'empty', 0, 'Bitfinex returned an empty book')
                    """,
                    (run_id, market, started_at, finished_at),
                )
        except sqlite3.Error as error:
            raise StorageError(f"failed to record empty crawl: {error}") from error

    def record_failure(
        self,
        run_id: str,
        market: str,
        started_at: str,
        finished_at: str,
        error_type: str,
        message: str,
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO crawl_logs
                        (run_id, market, started_at, finished_at, status, row_count, message)
                    VALUES (?, ?, ?, ?, 'failed', 0, ?)
                    """,
                    (run_id, market, started_at, finished_at, message),
                )
                connection.execute(
                    """
                    INSERT INTO error_logs
                        (run_id, market, occurred_at, error_type, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, market, finished_at, error_type, message),
                )
        except sqlite3.Error as error:
            raise StorageError(f"failed to record crawl failure: {error}") from error
