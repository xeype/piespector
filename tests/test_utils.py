from __future__ import annotations

import unittest

from piespector.formatting import format_bytes
from piespector.history import (
    BODY_STORAGE_LIMIT,
    SENSITIVE_HEADER_MARKER,
    TRUNCATION_MARKER,
    build_history_entry,
)
from piespector.placeholders import (
    PlaceholderMatch,
    apply_placeholder_completion,
    auto_pair_placeholder,
    placeholder_match,
)
from piespector.search import (
    activate_search_target,
    history_search_completion,
    history_search_display,
    move_destination_matches,
    request_path,
    resolve_move_destination,
    resolve_search_target,
    search_completion,
    search_matches,
)
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    HistoryEntry,
    PiespectorState,
    RequestDefinition,
    RequestKeyValue,
    ResponseSummary,
    format_headers_text,
    format_query_text,
    history_entry_matches,
    parse_headers_text,
    parse_query_text,
)


class PlaceholderTests(unittest.TestCase):
    def test_auto_pair_placeholder_wraps_single_open_brace(self) -> None:
        completed = auto_pair_placeholder("Hello {", 7)

        self.assertEqual(completed, ("Hello {{}}", 8))

    def test_auto_pair_placeholder_wraps_double_open_brace(self) -> None:
        completed = auto_pair_placeholder("URL {{", 6)

        self.assertEqual(completed, ("URL {{}}", 6))

    def test_placeholder_match_finds_current_placeholder(self) -> None:
        match = placeholder_match("{{BA}}", 4, ["BASE_URL", "TOKEN"])

        self.assertEqual(
            match,
            PlaceholderMatch(
                suggestion="BASE_URL",
                prefix="BA",
                start=0,
                end=6,
            ),
        )

    def test_apply_placeholder_completion_replaces_partial_placeholder(self) -> None:
        completed = apply_placeholder_completion("GET {{BA}}/health", 6, ["BASE_URL"])

        self.assertEqual(completed, ("GET {{BASE_URL}}/health", 14))

    def test_apply_placeholder_completion_returns_none_when_no_match(self) -> None:
        self.assertIsNone(apply_placeholder_completion("GET {{ZZ}}", 8, ["TOKEN"]))


