from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector import storage
from piespector.state import HistoryEntry


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


if __name__ == "__main__":
    unittest.main()
