from datetime import datetime, timezone
import threading

import pytest

from bitfinex_lending.account_storage import AccountStorageError
from bitfinex_lending import private_account_collector as module
from bitfinex_lending.private_account_collector import run_private_collection
from bitfinex_lending.private_client import PrivateClientError, PrivatePermissionError
from bitfinex_lending.collector_run_history import load_collector_runs


class FakeStorage:
    def __init__(self, root):
        self.root = root
        self.snapshots = []
        self.statuses = []

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def append_snapshot(self, dataset, collected_at, rows):
        self.snapshots.append((dataset, collected_at, rows))
        return len(rows)

    def write_status(self, status):
        self.statuses.append(status)


class FakeClient:
    def __init__(self, responses=None, permission_error=None):
        self.responses = responses or {}
        self.permission_error = permission_error
        self.calls = []

    def check_permissions(self):
        self.calls.append("permissions")
        if self.permission_error:
            raise self.permission_error
        return ({"read": ["funding", "history"], "write": []},)

    def fetch_private(self, path, payload):
        self.calls.append(path)
        response = self.responses.get(path, [])
        if isinstance(response, Exception):
            raise response
        return response


def test_permission_check_precedes_all_funding_requests(tmp_path):
    client = FakeClient(permission_error=PrivatePermissionError("write permissions detected"))
    storage = FakeStorage(tmp_path / "account")

    with pytest.raises(PrivatePermissionError):
        run_private_collection(client, storage, collected_at=datetime.now(timezone.utc))
    assert client.calls == ["permissions"]
    assert storage.snapshots == []
    assert storage.statuses[-1]["status"] == "permission_failed"


def test_permission_request_failure_writes_safe_failed_status_and_history(tmp_path):
    storage = FakeStorage(tmp_path / "account")
    history_root = tmp_path / "metadata" / "collector_runs"

    with pytest.raises(PrivateClientError):
        run_private_collection(
            FakeClient(permission_error=PrivateClientError("api-secret-abc")),
            storage,
            collected_at=datetime.now(timezone.utc),
            run_history_root=history_root,
            run_id_factory=lambda: "permission-request-failure",
        )

    assert storage.statuses[-1]["status"] == "permission_failed"
    assert "api-secret-abc" not in str(storage.statuses[-1])
    record = load_collector_runs(history_root)[0]
    assert record.status == "failed"
    assert record.permission_checked is False
    assert "api-secret-abc" not in str(record.failures)


def test_collects_all_four_allowlisted_datasets(tmp_path):
    responses = {
        "/v2/auth/r/funding/offers": [{"id": 1}],
        "/v2/auth/r/funding/offers/hist": [[5, "fUST"]],
        "/v2/auth/r/funding/trades/hist": [[2, "fUSD"]],
        "/v2/auth/r/funding/loans/hist": [[3, "fUSD"]],
        "/v2/auth/r/funding/credits": [[4, "fUSD"]],
    }
    client = FakeClient(responses)
    storage = FakeStorage(tmp_path / "account")

    summary = run_private_collection(
        client, storage, collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc)
    )

    assert summary.row_counts == {
        "funding_offers": 1,
        "funding_offers_history": 1,
        "funding_trades": 1,
        "funding_loans": 1,
        "funding_credits": 1,
    }
    assert client.calls[0] == "permissions"
    assert len(storage.snapshots) == 5
    assert storage.statuses[-1]["status"] == "success"


def test_single_endpoint_failure_is_recorded_without_losing_other_data(tmp_path):
    responses = {
        "/v2/auth/r/funding/offers": [{"id": 1}],
        "/v2/auth/r/funding/trades/hist": PrivateClientError("temporary"),
        "/v2/auth/r/funding/loans/hist": [],
        "/v2/auth/r/funding/credits": [],
    }
    client = FakeClient(responses)
    storage = FakeStorage(tmp_path / "account")

    summary = run_private_collection(
        client,
        storage,
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        max_attempts=1,
    )

    assert summary.row_counts["funding_offers"] == 1
    assert "funding_trades" in summary.failures
    assert storage.statuses[-1]["status"] == "partial"


def test_storage_failure_is_recorded_safely_in_status_and_run_history(tmp_path):
    class FailingStorage(FakeStorage):
        def append_snapshot(self, dataset, collected_at, rows):
            if dataset == "funding_offers":
                raise AccountStorageError("storage-sentinel-secret")
            return super().append_snapshot(dataset, collected_at, rows)

    storage = FailingStorage(tmp_path / "account")
    history_root = tmp_path / "metadata" / "collector_runs"
    summary = run_private_collection(
        FakeClient({"/v2/auth/r/funding/offers": [{"id": 1}]}),
        storage,
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        run_history_root=history_root,
        run_id_factory=lambda: "storage-failure",
    )

    assert "funding_offers" in summary.failures
    assert storage.statuses[-1]["status"] == "partial"
    assert "storage-sentinel-secret" not in str(storage.statuses[-1])
    record = load_collector_runs(history_root)[0]
    assert record.status == "partial"
    assert "storage-sentinel-secret" not in str(record.failures)


