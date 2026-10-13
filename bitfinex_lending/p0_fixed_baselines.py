"""Approved fixed comparison strategies for the P0 funding study."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_PRINCIPALS = tuple(float(index * 1000) for index in range(1, 11))
DEFAULT_PERIODS = (2, 5, 10, 30)
DEFAULT_QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)

OUTPUT_FIELDS = (
    "strategy_id",
    "strategy_type",
    "api_symbol",
    "asset",
    "principal",
    "rate_quantile",
    "fixed_rate",
    "fixed_period_days",
    "training_start",
    "training_end",
    "training_observations",
    "framework_status",
)


class BaselineError(ValueError):
    """Raised when a baseline definition could leak data or is invalid."""


@dataclass(frozen=True)
class BaselineDefinition:
    strategy_type: str
    rate_quantile: float | None
    period_days: int
    wait_hours: int


def baseline_definitions() -> tuple[BaselineDefinition, ...]:
    """Return the three fair, deterministic P0 comparison strategies."""
    return (
        BaselineDefinition("fixed_median", 0.50, 2, 24),
        BaselineDefinition("frr", None, 2, 1),
        BaselineDefinition("quick_fill", 0.10, 2, 1),
    )


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise BaselineError(f"{field} must be ISO 8601: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BaselineError(f"{field} must include a timezone offset")
    return parsed


def _quantile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _validate_candidates(
    rate_quantiles: tuple[float, ...],
    fixed_periods: tuple[int, ...],
    principals: tuple[float, ...],
) -> None:
    if not rate_quantiles or any(
        not math.isfinite(float(item)) or not 0 <= item <= 1
        for item in rate_quantiles
    ):
        raise BaselineError("rate_quantiles must contain finite values in [0, 1]")
    if not fixed_periods or any(
        isinstance(item, bool) or int(item) != item or item < 2
        for item in fixed_periods
    ):
        raise BaselineError("fixed_periods must contain whole days of at least 2")
    if not principals or any(
        not math.isfinite(float(item)) or item <= 0 for item in principals
    ):
        raise BaselineError("principals must contain finite positive values")


def build_fixed_baselines(
    lifecycle_path: Path,
    output_path: Path,
    *,
    training_end: str | None = None,
    rate_quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
    fixed_periods: tuple[int, ...] = DEFAULT_PERIODS,
    principals: tuple[float, ...] = DEFAULT_PRINCIPALS,
) -> int:
    """Preserve the preliminary CSV builder with the approved P0 defaults."""
    _validate_candidates(rate_quantiles, fixed_periods, principals)
    cutoff = _timestamp(training_end, "training_end") if training_end else None
    grouped: dict[tuple[str, str], list[tuple[datetime, float]]] = defaultdict(list)
    lifecycle_path = Path(lifecycle_path)
    if lifecycle_path.exists():
        with lifecycle_path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                created_at = _timestamp(row["created_at"], "created_at")
                if cutoff and created_at > cutoff:
                    continue
                try:
                    rate = float(row["rate"])
                except (TypeError, ValueError) as error:
                    raise BaselineError(f"rate must be numeric: {row['rate']!r}") from error
                if not math.isfinite(rate) or rate <= 0:
                    raise BaselineError("rate must be finite and greater than zero")
                grouped[(row["api_symbol"], row["asset"])].append((created_at, rate))

    output_rows: list[dict[str, object]] = []
    for (api_symbol, asset), observations in sorted(grouped.items()):
        times = [item[0] for item in observations]
        rates = [item[1] for item in observations]
        start_text = min(times).isoformat()
        end_text = training_end if training_end else max(times).isoformat()
        for quantile in rate_quantiles:
            fixed_rate = _quantile(rates, quantile)
            quantile_label = f"q{round(quantile * 100):03d}"
            for principal in principals:
                common = {
                    "api_symbol": api_symbol,
                    "asset": asset,
                    "principal": float(principal),
                    "rate_quantile": quantile,
                    "fixed_rate": format(fixed_rate, ".15g"),
                    "training_start": start_text,
                    "training_end": end_text,
                    "training_observations": len(observations),
                    "framework_status": "definition_only",
                }
                output_rows.append(
                    {
                        "strategy_id": f"B1-{asset}-{principal:g}-{quantile_label}",
                        "strategy_type": "B1_fixed_rate",
                        **common,
                        "fixed_period_days": "",
                    }
                )
                for period in fixed_periods:
                    output_rows.append(
                        {
                            "strategy_id": f"B2-{asset}-{principal:g}-{quantile_label}-{period}d",
                            "strategy_type": "B2_fixed_rate_fixed_period",
                            **common,
                            "fixed_period_days": int(period),
                        }
                    )

    output_rows.sort(key=lambda row: str(row["strategy_id"]))
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
    count = build_fixed_baselines(
        Path("data/modeling/p0_offer_lifecycle.csv"),
        Path("data/modeling/p0_fixed_baselines.csv"),
    )
    print(f"Wrote {count} preliminary fixed-baseline definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
