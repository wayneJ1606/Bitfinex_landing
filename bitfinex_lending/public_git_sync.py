from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable, Iterable, Sequence


APPROVED_PREFIXES = (
    Path("data/local_public/raw"),
    Path("data/local_public/market"),
    Path("data/local_public/metadata"),
)
FORBIDDEN_FIELDS = {"api_key", "api_secret", "offer_id", "event_id", "raw_payload"}


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncSummary:
    status: str
    file_count: int
    total_bytes: int
    commit_sha: str | None
    attempts: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_keys(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key).lower()
            yield from _json_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_keys(item)


def _validate_public_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise SyncError(f"unsupported public file: {path.name}")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        forbidden = FORBIDDEN_FIELDS.intersection(item.strip().lower() for item in header)
        if forbidden:
            raise SyncError(f"forbidden public fields: {sorted(forbidden)}")
        return
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SyncError(f"invalid public JSON: {path.name}") from error
        forbidden = FORBIDDEN_FIELDS.intersection(_json_keys(payload))
        if forbidden:
            raise SyncError(f"forbidden public fields: {sorted(forbidden)}")
        return
    raise SyncError(f"unsupported public file extension: {path.name}")


def collect_public_files(project_root: Path) -> tuple[Path, ...]:
    project_root = Path(project_root).resolve()
    files: list[Path] = []
    for prefix in APPROVED_PREFIXES:
        root = project_root / prefix
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.name == "sync_manifest.json":
                continue
            resolved = path.resolve()
            if project_root not in resolved.parents:
                raise SyncError(f"public path escapes project root: {path.name}")
            _validate_public_file(path)
            files.append(resolved)
    return tuple(sorted(files, key=lambda item: item.as_posix()))


def push_with_retries(operation: Callable[[], None], *, max_attempts: int = 3) -> int:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for attempt in range(1, max_attempts + 1):
        try:
            operation()
            return attempt
        except subprocess.CalledProcessError:
            if attempt == max_attempts:
                raise
    raise RuntimeError("unreachable")


def _run(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )


def _atomic_status(project_root: Path, summary: SyncSummary, error_type: str | None = None) -> None:
    path = project_root / "data/metadata/public_git_sync_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    payload = asdict(summary)
    if error_type is not None:
        payload["error_type"] = error_type
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sync_manifest(project_root: Path, files: Sequence[Path]) -> dict[str, object]:
    return {
        "schema_version": "local-public-git-sync-v1",
        "entries": [
            {
                "relative_path": path.relative_to(project_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }


def synchronize(
    project_root: Path,
    *,
    branch: str = "master",
    push: bool = False,
    remote_url: str | None = None,
    max_attempts: int = 3,
) -> SyncSummary:
    project_root = Path(project_root).resolve()
    files = collect_public_files(project_root)
    total_bytes = sum(path.stat().st_size for path in files)
    if not push:
        return SyncSummary("preview", len(files), total_bytes, None, 0)
    try:
        if remote_url is None:
            remote_url = _run(project_root, "remote", "get-url", "origin").stdout.strip()
        if not remote_url:
            raise SyncError("origin remote is unavailable")
        with tempfile.TemporaryDirectory(prefix="bitfinex-public-sync-") as temporary:
            checkout = Path(temporary) / "repository"
            subprocess.run(
                ["git", "clone", "--branch", branch, "--single-branch", remote_url, str(checkout)],
                check=True,
                capture_output=True,
                text=True,
                shell=False,
            )
            for source in files:
                relative = source.relative_to(project_root)
                destination = checkout / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            manifest_path = checkout / "data/local_public/metadata/sync_manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    _sync_manifest(project_root, files),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            _run(checkout, "config", "user.name", "Bitfinex local public sync")
            _run(checkout, "config", "user.email", "local-public-sync@users.noreply.github.com")
            stage_paths = tuple(
                prefix.as_posix()
                for prefix in APPROVED_PREFIXES
                if (checkout / prefix).exists()
            )
            _run(checkout, "add", "--", *stage_paths)
            unchanged = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=checkout,
                check=False,
                shell=False,
            ).returncode == 0
            if unchanged:
                summary = SyncSummary("no_changes", len(files), total_bytes, None, 0)
                _atomic_status(project_root, summary)
                return summary
            _run(checkout, "commit", "-m", "data: sync local public collection [skip ci]")

            def push_once() -> None:
                _run(checkout, "pull", "--rebase", "origin", branch)
                _run(checkout, "push", "origin", f"HEAD:{branch}")

            attempts = push_with_retries(push_once, max_attempts=max_attempts)
            commit_sha = _run(checkout, "rev-parse", "HEAD").stdout.strip()
            summary = SyncSummary("success", len(files), total_bytes, commit_sha, attempts)
            _atomic_status(project_root, summary)
            return summary
    except (OSError, subprocess.SubprocessError, SyncError) as error:
        summary = SyncSummary("failed", len(files), total_bytes, None, max_attempts)
        _atomic_status(project_root, summary, type(error).__name__)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronize allowlisted local public data")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--branch", default="master")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = synchronize(
            args.project_root,
            branch=args.branch,
            push=args.push,
        )
    except (OSError, subprocess.SubprocessError, SyncError) as error:
        print(f"status=failed error_type={type(error).__name__}")
        return 1
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
    print(f"push={str(args.push).lower()} branch={args.branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