def test_non_list_dataset_response_is_recorded_as_a_failure(tmp_path):
    client = FakeClient({"/v2/auth/r/funding/offers": {"error": "api-secret-abc"}})
    storage = FakeStorage(tmp_path / "account")

    summary = run_private_collection(
        client,
        storage,
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        max_attempts=1,
    )

    assert "funding_offers" in summary.failures
    assert "funding_offers" not in summary.row_counts
    assert "api-secret-abc" not in str(storage.statuses[-1])


def test_api_error_shaped_dataset_response_is_recorded_as_a_failure(tmp_path):
    client = FakeClient({"/v2/auth/r/funding/offers": ["error", 10020, "api-secret-abc"]})
    storage = FakeStorage(tmp_path / "account")

    summary = run_private_collection(
        client,
        storage,
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        max_attempts=1,
    )

    assert "funding_offers" in summary.failures
    assert "funding_offers" not in summary.row_counts
    assert "api-secret-abc" not in str(storage.statuses[-1])


def test_transient_failure_is_retried_with_bound(tmp_path):
    class RetryClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def fetch_private(self, path, payload):
            self.calls.append(path)
            if path == "/v2/auth/r/funding/offers":
                self.attempts += 1
                if self.attempts < 3:
                    raise OSError("network interrupted")
                return [{"id": 1}]
            return []

    client = RetryClient()
    storage = FakeStorage(tmp_path / "account")
    summary = run_private_collection(
        client,
        storage,
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        max_attempts=3,
        retry_delay=0,
    )

    assert summary.failures == {}
    assert client.attempts == 3


def test_permission_failure_is_not_retried(tmp_path):
    class PermissionFailureClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def fetch_private(self, path, payload):
            if path == "/v2/auth/r/funding/offers":
                self.attempts += 1
                raise PrivatePermissionError("permission denied")
            return []

    client = PermissionFailureClient()
    summary = run_private_collection(
        client,
        FakeStorage(tmp_path / "account"),
        collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        max_attempts=3,
        retry_delay=0,
    )

    assert "funding_offers" in summary.failures
    assert client.attempts == 1


def test_lock_prevents_second_collector(tmp_path):
    client = FakeClient()
    storage = FakeStorage(tmp_path / "account")
    storage.root.mkdir(parents=True)
    lock = module._acquire_lock(storage.root / ".private-collector.lock")

    try:
        with pytest.raises(RuntimeError, match="already running"):
            run_private_collection(client, storage, collected_at=datetime.now(timezone.utc))
    finally:
        module._release_lock(lock)
    assert client.calls == []


def test_stale_collector_lock_from_a_crashed_process_is_recovered(tmp_path):
    client = FakeClient()
    storage = FakeStorage(tmp_path / "account")
    storage.root.mkdir(parents=True)
    (storage.root / ".private-collector.lock").write_text("999999999", encoding="utf-8")

    summary = run_private_collection(
        client, storage, collected_at=datetime(2026, 8, 16, tzinfo=timezone.utc)
    )

    assert summary.failures == {}
    recovered_lock = module._acquire_lock(storage.root / ".private-collector.lock")
    module._release_lock(recovered_lock)


def test_two_stale_lock_recoverers_cannot_both_acquire_the_lock(tmp_path):
    lock_path = tmp_path / ".private-collector.lock"
    lock_path.write_text("999999999", encoding="utf-8")
    first_acquired = threading.Event()
    successes = []
    failures = []
    release_first = threading.Event()

    def acquire_first():
        try:
            lock = module._acquire_lock(lock_path)
            successes.append("first")
            first_acquired.set()
            assert release_first.wait(timeout=2)
            module._release_lock(lock)
        except Exception as error:
            failures.append(error)

    def acquire_second():
        try:
            module._acquire_lock(lock_path)
            successes.append("second")
        except Exception as error:
            failures.append(error)

    first = threading.Thread(target=acquire_first)
    second = threading.Thread(target=acquire_second)
    first.start()
    assert first_acquired.wait(timeout=2)
    second.start()
    second.join(timeout=2)
    release_first.set()
    first.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert successes == ["first"]
    assert len(failures) == 1


def test_private_collection_records_exact_endpoint_and_permission_history(tmp_path):
    responses = {
        "/v2/auth/r/funding/offers": [{"id": 1}],
        "/v2/auth/r/funding/trades/hist": PrivateClientError("temporary"),
    }
    history_root = tmp_path / "metadata" / "collector_runs"

    summary = run_private_collection(
        FakeClient(responses),
        FakeStorage(tmp_path / "account"),
        collected_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        max_attempts=1,
        run_history_root=history_root,
        run_id_factory=lambda: "private-run-1",
        clock=lambda: datetime(2026, 8, 19, tzinfo=timezone.utc),
    )

    record = load_collector_runs(history_root)[0]
    assert record.run_id == "private-run-1"
    assert record.status == "partial"
    assert record.permission_checked is True
    assert record.row_counts == summary.row_counts
    assert record.failures == summary.failures
    assert (record.successful_units, record.failed_units) == (4, 1)
