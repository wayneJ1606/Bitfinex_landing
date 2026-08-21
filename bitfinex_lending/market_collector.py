from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .client import ClientError
from .partitioned_csv import market_daily_path


class MarketClient(Protocol):
    def fetch_ticker(self, market: str) -> object: ...
    def fetch_funding_stats(self, market: str) -> object: ...
    def fetch_funding_candles(self, market: str) -> object: ...


MAX_DIAGNOSTIC_MESSAGE_LENGTH = 240


@dataclass(frozen=True)
class MarketCollectionDiagnostic:
    dataset: str
    error_type: str
    message: str

    @property
    def rendered(self) -> str:
        return (
            f"dataset={self.dataset} error_type={self.error_type} "
            f"message={self.message}"
        )


@dataclass(frozen=True)
class MarketCollectionResult:
    written: int
    failed: tuple[str, ...]
    diagnostics: tuple[MarketCollectionDiagnostic, ...] = ()


TICKER_FIELDS = ("collected_at", "market", "frr", "bid", "bid_period", "bid_size", "ask", "ask_period", "ask_size", "daily_change", "daily_change_perc", "last_price", "volume", "high", "low", "first_trade", "frr_amount_available")
STATS_FIELDS = ("collected_at", "market", "mts", "frr", "avg_period", "funding_amount", "funding_amount_used", "funding_below_threshold", "payload_json")
CANDLE_FIELDS = ("collected_at", "market", "candle_key", "mts", "open", "close", "high", "low", "volume")
PRICE_FIELDS = ("collected_at", "market", "bid", "ask", "daily_change", "daily_change_perc", "last_price", "volume", "high", "low", "first_trade")
FUNDING_MARKETS = ("fUSD", "fBTC", "fETH", "fUST")


def _append(path: Path, fields: tuple[str, ...], row: tuple[object, ...]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[list[str]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as stream:
            existing = list(csv.reader(stream))
    if existing and any(item[:2] == [str(row[0]), str(row[1])] for item in existing[1:]):
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        if existing:
            writer.writerows(existing[1:])
        writer.writerow(row)
    temporary.replace(path)
    return True


def _ticker_row(collected_at: str, market: str, payload: list[object]) -> tuple[object, ...]:
    values = list(payload) + [None] * 17
    return (collected_at, market, values[0], values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8], values[9], values[10], values[11], values[12], values[16], values[15])


def _diagnostic(dataset: str, error: Exception) -> MarketCollectionDiagnostic:
    message = " ".join(str(error).split()) or error.__class__.__name__
    return MarketCollectionDiagnostic(
        dataset=dataset,
        error_type=error.code if isinstance(error, ClientError) else error.__class__.__name__,
        message=message[:MAX_DIAGNOSTIC_MESSAGE_LENGTH],
    )


def collect_market_data(client: MarketClient, output_root: Path, *, collected_at: str) -> MarketCollectionResult:
    output_root = Path(output_root)
    written = 0
    failed: list[str] = []
    diagnostics: list[MarketCollectionDiagnostic] = []
    for market in FUNDING_MARKETS:
        try:
            ticker = list(client.fetch_ticker(market))
            written += _append(market_daily_path(output_root, "ticker", market, collected_at), TICKER_FIELDS, _ticker_row(collected_at, market, ticker))
        except Exception as error:
            dataset = f"ticker:{market}"
            failed.append(dataset)
            diagnostics.append(_diagnostic(dataset, error))
        try:
            stats = list(client.fetch_funding_stats(market))
            item = list(stats[-1]) if stats else []
            item += [None] * 12
            row = (collected_at, market, item[0], item[3], item[4], item[7], item[8], item[11], json.dumps(item, ensure_ascii=False))
            written += _append(market_daily_path(output_root, "funding_stats", market, collected_at), STATS_FIELDS, row)
        except Exception as error:
            dataset = f"funding_stats:{market}"
            failed.append(dataset)
            diagnostics.append(_diagnostic(dataset, error))
        try:
            candles = list(client.fetch_funding_candles(market))
            item = list(candles[-1]) if candles else []
            item += [None] * 6
            row = (collected_at, market, "trade:1h:a30:p2:p30", item[0], item[1], item[2], item[3], item[4], item[5])
            written += _append(market_daily_path(output_root, "funding_candles", market, collected_at), CANDLE_FIELDS, row)
        except Exception as error:
            dataset = f"funding_candles:{market}"
            failed.append(dataset)
            diagnostics.append(_diagnostic(dataset, error))
    for market in ("tBTCUSD", "tETHUSD"):
        try:
            payload = list(client.fetch_ticker(market))
            item = payload + [None] * 11
            row = (collected_at, market, item[0], item[2], item[4], item[5], item[6], item[7], item[8], item[9], item[10])
            written += _append(market_daily_path(output_root, "prices", market, collected_at), PRICE_FIELDS, row)
        except Exception as error:
            dataset = f"prices:{market}"
            failed.append(dataset)
            diagnostics.append(_diagnostic(dataset, error))
    return MarketCollectionResult(written, tuple(failed), tuple(diagnostics))
