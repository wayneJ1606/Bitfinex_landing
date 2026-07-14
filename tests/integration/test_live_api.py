from __future__ import annotations

from datetime import datetime, timezone

import pytest
import requests

from bitfinex_lending.client import BitfinexClient
from bitfinex_lending.parser import parse_book


@pytest.mark.integration
def test_live_fusd_book_matches_expected_schema() -> None:
    fetched_at = datetime.now(timezone.utc).isoformat()
    client = BitfinexClient(requests.Session())

    rows = parse_book(
        client.fetch_book("fUSD"),
        market="fUSD",
        run_id="live-smoke-test",
        fetched_at=fetched_at,
    )

    assert rows
    assert all(row.market == "fUSD" for row in rows)
    assert all(row.side in {"offer", "demand"} for row in rows)
    assert all(row.fetched_at == fetched_at for row in rows)

