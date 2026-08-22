from __future__ import annotations

import csv
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ASSET_BY_SYMBOL = {"fUST": "USDT", "fBTC": "BTC", "fETH": "ETH"}
MAX_PAIR_AGE_SECONDS = 90 * 60


class MarketHistoryError(ValueError):
    """A public market-history input cannot safely produce an observation."""


@dataclass(frozen=True)
class MarketHour:
    observed_at: datetime
    api_symbol: str
    asset: str
    frr: float
    ask_rate: float
    visible_demand_amount: float
    traded_high: float
    traded_volume: float
    funding_amount_used: float


def _error(category: str, path: Path, line: int, reason: str) -> MarketHistoryError:
    return MarketHistoryError(f"invalid {category} CSV {path.as_posix()} row {line}: {reason}")


def _timestamp(value: str, category: str, path: Path, line: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _error(category, path, line, "invalid timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error(category, path, line, "timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _number(value: str | None, field: str, category: str, path: Path, line: int) -> float:
    try:
        parsed = float(value or "")
    except ValueError as error:
        raise _error(category, path, line, f"{field} must be a number") from error
    if not math.isfinite(parsed):
        raise _error(category, path, line, f"{field} must be finite")
    return parsed


def _target_rows(root: Path, category: str, api_symbol: str) -> list[tuple[Path, int, dict[str, str]]]:
    category_root = root / category
    if not category_root.exists():
        return []
    if not category_root.is_dir():
        raise MarketHistoryError(f"invalid {category} root: must be a directory")
    rows: list[tuple[Path, int, dict[str, str]]] = []
    try:
        paths = sorted(category_root.rglob("*.csv"), key=lambda item: item.as_posix())
    except OSError as error:
        raise MarketHistoryError(f"cannot read {category} files: {error}") from error
    for path in paths:
        try:
            with path.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames is None:
                    raise _error(category, path, 1, "missing header")
                for line, row in enumerate(reader, start=2):
                    if row.get("market") == api_symbol:
                        rows.append((path, line, row))
        except MarketHistoryError:
            raise
        except (csv.Error, OSError, UnicodeDecodeError) as error:
            raise MarketHistoryError(f"cannot read {category} CSV {path.as_posix()}: {error}") from error
    return rows


def _public_series(root: Path, category: str, api_symbol: str, fields: tuple[str, ...]) -> tuple[tuple[datetime, tuple[float, ...]], ...]:
    seen: dict[datetime, tuple[float, ...]] = {}
    for path, line, row in _target_rows(root, category, api_symbol):
        if any(field not in row for field in ("collected_at", "market", *fields)):
            raise _error(category, path, line, "missing required field")
        timestamp = _timestamp(row["collected_at"], category, path, line)
        content = tuple(_number(row[field], field, category, path, line) for field in fields)
        previous = seen.get(timestamp)
        if previous is not None and previous != content:
            raise _error(category, path, line, "conflicting duplicate timestamp")
        seen[timestamp] = content
    return tuple(sorted(seen.items()))


def _raw_snapshots(raw_root: Path, api_symbol: str) -> tuple[tuple[datetime, float], ...]:
    if not raw_root.exists():
        return ()
    if not raw_root.is_dir():
        raise MarketHistoryError("invalid raw CSV root: must be a directory")
    demands: dict[datetime, float] = {}
    seen: set[tuple[str, str, datetime, float, int, int, float, str]] = set()
    try:
        paths = sorted(raw_root.rglob("*.csv"), key=lambda item: item.as_posix())
    except OSError as error:
        raise MarketHistoryError(f"cannot read raw CSV files: {error}") from error
    required = ("run_id", "market", "rate", "period", "count", "amount", "side", "fetched_at")
    for path in paths:
        try:
            with path.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames is None:
                    raise _error("raw funding-book", path, 1, "missing header")
                for line, row in enumerate(reader, start=2):
                    if row.get("market") != api_symbol:
                        continue
                    if any(field not in row for field in required):
                        raise _error("raw funding-book", path, line, "missing required field")
                    timestamp = _timestamp(row["fetched_at"], "raw funding-book", path, line)
                    rate = _number(row["rate"], "rate", "raw funding-book", path, line)
                    amount = _number(row["amount"], "amount", "raw funding-book", path, line)
                    try:
                        period, count = int(row["period"]), int(row["count"])
                    except (TypeError, ValueError) as error:
                        raise _error("raw funding-book", path, line, "period and count must be integers") from error
                    side = row["side"]
                    if side not in {"offer", "demand"}:
                        raise _error("raw funding-book", path, line, "side must be offer or demand")
                    key = (row["run_id"], api_symbol, timestamp, rate, period, count, amount, side)
                    if key in seen:
                        continue
                    seen.add(key)
                    if side == "demand":
                        demands[timestamp] = demands.get(timestamp, 0.0) + abs(amount)
        except MarketHistoryError:
            raise
        except (csv.Error, OSError, UnicodeDecodeError) as error:
            raise MarketHistoryError(f"cannot read raw funding-book CSV {path.as_posix()}: {error}") from error
    return tuple(sorted(demands.items()))


def _as_of(series: tuple[tuple[datetime, object], ...], observed_at: datetime) -> object | None:
    timestamps = [item[0] for item in series]
    index = bisect_right(timestamps, observed_at) - 1
    if index < 0:
        return None
    timestamp, value = series[index]
    if (observed_at - timestamp).total_seconds() > MAX_PAIR_AGE_SECONDS:
        return None
    return value


def load_market_hours(market_root: Path, raw_root: Path, api_symbol: str) -> tuple[MarketHour, ...]:
    if api_symbol not in ASSET_BY_SYMBOL:
        raise MarketHistoryError(f"unsupported API symbol: {api_symbol}")
    market_root = Path(market_root)
    tickers = _public_series(market_root, "ticker", api_symbol, ("frr", "ask"))
    candles = _public_series(market_root, "funding_candles", api_symbol, ("high", "volume"))
    stats = _public_series(market_root, "funding_stats", api_symbol, ("funding_amount_used",))
    books = _raw_snapshots(Path(raw_root), api_symbol)
    hours: dict[datetime, MarketHour] = {}
    for observed_at, (frr, ask_rate) in tickers:
        candle = _as_of(candles, observed_at)
        stat = _as_of(stats, observed_at)
        demand = _as_of(books, observed_at)
        if candle is None:
            raise MarketHistoryError(f"missing eligible candle for {api_symbol} at {observed_at.isoformat()}")
        if stat is None:
            raise MarketHistoryError(f"missing eligible funding stat for {api_symbol} at {observed_at.isoformat()}")
        if demand is None:
            raise MarketHistoryError(f"missing eligible funding-book snapshot for {api_symbol} at {observed_at.isoformat()}")
        candle_high, candle_volume = candle  # type: ignore[misc]
        hour_at = observed_at.replace(minute=0, second=0, microsecond=0)
        item = MarketHour(hour_at, api_symbol, ASSET_BY_SYMBOL[api_symbol], frr, ask_rate, float(demand), candle_high, candle_volume, stat[0])  # type: ignore[index]
        previous = hours.get(hour_at)
        if previous is not None and previous != item:
            raise MarketHistoryError(f"conflicting hourly observation for {api_symbol} at {hour_at.isoformat()}")
        hours[hour_at] = item
    return tuple(hours[timestamp] for timestamp in sorted(hours))
