from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector import storage
from piespector.storage import paths as storage_paths
from piespector.domain.requests import EnvVariable
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    HistoryEntry,
    RequestAuth,
    RequestBody,
    RequestDefinition,
)


class StorageTests(unittest.TestCase):
    def test_load_env_pairs_parses_comments_exports_and_quotes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / ".env"
            path.write_text(
                "# comment\n"
                "export API_URL=https://example.com\n"
                'TOKEN="line\\nvalue"\n'
                "RAW=literal\n"
                "INVALID\n"
                "EMPTY=\n"
                "SINGLE='quoted value'\n",
                encoding="utf-8",
            )

            env_pairs = storage.load_env_pairs(path)

        self.assertEqual(
            env_pairs,
            {
                "API_URL": "https://example.com",
                "TOKEN": "line\nvalue",
                "RAW": "literal",
                "EMPTY": "",
                "SINGLE": "quoted value",
            },
        )

    def test_save_env_pairs_round_trips_with_load_env_pairs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / ".env"
            storage.save_env_pairs(
                path,
                {
                    "TOKEN": 'a"b',
                    "MULTI": "line1\nline2",
                    "TAB": "a\tb",
                },
            )

            loaded = storage.load_env_pairs(path)

        self.assertEqual(
            loaded,
            {
                "TOKEN": 'a"b',
                "MULTI": "line1\nline2",
                "TAB": "a\tb",
            },
        )

    def test_app_data_dir_defaults_to_macos_application_support(self) -> None:
        with patch.object(storage_paths.Path, "home", return_value=Path("/Users/test")), patch.object(
            storage_paths.sys, "platform", "darwin"
        ), patch.dict(storage_paths.os.environ, {}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("/Users/test/Library/Application Support/piespector"))

    def test_app_data_dir_defaults_to_xdg_location_on_linux(self) -> None:
        with patch.object(storage_paths.Path, "home", return_value=Path("/home/test")), patch.object(
            storage_paths.sys, "platform", "linux"
        ), patch.dict(storage_paths.os.environ, {"XDG_DATA_HOME": "/tmp/xdg-data"}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("/tmp/xdg-data/piespector"))

    def test_app_data_dir_defaults_to_appdata_on_windows(self) -> None:
        with patch.object(storage_paths.Path, "home", return_value=Path("C:/Users/test")), patch.object(
            storage_paths.sys, "platform", "win32"
        ), patch.dict(storage_paths.os.environ, {"APPDATA": "C:/Users/test/AppData/Roaming"}, clear=True):
            path = storage.app_data_dir()

        self.assertEqual(path, Path("C:/Users/test/AppData/Roaming/piespector"))

    def test_discover_workspace_paths_prefers_legacy_workspace_files_until_migrated(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            app_data_dir = root / "app-data"
            workspace_dir = root / "workspace"
            workspace_dir.mkdir()
            legacy_env_workspace = workspace_dir / ".piespector.env.json"
            legacy_requests = workspace_dir / ".piespector.requests.json"
            legacy_history = workspace_dir / ".piespector.history.jsonl"
            legacy_env_workspace.write_text("{}", encoding="utf-8")
            legacy_requests.write_text("{}", encoding="utf-8")
            legacy_history.write_text("", encoding="utf-8")

            paths = storage.discover_workspace_paths(
                base_dir=app_data_dir,
                cwd=workspace_dir,
            )

        self.assertEqual(
            paths.env_workspace_path,
            app_data_dir / ".piespector.env.json",
        )
        self.assertEqual(paths.env_workspace_source_path, legacy_env_workspace)
        self.assertIsNone(paths.legacy_env_path)
        self.assertTrue(paths.needs_env_workspace_migration)
        self.assertEqual(paths.requests_source_path, legacy_requests)
        self.assertTrue(paths.needs_requests_migration)
        self.assertEqual(paths.history_source_path, legacy_history)
        self.assertTrue(paths.needs_history_migration)
        self.assertEqual(paths.log_path, app_data_dir / ".piespector.log")

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
        self.assertEqual(len(env_sets["Default"]), 1)
        self.assertEqual(env_sets["Default"][0].key, "API_URL")
        self.assertEqual(env_sets["Default"][0].value, "https://example.com")
        self.assertEqual(selected_env_name, "Default")

    def test_save_env_workspace_normalizes_missing_selected_env(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "envs.json"

            storage.save_env_workspace(
                path,
                ["Prod", "Staging"],
                {"Prod": [EnvVariable(key="API_URL", value="https://prod.example.com")]},
                "Missing",
            )
            env_names, env_sets, selected_env_name = storage.load_env_workspace(path)

        self.assertEqual(env_names, ["Prod"])
        self.assertEqual(len(env_sets["Prod"]), 1)
        self.assertEqual(env_sets["Prod"][0].key, "API_URL")
        self.assertEqual(env_sets["Prod"][0].value, "https://prod.example.com")
        self.assertEqual(selected_env_name, "Prod")

    def test_import_env_sets_loads_workspace_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "envs.json"
            path.write_text(
                json.dumps(
                    {
                        "selected_env_name": "Staging",
                        "envs": [
                            {"name": "Prod", "pairs": {"API_URL": "https://prod.example.com"}},
                            {"name": "Staging", "pairs": {"API_URL": "https://staging.example.com"}},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            env_names, env_sets = storage.import_env_sets(path)

        self.assertEqual(env_names, ["Prod", "Staging"])
        self.assertEqual(env_sets["Staging"]["API_URL"], "https://staging.example.com")

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
                    auth_oauth_client_authentication="body",
                    auth_oauth_header_prefix="Token",
                    auth_oauth_scope="read:all",
                ),
                RequestDefinition(
                    request_id="bearer-request",
                    name="Bearer Request",
                    auth_type="bearer",
                    auth_bearer_prefix="JWT",
                    auth_bearer_token="secret-bearer-token",
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
            saved_payload = json.loads(path.read_text(encoding="utf-8"))
            _collections, _folders, loaded_requests, _collapsed_collections, _collapsed_folders = (
                storage.load_request_workspace(path)
            )

        self.assertEqual(saved_payload["requests"][0]["auth"]["type"], "cookie")
        self.assertEqual(saved_payload["requests"][4]["body"]["type"], "graphql")
        self.assertNotIn("auth_type", saved_payload["requests"][0])
        self.assertNotIn("body_type", saved_payload["requests"][4])
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
        self.assertEqual(loaded_requests[2].auth_oauth_client_authentication, "body")
        self.assertEqual(loaded_requests[2].auth_oauth_header_prefix, "Token")
        self.assertEqual(loaded_requests[2].auth_oauth_scope, "read:all")
        self.assertEqual(loaded_requests[3].auth_type, "bearer")
        self.assertEqual(loaded_requests[3].auth_bearer_prefix, "JWT")
        self.assertEqual(loaded_requests[3].auth_bearer_token, "secret-bearer-token")
        self.assertEqual(loaded_requests[4].body_type, "graphql")
        self.assertEqual(loaded_requests[4].body_text, "query Health { health }")
        self.assertEqual(loaded_requests[5].body_type, "binary")
        self.assertEqual(loaded_requests[5].body_text, "/tmp/payload.bin")
        self.assertEqual(loaded_requests[6].raw_subtype, "html")
        self.assertEqual(loaded_requests[6].raw_body_texts["javascript"], "console.log('hi')")
        self.assertEqual(loaded_requests[7].raw_subtype, "javascript")

    def test_request_definition_accepts_nested_auth_and_body_objects(self) -> None:
        request = RequestDefinition(
            auth=RequestAuth(
                type="bearer",
                bearer_prefix="JWT",
                bearer_token="secret-bearer-token",
            ),
            body=RequestBody(
                type="graphql",
                text="query Health { health }",
            ),
        )

        self.assertEqual(request.auth.type, "bearer")
        self.assertEqual(request.auth_type, "bearer")
        self.assertEqual(request.auth.bearer_token, "secret-bearer-token")
        self.assertEqual(request.auth_bearer_token, "secret-bearer-token")
        self.assertEqual(request.body.type, "graphql")
        self.assertEqual(request.body_type, "graphql")
        self.assertEqual(request.body.graphql_text, "query Health { health }")
        self.assertEqual(request.body_text, "query Health { health }")

    def test_load_request_workspace_ignores_legacy_flat_auth_and_body_fields(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "legacy-requests.json"
            path.write_text(
                json.dumps(
                    {
                        "collections": [],
                        "folders": [],
                        "requests": [
                            {
                                "request_id": "legacy-auth",
                                "name": "Legacy Auth",
                                "auth_type": "cookie",
                                "auth_cookie_name": "session",
                                "auth_cookie_value": "secret",
                            },
                            {
                                "request_id": "legacy-body",
                                "name": "Legacy Body",
                                "body_type": "raw",
                                "raw_subtype": "html",
                                "body_text": "<p>hello</p>",
                                "raw_body_texts": {"javascript": "console.log('hi')"},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            _collections, _folders, loaded_requests, _collapsed_collections, _collapsed_folders = (
                storage.load_request_workspace(path)
            )

        self.assertEqual(loaded_requests[0].name, "Legacy Auth")
        self.assertEqual(loaded_requests[0].auth.type, "none")
        self.assertEqual(loaded_requests[0].auth_cookie_name, "session")
        self.assertEqual(loaded_requests[0].auth_cookie_value, "")
        self.assertEqual(loaded_requests[1].name, "Legacy Body")
        self.assertEqual(loaded_requests[1].body.type, "none")
        self.assertEqual(loaded_requests[1].body_text, "")
        self.assertEqual(loaded_requests[1].raw_body_texts, {})

    def test_export_collection_workspace_filters_transient_and_selected_collections(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "collections.json"
            collection_a = CollectionDefinition(collection_id="c1", name="Alpha")
            collection_b = CollectionDefinition(collection_id="c2", name="Beta")
            folder_a = FolderDefinition(
                folder_id="f1",
                name="Auth",
                collection_id=collection_a.collection_id,
            )
            requests = [
                RequestDefinition(
                    request_id="r1",
                    name="Keep Me",
                    collection_id=collection_a.collection_id,
                    folder_id=folder_a.folder_id,
                ),
                RequestDefinition(
                    request_id="r2",
                    name="Transient",
                    collection_id=collection_a.collection_id,
                    transient=True,
                ),
                RequestDefinition(
                    request_id="r3",
                    name="Other Collection",
                    collection_id=collection_b.collection_id,
                ),
            ]

            exported_count = storage.export_collection_workspace(
                path,
                [collection_a, collection_b],
                [folder_a],
                requests,
                collection_ids={collection_a.collection_id},
            )
            collections, folders, loaded_requests, _collapsed_collections, _collapsed_folders = (
                storage.load_request_workspace(path)
            )

        self.assertEqual(exported_count, 1)
        self.assertEqual([collection.name for collection in collections], ["Alpha"])
        self.assertEqual([folder.name for folder in folders], ["Auth"])
        self.assertEqual([request.name for request in loaded_requests], ["Keep Me"])

    def test_import_collection_workspace_filters_orphaned_folders_and_requests(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "import.json"
            payload = {
                "collections": [
                    {"collection_id": "c1", "name": "Alpha"},
                ],
                "folders": [
                    {"folder_id": "f1", "name": "Auth", "collection_id": "c1", "parent_folder_id": None},
                    {"folder_id": "f2", "name": "Ghost", "collection_id": "missing", "parent_folder_id": None},
                ],
                "requests": [
                    {"request_id": "r1", "name": "Keep", "collection_id": "c1", "folder_id": "f1"},
                    {"request_id": "r2", "name": "Drop Missing Collection", "collection_id": "missing", "folder_id": None},
                    {"request_id": "r3", "name": "Drop Missing Folder", "collection_id": "c1", "folder_id": "f2"},
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            collections, folders, requests = storage.import_collection_workspace(path)

        self.assertEqual([collection.name for collection in collections], ["Alpha"])
        self.assertEqual([folder.name for folder in folders], ["Auth"])
        self.assertEqual([request.name for request in requests], ["Keep"])


if __name__ == "__main__":
    unittest.main()
