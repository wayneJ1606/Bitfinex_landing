from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from bitfinex_lending.client import ClientError
from bitfinex_lending.config import Settings
from bitfinex_lending.local_stable_collector import _exclusive_lock, run_stable_collection
from bitfinex_lending.market_collector import FUNDING_MARKETS
from bitfinex_lending.models import FundingBookRow
from bitfinex_lending.collector_run_history import load_collector_runs


class FlakyClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_book(self, market: str) -> object:
        self.calls += 1
        if self.calls == 1:
            raise ClientError("network_error", "temporary failure")
        return [[0.0002, 2, 1, 10.0]]


class RecordingClient:
    def __init__(self) -> None:
        self.markets: list[str] = []

    def fetch_book(self, market: str) -> object:
        self.markets.append(market)
        return [[0.0002, 2, 1, 10.0]]


class Storage:
    def __init__(self) -> None:
        self.successes: list[tuple[FundingBookRow, ...]] = []
        self.failures: list[tuple[object, ...]] = []

    def initialize(self) -> None:
        pass

    def record_success(self, rows, *, started_at, finished_at) -> None:
        self.successes.append(tuple(rows))

    def record_empty(self, run_id, market, started_at, finished_at) -> None:
        pass

    def record_failure(self, *values) -> None:
        self.failures.append(values)


class PublicMarketClient:
    def fetch_ticker(self, market: str):
        if market == "fUSD":
            raise RuntimeError("ticker timed out\nretry later")
        if market.startswith("t"):
            return [100.0, 1.0, 101.0, 2.0, 0.1, 0.01, 100.5, 50.0, 105.0, 95.0, 0]
        return [0.001, 0.0009, 2, 100.0, 0.0011, 3, 80.0, 0.01, 0.02, 1000.0, 20.0, 0.002, 0.0008, 0, 0, 500.0, 0]

    def fetch_funding_stats(self, market: str):
        return [[1700000000000, 0, 0, 0.001, 3.0, 0, 0, 1000.0, 700.0, 0, 0, 12.0]]

    def fetch_funding_candles(self, market: str):
        return [[1700000000000, 0.001, 0.0012, 0.0013, 0.0009, 100.0]]


class FailingPublicMarketClient:
    def fetch_ticker(self, market: str):
        raise RuntimeError("public endpoint unavailable")

    def fetch_funding_stats(self, market: str):
        raise RuntimeError("public endpoint unavailable")

    def fetch_funding_candles(self, market: str):
        raise RuntimeError("public endpoint unavailable")


def test_stable_collection_retries_transient_client_failure(tmp_path: Path) -> None:
    client = FlakyClient()
    storage = Storage()
    summary = run_stable_collection(
        Settings(markets=("fUSD",), csv_directory=tmp_path / "raw"),
        client,
        storage,
        lambda rows, directory: directory / "fUSD.csv",
        uuid_factory=lambda: "run-1",
        clock=lambda: datetime(2026, 8, 16, tzinfo=timezone.utc),
        sleeper=lambda seconds: None,
        lock_path=tmp_path / "collector.lock",
        max_attempts=2,
    )
    assert summary.exit_code == 0
    assert client.calls == 2
    assert len(storage.successes) == 1
    assert storage.failures == []


def test_default_collection_requests_fust_once_and_returns_its_result(tmp_path: Path) -> None:
    client = RecordingClient()
    summary = run_stable_collection(
        Settings(
            database_path=tmp_path / "collector.sqlite3",
            csv_directory=tmp_path / "raw",
        ),
        client,
        Storage(),
        lambda rows, directory: directory / f"{rows[0].market}.csv",
        uuid_factory=lambda: "run-fust",
        clock=lambda: datetime(2026, 8, 22, tzinfo=timezone.utc),
        sleeper=lambda seconds: None,
        lock_path=tmp_path / "collector.lock",
        log_path=tmp_path / "collector.log",
    )

    assert summary is not None
    assert client.markets.count("fUST") == 1
    assert next(result for result in summary.results if result.market == "fUST").status == "success"


def test_stable_collection_skips_when_lock_is_held(tmp_path: Path) -> None:
    lock_path = tmp_path / "collector.lock"
    with _exclusive_lock(lock_path) as acquired:
        assert acquired
        result = run_stable_collection(
            Settings(markets=("fUSD",)),
            FlakyClient(),
            Storage(),
            lambda rows, directory: directory / "fUSD.csv",
            uuid_factory=lambda: "run-1",
            clock=lambda: datetime(2026, 8, 16, tzinfo=timezone.utc),
            sleeper=lambda seconds: None,
            lock_path=lock_path,
            max_attempts=1,
        )
    assert result is None


