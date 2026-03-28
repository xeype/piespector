from __future__ import annotations

from email.message import Message
from io import BytesIO
from pathlib import Path
import socket
import ssl
from tempfile import TemporaryDirectory
import unittest
from urllib import error
from unittest.mock import patch

from piespector.http_client import (
    _decode_body,
    _encode_multipart_form_data,
    perform_request,
    response_preview,
)
from piespector.state import RequestDefinition, RequestKeyValue


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
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body
        self.headers = FakeHeaders(headers)

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class HttpClientMiscTests(unittest.TestCase):
    def test_perform_request_returns_validation_error_for_invalid_url(self) -> None:
        request = RequestDefinition(url="example.com/api")

        response = perform_request(request, {})

        self.assertIn("Invalid URL", response.error)
        self.assertIsNone(response.status_code)

    def test_perform_request_surfaces_http_error_response(self) -> None:
        request = RequestDefinition(url="https://example.com/api")
        headers = Message()
        headers.add_header("Content-Type", "application/json; charset=utf-8")
        http_error = error.HTTPError(
            "https://example.com/api",
            401,
            "Unauthorized",
            headers,
            BytesIO(b'{"error":"unauthorized"}'),
        )

        with patch("piespector.http_client.request.urlopen", side_effect=http_error):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.body_text, '{"error":"unauthorized"}')
        self.assertEqual(response.error, "HTTP Error 401: Unauthorized")

    def test_perform_request_maps_url_error_to_friendly_message(self) -> None:
        request = RequestDefinition(url="https://missing.example.com")

        with patch(
            "piespector.http_client.request.urlopen",
            side_effect=error.URLError(socket.gaierror()),
        ):
            response = perform_request(request, {})

        self.assertEqual(response.error, "DNS lookup failed: could not resolve the host name.")

    def test_perform_request_maps_timeout_and_ssl_errors(self) -> None:
        request = RequestDefinition(url="https://example.com")

        with patch(
            "piespector.http_client.request.urlopen",
            side_effect=TimeoutError(),
        ):
            timeout_response = perform_request(request, {})

        with patch(
            "piespector.http_client.request.urlopen",
            side_effect=ssl.SSLError("bad ssl"),
        ):
            ssl_response = perform_request(request, {})

        self.assertEqual(timeout_response.error, "Request timed out: the server did not respond in time.")
        self.assertEqual(ssl_response.error, "SSL error: could not establish a secure connection.")

    def test_perform_request_reports_missing_binary_body_file(self) -> None:
        request = RequestDefinition(
            method="POST",
            url="https://example.com/upload",
            body_type="binary",
            body_text="/definitely/missing.bin",
        )

        response = perform_request(request, {})

        self.assertIn("Binary body file does not exist", response.error)

    def test_perform_request_encodes_form_data_body(self) -> None:
        request = RequestDefinition(
            method="POST",
            url="https://example.com/form",
            body_type="form-data",
        )
        request.body_form_items = [
            RequestKeyValue(key="name", value="piespector"),
            RequestKeyValue(key="kind", value="demo"),
        ]
        captured_data: list[bytes | None] = []
        captured_content_type: list[str | None] = []

        def fake_urlopen(req, timeout=15.0):
            headers = {key.lower(): value for key, value in req.header_items()}
            captured_data.append(req.data)
            captured_content_type.append(headers.get("content-type"))
            return FakeResponse(b'{"ok":true}', headers={"Content-Type": "application/json"})

        with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_content_type, ["multipart/form-data; boundary=piespector-boundary"])
        self.assertIn(b'Content-Disposition: form-data; name="name"', captured_data[0] or b"")
        self.assertIn(b"piespector", captured_data[0] or b"")

    def test_decode_body_falls_back_to_replacement_on_unicode_errors(self) -> None:
        self.assertEqual(_decode_body(b"\xff", "utf-8"), "\ufffd")

    def test_response_preview_truncates_long_text(self) -> None:
        preview = response_preview("x" * 10, limit=5)

        self.assertEqual(preview, "xxxxx\n…")

    def test_encode_multipart_form_data_contains_boundary_and_values(self) -> None:
        encoded = _encode_multipart_form_data(
            [("name", "piespector"), ("kind", "demo")],
            "boundary",
        )

        self.assertIn(b"--boundary", encoded)
        self.assertIn(b'Content-Disposition: form-data; name="name"', encoded)
        self.assertIn(b"piespector", encoded)

    def test_perform_request_decodes_response_body_with_replacement(self) -> None:
        request = RequestDefinition(url="https://example.com/binary")

        with patch(
            "piespector.http_client.request.urlopen",
            return_value=FakeResponse(b"\xff", headers={"Content-Type": "text/plain; charset=utf-8"}),
        ):
            response = perform_request(request, {})

        self.assertEqual(response.body_text, "\ufffd")


if __name__ == "__main__":
    unittest.main()
