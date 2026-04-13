from __future__ import annotations

import unittest

from rich.console import Console
from textual.widgets import Static, Tabs

from piespector.placeholders import PLACEHOLDER_HIGHLIGHT_COLOR
from piespector.domain.editor import (
    REQUEST_EDITOR_TAB_TO_JUMP_KEY,
    REQUEST_EDITOR_TABS,
    RESPONSE_TAB_TO_JUMP_KEY,
    RESPONSE_TABS,
)
from piespector.screens.help.render import render_help_viewport
from piespector.screens.base import PiespectorScreen
from piespector.screens.home.screen import HomeScreen
from piespector.ui.command_line_content import build_command_line_text
from piespector.screens.home.jump_titles import render_jump_hint_line, render_jump_panel_title
from piespector.screens.home.messages import response_caption
from piespector.screens.home.response_panel import (
    render_response_summary_line,
    response_status_style,
)
from piespector.screens.home.request.request_auth import render_request_auth_editor
from piespector.screens.home.request.request_options import render_request_options_editor
from piespector.screens.home.request.url_bar import render_request_url_display
from piespector.app import PiespectorApp
from piespector.state import (
    CollectionDefinition,
    PiespectorState,
    RequestDefinition,
    RequestKeyValue,
    ResponseSummary,
)
from piespector.ui.body_editor_modal import BodyEditorModal, BodyTextEditor
from piespector.ui.status_content import status_bar_content
from piespector.ui.status_hints import status_hint_items
from piespector.ui import APP_BINDINGS, APP_CSS


def render_plain(renderable, *, width: int = 120) -> str:
    console = Console(record=True, width=width)
    console.print(renderable)
    return console.export_text()


def render_static_content(widget: Static, *, width: int = 120) -> str:
    return render_plain(getattr(widget, "_Static__content"), width=width)


class RenderingMiscTests(unittest.TestCase):
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
        self.assertNotIn("Esc collapse", rendered)

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

    def test_home_normal_status_hints_do_not_advertise_escape_collapse(self) -> None:
        state = PiespectorState(current_tab="home")

        self.assertNotIn(("esc", "collapse"), status_hint_items(state))

    def test_render_jump_panel_title_omits_fake_jump_padding_outside_jump_mode(self) -> None:
        title = render_jump_panel_title(
            (("request", "Request"), ("auth", "Auth")),
            {},
            "Request",
            120,
        )

        self.assertEqual(title.plain, "Request")

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

    def test_render_jump_hint_line_lists_response_hotkeys(self) -> None:
        rendered = render_plain(
            render_jump_hint_line(RESPONSE_TABS, RESPONSE_TAB_TO_JUMP_KEY),
            width=40,
        )

        self.assertIn(" a ", rendered)
        self.assertIn(" s ", rendered)


class ScreenWidgetRenderingTests(unittest.IsolatedAsyncioTestCase):
    def make_app(self) -> PiespectorApp:
        app = PiespectorApp()
        app._load_env_workspace = lambda: None
        app._load_history = lambda: None
        app._load_request_workspace = lambda: None
        return app

    async def test_home_screen_url_display_keeps_placeholder_template(self) -> None:
        app = self.make_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="{{BASE_URL}}/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.env_pairs = {"BASE_URL": "https://example.com"}

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            url_display = app.screen.query_one("#url-display", Static)
            rendered = render_static_content(url_display, width=140)

            self.assertIn("{{BASE_URL}}/health", rendered)
            self.assertNotIn("https://example.com/health", rendered)

    async def test_home_response_panel_pretty_prints_json_body(self) -> None:
        app = self.make_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            last_response=ResponseSummary(
                status_code=200,
                elapsed_ms=12.3,
                body_length=17,
                body_text='{"ok":true}',
                response_headers=[("Content-Type", "application/json")],
            ),
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            response_title = app.screen.query_one("#response-title", Static)
            response_summary = app.screen.query_one("#response-summary", Static)
            response_body = app.screen.query_one("#response-body-content", Static)
            rendered = render_static_content(response_body, width=140)

            self.assertEqual(str(response_title.content), "Response")
            self.assertEqual(str(response_summary.content), "200 OK   12.3 ms   17 B")
            self.assertIn('"ok": true', rendered)

    async def test_history_screen_empty_state_renders_in_real_detail_widget(self) -> None:
        app = self.make_app()
        app.state.current_tab = "history"

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            history_list = app.screen.query_one("#history-list")
            history_detail = app.screen.query_one("#history-detail", Static)
            rendered = render_static_content(history_detail, width=140)

            self.assertEqual(history_list.row_count, 0)
            self.assertIn("No history yet.", rendered)
            self.assertIn("Send a request from the Home tab", rendered)

    async def test_home_request_auth_content_is_rendered_by_auth_pane(self) -> None:
        app = self.make_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            request_title = app.screen.query_one("#request-title", Static)
            auth_content = app.screen.query_one("#request-auth-content", Static)
            rendered = render_static_content(auth_content, width=120)

            self.assertEqual(str(request_title.content), "Request")
            self.assertIn("Bearer", rendered)
            self.assertIn("****oken", rendered)

    async def test_home_response_panel_without_response_uses_real_tabs_and_empty_message(self) -> None:
        app = self.make_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            response_tabs = app.screen.query_one("#response-tabs", Tabs)
            response_body = app.screen.query_one("#response-body-content", Static)
            rendered = render_static_content(response_body, width=140)

            self.assertEqual(response_tabs.tab_count, 2)
            self.assertIn("No response yet. Press s to send the active request.", rendered)


