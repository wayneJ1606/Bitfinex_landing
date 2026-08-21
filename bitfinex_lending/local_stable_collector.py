from __future__ import annotations

import logging
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import BinaryIO, Callable, Iterator, Protocol, Sequence
import msvcrt
import threading

from .client import ClientError
from .config import Settings
from .client import BitfinexClient
from .daily_csv import append_daily_snapshot
from .storage import Storage
from .market_collector import FUNDING_MARKETS, MarketClient, collect_market_data
from .models import FundingBookRow, MarketResult, RunSummary
from .runner import run_collection
from .collector_run_history import CollectorRunRecord, append_collector_run


class ClientLike(Protocol):
    def fetch_book(self, market: str) -> object: ...


Exporter = Callable[[Sequence[FundingBookRow], Path], Path]


RETRYABLE_CODES = frozenset({"network_error", "http_error", "invalid_json"})
_held_lock_paths: set[Path] = set()
_held_lock_paths_guard = threading.Lock()


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


class _RetryingClient:
    def __init__(self, client: ClientLike, attempts: int, delay: float, sleeper: Callable[[float], None]) -> None:
        self.client = client
        self.attempts = attempts
        self.delay = delay
        self.sleeper = sleeper

    def fetch_book(self, market: str) -> object:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                return self.client.fetch_book(market)
            except ClientError as error:
                last_error = error
                if error.code not in RETRYABLE_CODES or attempt == self.attempts - 1:
                    raise
                self.sleeper(self.delay * (2**attempt))
        raise RuntimeError(f"collection failed for {market}: {last_error}")


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[bool]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path = path.resolve()
    with _held_lock_paths_guard:
        if normalized_path in _held_lock_paths:
            held_in_process = True
        else:
            held_in_process = False
            _held_lock_paths.add(normalized_path)
    if held_in_process:
        yield False
        return
    try:
        with path.open("a+b") as handle:
            if not _try_lock(handle):
                yield False
                return
            try:
                yield True
            finally:
                _unlock(handle)
    finally:
        with _held_lock_paths_guard:
            _held_lock_paths.discard(normalized_path)


def _try_lock(handle: BinaryIO) -> bool:
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return False
    return True


def _unlock(handle: BinaryIO) -> None:
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def run_stable_collection(
    settings: Settings,
    client: ClientLike,
    storage,
    exporter: Exporter,
    *,
    uuid_factory: Callable[[], str],
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None] = sleep,
    lock_path: Path = Path("data/local-collector.lock"),
    log_path: Path = Path("data/local-collector.log"),
    max_attempts: int = 3,
    retry_delay_seconds: float = 2.0,
    market_client: MarketClient | None = None,
    run_history_root: Path | None = None,
) -> RunSummary | None:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds must not be negative")
    logger = logging.getLogger("bitfinex_lending.local_stable_collector")
    logger.setLevel(logging.INFO)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(Path(lock_path)) as acquired:
        if not acquired:
            logger.info("collection_skipped=lock_held")
            return None
        history_started = _utc_text(clock())
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        settings.csv_directory.mkdir(parents=True, exist_ok=True)
        storage.initialize()
        retrying_client = _RetryingClient(client, max_attempts, retry_delay_seconds, sleeper)
        summary = run_collection(
            settings,
            retrying_client,
            storage,
            exporter,
            uuid_factory=uuid_factory,
            clock=clock,
        )
        funding_results = summary.results
        if market_client is not None:
            market_result = collect_market_data(
                market_client,
                settings.market_directory,
                collected_at=clock().isoformat(),
            )
        else:
            market_result = None
        if market_result is not None and market_result.failed:
            summary = RunSummary(
                run_id=summary.run_id,
                results=summary.results
                + tuple(
                    MarketResult(
                        market=diagnostic.dataset,
                        status="failed",
                        row_count=0,
                        message=diagnostic.rendered,
                    )
                    for diagnostic in market_result.diagnostics
                ),
            )
        history_finished = _utc_text(clock())
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"run_id={summary.run_id} exit_code={summary.exit_code} "
                f"success={sum(item.status == 'success' for item in funding_results)} "
                f"empty={sum(item.status == 'empty' for item in funding_results)} "
                f"failed={sum(item.status == 'failed' for item in funding_results)}\n"
            )
            if market_result is not None:
                stream.write(
                    f"market_written={market_result.written} "
                    f"market_failed={','.join(market_result.failed) or 'none'}\n"
                )
        if run_history_root is not None:
            row_counts = {
                f"funding_book:{item.market}": item.row_count for item in funding_results
            }
            failures = {
                f"funding_book:{item.market}": item.message
                for item in funding_results
                if item.status == "failed"
            }
            successful_units = sum(item.status != "failed" for item in funding_results)
            failed_units = sum(item.status == "failed" for item in funding_results)
            if market_result is not None:
                market_units = len(FUNDING_MARKETS) * 3 + 2
                successful_units += market_units - len(market_result.failed)
                failed_units += len(market_result.failed)
                row_counts["market_rows_written"] = market_result.written
                failures.update(
                    {
                        diagnostic.dataset: diagnostic.rendered
                        for diagnostic in market_result.diagnostics
                    }
                )
            status = "success" if failed_units == 0 else ("partial" if successful_units else "failed")
            append_collector_run(
                run_history_root,
                CollectorRunRecord(
                    run_id=summary.run_id,
                    collector="public",
                    started_at=history_started,
                    finished_at=history_finished,
                    status=status,
                    expected_interval_minutes=60,
                    successful_units=successful_units,
                    failed_units=failed_units,
                    row_counts=row_counts,
                    failures=failures,
                ),
            )
        return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one stable local Bitfinex collection")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--lock-path", type=Path, default=Path("data/local-collector.lock"))
    parser.add_argument("--log-path", type=Path, default=Path("data/local-collector.log"))
    args = parser.parse_args(argv)
    import requests
    from datetime import datetime, timezone
    from uuid import uuid4

    settings = Settings()
    client = BitfinexClient(requests.Session(), base_url=settings.api_base_url, precision=settings.precision, length=settings.book_length, timeout=settings.timeout)
    summary = run_stable_collection(
        settings,
        client,
        Storage(settings.database_path),
        append_daily_snapshot,
        uuid_factory=lambda: str(uuid4()),
        clock=lambda: datetime.now(timezone.utc),
        lock_path=args.lock_path,
        log_path=args.log_path,
        max_attempts=args.max_attempts,
        retry_delay_seconds=args.retry_delay,
        market_client=client,
        run_history_root=settings.metadata_directory / "collector_runs",
    )
    if summary is None:
        print("collection_skipped=lock_held")
        return 2
    for item in summary.results:
        print(f"{item.market} {item.status} rows={item.row_count} message={item.message}")
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
