from __future__ import annotations

from typing import Any, Protocol

import requests


class ResponseLike(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class SessionLike(Protocol):
    def get(
        self, url: str, *, params: dict[str, Any], timeout: float
    ) -> ResponseLike: ...


class ClientError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class BitfinexClient:
    def __init__(
        self,
        session: SessionLike,
        *,
        base_url: str = "https://api-pub.bitfinex.com/v2",
        precision: str = "P0",
        length: int = 25,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._precision = precision
        self._length = length
        self._timeout = timeout

    def fetch_book(self, market: str) -> object:
        return self._get_json(f"/book/{market}/{self._precision}", {"len": self._length})

    def fetch_ticker(self, market: str) -> object:
        return self._get_json(f"/ticker/{market}", {})

    def fetch_funding_stats(self, market: str) -> object:
        return self._get_json(f"/funding/stats/{market}/hist", {"limit": 1})

    def fetch_funding_candles(self, market: str) -> object:
        key = f"trade:1h:{market}:a30:p2:p30"
        return self._get_json(f"/candles/{key}/hist", {"limit": 1})

    def _get_json(self, path: str, params: dict[str, Any]) -> object:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
            )
        except requests.RequestException as error:
            raise ClientError(
                "network_error", f"Bitfinex request failed: {error}"
            ) from error

        try:
            response.raise_for_status()
        except requests.RequestException as error:
            raise ClientError(
                "http_error", f"Bitfinex returned an HTTP error: {error}"
            ) from error

        try:
            return response.json()
        except (requests.JSONDecodeError, ValueError) as error:
            raise ClientError(
                "invalid_json", "Bitfinex response was not valid JSON"
            ) from error
