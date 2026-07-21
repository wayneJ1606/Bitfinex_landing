from __future__ import annotations

import sys
from datetime import datetime, timezone
from uuid import uuid4

import requests

from .client import BitfinexClient
from .config import Settings
from .daily_csv import append_daily_snapshot
from .runner import run_collection
from .storage import Storage, StorageError


def build_dependencies(settings: Settings) -> tuple[BitfinexClient, Storage]:
    client = BitfinexClient(
        requests.Session(),
        base_url=settings.api_base_url,
        precision=settings.precision,
        length=settings.book_length,
        timeout=settings.timeout,
    )
    return client, Storage(settings.database_path)


def main(settings: Settings | None = None) -> int:
    settings = settings or Settings()
    try:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        settings.csv_directory.mkdir(parents=True, exist_ok=True)
        client, storage = build_dependencies(settings)
        storage.initialize()
        summary = run_collection(
            settings,
            client,
            storage,
            append_daily_snapshot,
            uuid_factory=lambda: str(uuid4()),
            clock=lambda: datetime.now(timezone.utc),
        )
    except (OSError, StorageError) as error:
        print(f"fatal: {error}", file=sys.stderr)
        return 1

    print(f"run_id={summary.run_id}")
    for result in summary.results:
        print(
            f"{result.market} {result.status} rows={result.row_count} "
            f"message={result.message}"
        )
    success_count = sum(result.status == "success" for result in summary.results)
    empty_count = sum(result.status == "empty" for result in summary.results)
    failed_count = sum(result.status == "failed" for result in summary.results)
    print(
        f"success={success_count} empty={empty_count} failed={failed_count}"
    )
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

