from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .client import ClientError
from .config import Settings
from .csv_export import CsvExportError
from .models import FundingBookRow, MarketResult, RunSummary
from .parser import ParseError, parse_book
from .storage import StorageError


class ClientLike(Protocol):
    def fetch_book(self, market: str) -> object: ...


class StorageLike(Protocol):
    def record_success(
        self,
        rows: Sequence[FundingBookRow],
        *,
        started_at: str,
        finished_at: str,
    ) -> None: ...

    def record_empty(
        self, run_id: str, market: str, started_at: str, finished_at: str
    ) -> None: ...

    def record_failure(
        self,
        run_id: str,
        market: str,
        started_at: str,
        finished_at: str,
        error_type: str,
        message: str,
    ) -> None: ...


Exporter = Callable[[Sequence[FundingBookRow], Path], Path]


def _utc_iso(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


def _error_details(error: Exception) -> tuple[str, str]:
    if isinstance(error, ClientError):
        return error.code, str(error)
    if isinstance(error, ParseError):
        return "parse_error", str(error)
    if isinstance(error, CsvExportError):
        return "csv_export_error", str(error)
    return "internal_error", str(error) or error.__class__.__name__


def run_collection(
    settings: Settings,
    client: ClientLike,
    storage: StorageLike,
    exporter: Exporter,
    uuid_factory: Callable[[], str],
    clock: Callable[[], datetime],
) -> RunSummary:
    run_id = str(uuid_factory())
    results: list[MarketResult] = []

    for market in settings.markets:
        started_at = _utc_iso(clock)
        try:
            payload = client.fetch_book(market)
            rows = parse_book(payload, market, run_id, started_at)
            finished_at = _utc_iso(clock)
            if not rows:
                storage.record_empty(run_id, market, started_at, finished_at)
                results.append(
                    MarketResult(
                        market=market,
                        status="empty",
                        row_count=0,
                        message="Bitfinex returned an empty book",
                    )
                )
                continue

            csv_path = exporter(rows, settings.csv_directory)
            storage.record_success(
                rows,
                started_at=started_at,
                finished_at=finished_at,
            )
            results.append(
                MarketResult(
                    market=market,
                    status="success",
                    row_count=len(rows),
                    message=f"Fetched and stored {len(rows)} rows",
                    csv_path=csv_path,
                )
            )
        except StorageError:
            raise
        except Exception as error:
            finished_at = _utc_iso(clock)
            error_type, message = _error_details(error)
            storage.record_failure(
                run_id,
                market,
                started_at,
                finished_at,
                error_type,
                message,
            )
            results.append(
                MarketResult(
                    market=market,
                    status="failed",
                    row_count=0,
                    message=message,
                )
            )

    return RunSummary(run_id=run_id, results=tuple(results))