def test_exclusive_lock_blocks_same_process_overlap(tmp_path: Path) -> None:
    lock_path = tmp_path / "collector.lock"

    with _exclusive_lock(lock_path) as acquired:
        assert acquired
        with _exclusive_lock(lock_path) as concurrent:
            assert not concurrent


def test_exclusive_lock_blocks_other_process_and_recovers_after_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "collector.lock"
    child_code = (
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "from bitfinex_lending.local_stable_collector import _exclusive_lock\n"
        "with _exclusive_lock(Path(sys.argv[1])) as acquired:\n"
        "    print('acquired' if acquired else 'blocked', flush=True)\n"
        "    sys.stdin.read()\n"
        "    os._exit(0)\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", child_code, str(lock_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "acquired"
        with _exclusive_lock(lock_path) as concurrent:
            assert not concurrent
    finally:
        assert process.stdin is not None
        process.stdin.close()
        process.wait(timeout=10)

    with _exclusive_lock(lock_path) as recovered:
        assert recovered


def test_stable_collection_records_exact_public_run_history(tmp_path: Path) -> None:
    history_root = tmp_path / "metadata" / "collector_runs"
    summary = run_stable_collection(
        Settings(markets=("fUSD",), csv_directory=tmp_path / "raw"),
        FlakyClient(),
        Storage(),
        lambda rows, directory: directory / "fUSD.csv",
        uuid_factory=lambda: "public-run-1",
        clock=lambda: datetime(2026, 8, 19, tzinfo=timezone.utc),
        sleeper=lambda seconds: None,
        lock_path=tmp_path / "collector.lock",
        max_attempts=2,
        run_history_root=history_root,
    )

    record = load_collector_runs(history_root)[0]
    assert record.run_id == summary.run_id
    assert record.collector == "public"
    assert record.status == "success"
    assert record.row_counts == {"funding_book:fUSD": 1}
    assert (record.successful_units, record.failed_units) == (1, 0)


def test_market_dataset_failure_makes_public_run_nonzero_and_records_diagnostic(
    tmp_path: Path,
) -> None:
    history_root = tmp_path / "metadata" / "collector_runs"
    summary = run_stable_collection(
        Settings(markets=("fUSD",), csv_directory=tmp_path / "raw", market_directory=tmp_path / "market"),
        FlakyClient(),
        Storage(),
        lambda rows, directory: directory / "fUSD.csv",
        uuid_factory=lambda: "public-run-with-market-failure",
        clock=lambda: datetime(2026, 8, 19, tzinfo=timezone.utc),
        sleeper=lambda seconds: None,
        lock_path=tmp_path / "collector.lock",
        max_attempts=2,
        market_client=PublicMarketClient(),
        run_history_root=history_root,
    )

    record = load_collector_runs(history_root)[0]
    assert summary.exit_code == 1
    assert record.status == "partial"
    assert record.failed_units == 1
    assert record.successful_units == 1 + (len(FUNDING_MARKETS) * 3 + 2 - 1)
    assert record.failures["ticker:fUSD"] == (
        "dataset=ticker:fUSD error_type=RuntimeError message=ticker timed out retry later"
    )


def test_run_history_marks_total_public_collection_failure(tmp_path: Path) -> None:
    history_root = tmp_path / "metadata" / "collector_runs"
    summary = run_stable_collection(
        Settings(markets=("fUSD",), csv_directory=tmp_path / "raw", market_directory=tmp_path / "market"),
        FlakyClient(),
        Storage(),
        lambda rows, directory: directory / "fUSD.csv",
        uuid_factory=lambda: "public-run-total-failure",
        clock=lambda: datetime(2026, 8, 19, tzinfo=timezone.utc),
        sleeper=lambda seconds: None,
        lock_path=tmp_path / "collector.lock",
        max_attempts=1,
        market_client=FailingPublicMarketClient(),
        run_history_root=history_root,
    )

    record = load_collector_runs(history_root)[0]
    assert summary.exit_code == 1
    assert record.status == "failed"
    assert record.successful_units == 0
    assert record.failed_units == 1 + len(FUNDING_MARKETS) * 3 + 2
