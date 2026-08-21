from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Callable, Protocol

import requests


class ResponseLike(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class SessionLike(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
        allow_redirects: bool,
    ) -> ResponseLike: ...


class PrivateClientError(RuntimeError):
    """Base error for authenticated, read-only requests."""

    retryable = False


class PrivateTransientError(PrivateClientError):
    """An authenticated request failure that can be retried safely."""

    retryable = True


class PrivatePermissionError(PrivateClientError):
    """Raised when the API key is not safe for the collector."""


class ReadOnlyBitfinexClient:
    """Minimal Bitfinex authenticated client with an endpoint allowlist."""

    ALLOWED_PATHS = frozenset(
        {
            "/v2/auth/r/permissions",
            "/v2/auth/r/funding/offers",
            "/v2/auth/r/funding/offers/hist",
            "/v2/auth/r/funding/trades/hist",
            "/v2/auth/r/funding/loans/hist",
            "/v2/auth/r/funding/credits",
        }
    )
    REQUIRED_READ = frozenset({"funding", "history"})

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        session: SessionLike,
        *,
        base_url: str = "https://api.bitfinex.com",
        timeout: float = 10.0,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret are required")
        if base_url.rstrip("/") != "https://api.bitfinex.com":
            raise ValueError("authenticated requests require https://api.bitfinex.com")
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._nonce_factory = nonce_factory or (lambda: str(time.time_ns() // 1_000_000))
        self._last_nonce = 0

    def check_permissions(self) -> tuple[dict[str, Any], ...]:
        payload = self.fetch_private("/v2/auth/r/permissions", {})
        scopes = _permission_scopes(payload)
        read_scopes = set(scopes.get("read", ()))
        write_scopes = set(scopes.get("write", ()))
        if write_scopes:
            raise PrivatePermissionError(
                "read-only API key required; write permissions detected"
            )
        extra = read_scopes - self.REQUIRED_READ
        if extra:
            raise PrivatePermissionError(
                "enabled read permission is not allowlisted for this collector"
            )
        missing = self.REQUIRED_READ - read_scopes
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise PrivatePermissionError(f"missing required read permission: {missing_text}")
        return (scopes,)

    def fetch_private(self, path: str, payload: dict[str, object]) -> object:
        if path not in self.ALLOWED_PATHS:
            raise PrivatePermissionError(f"authenticated path is not allowlisted: {path}")
        nonce = self._next_nonce()
        body = dict(payload)
        signature_message = f"/api{path}{nonce}{json.dumps(body, separators=(',', ':'), ensure_ascii=False)}"
        signature = hmac.new(
            self._api_secret,
            signature_message.encode("utf-8"),
            hashlib.sha384,
        ).hexdigest()
        headers = {
            "bfx-apikey": self._api_key,
            "bfx-nonce": nonce,
            "bfx-signature": signature,
            "content-type": "application/json",
            "accept": "application/json",
        }
        try:
            response = self._session.post(
                f"{self._base_url}{path}",
                headers=headers,
                json=body,
                timeout=self._timeout,
                allow_redirects=False,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
                raise PrivateTransientError("Bitfinex authenticated service is temporarily unavailable") from error
            raise PrivateClientError("Bitfinex authenticated request was rejected") from error
        except requests.RequestException as error:
            raise PrivateTransientError("Bitfinex authenticated network request failed") from error
        except (ValueError, TypeError) as error:
            raise PrivateTransientError("Bitfinex returned invalid authenticated JSON") from error

    def _next_nonce(self) -> str:
        candidate = int(self._nonce_factory())
        if candidate <= self._last_nonce:
            candidate = self._last_nonce + 1
        self._last_nonce = candidate
        return str(candidate)


def _permission_scopes(payload: object) -> dict[str, tuple[str, ...]]:
    """Normalize Bitfinex permission response variants without exposing secrets."""
    if isinstance(payload, list) and all(
        isinstance(item, (list, tuple)) and len(item) >= 3 for item in payload
    ):
        read = [str(item[0]) for item in payload if bool(item[1])]
        write = [str(item[0]) for item in payload if bool(item[2])]
        return {"read": tuple(read), "write": tuple(write)}
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        first = payload[0]
        read = first.get("read", [])
        write = first.get("write", [])
        if isinstance(read, list) and isinstance(write, list):
            return {"read": tuple(str(item) for item in read), "write": tuple(str(item) for item in write)}
    if isinstance(payload, dict):
        read: list[str] = []
        write: list[str] = []
        for scope, value in payload.items():
            if not isinstance(value, dict):
                continue
            if value.get("read"):
                read.append(str(scope))
            if value.get("write"):
                write.append(str(scope))
        return {"read": tuple(read), "write": tuple(write)}
    raise PrivatePermissionError("unrecognized permissions response")
