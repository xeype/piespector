from __future__ import annotations

import json
from unittest.mock import patch
import unittest

from piespector.history import build_history_entry
from piespector.http_client import perform_request, preview_effective_headers
from piespector.state import RequestDefinition, ResponseSummary


class FakeHeaders:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self._headers = headers or {}

    def get_content_charset(self) -> str | None:
        content_type = self._headers.get("Content-Type", "")
        marker = "charset="
        if marker not in content_type:
            return None
        return content_type.split(marker, 1)[1].split(";", 1)[0].strip()

    def items(self) -> list[tuple[str, str]]:
        return list(self._headers.items())


class FakeResponse:
    def __init__(self, body: str, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = FakeHeaders(headers)

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class AuthTests(unittest.TestCase):
    def test_cookie_auth_adds_cookie_header(self) -> None:
        request = RequestDefinition(
            auth_type="cookie",
            auth_cookie_name="session",
            auth_cookie_value="{{TOKEN}}",
        )

        effective_headers, _auto_headers = preview_effective_headers(
            request,
            {"TOKEN": "abc123"},
        )

        self.assertEqual(effective_headers["Cookie"], "session=abc123")

    def test_custom_header_auth_adds_resolved_header(self) -> None:
        request = RequestDefinition(
            auth_type="custom-header",
            auth_custom_header_name="X-Session-Token",
            auth_custom_header_value="{{TOKEN}}",
        )

        effective_headers, _auto_headers = preview_effective_headers(
            request,
            {"TOKEN": "abc123"},
        )

        self.assertEqual(effective_headers["X-Session-Token"], "abc123")

    def test_custom_header_auth_is_redacted_in_history(self) -> None:
        request = RequestDefinition(
            name="Auth Request",
            url="https://example.com",
            auth_type="custom-header",
            auth_custom_header_name="X-Session-Token",
            auth_custom_header_value="secret-token",
        )

        entry = build_history_entry(
            request,
            {},
            ResponseSummary(status_code=200, elapsed_ms=10.0),
            "Auth Request",
        )

        self.assertEqual(entry.auth_type, "custom-header")
        self.assertEqual(entry.auth_name, "X-Session-Token")
        self.assertIn(("X-Session-Token", "<redacted>"), entry.request_headers)

    def test_oauth_preview_shows_inferred_authorization_header(self) -> None:
        request = RequestDefinition(
            auth_type="oauth2-client-credentials",
            auth_oauth_token_url="https://example.com/oauth/token",
            auth_oauth_client_id="client-id",
            auth_oauth_client_secret="client-secret",
            auth_oauth_client_authentication="basic-header",
            auth_oauth_header_prefix="Token",
            auth_oauth_scope="read:all",
        )

        effective_headers, _auto_headers = preview_effective_headers(request, {})

        self.assertEqual(effective_headers["Authorization"], "Token <oauth2-token>")

    def test_bearer_auth_uses_custom_header_prefix(self) -> None:
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_prefix="JWT",
            auth_bearer_token="abc123",
        )

        effective_headers, _auto_headers = preview_effective_headers(request, {})

        self.assertEqual(effective_headers["Authorization"], "JWT abc123")

    def test_oauth_client_credentials_fetches_token_before_api_request(self) -> None:
        request = RequestDefinition(
            method="GET",
            url="https://example.com/api/pies",
            auth_type="oauth2-client-credentials",
            auth_oauth_token_url="https://example.com/oauth/token",
            auth_oauth_client_id="client-id",
            auth_oauth_client_secret="client-secret",
            auth_oauth_client_authentication="basic-header",
            auth_oauth_header_prefix="Token",
            auth_oauth_scope="read:all",
        )
        captured_authorization: list[str | None] = []

        def fake_urlopen(req, timeout=15.0):
            url = req.full_url
            if url == "https://example.com/oauth/token":
                self.assertEqual(req.get_method(), "POST")
                self.assertEqual(
                    req.headers.get("Authorization"),
                    "Basic Y2xpZW50LWlkOmNsaWVudC1zZWNyZXQ=",
                )
                self.assertEqual(
                    req.data,
                    b"grant_type=client_credentials&scope=read%3Aall",
                )
                return FakeResponse(
                    json.dumps(
                        {
                            "access_token": "oauth-token",
                            "token_type": "Bearer",
                        }
                    ),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            captured_authorization.append(req.headers.get("Authorization"))
            return FakeResponse(
                '{"ok":true}',
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_authorization, ["Token oauth-token"])

    def test_oauth_client_credentials_can_send_client_credentials_in_body(self) -> None:
        request = RequestDefinition(
            method="GET",
            url="https://example.com/api/pies",
            auth_type="oauth2-client-credentials",
            auth_oauth_token_url="https://example.com/oauth/token",
            auth_oauth_client_id="client-id",
            auth_oauth_client_secret="client-secret",
            auth_oauth_client_authentication="body",
            auth_oauth_header_prefix="JWT",
            auth_oauth_scope="read:all",
        )
        captured_authorization: list[str | None] = []

        def fake_urlopen(req, timeout=15.0):
            url = req.full_url
            if url == "https://example.com/oauth/token":
                self.assertEqual(req.get_method(), "POST")
                self.assertIsNone(req.headers.get("Authorization"))
                self.assertEqual(
                    req.data,
                    b"grant_type=client_credentials&client_id=client-id&client_secret=client-secret&scope=read%3Aall",
                )
                return FakeResponse(
                    json.dumps(
                        {
                            "access_token": "oauth-token",
                            "token_type": "Bearer",
                        }
                    ),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            captured_authorization.append(req.headers.get("Authorization"))
            return FakeResponse(
                '{"ok":true}',
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_authorization, ["JWT oauth-token"])


if __name__ == "__main__":
    unittest.main()
