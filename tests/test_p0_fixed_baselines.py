import csv
from pathlib import Path

import pytest

from bitfinex_lending.p0_fixed_baselines import (
    BaselineError,
    DEFAULT_PERIODS,
    DEFAULT_PRINCIPALS,
    DEFAULT_QUANTILES,
    baseline_definitions,
    build_fixed_baselines,
)


def test_p0_defaults_match_the_approved_grid() -> None:
    assert DEFAULT_PRINCIPALS == tuple(float(index * 1000) for index in range(1, 11))
    assert DEFAULT_PERIODS == (2, 5, 10, 30)
    assert DEFAULT_QUANTILES == (0.10, 0.25, 0.50, 0.75, 0.90)


def test_three_baselines_have_the_approved_terms() -> None:
    definitions = {row.strategy_type: row for row in baseline_definitions()}

    assert set(definitions) == {"fixed_median", "frr", "quick_fill"}
    assert definitions["fixed_median"].rate_quantile == 0.50
    assert definitions["fixed_median"].period_days == 2
    assert definitions["fixed_median"].wait_hours == 24
    assert definitions["frr"].rate_quantile is None
    assert definitions["frr"].period_days == 2
    assert definitions["frr"].wait_hours == 1
    assert definitions["quick_fill"].rate_quantile == 0.10
    assert definitions["quick_fill"].period_days == 2
    assert definitions["quick_fill"].wait_hours == 1


LIFECYCLE_FIELDS = (
    "offer_id",
    "api_symbol",
    "asset",
    "created_at",
    "updated_at",
    "rate",
    "period",
    "status",
    "outcome",
)


def _write_lifecycle(path: Path, rows: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LIFECYCLE_FIELDS)
        writer.writeheader()
        for index, (created_at, rate) in enumerate(rows):
            writer.writerow(
                {
                    "offer_id": index,
                    "api_symbol": "fUST",
                    "asset": "USDT",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "rate": rate,
                    "period": 2,
                    "status": "EXECUTED",
                    "outcome": "executed",
                }
            )


def test_legacy_csv_builder_remains_available_with_explicit_grid(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    output = tmp_path / "baselines.csv"
    _write_lifecycle(
        lifecycle,
        [
            ("2026-08-01T00:00:00+00:00", 0.0001),
            ("2026-08-02T00:00:00+00:00", 0.0002),
            ("2026-08-03T00:00:00+00:00", 0.0003),
        ],
    )

    count = build_fixed_baselines(
        lifecycle,
        output,
        rate_quantiles=(0.0, 1.0),
        fixed_periods=(2, 5),
        principals=(1000.0, 2000.0),
    )

    assert count == 12
    rows = list(csv.DictReader(output.open(encoding="utf-8", newline="")))
    assert {row["strategy_type"] for row in rows} == {
        "B1_fixed_rate",
        "B2_fixed_rate_fixed_period",
    }
    assert {row["fixed_rate"] for row in rows} == {"0.0001", "0.0003"}
    assert all(row["framework_status"] == "definition_only" for row in rows)


def test_legacy_csv_builder_excludes_rates_after_training_cutoff(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    output = tmp_path / "baselines.csv"
    _write_lifecycle(
        lifecycle,
        [
            ("2026-08-01T00:00:00+00:00", 0.0001),
            ("2026-08-02T00:00:00+00:00", 0.0002),
            ("2026-08-10T00:00:00+00:00", 0.9),
        ],
    )

    build_fixed_baselines(
        lifecycle,
        output,
        training_end="2026-08-02T23:59:59+00:00",
        rate_quantiles=(0.5,),
        fixed_periods=(2,),
        principals=(1000.0,),
    )

    rows = list(csv.DictReader(output.open(encoding="utf-8", newline="")))
    assert {row["fixed_rate"] for row in rows} == {"0.00015"}
    assert all(row["training_observations"] == "2" for row in rows)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rate_quantiles": (-0.1,)},
        {"fixed_periods": (0,)},
        {"principals": (0.0,)},
    ],
)
def test_legacy_csv_builder_rejects_invalid_grid(
    tmp_path: Path,
    kwargs: dict[str, object],
) -> None:
    lifecycle = tmp_path / "lifecycle.csv"
    _write_lifecycle(lifecycle, [("2026-08-01T00:00:00+00:00", 0.0001)])

    with pytest.raises(BaselineError):
        build_fixed_baselines(lifecycle, tmp_path / "out.csv", **kwargs)
