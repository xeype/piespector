from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector import storage
from piespector.state import HistoryEntry, RequestDefinition


class StorageTests(unittest.TestCase):
    def test_app_data_dir_defaults_to_macos_application_support(self) -> None:
        with patch.object(storage.Path, "home", return_value=Path("/Users/test")), patch.object(
            storage.sys, "platform", "darwin"
        ), patch.dict(storage.os.environ, {}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("/Users/test/Library/Application Support/piespector"))

    def test_app_data_dir_defaults_to_xdg_location_on_linux(self) -> None:
        with patch.object(storage.Path, "home", return_value=Path("/home/test")), patch.object(
            storage.sys, "platform", "linux"
        ), patch.dict(storage.os.environ, {"XDG_DATA_HOME": "/tmp/xdg-data"}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("/tmp/xdg-data/piespector"))

    def test_app_data_dir_defaults_to_appdata_on_windows(self) -> None:
        with patch.object(storage.Path, "home", return_value=Path("C:/Users/test")), patch.object(
            storage.sys, "platform", "win32"
        ), patch.dict(storage.os.environ, {"APPDATA": "C:/Users/test/AppData/Roaming"}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("C:/Users/test/AppData/Roaming/piespector"))

    def test_save_request_workspace_creates_parent_directory(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "workspace" / "requests.json"

            storage.save_request_workspace(path, [], [], [], set(), set())

            self.assertTrue(path.exists())

    def test_append_history_entry_creates_parent_directory(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "history" / "history.jsonl"
            entry = HistoryEntry(
                history_id="h1",
                created_at="2026-03-27T00:00:00+01:00",
                source_request_id=None,
                source_request_name="Books",
                source_request_path="books / getBooks",
                method="GET",
                url="https://example.com/books",
                auth_type="none",
                auth_location="",
                auth_name="",
                request_headers=[],
                request_body="",
                request_body_type="none",
                status_code=200,
                elapsed_ms=123.4,
                response_size=42,
                response_headers=[],
                response_body="{}",
                error="",
            )

            storage.append_history_entry(path, entry)

            self.assertTrue(path.exists())

    def test_save_history_entries_round_trips_with_load_history_entries(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "history.jsonl"
            entries = [
                HistoryEntry(
                    history_id="newer",
                    created_at="2026-03-27T00:00:02+01:00",
                    source_request_id=None,
                    source_request_name="Newer",
                    source_request_path="books / newer",
                    method="GET",
                    url="https://example.com/newer",
                    auth_type="none",
                    auth_location="",
                    auth_name="",
                    request_headers=[],
                    request_body="",
                    request_body_type="none",
                    status_code=200,
                    elapsed_ms=20.0,
                    response_size=2,
                    response_headers=[],
                    response_body="{}",
                    error="",
                ),
                HistoryEntry(
                    history_id="older",
                    created_at="2026-03-27T00:00:01+01:00",
                    source_request_id=None,
                    source_request_name="Older",
                    source_request_path="books / older",
                    method="GET",
                    url="https://example.com/older",
                    auth_type="none",
                    auth_location="",
                    auth_name="",
                    request_headers=[],
                    request_body="",
                    request_body_type="none",
                    status_code=200,
                    elapsed_ms=10.0,
                    response_size=2,
                    response_headers=[],
                    response_body="{}",
                    error="",
                ),
            ]

            storage.save_history_entries(path, entries)
            loaded = storage.load_history_entries(path)

        self.assertEqual([entry.history_id for entry in loaded], ["newer", "older"])

    def test_load_env_workspace_uses_legacy_env_file_when_new_workspace_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace_path = root / "app-data" / ".piespector.env.json"
            legacy_env_path = root / ".env"
            legacy_env_path.write_text("API_URL=https://example.com\n", encoding="utf-8")

            env_names, env_sets, selected_env_name = storage.load_env_workspace(
                workspace_path,
                legacy_env_path,
            )

        self.assertEqual(env_names, ["Default"])
        self.assertEqual(env_sets, {"Default": {"API_URL": "https://example.com"}})
        self.assertEqual(selected_env_name, "Default")

    def test_request_workspace_round_trips_cookie_and_custom_header_auth(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "requests.json"
            requests = [
                RequestDefinition(
                    request_id="cookie-request",
                    name="Cookie Request",
                    auth_type="cookie",
                    auth_cookie_name="session",
                    auth_cookie_value="secret",
                ),
                RequestDefinition(
                    request_id="header-request",
                    name="Header Request",
                    auth_type="custom-header",
                    auth_custom_header_name="X-Session-Token",
                    auth_custom_header_value="secret-token",
                ),
                RequestDefinition(
                    request_id="oauth-request",
                    name="OAuth Request",
                    auth_type="oauth2-client-credentials",
                    auth_oauth_token_url="https://example.com/oauth/token",
                    auth_oauth_client_id="client-id",
                    auth_oauth_client_secret="client-secret",
                    auth_oauth_scope="read:all",
                ),
                RequestDefinition(
                    request_id="graphql-request",
                    name="GraphQL Request",
                    body_type="graphql",
                    body_text="query Health { health }",
                ),
                RequestDefinition(
                    request_id="binary-request",
                    name="Binary Request",
                    body_type="binary",
                    body_text="/tmp/payload.bin",
                ),
                RequestDefinition(
                    request_id="html-request",
                    name="HTML Request",
                    body_type="raw",
                    raw_subtype="html",
                    body_text="<p>hello</p>",
                    raw_body_texts={"javascript": "console.log('hi')"},
                ),
                RequestDefinition(
                    request_id="javascript-request",
                    name="JavaScript Request",
                    body_type="raw",
                    raw_subtype="javascript",
                    body_text="console.log('hi')",
                ),
            ]

            storage.save_request_workspace(path, [], [], requests, set(), set())
            _collections, _folders, loaded_requests, _collapsed_collections, _collapsed_folders = (
                storage.load_request_workspace(path)
            )

        self.assertEqual(loaded_requests[0].auth_type, "cookie")
        self.assertEqual(loaded_requests[0].auth_cookie_name, "session")
        self.assertEqual(loaded_requests[0].auth_cookie_value, "secret")
        self.assertEqual(loaded_requests[1].auth_type, "custom-header")
        self.assertEqual(loaded_requests[1].auth_custom_header_name, "X-Session-Token")
        self.assertEqual(loaded_requests[1].auth_custom_header_value, "secret-token")
        self.assertEqual(loaded_requests[2].auth_type, "oauth2-client-credentials")
        self.assertEqual(
            loaded_requests[2].auth_oauth_token_url,
            "https://example.com/oauth/token",
        )
        self.assertEqual(loaded_requests[2].auth_oauth_client_id, "client-id")
        self.assertEqual(loaded_requests[2].auth_oauth_client_secret, "client-secret")
        self.assertEqual(loaded_requests[2].auth_oauth_scope, "read:all")
        self.assertEqual(loaded_requests[3].body_type, "graphql")
        self.assertEqual(loaded_requests[3].body_text, "query Health { health }")
        self.assertEqual(loaded_requests[4].body_type, "binary")
        self.assertEqual(loaded_requests[4].body_text, "/tmp/payload.bin")
        self.assertEqual(loaded_requests[5].raw_subtype, "html")
        self.assertEqual(loaded_requests[5].raw_body_texts["javascript"], "console.log('hi')")
        self.assertEqual(loaded_requests[6].raw_subtype, "javascript")


if __name__ == "__main__":
    unittest.main()
