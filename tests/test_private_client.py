import base64
import hashlib
import hmac
import json

import pytest
import requests

from bitfinex_lending.private_client import (
    PrivatePermissionError,
    ReadOnlyBitfinexClient,
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, *, headers, json, timeout, allow_redirects=None):
        self.calls.append((url, headers, json, timeout, allow_redirects))
        return Response(self.payload)


def make_client(session, nonces=(1000, 1001)):
    values = iter(nonces)
    return ReadOnlyBitfinexClient(
        "key",
        "secret",
        session,
        nonce_factory=lambda: str(next(values)),
    )


def test_private_request_has_bitfinex_signature_headers_and_increasing_nonces():
    session = Session([{"read": ["funding", "history"], "write": []}])
    client = make_client(session)

    client.check_permissions()
    client.fetch_private("/v2/auth/r/funding/offers", {})

    first_headers = session.calls[0][1]
    second_headers = session.calls[1][1]
    assert first_headers["bfx-apikey"] == "key"
    assert int(second_headers["bfx-nonce"]) > int(first_headers["bfx-nonce"])
    body = session.calls[0][2]
    expected_signature = hmac.new(
        b"secret",
        f"/api/v2/auth/r/permissions1000{json.dumps(body, separators=(',', ':'))}".encode(),
        hashlib.sha384,
    ).hexdigest()
    assert first_headers["bfx-signature"] == expected_signature
    assert body == {}
    assert "bfx-payload" not in first_headers


def test_permissions_reject_any_write_scope():
    session = Session([{"read": ["funding", "history"], "write": ["orders"]}])
    client = make_client(session)

    with pytest.raises(PrivatePermissionError, match="write"):
        client.check_permissions()


def test_permissions_reject_missing_required_read_scope():
    session = Session([{"read": ["funding"], "write": []}])
    client = make_client(session)

    with pytest.raises(PrivatePermissionError, match="history"):
        client.check_permissions()


def test_permissions_reject_an_additional_enabled_read_scope():
    session = Session([{"read": ["funding", "history", "wallets"], "write": []}])
    client = make_client(session)

    with pytest.raises(PrivatePermissionError, match="not allowlisted"):
        client.check_permissions()


def test_permissions_accept_official_scope_read_write_array_format():
    session = Session([["funding", 1, 0], ["history", 1, 0]])
    client = make_client(session)

    assert client.check_permissions() == ({"read": ("funding", "history"), "write": ()},)


def test_forbidden_authenticated_path_is_rejected_before_request():
    session = Session({})
    client = make_client(session)

    with pytest.raises(PrivatePermissionError, match="not allowlisted"):
        client.fetch_private("/v2/auth/w/order/submit", {})
    assert session.calls == []


def test_authenticated_client_rejects_any_base_url_except_bitfinex_api():
    with pytest.raises(ValueError, match="https://api.bitfinex.com"):
        ReadOnlyBitfinexClient("key", "secret", Session({}), base_url="https://proxy.example")


def test_funding_offer_history_path_is_allowlisted():
    session = Session([])
    client = make_client(session)

    assert client.fetch_private("/v2/auth/r/funding/offers/hist", {}) == []
    assert session.calls[0][0].endswith("/v2/auth/r/funding/offers/hist")


def test_authenticated_requests_disable_redirects():
    session = Session([])
    client = make_client(session)

    client.fetch_private("/v2/auth/r/funding/offers", {})

    assert session.calls[0][4] is False


def test_network_failures_are_marked_retryable_without_exposing_request_details():
    class NetworkFailureSession:
        def post(self, *args, **kwargs):
            raise requests.ConnectionError("connection interrupted")

    client = make_client(NetworkFailureSession())

    with pytest.raises(Exception) as error:
        client.fetch_private("/v2/auth/r/funding/offers", {})

    assert error.value.retryable is True
    assert "connection interrupted" not in str(error.value)


def test_unauthorized_authenticated_requests_are_not_retryable():
    class UnauthorizedResponse:
        def raise_for_status(self):
            response = requests.Response()
            response.status_code = 401
            raise requests.HTTPError("api-secret-abc", response=response)

        def json(self):
            return []

    class UnauthorizedSession:
        def post(self, *args, **kwargs):
            return UnauthorizedResponse()

    with pytest.raises(Exception) as error:
        make_client(UnauthorizedSession()).fetch_private("/v2/auth/r/funding/offers", {})

    assert error.value.retryable is False
    assert "api-secret-abc" not in str(error.value)


@pytest.mark.parametrize("status_code", [429, 503])
def test_rate_limit_and_server_errors_are_retryable(status_code):
    class FailedResponse:
        def raise_for_status(self):
            response = requests.Response()
            response.status_code = status_code
            raise requests.HTTPError("temporary", response=response)

        def json(self):
            return []

    class FailedSession:
        def post(self, *args, **kwargs):
            return FailedResponse()

    with pytest.raises(Exception) as error:
        make_client(FailedSession()).fetch_private("/v2/auth/r/funding/offers", {})

    assert error.value.retryable is True


def test_invalid_json_is_retryable_without_exposing_response_text():
    class InvalidJsonResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("api-secret-abc")

    class InvalidJsonSession:
        def post(self, *args, **kwargs):
            return InvalidJsonResponse()

    with pytest.raises(Exception) as error:
        make_client(InvalidJsonSession()).fetch_private("/v2/auth/r/funding/offers", {})

    assert error.value.retryable is True
    assert "api-secret-abc" not in str(error.value)


def test_permission_response_never_exposes_secret_in_error():
    session = Session([{"read": ["funding"], "write": ["orders"]}])
    client = ReadOnlyBitfinexClient(
        "key",
        "super-secret-value",
        session,
        nonce_factory=lambda: "1000",
    )

    with pytest.raises(PrivatePermissionError) as error:
        client.check_permissions()
    assert "super-secret-value" not in str(error.value)
