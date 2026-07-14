from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from bitfinex_lending.client import BitfinexClient, ClientError


@dataclass
class FakeResponse:
    payload: object = None
    http_error: Exception | None = None
    json_error: Exception | None = None

    def raise_for_status(self) -> None:
        if self.http_error:
            raise self.http_error

    def json(self) -> object:
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(
        self,
        response: FakeResponse | None = None,
        request_error: Exception | None = None,
    ) -> None:
        self.response = response or FakeResponse()
        self.request_error = request_error
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> FakeResponse:
        self.calls.append((url, params, timeout))
        if self.request_error:
            raise self.request_error
        return self.response


def test_fetch_book_uses_expected_endpoint_and_options() -> None:
    session = FakeSession(FakeResponse(payload=[[0.0002, 2, 1, 10.0]]))
    client = BitfinexClient(session=session)

    payload = client.fetch_book("fUSD")

    assert payload == [[0.0002, 2, 1, 10.0]]
    assert session.calls == [
        (
            "https://api-pub.bitfinex.com/v2/book/fUSD/P0",
            {"len": 25},
            10.0,
        )
    ]


def test_fetch_book_converts_network_failure() -> None:
    client = BitfinexClient(
        session=FakeSession(request_error=requests.Timeout("too slow"))
    )

    with pytest.raises(ClientError) as caught:
        client.fetch_book("fUSD")

    assert caught.value.code == "network_error"
    assert str(caught.value) == "Bitfinex request failed: too slow"


def test_fetch_book_converts_http_failure() -> None:
    response = FakeResponse(http_error=requests.HTTPError("503 unavailable"))
    client = BitfinexClient(session=FakeSession(response))

    with pytest.raises(ClientError) as caught:
        client.fetch_book("fUSD")

    assert caught.value.code == "http_error"
    assert str(caught.value) == "Bitfinex returned an HTTP error: 503 unavailable"


def test_fetch_book_converts_invalid_json() -> None:
    response = FakeResponse(json_error=requests.JSONDecodeError("invalid", "x", 0))
    client = BitfinexClient(session=FakeSession(response))

    with pytest.raises(ClientError) as caught:
        client.fetch_book("fUSD")

    assert caught.value.code == "invalid_json"
    assert str(caught.value) == "Bitfinex response was not valid JSON"

