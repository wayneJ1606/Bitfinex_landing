from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bitfinex_lending.feature_csv import (
    FIELD_NAMES,
    FeatureCsvError,
    export_modeling_features,
)
from bitfinex_lending.models import ModelingFeature


EXPECTED_HEADER = [
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
]


def make_feature(
    market: str,
    feature_time: str,
    *,
    previous: float | None = None,
    rate_change: float | None = None,
    amount_change: float | None = None,
    target: float | None = None,
) -> ModelingFeature:
    return ModelingFeature(
        market=market,
        feature_time=feature_time,
        hour=4,
        day_of_week=1,
        avg_rate=0.0002,
        weighted_avg_rate=0.00025,
        min_rate=0.0001,
        max_rate=0.0003,
        total_amount=40.0,
        avg_period=3.5,
        offer_count=2,
        demand_count=3,
        rate_spread=0.0002,
        previous_weighted_avg_rate=previous,
        rate_change=rate_change,
        amount_change=amount_change,
        target_next_weighted_avg_rate=target,
    )


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


def test_export_writes_fixed_header_utf8_nulls_and_utc_sorted_rows(
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "nested" / "csv"
    features = (
        make_feature("f美元", "2026-07-14T06:00:00+00:00", previous=0.0001),
        make_feature("fBTC", "2026-07-14T13:00:00+08:00", target=0.0003),
        make_feature("fBTC", "2026-07-14T04:00:00+00:00"),
    )

    path = export_modeling_features(features, output_directory)

    assert path == output_directory / "modeling_features.csv"
    rows = read_csv(path)
    assert list(FIELD_NAMES) == EXPECTED_HEADER
    assert rows[0] == EXPECTED_HEADER
    assert [(row[0], row[1]) for row in rows[1:]] == [
        ("fBTC", "2026-07-14T04:00:00+00:00"),
        ("fBTC", "2026-07-14T13:00:00+08:00"),
        ("f美元", "2026-07-14T06:00:00+00:00"),
    ]
    assert rows[1][13:] == ["", "", "", ""]
    assert rows[2][13:] == ["", "", "", "0.0003"]
    assert list(output_directory.glob("*.tmp")) == []


def test_export_empty_dataset_creates_header_only_file(tmp_path: Path) -> None:
    path = export_modeling_features((), tmp_path)

    assert read_csv(path) == [EXPECTED_HEADER]


def test_export_atomically_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "modeling_features.csv"
    target.write_text("old content", encoding="utf-8")

    export_modeling_features((make_feature("fUSD", "2026-07-14T04:00:00Z"),), tmp_path)

    assert read_csv(target)[0] == EXPECTED_HEADER
    assert "old content" not in target.read_text(encoding="utf-8")
    assert list(tmp_path.glob("*.tmp")) == []


def test_export_preserves_target_and_removes_tmp_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "modeling_features.csv"
    target.write_text("previous dataset", encoding="utf-8")

    def fail_replace(self: Path, destination: Path) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(FeatureCsvError, match="failed to export modeling features"):
        export_modeling_features(
            (make_feature("fUSD", "2026-07-14T04:00:00+00:00"),), tmp_path
        )

    assert target.read_text(encoding="utf-8") == "previous dataset"
    assert list(tmp_path.glob("*.tmp")) == []
