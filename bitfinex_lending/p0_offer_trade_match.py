from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ASSET_NAMES = {"fUST": "USDT", "fUSD": "USD", "fBTC": "BTC", "fETH": "ETH"}
OUTPUT_FIELDS = (
    "offer_id",
    "api_symbol",
    "asset",
    "offer_created_at",
    "offer_updated_at",
    "offer_rate",
    "offer_period",
    "offer_amount_original",
    "offer_outcome",
    "offer_status",
    "matched_trade_count",
    "matched_amount",
    "first_trade_at",
    "last_trade_at",
    "wait_minutes",
    "symbol_consistent",
    "rate_consistent",
    "period_consistent",
    "match_status",
)


def _utc_from_milliseconds(value: object) -> str:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()


def _read_lifecycle(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_unique_trades(path: Path) -> list[list[object]]:
    unique: dict[str, list[object]] = {}
    paths = sorted(path.rglob("*.csv")) if path.is_dir() else (
        [path] if path.exists() else []
    )
    for source in paths:
        with source.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                payload = json.loads(row["raw_payload"])
                unique[str(payload[0])] = payload
    return list(unique.values())


def _consistent_number(expected: str, values: list[object], *, abs_tolerance: float = 1e-12) -> bool:
    if expected == "":
        return False
    return all(
        math.isclose(float(expected), float(value), rel_tol=1e-9, abs_tol=abs_tolerance)
        for value in values
    )


def _trade_details(trades: list[list[object]]) -> dict[str, object]:
    ordered = sorted(trades, key=lambda payload: int(payload[2]))
    return {
        "matched_trade_count": len(ordered),
        "matched_amount": sum(abs(float(payload[4])) for payload in ordered),
        "first_trade_at": _utc_from_milliseconds(ordered[0][2]),
        "last_trade_at": _utc_from_milliseconds(ordered[-1][2]),
    }


def build_offer_trade_matches(
    lifecycle_path: Path,
    trades_path: Path,
    output_path: Path,
) -> dict[str, int]:
    lifecycle_rows = _read_lifecycle(Path(lifecycle_path))
    trades_by_offer: dict[str, list[list[object]]] = defaultdict(list)
    for payload in _read_unique_trades(Path(trades_path)):
        trades_by_offer[str(payload[3])].append(payload)

    output_rows: list[dict[str, object]] = []
    lifecycle_offer_ids: set[str] = set()
    for offer in lifecycle_rows:
        offer_id = offer["offer_id"]
        lifecycle_offer_ids.add(offer_id)
        matched = trades_by_offer.get(offer_id, [])
        result: dict[str, object] = {
            "offer_id": offer_id,
            "api_symbol": offer["api_symbol"],
            "asset": offer["asset"],
            "offer_created_at": offer["created_at"],
            "offer_updated_at": offer["updated_at"],
            "offer_rate": offer["rate"],
            "offer_period": offer["period"],
            "offer_amount_original": offer["amount_original"],
            "offer_outcome": offer["outcome"],
            "offer_status": offer["status"],
            "matched_trade_count": 0,
            "matched_amount": 0.0,
            "first_trade_at": "",
            "last_trade_at": "",
            "wait_minutes": "",
            "symbol_consistent": "",
            "rate_consistent": "",
            "period_consistent": "",
        }
        if matched:
            details = _trade_details(matched)
            result.update(details)
            created_at = datetime.fromisoformat(offer["created_at"])
            first_trade_at = datetime.fromisoformat(str(details["first_trade_at"]))
            wait_minutes = (first_trade_at - created_at).total_seconds() / 60
            symbol_consistent = all(
                str(payload[1]) == offer["api_symbol"] for payload in matched
            )
            rate_consistent = _consistent_number(
                offer["rate"], [payload[5] for payload in matched], abs_tolerance=5e-9
            )
            period_consistent = _consistent_number(
                offer["period"], [payload[6] for payload in matched]
            )
            result["symbol_consistent"] = str(symbol_consistent).lower()
            result["rate_consistent"] = str(rate_consistent).lower()
            result["period_consistent"] = str(period_consistent).lower()
            if wait_minutes < 0:
                result["match_status"] = "matched_time_inconsistent"
            elif not (symbol_consistent and rate_consistent and period_consistent):
                result["wait_minutes"] = round(wait_minutes, 6)
                result["match_status"] = "matched_attributes_inconsistent"
            elif not math.isclose(
                float(details["matched_amount"]),
                float(offer["amount_original"]),
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                result["wait_minutes"] = round(wait_minutes, 6)
                result["match_status"] = (
                    "matched_amount_partial"
                    if float(details["matched_amount"]) < float(offer["amount_original"])
                    else "matched_amount_excess"
                )
            else:
                result["wait_minutes"] = round(wait_minutes, 6)
                result["match_status"] = "matched"
        elif offer["outcome"] == "executed":
            result["match_status"] = "executed_trade_not_in_current_history"
        elif offer["outcome"] == "canceled":
            result["match_status"] = "canceled_without_trade"
        else:
            result["match_status"] = "offer_without_trade"
        output_rows.append(result)

    for offer_id, orphan_trades in trades_by_offer.items():
        if offer_id in lifecycle_offer_ids:
            continue
        details = _trade_details(orphan_trades)
        symbol = str(orphan_trades[0][1])
        output_rows.append(
            {
                "offer_id": offer_id,
                "api_symbol": symbol,
                "asset": ASSET_NAMES.get(symbol, symbol.removeprefix("f")),
                "offer_created_at": "",
                "offer_updated_at": "",
                "offer_rate": "",
                "offer_period": "",
                "offer_amount_original": "",
                "offer_outcome": "",
                "offer_status": "",
                **details,
                "wait_minutes": "",
                "symbol_consistent": "",
                "rate_consistent": "",
                "period_consistent": "",
                "match_status": "trade_without_offer_history",
            }
        )

    output_rows.sort(key=lambda row: (str(row["offer_created_at"]), str(row["offer_id"])))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    temporary.replace(output_path)
    return dict(Counter(str(row["match_status"]) for row in output_rows))


def main() -> int:
    summary = build_offer_trade_matches(
        Path("data/modeling/p0_offer_lifecycle.csv"),
        Path("data/account/funding_trades"),
        Path("data/modeling/p0_offer_trade_matches.csv"),
    )
    print(f"Wrote {sum(summary.values())} offer/trade audit rows: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
