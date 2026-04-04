from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector.http_client import perform_request, preview_effective_headers, validate_raw_body
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


class BodyTests(unittest.TestCase):
    def test_raw_html_uses_text_html_content_type(self) -> None:
        request = RequestDefinition(method="POST", body_type="raw", raw_subtype="html")

        effective_headers, _auto_headers = preview_effective_headers(request, {})

        self.assertEqual(effective_headers["Content-Type"], "text/html")

    def test_raw_javascript_uses_application_javascript_content_type(self) -> None:
        request = RequestDefinition(method="POST", body_type="raw", raw_subtype="javascript")

        effective_headers, _auto_headers = preview_effective_headers(request, {})

        self.assertEqual(effective_headers["Content-Type"], "application/javascript")

    def test_graphql_body_sends_application_graphql(self) -> None:
        request = RequestDefinition(
            method="POST",
            url="https://example.com/graphql",
            body_type="graphql",
            body_text="query Health { health }",
        )
        captured_data: list[bytes | None] = []
        captured_content_type: list[str | None] = []

        def fake_urlopen(req, timeout=15.0, context=None):
            headers = {key.lower(): value for key, value in req.header_items()}
            captured_data.append(req.data)
            captured_content_type.append(headers.get("content-type"))
            return FakeResponse('{"ok":true}', headers={"Content-Type": "application/json"})

        with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_data, [b"query Health { health }"])
        self.assertEqual(captured_content_type, ["application/graphql"])

    def test_binary_body_reads_file_bytes_and_sets_octet_stream(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "payload.bin"
            file_path.write_bytes(b"\x00\x01piespector")
            request = RequestDefinition(
                method="POST",
                url="https://example.com/upload",
                body_type="binary",
                body_text=str(file_path),
            )
            captured_data: list[bytes | None] = []
            captured_content_type: list[str | None] = []

            def fake_urlopen(req, timeout=15.0, context=None):
                headers = {key.lower(): value for key, value in req.header_items()}
                captured_data.append(req.data)
                captured_content_type.append(headers.get("content-type"))
                return FakeResponse('{"ok":true}', headers={"Content-Type": "application/json"})

            with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
                response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_data, [b"\x00\x01piespector"])
        self.assertEqual(captured_content_type, ["application/octet-stream"])

    def test_urlencoded_body_encodes_special_characters(self) -> None:
        request = RequestDefinition(
            method="POST",
            url="https://example.com/form",
            body_type="x-www-form-urlencoded",
        )
        request.body_urlencoded_items = [
            RequestKeyValue(key="name", value="pie spector", enabled=True),
            RequestKeyValue(key="note", value="a&b", enabled=True),
        ]
        captured_data: list[bytes | None] = []
        captured_content_type: list[str | None] = []

        def fake_urlopen(req, timeout=15.0, context=None):
            headers = {key.lower(): value for key, value in req.header_items()}
            captured_data.append(req.data)
            captured_content_type.append(headers.get("content-type"))
            return FakeResponse('{"ok":true}', headers={"Content-Type": "application/json"})

        with patch("piespector.http_client.request.urlopen", side_effect=fake_urlopen):
            response = perform_request(request, {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_data, [b"name=pie+spector&note=a%26b"])
        self.assertEqual(captured_content_type, ["application/x-www-form-urlencoded"])

    def test_raw_html_validator_reports_mismatched_tags(self) -> None:
        request = RequestDefinition(body_type="raw", raw_subtype="html")

        error = validate_raw_body(request, "<div><span></div>")

        self.assertIn("Invalid HTML", error or "")

    def test_raw_javascript_validator_reports_unclosed_brace(self) -> None:
        request = RequestDefinition(body_type="raw", raw_subtype="javascript")

        error = validate_raw_body(request, "function test() { return 1;")

        self.assertIn("Invalid JavaScript", error or "")

    def test_graphql_validator_reports_unclosed_brace(self) -> None:
        request = RequestDefinition(body_type="graphql")

        error = validate_raw_body(request, "query Health { health")

        self.assertIn("Invalid GraphQL", error or "")


if __name__ == "__main__":
    unittest.main()
