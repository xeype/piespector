from __future__ import annotations

import unittest

from rich.console import Console

from piespector.rendering import render_viewport
from piespector.scrollbars import ThinScrollBarRender
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    HistoryEntry,
    PiespectorState,
    RequestDefinition,
    ResponseSummary,
)
from piespector.ui import APP_BINDINGS, APP_CSS


def render_plain(renderable, *, width: int = 120) -> str:
    console = Console(record=True, width=width)
    console.print(renderable)
    return console.export_text()


class RenderingMiscTests(unittest.TestCase):
    def test_render_home_viewport_empty_state(self) -> None:
        state = PiespectorState(current_tab="home")

        rendered = render_plain(render_viewport(state, viewport_height=20, viewport_width=120))

        self.assertIn("No collections or requests yet.", rendered)
        self.assertIn(":new collection NAME", rendered)

    def test_render_history_viewport_empty_state(self) -> None:
        state = PiespectorState(current_tab="history")

        rendered = render_plain(render_viewport(state, viewport_height=20, viewport_width=120))

        self.assertIn("No history yet.", rendered)
        self.assertIn(":history", rendered)

    def test_render_help_viewport_history_context(self) -> None:
        state = PiespectorState(current_tab="help", help_source_tab="history", help_source_mode="NORMAL")

        rendered = render_plain(render_viewport(state, viewport_height=24, viewport_width=120))

        self.assertIn("Context History", rendered)
        self.assertIn("j/k entries, s filter, e detail mode, : command", rendered)

    def test_render_env_viewport_empty_and_populated_states(self) -> None:
        empty_state = PiespectorState(current_tab="env")
        empty_rendered = render_plain(render_viewport(empty_state, viewport_height=20, viewport_width=120))

        self.assertIn("No registered values.", empty_rendered)
        self.assertIn(":set KEY=value", empty_rendered)

        populated_state = PiespectorState(current_tab="env")
        populated_state.env_names = ["Default"]
        populated_state.env_sets = {"Default": {"API_URL": "https://example.com"}}
        populated_state.selected_env_name = "Default"
        populated_state.env_pairs = populated_state.env_sets["Default"]

        populated_rendered = render_plain(render_viewport(populated_state, viewport_height=20, viewport_width=120))

        self.assertIn("API_URL", populated_rendered)
        self.assertIn("https://example.com", populated_rendered)
        self.assertIn("Rows 1-1 of 1", populated_rendered)

    def test_render_home_response_pretty_prints_json_body(self) -> None:
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        folder = FolderDefinition(folder_id="f1", name="Core", collection_id="c1")
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id="c1",
            folder_id="f1",
        )
        request.last_response = ResponseSummary(
            status_code=200,
            elapsed_ms=12.3,
            body_length=17,
            body_text='{"ok":true}',
            response_headers=[("Content-Type", "application/json")],
        )
        state = PiespectorState(current_tab="home")
        state.collections = [collection]
        state.folders = [folder]
        state.requests = [request]
        state.ensure_request_workspace()
        state._set_selected_sidebar_by_request_id(request.request_id)
        state.open_selected_request(pin=True)

        rendered = render_plain(render_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("Status 200", rendered)
        self.assertIn('"ok": true', rendered)
        self.assertIn("Response", rendered)

    def test_render_history_viewport_shows_selected_entry_detail(self) -> None:
        state = PiespectorState(current_tab="history")
        state.selected_history_response_tab = "headers"
        state.history_entries = [
            HistoryEntry(
                history_id="h1",
                source_request_name="Health",
                source_request_path="Desserts / Health",
                method="GET",
                url="https://example.com/health",
                auth_type="bearer",
                auth_location="header",
                auth_name="Authorization",
                request_headers=[("Authorization", "<redacted>")],
                response_headers=[("Content-Type", "application/json")],
                response_body='{"ok":true}',
                status_code=200,
                response_size=11,
            )
        ]

        rendered = render_plain(render_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("Health", rendered)
        self.assertIn("GET", rendered)
        self.assertIn("Content-Type", rendered)
        self.assertIn("application/json", rendered)


class UiAndScrollbarTests(unittest.TestCase):
    def test_ui_constants_include_core_selectors_and_binding(self) -> None:
        self.assertIn("#response-viewer", APP_CSS)
        self.assertIn("#command-line", APP_CSS)
        self.assertEqual(APP_BINDINGS[0].key, ":")
        self.assertEqual(APP_BINDINGS[0].action, "enter_command_mode")

    def test_thin_scrollbar_render_uses_line_thumbs(self) -> None:
        vertical = list(
            ThinScrollBarRender.render_bar(
                size=5,
                virtual_size=10,
                window_size=4,
                position=2,
                vertical=True,
            ).segments
        )
        horizontal = list(
            ThinScrollBarRender.render_bar(
                size=5,
                virtual_size=10,
                window_size=4,
                position=2,
                vertical=False,
            ).segments
        )

        self.assertTrue(any(segment.text == "┃" for segment in vertical))
        self.assertTrue(any(segment.text == "━" for segment in horizontal))


if __name__ == "__main__":
    unittest.main()
