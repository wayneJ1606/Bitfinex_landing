from __future__ import annotations

import bisect
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ACCOUNT_DATASETS = (
    "funding_offers",
    "funding_offers_history",
    "funding_trades",
    "funding_loans",
    "funding_credits",
)
ASSET_NAMES = {"fUST": "USDT", "fUSD": "USD", "fBTC": "BTC", "fETH": "ETH"}
OUTPUT_FIELDS = (
    "dataset",
    "event_id",
    "api_symbol",
    "asset",
    "collected_at",
    "source_timestamp",
    "is_first_seen",
    "status",
    "amount",
    "rate",
    "period",
    "offer_id",
    "market_matched",
    "market_collected_at",
    "market_age_minutes",
    "market_frr",
    "market_bid",
    "market_ask",
)


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _load_tickers(root: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[tuple[str, str], ...]] = set()
    ticker_root = Path(root) / "ticker"
    if not ticker_root.exists():
        return result
    for path in ticker_root.rglob("f*.csv"):
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            signature = tuple(sorted(row.items()))
            if signature not in seen:
                seen.add(signature)
                result.setdefault(row["market"], []).append(row)
    for rows in result.values():
        rows.sort(key=lambda row: _instant(row["collected_at"]))
    return result


def _private_fields(dataset: str, payload: list[object]) -> dict[str, object]:
    values = payload + [None] * 20
    if dataset in {"funding_offers", "funding_offers_history"}:
        return {"symbol": values[1], "amount": values[4], "status": values[10], "rate": values[14], "period": values[15], "offer_id": values[0]}
    if dataset == "funding_trades":
        return {"symbol": values[1], "amount": values[4], "status": "EXECUTED", "rate": values[5], "period": values[6], "offer_id": values[3]}
    return {"symbol": values[1], "amount": values[5], "status": values[7], "rate": values[11], "period": values[12], "offer_id": ""}


def _match_market(
    rows: list[dict[str, str]], collected_at: datetime, tolerance_minutes: float
) -> dict[str, str] | None:
    times = [_instant(row["collected_at"]) for row in rows]
    index = bisect.bisect_right(times, collected_at) - 1
    if index < 0:
        return None
    candidate = rows[index]
    age = (collected_at - times[index]).total_seconds() / 60
    return candidate if age <= tolerance_minutes else None


def build_p0_alignment(
    account_root: Path,
    market_root: Path,
    output_path: Path,
    *,
    tolerance_minutes: float = 90,
) -> int:
    account_root = Path(account_root)
    tickers = _load_tickers(Path(market_root))
    source_rows: list[tuple[str, dict[str, str]]] = []
    source_seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for dataset in ACCOUNT_DATASETS:
        legacy = account_root / f"{dataset}.csv"
        partitioned = account_root / dataset
        paths = ([legacy] if legacy.exists() else []) + (
            sorted(partitioned.rglob("*.csv")) if partitioned.exists() else []
        )
        for path in paths:
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    signature = (dataset, tuple(sorted(row.items())))
                    if signature not in source_seen:
                        source_seen.add(signature)
                        source_rows.append((dataset, row))
    source_rows.sort(key=lambda item: _instant(item[1]["collected_at"]))

    seen: set[tuple[str, str]] = set()
    output_rows: list[dict[str, object]] = []
    for dataset, source in source_rows:
        payload = json.loads(source["raw_payload"])
        private = _private_fields(dataset, payload)
        symbol = str(private["symbol"] or "")
        collected = _instant(source["collected_at"])
        market = _match_market(tickers.get(symbol, []), collected, tolerance_minutes)
        first_key = (dataset, source["event_id"])
        is_first = first_key not in seen
        seen.add(first_key)
        market_time = _instant(market["collected_at"]) if market else None
        output_rows.append(
            {
                "dataset": dataset,
                "event_id": source["event_id"],
                "api_symbol": symbol,
                "asset": ASSET_NAMES.get(symbol, symbol.removeprefix("f")),
                "collected_at": source["collected_at"],
                "source_timestamp": source["source_timestamp"],
                "is_first_seen": int(is_first),
                "status": private["status"] or "",
                "amount": private["amount"] if private["amount"] is not None else "",
                "rate": private["rate"] if private["rate"] is not None else "",
                "period": private["period"] if private["period"] is not None else "",
                "offer_id": private["offer_id"] if private["offer_id"] is not None else "",
                "market_matched": int(market is not None),
                "market_collected_at": market["collected_at"] if market else "",
                "market_age_minutes": round((collected - market_time).total_seconds() / 60, 6) if market_time else "",
                "market_frr": market.get("frr", "") if market else "",
                "market_bid": market.get("bid", "") if market else "",
                "market_ask": market.get("ask", "") if market else "",
            }
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    temporary.replace(output_path)
    return len(output_rows)


def main() -> int:
    count = build_p0_alignment(
        Path("data/account"),
        Path("data/market"),
        Path("data/modeling/p0_aligned_private_market.csv"),
    )
    print(f"Wrote {count} aligned private observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
