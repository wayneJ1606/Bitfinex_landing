from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .partitioned_csv import account_daily_path, market_daily_path


ACCOUNT_DATASETS = (
    "funding_offers",
    "funding_offers_history",
    "funding_trades",
    "funding_loans",
    "funding_credits",
)
MARKET_CATEGORIES = ("ticker", "funding_stats", "funding_candles", "prices")


class MigrationError(RuntimeError):
    """Raised when a daily CSV migration cannot be proven safe."""


@dataclass(frozen=True)
class MigrationSummary:
    source_rows: int
    inserted_rows: int
    duplicate_rows: int
    output_files: int


def _rows(path: Path) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = tuple(next(reader))
            if not header or "collected_at" not in header:
                raise MigrationError(f"missing collected_at header: {path}")
            return header, [tuple(row) for row in reader]
    except StopIteration as exc:
        raise MigrationError(f"missing CSV header: {path}") from exc
    except (OSError, csv.Error) as exc:
        raise MigrationError(f"cannot read CSV {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _legacy_files(data_root: Path) -> list[Path]:
    files = [data_root / "account" / f"{dataset}.csv" for dataset in ACCOUNT_DATASETS]
    for category in MARKET_CATEGORIES:
        root = data_root / "market" / category
        if root.exists():
            files.extend(path for path in root.glob("*.csv") if path.is_file())
    return sorted((path for path in files if path.exists()), key=lambda path: path.as_posix())


def _rollback_staged_files(moved: list[tuple[Path, Path]]) -> list[str]:
    failures: list[str] = []
    for source, destination in reversed(moved):
        if not destination.exists():
            failures.append(f"staged file is missing during rollback: {destination}")
            continue
        if source.exists():
            failures.append(f"refusing to overwrite source during rollback: {source}")
            continue
        try:
            source.parent.mkdir(parents=True, exist_ok=True)
            destination.replace(source)
        except OSError as exc:
            failures.append(f"cannot restore {source} from {destination}: {exc}")
    return failures


def stage_legacy_files(data_root: Path, backup_root: Path) -> tuple[Path, ...]:
    data_root = Path(data_root).resolve()
    backup_root = Path(backup_root).resolve()
    archive_root = (data_root / "archive").resolve()
    if not backup_root.is_relative_to(archive_root) or backup_root == archive_root:
        raise MigrationError("backup_root must be a dedicated directory under data/archive")
    sources = _legacy_files(data_root)
    if not sources:
        raise MigrationError("no legacy CSV files found to stage")
    destinations = [backup_root / source.relative_to(data_root) for source in sources]
    if any(destination.exists() for destination in destinations):
        raise MigrationError("backup destination already contains a staged CSV")
    manifest_path = backup_root / "manifest.json"
    temporary_manifest = backup_root / "manifest.json.staging"
    if manifest_path.exists() or temporary_manifest.exists():
        raise MigrationError("backup directory already contains a staging manifest")

    manifest: list[dict[str, object]] = []
    moved: list[tuple[Path, Path]] = []
    try:
        for source, destination in zip(sources, destinations, strict=True):
            _, rows = _rows(source)
            manifest.append(
                {
                    "relative_path": source.relative_to(data_root).as_posix(),
                    "rows": len(rows),
                    "sha256": _sha256(source),
                }
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            moved.append((source, destination))
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_manifest.replace(manifest_path)
    except (OSError, csv.Error, MigrationError) as exc:
        rollback_failures = _rollback_staged_files(moved)
        temporary_manifest.unlink(missing_ok=True)
        if rollback_failures:
            detail = "; ".join(rollback_failures)
            raise MigrationError(f"staging failed ({exc}); rollback incomplete: {detail}") from exc
        raise MigrationError(f"cannot stage legacy CSV files: {exc}") from exc
    return tuple(destinations)


def _staged_files(backup_root: Path) -> list[tuple[str, str, Path]]:
    result: list[tuple[str, str, Path]] = []
    account_root = backup_root / "account"
    for dataset in ACCOUNT_DATASETS:
        path = account_root / f"{dataset}.csv"
        if path.exists():
            result.append(("account", dataset, path))
    for category in MARKET_CATEGORIES:
        category_root = backup_root / "market" / category
        if category_root.exists():
            result.extend(("market", category, path) for path in category_root.glob("*.csv"))
    return sorted(result, key=lambda item: item[2].as_posix())


def _target_path(
    data_root: Path,
    kind: str,
    name: str,
    source: Path,
    collected_at: str,
) -> Path:
    if kind == "account":
        return account_daily_path(data_root / "account", name, collected_at)
    return market_daily_path(data_root / "market", name, source.stem, collected_at)


def _merge_rows(
    path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]]
) -> tuple[int, int]:
    existing: list[tuple[str, ...]] = []
    if path.exists():
        existing_header, existing = _rows(path)
        if existing_header != header:
            raise MigrationError(f"header mismatch in target: {path}")
    seen = set(existing)
    inserted: list[tuple[str, ...]] = []
    duplicates = 0
    for row in rows:
        if row in seen:
            duplicates += 1
        else:
            seen.add(row)
            inserted.append(row)
    if not inserted:
        return 0, duplicates
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(existing)
            writer.writerows(inserted)
        temporary.replace(path)
    except (OSError, csv.Error) as exc:
        temporary.unlink(missing_ok=True)
        raise MigrationError(f"cannot write target CSV {path}: {exc}") from exc
    return len(inserted), duplicates


