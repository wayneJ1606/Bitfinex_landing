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
        url = f"{self._base_url}/book/{market}/{self._precision}"
        try:
            response = self._session.get(
                url,
                params={"len": self._length},
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

