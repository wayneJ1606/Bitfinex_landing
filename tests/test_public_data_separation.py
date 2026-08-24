from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from bitfinex_lending.public_data_separation import (
    SeparationError,
    archive_verified_sources,
    stage_public_history,
)


def _write(path: Path, content: str = "header\nrow\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_stages_only_public_files_on_or_after_start_date(tmp_path: Path) -> None:
    old = tmp_path / "data/raw/2026/08/15/fUST.csv"
    new = tmp_path / "data/raw/2026/08/16/fUST.csv"
    market = tmp_path / "data/market/ticker/2026/08/16/fUST.csv"
    for path in (old, new, market):
        _write(path)

    summary = stage_public_history(tmp_path / "data", date(2026, 8, 16))

    assert summary.file_count == 2
    assert summary.changed_count == 2
    assert summary.total_rows == 2
    assert not (tmp_path / "data/local_public/raw/2026/08/15/fUST.csv").exists()
    assert (tmp_path / "data/local_public/raw/2026/08/16/fUST.csv").exists()
    assert (tmp_path / "data/local_public/market/ticker/2026/08/16/fUST.csv").exists()


def test_rejects_a_different_existing_destination(tmp_path: Path) -> None:
    _write(tmp_path / "data/raw/2026/08/16/fUST.csv", "source\n")
    _write(tmp_path / "data/local_public/raw/2026/08/16/fUST.csv", "different\n")

    with pytest.raises(SeparationError, match="collision"):
        stage_public_history(tmp_path / "data", date(2026, 8, 16))


def test_identical_rerun_is_a_noop_and_manifest_is_public(tmp_path: Path) -> None:
    _write(tmp_path / "data/raw/2026/08/16/fUST.csv")
    first = stage_public_history(tmp_path / "data", date(2026, 8, 16))
    second = stage_public_history(tmp_path / "data", date(2026, 8, 16))
    payload = json.loads(second.manifest_path.read_text(encoding="utf-8"))

    assert first.changed_count == 1
    assert second.changed_count == 0
    assert str(tmp_path) not in second.manifest_path.read_text(encoding="utf-8")
    assert "account" not in json.dumps(payload).lower()


def test_archive_refuses_git_tracked_sources(tmp_path: Path) -> None:
    source = tmp_path / "data/raw/2026/08/16/fUST.csv"
    _write(source)
    summary = stage_public_history(tmp_path / "data", date(2026, 8, 16))

    with pytest.raises(SeparationError, match="tracked"):
        archive_verified_sources(
            tmp_path / "data",
            summary.manifest_path,
            tmp_path / "data/archive/pre-separation",
            {Path("raw/2026/08/16/fUST.csv")},
        )
    assert source.exists()


def test_archive_moves_only_hash_verified_sources(tmp_path: Path) -> None:
    source = tmp_path / "data/raw/2026/08/16/fUST.csv"
    _write(source)
    summary = stage_public_history(tmp_path / "data", date(2026, 8, 16))
    archive = tmp_path / "data/archive/pre-separation"

    moved = archive_verified_sources(
        tmp_path / "data", summary.manifest_path, archive, set()
    )

    assert moved == 1
    assert not source.exists()
    assert (archive / "raw/2026/08/16/fUST.csv").exists()
    assert (tmp_path / "data/local_public/raw/2026/08/16/fUST.csv").exists()