def migrate_staged_files(backup_root: Path, data_root: Path) -> MigrationSummary:
    backup_root = Path(backup_root)
    data_root = Path(data_root)
    source_rows = inserted_rows = duplicate_rows = 0
    outputs: set[Path] = set()
    for kind, name, source in _staged_files(backup_root):
        header, rows = _rows(source)
        collected_index = header.index("collected_at")
        grouped: dict[Path, list[tuple[str, ...]]] = {}
        for row in rows:
            if len(row) != len(header):
                raise MigrationError(f"row width mismatch in source: {source}")
            target = _target_path(data_root, kind, name, source, row[collected_index])
            source_rows += 1
            outputs.add(target)
            grouped.setdefault(target, []).append(row)
        for target, target_rows in grouped.items():
            inserted, duplicates = _merge_rows(target, header, target_rows)
            inserted_rows += inserted
            duplicate_rows += duplicates
    if source_rows == 0:
        raise MigrationError("staged backup contains no CSV rows")
    return MigrationSummary(source_rows, inserted_rows, duplicate_rows, len(outputs))


def _verify_manifest(backup_root: Path) -> None:
    manifest_path = backup_root / "manifest.json"
    if not manifest_path.exists():
        raise MigrationError("backup manifest is missing")
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in entries:
        path = backup_root / str(entry["relative_path"])
        if not path.exists() or _sha256(path) != entry["sha256"]:
            raise MigrationError(f"backup hash mismatch: {path}")
        _, rows = _rows(path)
        if len(rows) != int(entry["rows"]):
            raise MigrationError(f"backup row count mismatch: {path}")


def verify_staged_migration(backup_root: Path, data_root: Path) -> int:
    backup_root = Path(backup_root)
    data_root = Path(data_root)
    _verify_manifest(backup_root)
    expected: dict[Path, tuple[tuple[str, ...], list[tuple[str, ...]]]] = {}
    for kind, name, source in _staged_files(backup_root):
        header, rows = _rows(source)
        collected_index = header.index("collected_at")
        for row in rows:
            target = _target_path(data_root, kind, name, source, row[collected_index])
            existing = expected.setdefault(target, (header, []))
            if existing[0] != header:
                raise MigrationError(f"conflicting source headers for target: {target}")
            existing[1].append(row)
    verified = 0
    for target, (header, rows) in expected.items():
        if not target.exists():
            raise MigrationError(f"daily target is missing: {target}")
        target_header, target_rows = _rows(target)
        target_set = set(target_rows)
        if target_header != header or any(row not in target_set for row in rows):
            raise MigrationError(f"source row is missing from daily target: {target}")
        verified += len(rows)
    if verified == 0:
        raise MigrationError("no staged rows were available to verify")
    return verified


def delete_verified_backup(backup_root: Path, data_root: Path) -> int:
    backup_root = Path(backup_root).resolve()
    data_root = Path(data_root).resolve()
    archive_root = (data_root / "archive").resolve()
    if not backup_root.is_relative_to(archive_root) or backup_root == archive_root:
        raise MigrationError("refusing to delete outside a dedicated data/archive directory")
    verified = verify_staged_migration(backup_root, data_root)
    shutil.rmtree(backup_root)
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely migrate legacy CSVs to UTC daily partitions")
    parser.add_argument("phase", choices=("stage", "migrate", "verify", "delete"))
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--backup-root", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "stage":
        result: object = {"staged_files": len(stage_legacy_files(args.data_root, args.backup_root))}
    elif args.phase == "migrate":
        result = asdict(migrate_staged_files(args.backup_root, args.data_root))
    elif args.phase == "verify":
        result = {"verified_rows": verify_staged_migration(args.backup_root, args.data_root)}
    else:
        result = {"deleted_verified_rows": delete_verified_backup(args.backup_root, args.data_root)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
