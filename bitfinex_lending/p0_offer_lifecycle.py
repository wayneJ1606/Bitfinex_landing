from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ASSET_NAMES = {"fUST": "USDT", "fUSD": "USD", "fBTC": "BTC", "fETH": "ETH"}
OUTPUT_FIELDS = (
    "offer_id",
    "api_symbol",
    "asset",
    "created_at",
    "updated_at",
    "first_collected_at",
    "last_collected_at",
    "lifecycle_minutes",
    "amount_original",
    "amount_remaining",
    "rate",
    "period",
    "status",
    "outcome",
    "observation_count",
)


def _utc_from_milliseconds(value: object) -> str:
    milliseconds = int(value)
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat()


def _outcome(status: str) -> str:
    normalized = status.upper()
    if normalized.startswith("EXECUTED"):
        return "executed"
    if normalized.startswith("CANCELED"):
        return "canceled"
    if normalized == "ACTIVE":
        return "active"
    return "other"


def build_offer_lifecycle(history_path: Path, output_path: Path) -> int:
    history_path = Path(history_path)
    observations: dict[str, list[dict[str, object]]] = defaultdict(list)
    paths = sorted(history_path.rglob("*.csv")) if history_path.is_dir() else (
        [history_path] if history_path.exists() else []
    )
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                payload = json.loads(row["raw_payload"])
                observations[str(payload[0])].append(
                    {"payload": payload, "collected_at": row["collected_at"]}
                )

    lifecycle_rows: list[dict[str, object]] = []
    for offer_id, items in observations.items():
        items.sort(key=lambda item: (int(item["payload"][3]), str(item["collected_at"])))
        latest = items[-1]["payload"]
        collected_times = sorted(str(item["collected_at"]) for item in items)
        symbol = str(latest[1])
        created_ms = int(latest[2])
        updated_ms = int(latest[3])
        status = str(latest[10] or "")
        lifecycle_rows.append(
            {
                "offer_id": offer_id,
                "api_symbol": symbol,
                "asset": ASSET_NAMES.get(symbol, symbol.removeprefix("f")),
                "created_at": _utc_from_milliseconds(created_ms),
                "updated_at": _utc_from_milliseconds(updated_ms),
                "first_collected_at": collected_times[0],
                "last_collected_at": collected_times[-1],
                "lifecycle_minutes": round((updated_ms - created_ms) / 60_000, 6),
                "amount_original": latest[5] if latest[5] is not None else "",
                "amount_remaining": latest[4] if latest[4] is not None else "",
                "rate": latest[14] if latest[14] is not None else "",
                "period": latest[15] if latest[15] is not None else "",
                "status": status,
                "outcome": _outcome(status),
                "observation_count": len(items),
            }
        )
    lifecycle_rows.sort(key=lambda row: (str(row["created_at"]), str(row["offer_id"])))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(lifecycle_rows)
    temporary.replace(output_path)
    return len(lifecycle_rows)


def main() -> int:
    count = build_offer_lifecycle(
        Path("data/account/funding_offers_history"),
        Path("data/modeling/p0_offer_lifecycle.csv"),
    )
    print(f"Wrote {count} offer lifecycle rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
