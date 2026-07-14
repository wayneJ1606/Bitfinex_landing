from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bitfinex_lending.models import FundingBookRow, ModelingFeature
from bitfinex_lending.storage import Storage, StorageError


FEATURE_COLUMNS = {
    "id",
    "market",
    "feature_time",
    "hour",
    "day_of_week",
    "avg_rate",
    "weighted_avg_rate",
    "min_rate",
    "max_rate",
    "total_amount",
    "avg_period",
    "offer_count",
    "demand_count",
    "rate_spread",
    "previous_weighted_avg_rate",
    "rate_change",
    "amount_change",
    "target_next_weighted_avg_rate",
}


def feature(
    *,
    market: str = "fUSD",
    feature_time: str = "2026-07-14T12:00:00+00:00",
    previous_weighted_avg_rate: float | None = None,
    rate_change: float | None = None,
    amount_change: float | None = None,
    target_next_weighted_avg_rate: float | None = None,
) -> ModelingFeature:
    return ModelingFeature(
        market=market,
        feature_time=feature_time,
        hour=12,
        day_of_week=1,
        avg_rate=0.0003,
        weighted_avg_rate=0.00035,
        min_rate=0.0002,
        max_rate=0.0004,
        total_amount=40.0,
        avg_period=4.0,
        offer_count=2,
        demand_count=3,
        rate_spread=0.0002,
        previous_weighted_avg_rate=previous_weighted_avg_rate,
        rate_change=rate_change,
        amount_change=amount_change,
        target_next_weighted_avg_rate=target_next_weighted_avg_rate,
    )


def test_initialize_creates_modeling_feature_schema_and_unique_key(
    tmp_path: Path,
) -> None:
    database = tmp_path / "features.sqlite3"
    Storage(database).initialize()

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(modeling_features)")
        }
        unique_indexes = connection.execute(
            "PRAGMA index_list(modeling_features)"
        ).fetchall()
        unique_column_sets = {
            tuple(
                row[2]
                for row in connection.execute(
                    f"PRAGMA index_info({index[1]})"
                ).fetchall()
            )
            for index in unique_indexes
            if index[2]
        }

    assert columns == FEATURE_COLUMNS
    assert ("market", "feature_time") in unique_column_sets


def test_load_snapshots_returns_rows_ordered_by_market_time_and_id(
    tmp_path: Path,
) -> None:
    database = tmp_path / "features.sqlite3"
    storage = Storage(database)
    storage.initialize()
    source_rows = [
        ("run-1", "fUSD", 0.0001, 2, 1, 10.0, "offer", "2026-07-15T00:30:00+14:00"),
        ("run-2", "fUSD", 0.0004, 3, 2, -5.0, "demand", "2026-07-14T23:00:00-12:00"),
        ("run-1", "fBTC", 0.0003, 4, 3, 7.0, "offer", "2026-07-14T12:00:00+00:00"),
        ("run-1", "fUSD", 0.0002, 6, 4, 20.0, "offer", "2026-07-14T12:00:00+00:00"),
        ("run-1", "fUSD", 0.0003, 5, 5, 30.0, "offer", "2026-07-14T20:00:00+08:00"),
    ]
    with sqlite3.connect(database) as connection:
        connection.executemany(
            """INSERT INTO funding_book_snapshots
               (run_id, market, rate, period, count, amount, side, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            source_rows,
        )

    loaded = storage.load_snapshots()

    assert loaded == (
        FundingBookRow(*source_rows[2]),
        FundingBookRow(*source_rows[0]),
        FundingBookRow(*source_rows[3]),
        FundingBookRow(*source_rows[4]),
        FundingBookRow(*source_rows[1]),
    )


def test_replace_features_removes_stale_rows_and_round_trips_nullable_fields(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "features.sqlite3")
    storage.initialize()
    storage.replace_features((feature(market="fBTC"), feature()))
    current = feature(
        feature_time="2026-07-14T13:00:00+00:00",
        previous_weighted_avg_rate=0.00035,
        rate_change=0.00001,
        amount_change=-2.0,
        target_next_weighted_avg_rate=None,
    )

    storage.replace_features((current,))

    assert storage.load_features() == (current,)


def test_load_features_orders_markets_then_utc_instants_stably(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "features.sqlite3")
    storage.initialize()
    usd_late = feature(feature_time="2026-07-14T23:00:00-12:00")
    usd_early = feature(feature_time="2026-07-15T00:30:00+14:00")
    btc = feature(market="fBTC", feature_time="2026-07-15T09:00:00+08:00")
    storage.replace_features((usd_late, btc, usd_early))

    assert storage.load_features() == (btc, usd_early, usd_late)


def test_replace_features_rolls_back_when_rebuild_contains_duplicate_key(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "features.sqlite3")
    storage.initialize()
    original = feature()
    storage.replace_features((original,))
    duplicate = feature(market="fBTC")

    with pytest.raises(StorageError, match="failed to replace modeling features"):
        storage.replace_features((duplicate, duplicate))

    assert storage.load_features() == (original,)
