from __future__ import annotations

import logging
import json
import os
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

import requests

from .account_storage import AccountStorage, AccountStorageError
from .config import Settings
from .private_client import (
    PrivateClientError,
    PrivatePermissionError,
    ReadOnlyBitfinexClient,
)
from .collector_run_history import CollectorRunRecord, append_collector_run


class PrivateClientLike(Protocol):
    def check_permissions(self) -> object: ...

    def fetch_private(self, path: str, payload: dict[str, object]) -> object: ...


class AccountStorageLike(Protocol):
    root: Path

    def initialize(self) -> None: ...

    def append_snapshot(self, dataset: str, collected_at: str, rows: list[Any]) -> int: ...

    def write_status(self, status: dict[str, object]) -> None: ...


ENDPOINTS = (
    ("funding_offers", "/v2/auth/r/funding/offers"),
    ("funding_offers_history", "/v2/auth/r/funding/offers/hist"),
    ("funding_trades", "/v2/auth/r/funding/trades/hist"),
    ("funding_loans", "/v2/auth/r/funding/loans/hist"),
    ("funding_credits", "/v2/auth/r/funding/credits"),
)


@dataclass(frozen=True)
class CollectionSummary:
    row_counts: dict[str, int]
    failures: dict[str, str]
    started_at: str
    finished_at: str
    permission_checked: bool = True