class HistoryTests(unittest.TestCase):
    def test_build_history_entry_redacts_sensitive_headers_and_snapshots_urlencoded_body(self) -> None:
        request = RequestDefinition(
            request_id="request-1",
            name="Create Pie",
            method="POST",
            url="{{BASE_URL}}/pies",
            auth_type="api-key",
            auth_api_key_name="X-Token",
            auth_api_key_value="secret-token",
            auth_api_key_location="header",
            body_type="x-www-form-urlencoded",
            body_urlencoded_items=[
                RequestKeyValue(key="name", value="apple pie"),
                RequestKeyValue(key="size", value="large"),
            ],
        )
        response = ResponseSummary(
            status_code=201,
            elapsed_ms=42.0,
            body_length=2,
            body_text="ok",
            response_headers=[("Set-Cookie", "session=secret")],
        )

        entry = build_history_entry(
            request,
            {"BASE_URL": "https://example.com"},
            response,
            "Desserts / Create Pie",
        )

        self.assertEqual(entry.url, "https://example.com/pies")
        self.assertIn(("X-Token", SENSITIVE_HEADER_MARKER), entry.request_headers)
        self.assertEqual(entry.request_body, "name=apple+pie&size=large")
        self.assertIn(("Set-Cookie", SENSITIVE_HEADER_MARKER), entry.response_headers)

    def test_build_history_entry_truncates_large_request_and_response_bodies(self) -> None:
        large_body = "x" * (BODY_STORAGE_LIMIT + 10)
        request = RequestDefinition(
            method="POST",
            url="https://example.com/upload",
            body_type="raw",
            raw_subtype="text",
            body_text=large_body,
        )
        response = ResponseSummary(
            status_code=200,
            body_length=len(large_body),
            body_text=large_body,
        )

        entry = build_history_entry(request, {}, response, "Uploads / Large")

        self.assertTrue(entry.request_body.endswith(TRUNCATION_MARKER))
        self.assertTrue(entry.response_body.endswith(TRUNCATION_MARKER))
        self.assertEqual(len(entry.request_body), BODY_STORAGE_LIMIT + len(TRUNCATION_MARKER))


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = PiespectorState(current_tab="home")
        self.collection = CollectionDefinition(collection_id="c1", name="Desserts")
        self.folder = FolderDefinition(
            folder_id="f1",
            name="Auth",
            collection_id=self.collection.collection_id,
        )
        self.child_folder = FolderDefinition(
            folder_id="f2",
            name="Nested",
            collection_id=self.collection.collection_id,
            parent_folder_id=self.folder.folder_id,
        )
        self.request = RequestDefinition(
            request_id="r1",
            name="OAuth Protected",
            collection_id=self.collection.collection_id,
            folder_id=self.child_folder.folder_id,
        )
        self.state.collections = [self.collection]
        self.state.folders = [self.folder, self.child_folder]
        self.state.requests = [self.request]
        self.state.ensure_request_workspace()

    def test_search_completion_and_matches_include_request_path(self) -> None:
        matches = search_matches(self.state, "oauth")

        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].display,
            "Desserts / Auth / Nested / OAuth Protected",
        )
        self.assertEqual(search_completion(self.state, "oauth"), matches[0].display)

    def test_resolve_search_target_prefers_exact_request_path_and_can_activate_it(self) -> None:
        target = resolve_search_target(
            self.state,
            "Desserts / Auth / Nested / OAuth Protected",
        )

        self.assertIsNotNone(target)
        activated = activate_search_target(self.state, target)

        self.assertTrue(activated)
        self.assertEqual(self.state.current_tab, "home")
        self.assertEqual(self.state.active_request_id, self.request.request_id)
        self.assertEqual(self.state.message, "Opened request OAuth Protected.")

    def test_activate_search_target_can_open_collection_and_folder(self) -> None:
        collection_target = resolve_search_target(self.state, "Desserts")
        folder_target = resolve_search_target(self.state, "Desserts / Auth")

        self.assertIsNotNone(collection_target)
        self.assertTrue(activate_search_target(self.state, collection_target))
        self.assertEqual(self.state.get_selected_sidebar_node().kind, "collection")
        self.assertEqual(self.state.message, "Opened collection Desserts.")

        self.assertIsNotNone(folder_target)
        self.assertTrue(activate_search_target(self.state, folder_target))
        self.assertEqual(self.state.get_selected_sidebar_node().kind, "folder")
        self.assertEqual(self.state.message, "Opened folder Auth.")

    def test_resolve_search_target_returns_none_for_ambiguous_partial_match(self) -> None:
        second_request = RequestDefinition(
            request_id="r2",
            name="OAuth Protected",
            collection_id=self.collection.collection_id,
        )
        self.state.requests.append(second_request)
        self.state.ensure_request_workspace()

        self.assertIsNone(resolve_search_target(self.state, "OAuth Pro"))

    def test_move_destination_resolution_skips_descendant_folders(self) -> None:
        matches = move_destination_matches(
            self.state,
            "nest",
            source_kind="folder",
            source_id=self.folder.folder_id,
        )

        self.assertEqual(matches, [])
        self.assertIsNone(
            resolve_move_destination(
                self.state,
                "Desserts / Auth / Nested",
                source_kind="folder",
                source_id=self.folder.folder_id,
            )
        )

    def test_request_path_builds_collection_and_folder_hierarchy(self) -> None:
        self.assertEqual(
            request_path(self.state, self.request),
            "Desserts / Auth / Nested / OAuth Protected",
        )

    def test_history_search_completion_uses_display_prefix(self) -> None:
        entry = HistoryEntry(
            history_id="h1",
            method="GET",
            status_code=200,
            source_request_name="Health",
        )
        self.state.history_entries = [entry]

        self.assertEqual(history_search_display(entry), "GET 200 Health")
        self.assertEqual(history_search_completion(self.state, "GET 200"), "GET 200 Health")
        self.assertIsNone(history_search_completion(self.state, "health"))


class StateParserTests(unittest.TestCase):
    def test_history_entry_matches_checks_status_name_path_and_url(self) -> None:
        entry = HistoryEntry(
            history_id="h1",
            method="GET",
            status_code=200,
            source_request_name="Health",
            source_request_path="Core / Health",
            url="https://example.com/health",
        )

        self.assertTrue(history_entry_matches(entry, "get 200"))
        self.assertTrue(history_entry_matches(entry, "core / health"))
        self.assertTrue(history_entry_matches(entry, "example.com/health"))
        self.assertFalse(history_entry_matches(entry, "auth token"))

    def test_parse_and_format_query_text_supports_newlines_and_blank_values(self) -> None:
        parsed = parse_query_text("name=pie&empty\nflag&size = large ")

        self.assertEqual(parsed, [("name", "pie"), ("empty", ""), ("flag", ""), ("size", "large")])
        self.assertEqual(format_query_text(parsed), "name=pie&empty&flag&size=large")

    def test_parse_and_format_headers_text_support_colons_equals_and_semicolons(self) -> None:
        parsed = parse_headers_text("Accept: application/json;X-Token=abc123\nFlag")

        self.assertEqual(
            parsed,
            [("Accept", "application/json"), ("X-Token", "abc123"), ("Flag", "")],
        )
        self.assertEqual(
            format_headers_text(parsed),
            "Accept: application/json\nX-Token: abc123\nFlag",
        )


class FormattingTests(unittest.TestCase):
    def test_format_bytes_handles_thresholds(self) -> None:
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(999), "999 B")
        self.assertEqual(format_bytes(1000), "1 kB")
        self.assertEqual(format_bytes(1500), "1.5 kB")
        self.assertEqual(format_bytes(999_950), "1 MB")
        self.assertEqual(format_bytes(1_000_000), "1 MB")


if __name__ == "__main__":
    unittest.main()
