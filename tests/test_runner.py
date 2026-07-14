from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from bitfinex_lending.client import ClientError
from bitfinex_lending.config import Settings
from bitfinex_lending.models import FundingBookRow
from bitfinex_lending.runner import run_collection


class FakeClient:
    def __init__(self, outcomes: dict[str, object]) -> None:
        self.outcomes = outcomes
        self.markets: list[str] = []

    def fetch_book(self, market: str) -> object:
        self.markets.append(market)
        outcome = self.outcomes[market]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeStorage:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def record_success(
        self,
        rows: Sequence[FundingBookRow],
        *,
        started_at: str,
        finished_at: str,
    ) -> None:
        self.events.append(("success", rows[0].market, len(rows), started_at, finished_at))

    def record_empty(
        self, run_id: str, market: str, started_at: str, finished_at: str
    ) -> None:
        self.events.append(("empty", market, run_id, started_at, finished_at))

    def record_failure(
        self,
        run_id: str,
        market: str,
        started_at: str,
        finished_at: str,
        error_type: str,
        message: str,
    ) -> None:
        self.events.append(("failed", market, error_type, message))


class FakeExporter:
    def __init__(self) -> None:
        self.markets: list[str] = []

    def __call__(
        self, rows: Sequence[FundingBookRow], output_directory: Path
    ) -> Path:
        self.markets.append(rows[0].market)
        return output_directory / f"{rows[0].market}.csv"


class TickingClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def test_run_collection_continues_after_failure_and_summarizes_results() -> None:
    client = FakeClient(
        {
            "fUSD": [[0.0002, 2, 1, 10.0]],
            "fBTC": ClientError("network_error", "request timed out"),
            "fETH": [[0.0003, 7, 2, -5.0]],
        }
    )
    storage = FakeStorage()
    exporter = FakeExporter()

    summary = run_collection(
        Settings(csv_directory=Path("exports")),
        client,
        storage,
        exporter,
        uuid_factory=lambda: "run-1",
        clock=TickingClock(),
    )

    assert client.markets == ["fUSD", "fBTC", "fETH"]
    assert exporter.markets == ["fUSD", "fETH"]
    assert summary.run_id == "run-1"
    assert summary.exit_code == 1
    assert [result.status for result in summary.results] == [
        "success",
        "failed",
        "success",
    ]
    assert storage.events[1][:4] == (
        "failed",
        "fBTC",
        "network_error",
        "request timed out",
    )


def test_run_collection_records_empty_as_successful_warning() -> None:
    client = FakeClient({"fUSD": [], "fBTC": [], "fETH": []})
    storage = FakeStorage()
    exporter = FakeExporter()

    summary = run_collection(
        Settings(),
        client,
        storage,
        exporter,
        uuid_factory=lambda: "run-empty",
        clock=TickingClock(),
    )

    assert summary.exit_code == 0
    assert summary.warning_count == 3
    assert [event[0] for event in storage.events] == ["empty", "empty", "empty"]
    assert exporter.markets == []


def test_run_collection_uses_one_run_id_and_timezone_aware_utc_times() -> None:
    client = FakeClient(
        {market: [[0.0002, 2, 1, 10.0]] for market in Settings().markets}
    )
    storage = FakeStorage()

    summary = run_collection(
        Settings(),
        client,
        storage,
        FakeExporter(),
        uuid_factory=lambda: "shared-run",
        clock=TickingClock(),
    )

    assert summary.exit_code == 0
    for event in storage.events:
        assert event[3].endswith("+00:00")
        assert event[4].endswith("+00:00")

