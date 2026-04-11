from __future__ import annotations

import unittest

from rich.console import Console

from piespector.placeholders import PLACEHOLDER_HIGHLIGHT_COLOR
from piespector.domain.editor import (
    REQUEST_EDITOR_TAB_TO_JUMP_KEY,
    REQUEST_EDITOR_TABS,
    RESPONSE_TAB_TO_JUMP_KEY,
    RESPONSE_TABS,
)
from piespector.screens.help.render import render_help_viewport
from piespector.screens.history.render import render_history_viewport
from piespector.ui.command_line_content import build_command_line_text
from piespector.screens.home.jump_titles import render_jump_hint_line, render_jump_panel_title
from piespector.screens.home.messages import response_caption
from piespector.screens.home.render import (
    render_home_editor as _render_home_editor,
    render_home_viewport,
)
from piespector.screens.home.response_panel import (
    render_request_response,
    render_response_summary_line,
    response_status_style,
)
from piespector.screens.home.request.request_auth import render_request_auth_editor
from piespector.screens.home.request.url_bar import render_request_url_display, render_top_url_bar
from piespector.screens.home.sidebar import render_home_sidebar
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    HistoryEntry,
    PiespectorState,
    RequestDefinition,
    RequestKeyValue,
    ResponseSummary,
)
from piespector.ui.status_content import status_bar_content
from piespector.ui.status_hints import status_hint_items
from piespector.ui import APP_BINDINGS, APP_CSS


def render_plain(renderable, *, width: int = 120) -> str:
    console = Console(record=True, width=width)
    console.print(renderable)
    return console.export_text()


