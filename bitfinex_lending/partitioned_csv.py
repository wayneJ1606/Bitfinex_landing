from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def utc_partition(value: str) -> tuple[str, str, str]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"timestamp must be ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    observed = parsed.astimezone(timezone.utc)
    return observed.strftime("%Y"), observed.strftime("%m"), observed.strftime("%d")


def account_daily_path(root: Path, dataset: str, collected_at: str) -> Path:
    year, month, day = utc_partition(collected_at)
    return Path(root) / dataset / year / month / f"{day}.csv"


def market_daily_path(
    root: Path, category: str, market: str, collected_at: str
) -> Path:
    year, month, day = utc_partition(collected_at)
    return Path(root) / category / year / month / day / f"{market}.csv"