class UiAndScrollbarTests(unittest.TestCase):
    def test_ui_constants_include_core_selectors_and_binding(self) -> None:
        self.assertNotIn("#response-modal", APP_CSS)
        self.assertNotIn("#body-editor-modal", APP_CSS)
        self.assertIn("#body-editor-modal", BodyEditorModal.DEFAULT_CSS)
        self.assertIn("BodyTextEditor", BodyTextEditor.DEFAULT_CSS)
        self.assertNotIn("#response-viewer", APP_CSS)
        self.assertIn("#command-line", APP_CSS)
        self.assertNotIn("#sidebar-tree:focus", APP_CSS)
        self.assertNotIn(".jump-overlay", APP_CSS)
        self.assertNotIn("#jump-sidebar-overlay", APP_CSS)
        app_bindings = {(binding.key, binding.action) for binding in APP_BINDINGS}
        screen_bindings = {(binding.key, binding.action) for binding in PiespectorScreen.BINDINGS}
        home_bindings = {(binding.key, binding.action) for binding in HomeScreen.BINDINGS}
        self.assertIn(("ctrl+p", "command_palette"), app_bindings)
        self.assertIn(("ctrl+o", "enter_jump_mode"), app_bindings)
        self.assertIn(("/", "search_workspace"), screen_bindings)
        self.assertIn(("j", "home_browse_down"), home_bindings)
        self.assertIn(("ctrl+j", "home_next_collection"), home_bindings)

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

    def test_command_line_uses_app_background(self) -> None:
        self.assertIn("#command-line {", APP_CSS)
        self.assertNotIn("#command-input {", APP_CSS)
        self.assertIn("background: $background;", APP_CSS)
        self.assertNotIn("background: $footer-background;", APP_CSS)
        self.assertRegex(
            APP_CSS,
            r"#command-line \{[\s\S]*?background: \$background;",
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


class RequestOptionsRenderingTests(unittest.TestCase):
    def test_render_request_options_editor_shows_both_fields(self) -> None:
        state = PiespectorState(current_tab="home")
        state.mode = "HOME_REQUEST_SELECT"
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            verify_ssl=True,
            follow_redirects=False,
        )

        rendered = render_plain(render_request_options_editor(request, state), width=200)

        self.assertIn("Verify SSL", rendered)
        self.assertIn("Follow", rendered)
        self.assertIn("Redirects", rendered)
        self.assertIn("[x] Enabled", rendered)
        self.assertIn("[ ] Disabled", rendered)

    def test_render_request_options_editor_shows_disabled_verify_ssl(self) -> None:
        state = PiespectorState(current_tab="home")
        state.mode = "HOME_REQUEST_SELECT"
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            verify_ssl=False,
            follow_redirects=True,
        )

        rendered = render_plain(render_request_options_editor(request, state), width=200)

        self.assertIn("[ ] Disabled", rendered)
        self.assertIn("[x] Enabled", rendered)


if __name__ == "__main__":
    unittest.main()