class RenderingMiscTests(unittest.TestCase):
    def test_render_home_viewport_empty_state(self) -> None:
        state = PiespectorState(current_tab="home")

        rendered = render_plain(render_home_viewport(state, viewport_height=20, viewport_width=120))

        self.assertIn("No collections or requests yet.", rendered)
        self.assertIn("Ctrl+P", rendered)
        self.assertIn("new collection NAME", rendered)

    def test_render_history_viewport_empty_state(self) -> None:
        state = PiespectorState(current_tab="history")

        rendered = render_plain(render_history_viewport(state, viewport_height=20, viewport_width=120))

        self.assertIn("No history yet.", rendered)
        self.assertIn("Ctrl+P", rendered)
        self.assertIn("history", rendered)

    def test_render_help_viewport_history_context(self) -> None:
        state = PiespectorState(current_tab="help", help_source_tab="history", help_source_mode="NORMAL")

        rendered = render_plain(render_help_viewport(state))

        self.assertIn("Context History", rendered)
        self.assertIn("j/k entries, / search, e or Enter detail mode, ctrl+p commands", rendered)

    def test_render_help_viewport_home_request_context_uses_real_commands(self) -> None:
        state = PiespectorState(current_tab="help", help_source_tab="home", help_source_mode="HOME_REQUEST_SELECT")
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
        )
        state.collections = [collection]
        state.requests = [request]
        state.ensure_request_workspace()
        state._set_selected_sidebar_by_request_id(request.request_id)

        rendered = render_plain(render_help_viewport(state), width=140)
        commands_section = rendered.split("Keys", 1)[0]

        self.assertIn("Opened from Home Request Select", rendered)
        self.assertIn("send", rendered)
        self.assertNotIn("close", commands_section)
        self.assertNotIn("import PATH", commands_section)
        self.assertIn("Request: h/l tabs, j/k fields, e or Enter edit, s send, v response", rendered)

    def test_render_help_viewport_home_normal_context_lists_s_send(self) -> None:
        state = PiespectorState(current_tab="help", help_source_tab="home", help_source_mode="NORMAL")

        rendered = render_plain(render_help_viewport(state), width=140)

        self.assertIn("c close opened request", rendered)
        self.assertIn("/ search, s send", rendered)

    def test_render_help_viewport_env_select_context_shows_current_keys(self) -> None:
        state = PiespectorState(current_tab="help", help_source_tab="env", help_source_mode="ENV_SELECT")

        rendered = render_plain(render_help_viewport(state), width=140)

        self.assertIn("Context Env", rendered)
        self.assertIn("h/l fields (Variable/Value/Sensitive/Description), e edit, a add, d delete, Esc back", rendered)

    def test_render_help_viewport_home_params_context_uses_shift_field_keys(self) -> None:
        state = PiespectorState(
            current_tab="help",
            help_source_tab="home",
            help_source_mode="HOME_PARAMS_SELECT",
        )

        rendered = render_plain(render_help_viewport(state), width=160)

        self.assertIn("Params: h/l tabs, j/k rows, H/L fields, e or Enter edit", rendered)
        self.assertNotIn("left/right fields", rendered)

    def test_render_help_viewport_home_url_edit_context_shows_escape_cancel(self) -> None:
        state = PiespectorState(
            current_tab="help",
            help_source_tab="home",
            help_source_mode="HOME_URL_EDIT",
        )

        rendered = render_plain(render_help_viewport(state), width=160)

        self.assertIn(
            "URL edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+v paste",
            rendered,
        )

    def test_render_help_viewport_home_body_context_uses_shift_field_keys(self) -> None:
        state = PiespectorState(
            current_tab="help",
            help_source_tab="home",
            help_source_mode="HOME_BODY_SELECT",
        )
        request = RequestDefinition(request_id="r1", body_type="form-data")
        state.requests = [request]
        state.active_request_id = request.request_id

        rendered = render_plain(render_help_viewport(state), width=160)

        self.assertIn("Body: h/l tabs, j/k rows, H/L fields, e or Enter open or edit", rendered)

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

        rendered = render_plain(render_home_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("200 OK   12.3 ms   17 B", rendered)
        self.assertNotIn("Status 200", rendered)
        self.assertIn('"ok": true', rendered)
        self.assertIn("Response", rendered)

    def test_render_response_summary_line_colors_status_by_status_code(self) -> None:
        cases = (
            (200, "#00ff00"),
            (302, "#00ffff"),
            (404, "#ffff00"),
            (503, "#ff0000"),
            (None, "white"),
        )

        for status_code, expected_style in cases:
            with self.subTest(status_code=status_code):
                summary = render_response_summary_line(status_code, 12.3, 17)
                if status_code == 200:
                    expected_label = "200 OK"
                elif status_code == 302:
                    expected_label = "302 Found"
                elif status_code == 404:
                    expected_label = "404 Not Found"
                elif status_code == 503:
                    expected_label = "503 Service Unavailable"
                else:
                    expected_label = "-"

                self.assertEqual(summary.plain, f"{expected_label}   12.3 ms   17 B")
                self.assertEqual(summary.spans[0].style, expected_style)
                self.assertEqual(response_status_style(status_code), expected_style)

    def test_response_caption_places_error_after_line_range(self) -> None:
        caption = response_caption(
            0,
            5,
            5,
            shortcuts_enabled=False,
            response_tab="body",
            response_selected=False,
            unit_label="Lines",
            error="HTTP Error 500: Internal Server Error",
        )

        self.assertEqual(
            caption,
            "Body  |  Lines 1-5 of 5  |  Error: HTTP Error 500: Internal Server Error",
        )

    def test_render_home_editor_header_keeps_placeholder_url_without_resolved_block(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="{{BASE_URL}}/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.env_pairs = {"BASE_URL": "https://example.com"}
        state.ensure_request_workspace()
        state.open_selected_request(pin=True)

        rendered = render_plain(render_home_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("{{BASE_URL}}/health", rendered)
        self.assertNotIn("https://example.com/health", rendered)
        self.assertNotIn("Env Default", rendered)
        self.assertNotIn("Resolved URL:", rendered)

    def test_render_top_url_bar_url_click_targets_app_action(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="{{BASE_URL}}/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.env_pairs = {"BASE_URL": "https://example.com"}

        panel = render_top_url_bar(state)
        clickable_spans = [
            span
            for span in panel.renderable.spans
            if getattr(span.style, "meta", None)
            and span.style.meta.get("@click") == "app.copy_active_request_url"
        ]
        self.assertTrue(clickable_spans)

    def test_render_top_url_bar_keeps_active_tab_visible_in_window(self) -> None:
        state = PiespectorState(current_tab="home")
        requests = [
            RequestDefinition(request_id=f"r{i}", name=f"Request {i}", method="GET", url=f"http://localhost/{i}")
            for i in range(1, 10)
        ]
        state.requests = requests
        state.open_request_ids = [request.request_id for request in requests]
        state.active_request_id = requests[-1].request_id

        rendered = render_plain(render_top_url_bar(state, viewport_width=60), width=60)

        self.assertIn("Request 9", rendered)
        self.assertIn("…", rendered)

    def test_render_top_url_bar_omits_hl_switch_subtitle(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id

        rendered = render_plain(render_top_url_bar(state), width=100)

        self.assertNotIn("h/l switch", rendered)

    def test_render_top_url_bar_method_selector_stays_compact_when_dropdown_is_open(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.mode = "HOME_REQUEST_METHOD_SELECT"

        selector_rendered = render_plain(render_top_url_bar(state), width=100)

        self.assertIn("GET", selector_rendered)
        self.assertIn("https://example.com/health", selector_rendered)
        self.assertNotIn("POST", selector_rendered)

        state.mode = "HOME_REQUEST_METHOD_EDIT"
        compact_rendered = render_plain(render_top_url_bar(state), width=100)

        self.assertIn("GET", compact_rendered)
        self.assertIn("https://example.com/health", compact_rendered)
        self.assertNotIn("\n        GET", compact_rendered)

    def test_render_top_url_bar_url_edit_keeps_placeholder_url_preview(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="{{BASE_URL}}/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.env_pairs = {"BASE_URL": "https://example.com"}
        state.mode = "HOME_URL_EDIT"

        rendered = render_plain(render_top_url_bar(state), width=100)

        self.assertIn("{{BASE_URL}}/health", rendered)
        self.assertNotIn("https://example.com/health", rendered)
        self.assertNotIn("env: BASE_URL", rendered)

    def test_render_request_url_display_uses_multiple_styles_for_url_parts(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Docs",
            method="GET",
            url="https://{{HOST}}/health",
            query_items=[
                RequestKeyValue(key="page", value="{{PAGE}}"),
            ],
        )

        rendered = render_request_url_display(request)

        self.assertEqual(rendered.plain, "https://{{HOST}}/health?page={{PAGE}}")
        self.assertGreaterEqual(len(rendered.spans), 6)
        placeholder_spans = [
            span
            for span in rendered.spans
            if rendered.plain[span.start : span.end] in {"{{HOST}}", "{{PAGE}}"}
        ]
        self.assertEqual(
            {rendered.plain[span.start : span.end] for span in placeholder_spans},
            {"{{HOST}}", "{{PAGE}}"},
        )
        self.assertTrue(all(span.style.bold is not True for span in placeholder_spans))
        self.assertTrue(
            all(str(span.style) == PLACEHOLDER_HIGHLIGHT_COLOR for span in placeholder_spans)
        )

    def test_render_request_auth_editor_highlights_placeholder_values_when_not_editing(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Auth",
            auth_type="bearer",
            auth_bearer_prefix="Bearer",
            auth_bearer_token="{{TOKEN}}",
        )
        state = PiespectorState(current_tab="home")

        rendered = render_request_auth_editor(request, state, include_type_selector=False)
        table = rendered.renderables[0]
        token_cell = table.columns[1]._cells[1]

        self.assertEqual(token_cell.plain, "{{TOKEN}}")
        self.assertEqual(
            [
                token_cell.plain[span.start : span.end]
                for span in token_cell.spans
                if str(span.style) == PLACEHOLDER_HIGHLIGHT_COLOR
            ],
            ["{{TOKEN}}"],
        )

    def test_render_home_viewport_without_active_request_uses_single_empty_workspace(self) -> None:
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
        )
        state = PiespectorState(current_tab="home")
        state.collections = [collection]
        state.requests = [request]
        state.ensure_request_workspace()
        state.request_workspace_initialized = True
        state._set_selected_sidebar_node("collection", collection.collection_id)
        state.active_request_id = None
        state.preview_request_id = None

        rendered = render_plain(render_home_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("No active request.", rendered)
        self.assertNotIn("Response", rendered)
        self.assertNotIn("Body   Headers", rendered)

    def test_jump_mode_uses_command_line_hint_not_bottom_hints(self) -> None:
        state = PiespectorState(current_tab="home")
        state.enter_jump_mode()

        command_line = build_command_line_text(state).plain
        status = status_bar_content(state)

        self.assertEqual(command_line, "Press a key to jump")
        self.assertEqual(status_hint_items(state), [])
        self.assertEqual(status.hints, ())
        self.assertNotIn("Headers", status.context_label)
        self.assertNotIn("Body", status.context_label)

    def test_url_edit_uses_escape_in_command_line_and_status_hints(self) -> None:
        state = PiespectorState(current_tab="home", mode="HOME_URL_EDIT")

        command_line = build_command_line_text(state).plain

        self.assertEqual(command_line, "Editing URL. Enter saves, Esc cancels.")
        self.assertIn(("esc", "cancel"), status_hint_items(state))

    def test_render_jump_panel_title_omits_fake_jump_padding_outside_jump_mode(self) -> None:
        title = render_jump_panel_title(
            (("request", "Request"), ("auth", "Auth")),
            {},
            "Request",
            120,
        )

        self.assertEqual(title.plain, "Request")

    def test_render_home_editor_supports_auth_tab(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            auth_type="bearer",
            auth_bearer_token="token",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.home_editor_tab = "auth"

        rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        self.assertIn("Bearer Token", rendered)

    def test_render_home_editor_auth_type_edit_shows_dropdown_values(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            auth_type="none",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.home_editor_tab = "auth"
        state.enter_home_auth_type_edit_mode(origin_mode="HOME_AUTH_SELECT")

        rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        self.assertIn("No Auth", rendered)
        self.assertNotIn("Basic Auth", rendered)
        self.assertNotIn("Bearer Token", rendered)

    def test_render_home_editor_body_type_edit_shows_dropdown_values(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="none",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.home_editor_tab = "body"
        state.enter_home_body_type_edit_mode(origin_mode="HOME_BODY_SELECT")

        rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        self.assertIn("None", rendered)
        self.assertNotIn("Form-Data", rendered)
        self.assertNotIn("Raw", rendered)

    def test_render_home_editor_params_tab_hides_composed_url_footer(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.home_editor_tab = "params"

        rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        self.assertNotIn("Composed URL:", rendered)

    def test_render_jump_hint_line_lists_request_hotkeys(self) -> None:
        rendered = render_plain(
            render_jump_hint_line(REQUEST_EDITOR_TABS, REQUEST_EDITOR_TAB_TO_JUMP_KEY),
            width=80,
        )

        self.assertIn(" q ", rendered)
        self.assertIn(" w ", rendered)
        self.assertIn(" e ", rendered)
        self.assertIn(" r ", rendered)
        self.assertIn(" t ", rendered)

    def test_render_home_editor_uses_fixed_request_title(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="test123",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id

        rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        first_line = rendered.splitlines()[0]
        self.assertIn("Request", first_line)

    def test_render_home_editor_keeps_same_height_in_jump_mode(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="test123",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id

        normal_rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))
        state.enter_jump_mode()
        jump_rendered = render_plain(_render_home_editor(request, state, viewport_height=20, viewport_width=120))

        self.assertEqual(len(normal_rendered.splitlines()), len(jump_rendered.splitlines()))

    def test_render_home_editor_selected_block_keeps_request_title(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="test123",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.home_editor_tab = "body"
        state.mode = "HOME_BODY_SELECT"

        panel = _render_home_editor(request, state, viewport_height=20, viewport_width=120)

        self.assertEqual(panel.title.plain, "Request")

    def test_render_home_sidebar_keeps_collections_title(self) -> None:
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
        )
        state = PiespectorState(current_tab="home")
        state.collections = [collection]
        state.requests = [request]
        state.ensure_request_workspace()
        state.mode = "NORMAL"

        panel = render_home_sidebar(state, visible_rows=8)
        rendered = render_plain(panel, width=120)

        self.assertEqual(panel.title.plain, "Collections")
        self.assertIn("Rows 1-2 of 2", rendered)
        self.assertNotIn("j/k browse", rendered)

    def test_render_response_panel_shows_tabs_without_response(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id

        rendered = render_plain(
            render_request_response(
                request,
                state,
                viewport_height=18,
                viewport_width=120,
                shortcuts_enabled=True,
            )
        )

        self.assertIn("Body", rendered)
        self.assertIn("Headers", rendered)
        self.assertIn("No response yet. Press s to send the active request.", rendered)
        self.assertGreaterEqual(len(rendered.splitlines()), 8)

    def test_render_jump_hint_line_lists_response_hotkeys(self) -> None:
        rendered = render_plain(
            render_jump_hint_line(RESPONSE_TABS, RESPONSE_TAB_TO_JUMP_KEY),
            width=40,
        )

        self.assertIn(" a ", rendered)
        self.assertIn(" s ", rendered)

    def test_render_response_panel_keeps_same_height_in_jump_mode(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id

        normal_rendered = render_plain(
            render_request_response(
                request,
                state,
                viewport_height=20,
                viewport_width=120,
                shortcuts_enabled=True,
            )
        )
        state.enter_jump_mode()
        jump_rendered = render_plain(
            render_request_response(
                request,
                state,
                viewport_height=20,
                viewport_width=120,
                shortcuts_enabled=True,
            )
        )

        self.assertEqual(len(normal_rendered.splitlines()), len(jump_rendered.splitlines()))

    def test_render_response_panel_selected_block_keeps_response_title(self) -> None:
        request = RequestDefinition(
            request_id="r1",
            name="Health",
        )
        state = PiespectorState(current_tab="home")
        state.requests = [request]
        state.active_request_id = request.request_id
        state.mode = "HOME_RESPONSE_SELECT"

        panel = render_request_response(
            request,
            state,
            viewport_height=20,
            viewport_width=120,
            shortcuts_enabled=True,
        )

        self.assertEqual(panel.title.plain, "Response")

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

        rendered = render_plain(render_history_viewport(state, viewport_height=24, viewport_width=140), width=140)

        self.assertIn("Health", rendered)
        self.assertIn("GET", rendered)
        self.assertIn("Content-Type", rendered)
        self.assertIn("application/json", rendered)


class UiAndScrollbarTests(unittest.TestCase):
    def test_ui_constants_include_core_selectors_and_binding(self) -> None:
        self.assertIn("#response-modal", APP_CSS)
        self.assertNotIn("#response-viewer", APP_CSS)
        self.assertIn("#command-line", APP_CSS)
        self.assertNotIn("#sidebar-tree:focus", APP_CSS)
        self.assertNotIn(".jump-overlay", APP_CSS)
        self.assertNotIn("#jump-sidebar-overlay", APP_CSS)
        bindings = {(binding.key, binding.action) for binding in APP_BINDINGS}
        self.assertIn(("ctrl+p", "command_palette"), bindings)
        self.assertIn(("/", "search_workspace"), bindings)
        self.assertIn(("ctrl+o", "enter_jump_mode"), bindings)
        self.assertIn(("j", "home_browse_down"), bindings)
        self.assertIn(("ctrl+j", "home_next_collection"), bindings)

    def test_status_hints_use_shift_field_keys_for_params_and_headers(self) -> None:
        params_state = PiespectorState(current_tab="home", mode="HOME_PARAMS_SELECT")
        headers_state = PiespectorState(current_tab="home", mode="HOME_HEADERS_SELECT")
        body_state = PiespectorState(current_tab="home", mode="HOME_BODY_SELECT")
        request = RequestDefinition(body_type="form-data")
        body_state.requests = [request]
        body_state.active_request_id = request.request_id

        self.assertIn(("H/L", "fields"), status_hint_items(params_state))
        self.assertIn(("H/L", "fields"), status_hint_items(headers_state))
        self.assertIn(("H/L", "fields"), status_hint_items(body_state))

    def test_css_uses_native_widget_scrollbars(self) -> None:
        self.assertIn("DataTable {", APP_CSS)
        self.assertIn("TextArea {", APP_CSS)
        self.assertIn("scrollbar-size: 1 1;", APP_CSS)
        self.assertRegex(
            APP_CSS,
            r"#sidebar-tree \{[\s\S]*?scrollbar-size: 1 1;",
        )

    def test_command_input_uses_app_background(self) -> None:
        self.assertIn("#command-input {", APP_CSS)
        self.assertIn("background: $background;", APP_CSS)
        self.assertNotIn("background: $footer-background;", APP_CSS)
        self.assertRegex(
            APP_CSS,
            r"#command-input \{[\s\S]*?&:focus \{[\s\S]*?background: \$background;[\s\S]*?background-tint: 0%;",
        )

    def test_sidebar_tree_uses_app_background(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#sidebar-tree \{[\s\S]*?background: \$background;",
        )
        self.assertRegex(
            APP_CSS,
            r"#sidebar-tree \{[\s\S]*?&:focus \{[\s\S]*?background: \$background;[\s\S]*?background-tint: 0%;",
        )

    def test_data_table_uses_app_background(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"DataTable \{[\s\S]*?background: \$background;",
        )
        self.assertRegex(
            APP_CSS,
            r"DataTable \{[\s\S]*?& > \.datatable--odd-row,[\s\S]*?& > \.datatable--even-row \{[\s\S]*?background: \$background;",
        )
        self.assertRegex(
            APP_CSS,
            r"DataTable \{[\s\S]*?&:focus \{[\s\S]*?background: \$background;[\s\S]*?background-tint: 0%;",
        )

    def test_request_body_table_styles_add_row_separately(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#request-body-table > \.request-body-table--add-row \{[\s\S]*?background: \$surface-darken-1 40%;",
        )

    def test_sidebar_container_is_slightly_wider(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#sidebar-container \{[\s\S]*?width: 40;[\s\S]*?min-width: 36;[\s\S]*?max-width: 46;",
        )

    def test_css_includes_focus_frame_highlight(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#url-bar-container \{[\s\S]*?border: solid \$surface-lighten-2;",
        )
        self.assertRegex(
            APP_CSS,
            r"#url-bar-container\.piespector-focus-frame \{[\s\S]*?border: solid \$accent;",
        )
        self.assertRegex(
            APP_CSS,
            r"#sidebar-container \{[\s\S]*?border: solid \$surface-lighten-2;[\s\S]*?border-title-color: \$text-muted;",
        )
        self.assertRegex(
            APP_CSS,
            r"#request-panel \{[\s\S]*?border: solid \$surface-lighten-2;[\s\S]*?border-title-color: \$text-muted;",
        )
        self.assertRegex(
            APP_CSS,
            r"#response-panel \{[\s\S]*?border: solid \$surface-lighten-2;[\s\S]*?border-title-color: \$text-muted;",
        )
        self.assertRegex(
            APP_CSS,
            r"#sidebar-container\.piespector-focus-frame,[\s\S]*?#request-panel\.piespector-focus-frame,[\s\S]*?#response-panel\.piespector-focus-frame \{[\s\S]*?border: solid \$accent;[\s\S]*?border-title-color: \$text;",
        )

    def test_css_highlights_active_request_and_response_tabs(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#request-tabs ContentTabs:focus \.-active \{[\s\S]*?color: \$text;[\s\S]*?background: \$accent;",
        )
        self.assertRegex(
            APP_CSS,
            r"#request-panel\.piespector-tab-select #request-tabs ContentTab\.-active \{[\s\S]*?background: \$accent;[\s\S]*?color: \$text;",
        )
        self.assertRegex(
            APP_CSS,
            r"#response-tabs:focus \.-active \{[\s\S]*?color: \$text;[\s\S]*?background: \$accent;",
        )
        self.assertRegex(
            APP_CSS,
            r"#response-panel\.piespector-tab-select #response-tabs Tab\.-active \{[\s\S]*?background: \$accent;[\s\S]*?color: \$text;",
        )

    def test_css_uses_current_tree_and_table_cursor_styles(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#sidebar-tree \{[\s\S]*?& > \.tree--cursor \{[\s\S]*?background: transparent;",
        )
        self.assertRegex(
            APP_CSS,
            r"#sidebar-tree \{[\s\S]*?&:focus \{[\s\S]*?& > \.tree--cursor \{[\s\S]*?color: \$text;[\s\S]*?background: \$accent;[\s\S]*?text-style: none;",
        )
        self.assertRegex(
            APP_CSS,
            r"DataTable \{[\s\S]*?& > \.datatable--cursor,[\s\S]*?& > \.datatable--fixed-cursor \{[\s\S]*?color: \$text;[\s\S]*?background: \$accent;",
        )

    def test_css_uses_accent_outline_for_selected_home_select_widgets(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"#method-select\.piespector-selected-element > SelectCurrent \{[\s\S]*?outline: solid \$accent;",
        )
        self.assertRegex(
            APP_CSS,
            r"#auth-type-select\.piespector-selected-element > SelectCurrent,[\s\S]*?#auth-option-select\.piespector-selected-element > SelectCurrent,[\s\S]*?#body-type-select\.piespector-selected-element > SelectCurrent,[\s\S]*?#body-raw-type-select\.piespector-selected-element > SelectCurrent \{[\s\S]*?outline: solid \$accent;",
        )

    def test_select_widgets_use_surface_background(self) -> None:
        self.assertRegex(
            APP_CSS,
            r"Select > SelectCurrent \{[\s\S]*?background: \$surface;",
        )
        self.assertRegex(
            APP_CSS,
            r"Select:focus > SelectCurrent \{[\s\S]*?background: \$surface;[\s\S]*?background-tint: 0%;",
        )
        self.assertRegex(
            APP_CSS,
            r"Select > SelectOverlay \{[\s\S]*?background: \$surface;",
        )
        self.assertRegex(
            APP_CSS,
            r"Select > SelectOverlay:focus \{[\s\S]*?background: \$surface;[\s\S]*?background-tint: 0%;",
        )
        self.assertRegex(
            APP_CSS,
            r"Select > SelectOverlay > \.option-list--option,[\s\S]*?background: \$surface;",
        )


if __name__ == "__main__":
    unittest.main()
