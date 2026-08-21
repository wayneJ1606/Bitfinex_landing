from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Sequence

from .partitioned_csv import account_daily_path


DATASETS = frozenset(
    {
        "funding_offers",
        "funding_offers_history",
        "funding_trades",
        "funding_loans",
        "funding_credits",
    }
)
DATASET_ENDPOINTS = {
    "funding_offers": "/v2/auth/r/funding/offers",
    "funding_offers_history": "/v2/auth/r/funding/offers/hist",
    "funding_trades": "/v2/auth/r/funding/trades/hist",
    "funding_loans": "/v2/auth/r/funding/loans/hist",
    "funding_credits": "/v2/auth/r/funding/credits",
}
CSV_FIELDS = (
    "event_id",
    "collected_at",
    "source_timestamp",
    "source_endpoint",
    "schema_version",
    "raw_payload",
)
SCHEMA_VERSION = "account-v1"


class AccountStorageError(RuntimeError):
    """Raised when private account data cannot be stored safely."""


class AccountStorage:
    def __init__(self, root: Path, *, metadata_root: Path | None = None) -> None:
        self.root = Path(root)
        self.database_path = self.root / "account_events.sqlite3"
        self.metadata_root = Path(metadata_root) if metadata_root is not None else self.root.parent / "metadata"
        self.status_path = self.metadata_root / "account_collector_status.json"

    def initialize(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.metadata_root.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS account_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dataset TEXT NOT NULL,
                        event_key TEXT NOT NULL UNIQUE,
                        event_id TEXT NOT NULL,
                        collected_at TEXT NOT NULL,
                        last_collected_at TEXT NOT NULL,
                        source_timestamp TEXT NOT NULL,
                        source_endpoint TEXT NOT NULL,
                        schema_version TEXT NOT NULL,
                        raw_payload TEXT NOT NULL,
                        UNIQUE(dataset, event_id, raw_payload)
                    );
                    CREATE INDEX IF NOT EXISTS idx_account_events_dataset_time
                        ON account_events(dataset, collected_at);
                    """
                )
                self._migrate_event_identity(connection)
        except (OSError, sqlite3.Error) as error:
            raise AccountStorageError(f"failed to initialize account storage: {error}") from error

    def append_snapshot(
        self, dataset: str, collected_at: str, rows: Sequence[object]
    ) -> int:
        if dataset not in DATASETS:
            raise ValueError(f"unsupported account dataset: {dataset}")
        self.initialize()
        endpoint = DATASET_ENDPOINTS[dataset]
        inserted = 0
        try:
            with sqlite3.connect(self.database_path) as connection:
                for row in rows:
                    raw_payload = json.dumps(
                        row, ensure_ascii=False, separators=(",", ":"), default=str
                    )
                    event_id = _event_id(row, raw_payload)
                    source_timestamp = _source_timestamp(row)
                    event_key = hashlib.sha256(
                        f"{dataset}|{event_id}|{raw_payload}".encode("utf-8")
                    ).hexdigest()
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO account_events
                            (dataset, event_key, event_id, collected_at,
                             last_collected_at, source_timestamp, source_endpoint,
                             schema_version, raw_payload)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dataset,
                            event_key,
                            event_id,
                            collected_at,
                            collected_at,
                            source_timestamp,
                            endpoint,
                            SCHEMA_VERSION,
                            raw_payload,
                        ),
                    )
                    if cursor.rowcount == 1:
                        inserted += 1
                    else:
                        connection.execute(
                            """
                            UPDATE account_events
                            SET last_collected_at = ?
                            WHERE dataset = ? AND event_id = ? AND raw_payload = ?
                            """,
                            (collected_at, dataset, event_id, raw_payload),
                        )
            self._materialize_csv(dataset, collected_at)
        except (OSError, sqlite3.Error) as error:
            raise AccountStorageError(f"failed to append {dataset}: {error}") from error
        return inserted

    def _migrate_event_identity(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(account_events)")
        }
        if "last_collected_at" in columns:
            return
        connection.executescript(
            """
            ALTER TABLE account_events RENAME TO account_events_legacy;
            CREATE TABLE account_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL,
                event_key TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                last_collected_at TEXT NOT NULL,
                source_timestamp TEXT NOT NULL,
                source_endpoint TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                raw_payload TEXT NOT NULL,
                UNIQUE(dataset, event_id, raw_payload)
            );
            INSERT OR IGNORE INTO account_events
                (dataset, event_key, event_id, collected_at, last_collected_at,
                 source_timestamp, source_endpoint, schema_version, raw_payload)
            SELECT legacy.dataset, legacy.event_key, legacy.event_id,
                   legacy.collected_at,
                   (SELECT MAX(newer.collected_at)
                    FROM account_events_legacy AS newer
                    WHERE newer.dataset = legacy.dataset
                      AND newer.event_id = legacy.event_id
                      AND newer.raw_payload = legacy.raw_payload),
                   legacy.source_timestamp, legacy.source_endpoint,
                   legacy.schema_version, legacy.raw_payload
            FROM account_events_legacy AS legacy
            ORDER BY legacy.id;
            DROP TABLE account_events_legacy;
            CREATE INDEX IF NOT EXISTS idx_account_events_dataset_time
                ON account_events(dataset, collected_at);
            """
        )

    def _materialize_csv(self, dataset: str, collected_at: str) -> None:
        csv_path = account_daily_path(self.root, dataset, collected_at)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = csv_path.with_suffix(".csv.tmp")
        try:
            with sqlite3.connect(self.database_path) as connection, temporary_path.open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
                writer.writeheader()
                rows = connection.execute(
                    """
                    SELECT event_id, collected_at, source_timestamp, source_endpoint,
                           schema_version, raw_payload
                    FROM account_events
                    WHERE dataset = ?
                    ORDER BY id
                    """,
                    (dataset,),
                )
                for row in rows:
                    if account_daily_path(self.root, dataset, row[1]) == csv_path:
                        writer.writerow(dict(zip(CSV_FIELDS, row)))
            temporary_path.replace(csv_path)
        except (OSError, sqlite3.Error):
            temporary_path.unlink(missing_ok=True)
            raise

    def write_status(self, status: dict[str, object]) -> None:
        self.initialize()
        temporary_path = self.status_path.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self.status_path)
        except OSError as error:
            raise AccountStorageError(f"failed to write account status: {error}") from error


def _event_id(row: object, raw_payload: str) -> str:
    if isinstance(row, dict):
        for key in ("id", "ID", "offer_id", "OFFER_ID", "mts_create", "MTS_CREATE"):
            if row.get(key) is not None:
                return str(row[key])
    if isinstance(row, (list, tuple)) and row:
        return str(row[0])
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()[:24]


def _source_timestamp(row: object) -> str:
    if isinstance(row, dict):
        for key in ("mts_create", "MTS_CREATE", "mts_created", "MTS_CREATED", "timestamp"):
            if row.get(key) is not None:
                return str(row[key])
    if isinstance(row, (list, tuple)) and len(row) > 2:
        return str(row[2])
    return ""
