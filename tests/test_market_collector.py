from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.client import ClientError
import bitfinex_lending.market_collector as market_collector
from bitfinex_lending.market_collector import collect_market_data


class FakeMarketClient:
    def fetch_ticker(self, market: str):
        if market.startswith("t"):
            return [100.0, 1.0, 101.0, 2.0, 0.1, 0.01, 100.5, 50.0, 105.0, 95.0, 0]
        return [0.001, 0.0009, 2, 100.0, 0.0011, 3, 80.0, 0.01, 0.02, 1000.0, 20.0, 0.002, 0.0008, 0, 0, 500.0, 0]

    def fetch_funding_stats(self, market: str):
        return [[1700000000000, 0, 0, 0.001, 3.0, 0, 0, 1000.0, 700.0, 0, 0, 12.0]]

    def fetch_funding_candles(self, market: str):
        return [[1700000000000, 0.001, 0.0012, 0.0013, 0.0009, 100.0]]


def test_collect_market_data_writes_separate_public_datasets(tmp_path: Path) -> None:
    result = collect_market_data(
        FakeMarketClient(), tmp_path, collected_at="2026-08-16T00:47:00+00:00"
    )
    assert result.failed == ()
    assert result.written == 14
    ticker = tmp_path / "ticker" / "2026" / "08" / "16" / "fUSD.csv"
    assert ticker.exists()
    with ticker.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["market"] == "fUSD"
    assert rows[0]["frr"] == "0.001"
    assert (tmp_path / "ticker" / "2026" / "08" / "16" / "fUST.csv").exists()
    assert (tmp_path / "funding_stats" / "2026" / "08" / "16" / "fUST.csv").exists()
    assert (tmp_path / "funding_candles" / "2026" / "08" / "16" / "fUST.csv").exists()
    assert (tmp_path / "prices" / "2026" / "08" / "16" / "tBTCUSD.csv").exists()


def test_collect_market_data_deduplicates_same_collection_timestamp(tmp_path: Path) -> None:
    client = FakeMarketClient()
    first = collect_market_data(client, tmp_path, collected_at="2026-08-16T00:47:00+00:00")
    second = collect_market_data(client, tmp_path, collected_at="2026-08-16T00:47:00+00:00")
    assert first.written == 14
    assert second.written == 0


def test_market_partition_uses_utc_date(tmp_path: Path) -> None:
    collect_market_data(
        FakeMarketClient(), tmp_path, collected_at="2026-08-16T00:30:00+08:00"
    )

    assert (tmp_path / "ticker" / "2026" / "08" / "15" / "fUSD.csv").exists()


class FailingTickerClient(FakeMarketClient):
    def fetch_ticker(self, market: str):
        if market == "fUSD":
            raise ClientError("http_error", "endpoint unavailable\nretry later")
        return super().fetch_ticker(market)


def test_endpoint_failure_is_diagnosed_without_stopping_other_datasets(tmp_path: Path) -> None:
    result = collect_market_data(
        FailingTickerClient(), tmp_path, collected_at="2026-08-16T00:47:00+00:00"
    )

    assert result.failed == ("ticker:fUSD",)
    assert result.written == 13
    assert result.diagnostics[0].dataset == "ticker:fUSD"
    assert result.diagnostics[0].error_type == "http_error"
    assert result.diagnostics[0].message == "endpoint unavailable retry later"
    assert (tmp_path / "funding_stats" / "2026" / "08" / "16" / "fUSD.csv").exists()


def test_local_csv_write_failure_is_diagnosed_without_stopping_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_append = market_collector._append
    failed_once = False

    def failing_append(path, fields, row):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("disk full\nwhile writing")
        return real_append(path, fields, row)

    monkeypatch.setattr(market_collector, "_append", failing_append)

    result = collect_market_data(
        FakeMarketClient(), tmp_path, collected_at="2026-08-16T00:47:00+00:00"
    )

    assert result.failed == ("ticker:fUSD",)
    assert result.written == 13
    assert result.diagnostics[0].dataset == "ticker:fUSD"
    assert result.diagnostics[0].error_type == "OSError"
    assert result.diagnostics[0].message == "disk full while writing"
