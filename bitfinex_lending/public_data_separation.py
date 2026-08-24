from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Iterable, Sequence


APPROVED_MARKET_DATASETS = frozenset(
    {"ticker", "funding_stats", "funding_candles", "prices"}
)


class SeparationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeparationSummary:
    file_count: int
    changed_count: int
    total_bytes: int
    total_rows: int
    manifest_path: Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return max(sum(1 for _ in csv.reader(stream)) - 1, 0)


def _path_date(parts: tuple[str, ...]) -> date | None:
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (IndexError, TypeError, ValueError):
        return None


def _approved_sources(data_root: Path, start_date: date) -> tuple[Path, ...]:
    sources: list[Path] = []
    raw_root = data_root / "raw"
    if raw_root.exists():
        for path in raw_root.rglob("*.csv"):
            relative = path.relative_to(raw_root)
            observed = _path_date(relative.parts)
            if observed is not None and observed >= start_date:
                sources.append(path)
    market_root = data_root / "market"
    for dataset in sorted(APPROVED_MARKET_DATASETS):
        dataset_root = market_root / dataset
        if not dataset_root.exists():
            continue
        for path in dataset_root.rglob("*.csv"):
            relative = path.relative_to(dataset_root)
            observed = _path_date(relative.parts)
            if observed is not None and observed >= start_date:
                sources.append(path)
    return tuple(sorted(sources, key=lambda item: item.as_posix()))


def _destination_relative(source_relative: Path) -> Path:
    if source_relative.parts[0] == "raw":
        return Path("local_public/raw").joinpath(*source_relative.parts[1:])
    if (
        len(source_relative.parts) > 1
        and source_relative.parts[0] == "market"
        and source_relative.parts[1] in APPROVED_MARKET_DATASETS
    ):
        return Path("local_public/market").joinpath(*source_relative.parts[1:])
    raise SeparationError(f"unapproved public source: {source_relative.as_posix()}")


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def stage_public_history(data_root: Path, start_date: date) -> SeparationSummary:
    data_root = Path(data_root).resolve()
    entries: list[dict[str, object]] = []
    changed = 0
    for source in _approved_sources(data_root, start_date):
        if source.is_symlink() or not source.is_file():
            raise SeparationError(f"unsupported public source: {source.name}")
        source_relative = source.relative_to(data_root)
        destination_relative = _destination_relative(source_relative)
        destination = data_root / destination_relative
        source_hash = sha256(source)
        if destination.exists():
            if destination.is_symlink() or sha256(destination) != source_hash:
                raise SeparationError(
                    f"collision at {destination_relative.as_posix()}"
                )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            shutil.copyfile(source, temporary)
            if temporary.stat().st_size != source.stat().st_size or sha256(temporary) != source_hash:
                temporary.unlink(missing_ok=True)
                raise SeparationError(f"copy verification failed: {source_relative.as_posix()}")
            temporary.replace(destination)
            changed += 1
        entries.append(
            {
                "source_relative": source_relative.as_posix(),
                "destination_relative": destination_relative.as_posix(),
                "size": source.stat().st_size,
                "rows": _csv_rows(source),
                "sha256": source_hash,
            }
        )
    manifest_path = data_root / "local_public/metadata/separation_manifest.json"
    payload = {
        "schema_version": "local-public-separation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date.isoformat(),
        "entries": entries,
    }
    _atomic_json(manifest_path, payload)
    return SeparationSummary(
        file_count=len(entries),
        changed_count=changed,
        total_bytes=sum(int(entry["size"]) for entry in entries),
        total_rows=sum(int(entry["rows"]) for entry in entries),
        manifest_path=manifest_path,
    )


def archive_verified_sources(
    data_root: Path,
    manifest_path: Path,
    archive_root: Path,
    tracked_paths: Iterable[Path],
) -> int:
    data_root = Path(data_root).resolve()
    archive_root = Path(archive_root).resolve()
    if data_root not in archive_root.parents:
        raise SeparationError("archive root must stay within data root")
    tracked = {Path(path).as_posix() for path in tracked_paths}
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise SeparationError("manifest entries are missing")
    verified: list[tuple[Path, Path]] = []
    for entry in entries:
        source_relative = Path(str(entry["source_relative"]))
        destination_relative = Path(str(entry["destination_relative"]))
        if source_relative.is_absolute() or ".." in source_relative.parts:
            raise SeparationError("manifest contains an unsafe source path")
        if source_relative.as_posix() in tracked:
            raise SeparationError(f"tracked source cannot be archived: {source_relative}")
        source = data_root / source_relative
        destination = data_root / destination_relative
        expected = str(entry["sha256"])
        if not source.exists() or sha256(source) != expected:
            raise SeparationError(f"source hash changed: {source_relative}")
        if not destination.exists() or sha256(destination) != expected:
            raise SeparationError(f"destination hash mismatch: {destination_relative}")
        verified.append((source, source_relative))
    for source, source_relative in verified:
        archive_path = archive_root / source_relative
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            if sha256(archive_path) != sha256(source):
                raise SeparationError(f"archive collision: {source_relative}")
            source.unlink()
        else:
            source.replace(archive_path)
    return len(verified)


def _tracked_public_paths(project_root: Path) -> set[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "data/raw", "data/market"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        Path(line).relative_to("data")
        for line in completed.stdout.splitlines()
        if line.strip()
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Separate local public Bitfinex history")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--archive-verified", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = stage_public_history(args.data_root, args.start_date)
        moved = 0
        if args.archive_verified:
            project_root = args.data_root.resolve().parent
            moved = archive_verified_sources(
                args.data_root,
                summary.manifest_path,
                args.data_root / "archive/local-public-pre-separation-20260824",
                _tracked_public_paths(project_root),
            )
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, SeparationError) as error:
        print(f"status=failed error={error}")
        return 1
    print(
        f"status=success files={summary.file_count} changed={summary.changed_count} "
        f"bytes={summary.total_bytes} rows={summary.total_rows} archived={moved}"
    )
    print(f"manifest={summary.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