def run_private_collection(
    client: PrivateClientLike,
    storage: AccountStorageLike,
    *,
    collected_at: datetime,
    max_attempts: int = 3,
    retry_delay: float = 2.0,
    run_history_root: Path | None = None,
    run_id_factory: Callable[[], str] = lambda: str(uuid4()),
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> CollectionSummary:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    storage.initialize()
    lock_path = storage.root / ".private-collector.lock"
    _acquire_lock(lock_path)
    run_id = str(run_id_factory())
    started_at = clock().astimezone(timezone.utc).isoformat()
    try:
        try:
            client.check_permissions()
        except (PrivateClientError, OSError, ValueError, TypeError) as error:
            finished_at = clock().astimezone(timezone.utc).isoformat()
            storage.write_status(
                {
                    "status": "permission_failed",
                    "permission_checked": False,
                    "failures": {"permissions": _safe_error_text(error)},
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "schema_version": "account-collector-v1",
                }
            )
            if run_history_root is not None:
                append_collector_run(
                    run_history_root,
                    CollectorRunRecord(
                        run_id=run_id,
                        collector="private",
                        started_at=started_at,
                        finished_at=finished_at,
                        status="failed",
                        expected_interval_minutes=5,
                        successful_units=0,
                        failed_units=1,
                        row_counts={},
                        failures={"permissions": _safe_error_text(error)},
                        permission_checked=False,
                    ),
                )
            raise
        collected_text = collected_at.astimezone(timezone.utc).isoformat()
        row_counts: dict[str, int] = {}
        failures: dict[str, str] = {}
        for dataset, endpoint in ENDPOINTS:
            try:
                rows = _fetch_with_retry(
                    client, endpoint, max_attempts=max_attempts, retry_delay=retry_delay
                )
                normalized_rows = _dataset_rows(rows)
                row_counts[dataset] = storage.append_snapshot(
                    dataset, collected_text, normalized_rows
                )
            except (
                AccountStorageError,
                PrivateClientError,
                OSError,
                ValueError,
                TypeError,
            ) as error:
                failures[dataset] = _safe_error_text(error)
                logging.getLogger(__name__).warning(
                    "private dataset %s failed: %s", dataset, failures[dataset]
                )
        finished_at = clock().astimezone(timezone.utc).isoformat()
        successful_units = len(ENDPOINTS) - len(failures)
        failed_units = len(failures)
        status = "success" if not failures else ("partial" if successful_units else "failed")
        summary = CollectionSummary(row_counts, failures, started_at, finished_at)
        storage.write_status(
            {
                "status": status,
                "permission_checked": True,
                "row_counts": row_counts,
                "failures": failures,
                "started_at": started_at,
                "finished_at": finished_at,
                "schema_version": "account-collector-v1",
            }
        )
        if run_history_root is not None:
            append_collector_run(
                run_history_root,
                CollectorRunRecord(
                    run_id=run_id,
                    collector="private",
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    expected_interval_minutes=5,
                    successful_units=successful_units,
                    failed_units=failed_units,
                    row_counts=row_counts,
                    failures=failures,
                    permission_checked=True,
                ),
            )
        return summary
    finally:
        _release_lock(lock_path)


def _fetch_with_retry(
    client: PrivateClientLike,
    endpoint: str,
    *,
    max_attempts: int,
    retry_delay: float,
) -> object:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return client.fetch_private(endpoint, {})
        except (OSError, PrivateClientError) as error:
            last_error = error
            if (
                attempt + 1 < max_attempts
                and (isinstance(error, OSError) or error.retryable)
                and retry_delay > 0
            ):
                time.sleep(retry_delay * (2**attempt))
            elif not isinstance(error, OSError) and not error.retryable:
                raise
    assert last_error is not None
    raise last_error


def _dataset_rows(response: object) -> list[Any]:
    if not isinstance(response, list):
        raise PrivateClientError("invalid authenticated dataset response")
    if response and isinstance(response[0], str) and response[0].casefold() == "error":
        raise PrivateClientError("Bitfinex returned an authenticated API error")
    return response


def _acquire_lock(path: Path) -> None:
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid()}, handle)
            return
        except FileExistsError as error:
            if not _lock_owner_is_gone(path):
                raise RuntimeError("private collector is already running") from error
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _lock_owner_is_gone(path: Path) -> bool:
    try:
        contents = path.read_text(encoding="utf-8").strip()
        metadata = json.loads(contents)
        pid = metadata["pid"] if isinstance(metadata, dict) else metadata
    except json.JSONDecodeError:
        try:
            pid = int(contents)
        except (UnboundLocalError, ValueError):
            return False
    except (OSError, KeyError, TypeError):
        return False
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError as error:
        return getattr(error, "winerror", None) == 87
    return False


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _safe_error_text(error: Exception) -> str:
    if isinstance(error, PrivatePermissionError):
        return "permission validation failed"
    if isinstance(error, PrivateClientError):
        return "authenticated request failed"
    if isinstance(error, OSError):
        return "network or storage error"
    if isinstance(error, (ValueError, TypeError)):
        return "invalid response"
    return "private collector failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Bitfinex Funding data read-only")
    parser.add_argument("--dry-run", action="store_true", help="check permissions only")
    parser.add_argument("--account-root", type=Path, default=Path("data/account"))
    parser.add_argument("--metadata-root", type=Path, default=Path("data/metadata"))
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    args = parser.parse_args(argv)

    api_key = os.environ.get("BITFINEX_READONLY_API_KEY")
    api_secret = os.environ.get("BITFINEX_READONLY_API_SECRET")
    if not api_key or not api_secret:
        print(
            "Missing read-only Bitfinex credentials: set "
            "BITFINEX_READONLY_API_KEY and BITFINEX_READONLY_API_SECRET.",
            file=__import__("sys").stderr,
        )
        return 2

    try:
        client = ReadOnlyBitfinexClient(
            api_key,
            api_secret,
            requests.Session(),
            base_url=Settings().private_api_base_url,
        )
        if args.dry_run:
            client.check_permissions()
            print("Read-only permissions verified; no account data was collected.")
            return 0
        storage = AccountStorage(args.account_root, metadata_root=args.metadata_root)
        summary = run_private_collection(
            client,
            storage,
            collected_at=datetime.now(timezone.utc),
            max_attempts=args.max_attempts,
            retry_delay=args.retry_delay,
            run_history_root=args.metadata_root / "collector_runs",
        )
        print(
            f"Private collection finished: {sum(summary.row_counts.values())} rows, "
            f"{len(summary.failures)} dataset failures."
        )
        return 0 if not summary.failures else 1
    except Exception as error:
        print(f"Private collection stopped: {_safe_error_text(error)}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
