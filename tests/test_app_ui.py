from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from rich.console import Console

from piespector.app import PiespectorApp
from piespector.ui.rendering_helpers import (
    detect_text_syntax_language,
    request_body_syntax_language,
    text_area_syntax_language,
)
from piespector.domain.workspace import CollectionDefinition, FolderDefinition
from piespector.ui.command_palette import PiespectorCommandProvider, PiespectorSearchProvider
from piespector.ui.rendering_helpers import preview_syntax_language
from piespector.ui.command_line_content import build_command_line_text
from piespector.ui.help_panel import PiespectorHelpPanel
from piespector.ui.selection import selected_element_style
from piespector.state import HistoryEntry, RequestDefinition, RequestKeyValue, ResponseSummary
from textual.color import Color
from textual.command import CommandInput, CommandPalette
from textual.widgets import DataTable, Input, Label, Select, Static, TabbedContent, Tabs, TextArea
from textual.widgets._tabs import Underline
from textual.widgets._text_area import LanguageDoesNotExist


class FakeKeyEvent:
    def __init__(self, key: str, character: str | None = None) -> None:
        self.key = key
        self.character = character
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class FakeTextArea:
    def __init__(self) -> None:
        self._language: str | None = None

    @property
    def language(self) -> str | None:
        return self._language

    @language.setter
    def language(self, value: str | None) -> None:
        if value in {"graphql", "unknown-language"}:
            raise LanguageDoesNotExist("graphql unsupported")
        self._language = value


def render_plain(renderable, *, width: int = 120) -> str:
    console = Console(record=True, width=width, file=io.StringIO())
    console.print(renderable)
    return console.export_text()


class AppUiTests(unittest.TestCase):
    def test_app_uses_monokai_theme_by_default(self) -> None:
        app = PiespectorApp()

        self.assertEqual(app.theme, "monokai")

    def test_selected_element_style_uses_theme_blue_fill(self) -> None:
        app = PiespectorApp()

        style = selected_element_style(app, selected=True)

        self.assertIsNotNone(style)
        self.assertEqual(
            style.bgcolor.name,
            app.theme_variables["accent-darken-2"].lower(),
        )

    def test_auth_text_field_save_returns_to_auth_rows(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="old-token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_AUTH_SELECT"
        app.state.selected_auth_index = 2

        app.state.enter_home_auth_edit_mode()
        app.state.save_selected_auth_field("new-token")

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 2)
        self.assertEqual(request.auth_bearer_token, "new-token")

    def test_opening_auth_section_enters_auth_rows_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"

        app.home_controller.enter_current_home_value_select_mode()

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 0)

    def test_auth_type_edit_e_closes_dropdown_without_advancing_focus(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"
        app.state.mode = "HOME_AUTH_TYPE_EDIT"
        app.state.selected_auth_index = 0
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.auth.handle_home_auth_type_edit_key(event)

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 0)
        self.assertTrue(event.stopped)

    def test_section_select_j_enters_auth_rows_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"
        app.state.mode = "HOME_SECTION_SELECT"
        event = FakeKeyEvent("j")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.navigation.handle_home_section_select_key(event)

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 0)
        self.assertTrue(event.stopped)

    def test_collections_e_on_request_pins_request_and_stays_in_collections(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.ensure_request_workspace()
        app.state._set_selected_sidebar_by_request_id(request.request_id)
        app.state.open_selected_request(pin=False)
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_viewport"):
            handled = app.home_controller.handle_home_view_key(event)

        self.assertTrue(handled)
        self.assertEqual(app.state.mode, "NORMAL")
        self.assertEqual(app.state.active_request_id, request.request_id)
        self.assertIn(request.request_id, app.state.open_request_ids)
        self.assertTrue(event.stopped)

    def test_request_select_l_moves_to_auth_block(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "request"
        app.state.mode = "HOME_REQUEST_SELECT"
        event = FakeKeyEvent("l")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.request.handle_home_request_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "auth")
        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertTrue(event.stopped)

    def test_request_select_k_on_first_field_returns_to_section_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "request"
        app.state.mode = "HOME_REQUEST_SELECT"
        app.state.selected_request_field_index = 0
        event = FakeKeyEvent("k")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.request.handle_home_request_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "request")
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertTrue(event.stopped)

    def test_jump_to_method_opens_top_bar_method_selector_not_dropdown(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_SECTION_SELECT"

        app.interaction_controller._open_home_top_bar_jump_target("method")

        self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")
        self.assertEqual(app.state.selected_top_bar_field, "method")

    def test_method_selector_e_opens_method_dropdown(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_REQUEST_METHOD_SELECT"
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.request.handle_home_request_method_select_key(event)

        self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_EDIT")
        self.assertTrue(event.stopped)

    def test_jump_to_url_opens_top_bar_url_inline_edit(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_SECTION_SELECT"

        app.interaction_controller._open_home_top_bar_jump_target("url")

        self.assertEqual(app.state.mode, "HOME_URL_EDIT")

    def test_app_on_key_method_selector_e_and_escape_work(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")

        with patch.object(app, "_refresh_screen"):
            app.on_key(FakeKeyEvent("e"))
        self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_EDIT")

        with patch.object(app, "_refresh_screen"):
            app.on_key(FakeKeyEvent("escape"))
        self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")

        with patch.object(app, "_refresh_screen"):
            app.on_key(FakeKeyEvent("escape"))
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")

    def test_app_on_key_url_edit_escape_does_not_leave_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_SECTION_SELECT"
        app.state.enter_home_url_edit_mode()

        with patch.object(app, "_refresh_screen"):
            app.on_key(FakeKeyEvent("escape"))
        self.assertEqual(app.state.mode, "HOME_URL_EDIT")

    def test_method_selector_does_not_block_jump_action(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health", method="GET")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")

        self.assertTrue(app.check_action("enter_jump_mode", ()))

    def test_method_dropdown_escape_returns_to_method_selector(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_REQUEST_METHOD_SELECT"
        app.state.enter_home_method_edit_mode()
        event = FakeKeyEvent("escape")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.request.handle_home_request_method_edit_key(event)

        self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")
        self.assertTrue(event.stopped)

    def test_params_select_l_moves_to_headers_block(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            query_items=[],
            header_items=[],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_PARAMS_SELECT"
        event = FakeKeyEvent("l")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.params.handle_home_params_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "headers")
        self.assertEqual(app.state.mode, "HOME_HEADERS_SELECT")
        self.assertTrue(event.stopped)

    def test_params_select_k_on_first_row_returns_to_section_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            query_items=[RequestKeyValue(key="page", value="1")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_PARAMS_SELECT"
        app.state.selected_param_index = 0
        event = FakeKeyEvent("k")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.params.handle_home_params_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "params")
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertTrue(event.stopped)

    def test_params_select_shift_l_keeps_params_block_and_moves_field(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            query_items=[],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_PARAMS_SELECT"
        app.state.selected_param_field_index = 0
        event = FakeKeyEvent("L")

        with patch.object(app, "_refresh_home_request_panel"):
            app.home_controller.params.handle_home_params_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "params")
        self.assertEqual(app.state.selected_param_field_index, 1)
        self.assertEqual(app.state.mode, "HOME_PARAMS_SELECT")
        self.assertTrue(event.stopped)

    def test_params_select_right_arrow_does_not_move_field(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            query_items=[],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_PARAMS_SELECT"
        app.state.selected_param_field_index = 0
        event = FakeKeyEvent("right")

        with patch.object(app, "_refresh_home_request_panel") as refresh_panel:
            app.home_controller.params.handle_home_params_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "params")
        self.assertEqual(app.state.selected_param_field_index, 0)
        self.assertEqual(app.state.mode, "HOME_PARAMS_SELECT")
        refresh_panel.assert_not_called()
        self.assertFalse(event.stopped)

    def test_creating_param_keeps_focus_on_new_row_key(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(query_items=[])
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_PARAMS_SELECT"
        app.state.selected_param_index = 0
        app.state.selected_param_field_index = 0
        app.state.enter_home_params_edit_mode(creating=True)

        saved_key = app.state.save_selected_param_field("page")

        self.assertEqual(saved_key, "page")
        self.assertEqual(app.state.mode, "HOME_PARAMS_SELECT")
        self.assertEqual(app.state.selected_param_index, 0)
        self.assertEqual(app.state.selected_param_field_index, 0)
        self.assertEqual(request.query_items[0].key, "page")
        self.assertEqual(request.query_items[0].value, "")

    def test_response_select_j_scrolls_response(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_RESPONSE_SELECT"
        event = FakeKeyEvent("j")

        with patch.object(app, "_refresh_viewport"):
            app.home_controller.response.handle_home_response_select_key(event)

        self.assertEqual(app.state.response_scroll_offset, 1)
        self.assertTrue(event.stopped)

    def test_opening_body_section_enters_body_rows_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="form-data",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"

        app.home_controller.enter_current_home_value_select_mode()

        self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
        self.assertEqual(app.state.selected_body_index, 0)

    def test_auth_select_k_on_type_row_returns_to_section_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_token="token",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"
        app.state.mode = "HOME_AUTH_SELECT"
        app.state.selected_auth_index = 0
        event = FakeKeyEvent("k")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.auth.handle_home_auth_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "auth")
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertTrue(event.stopped)

    def test_creating_header_keeps_focus_on_new_row_key(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(header_items=[])
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_HEADERS_SELECT"
        app.state.selected_header_index = 0
        app.state.selected_header_field_index = 0
        app.state.enter_home_headers_edit_mode(creating=True)

        saved_key = app.state.save_selected_header_field("X-Trace-Id")

        self.assertEqual(saved_key, "X-Trace-Id")
        self.assertEqual(app.state.mode, "HOME_HEADERS_SELECT")
        self.assertEqual(app.state.selected_header_index, 0)
        self.assertEqual(app.state.selected_header_field_index, 0)
        self.assertEqual(request.header_items[0].key, "X-Trace-Id")
        self.assertEqual(request.header_items[0].value, "")

    def test_headers_select_shift_l_keeps_headers_block_and_moves_field(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            header_items=[],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "headers"
        app.state.mode = "HOME_HEADERS_SELECT"
        app.state.selected_header_field_index = 0
        event = FakeKeyEvent("L")

        with patch.object(app, "_refresh_home_request_panel"):
            app.home_controller.headers.handle_home_headers_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "headers")
        self.assertEqual(app.state.selected_header_field_index, 1)
        self.assertEqual(app.state.mode, "HOME_HEADERS_SELECT")
        self.assertTrue(event.stopped)

    def test_headers_select_k_on_first_row_returns_to_section_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            header_items=[RequestKeyValue(key="Accept", value="application/json")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "headers"
        app.state.mode = "HOME_HEADERS_SELECT"
        app.state.selected_header_index = 0
        event = FakeKeyEvent("k")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.headers.handle_home_headers_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "headers")
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertTrue(event.stopped)

    def test_body_select_e_on_type_row_opens_body_type_dropdown(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="form-data",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 0
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.body.handle_home_body_select_key(event)

        self.assertEqual(app.state.mode, "HOME_BODY_TYPE_EDIT")
        self.assertEqual(app.state.selected_body_index, 0)
        self.assertTrue(event.stopped)

    def test_body_select_k_on_type_row_returns_to_section_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="form-data",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 0
        event = FakeKeyEvent("k")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.body.handle_home_body_select_key(event)

        self.assertEqual(app.state.home_editor_tab, "body")
        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertTrue(event.stopped)

    def test_body_type_edit_e_on_raw_closes_dropdown_without_opening_editor(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="raw",
            raw_subtype="json",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_TYPE_EDIT"
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.body.handle_home_body_type_edit_key(event)

        self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
        self.assertEqual(app.state.selected_body_index, 0)
        self.assertTrue(event.stopped)

    def test_raw_body_select_e_on_subtype_row_opens_raw_subtype_dropdown(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="raw",
            raw_subtype="json",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 1
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen") as refresh_screen:
            app.home_controller.body.handle_home_body_select_key(event)

        self.assertEqual(app.state.mode, "HOME_BODY_RAW_TYPE_EDIT")
        self.assertEqual(app.state.selected_body_index, 1)
        refresh_screen.assert_called_once()
        self.assertTrue(event.stopped)

    def test_raw_body_subtype_edit_e_closes_dropdown_without_opening_editor(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="raw",
            raw_subtype="javascript",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_RAW_TYPE_EDIT"
        app.state.selected_body_index = 1
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.body.handle_home_body_raw_type_edit_key(event)

        self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
        self.assertEqual(app.state.selected_body_index, 1)
        self.assertTrue(event.stopped)

    def test_raw_body_select_e_on_body_row_opens_body_editor(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            body_type="raw",
            raw_subtype="javascript",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 2
        event = FakeKeyEvent("e")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.body.handle_home_body_select_key(event)

        self.assertEqual(app.state.mode, "HOME_BODY_TEXTAREA")
        self.assertTrue(event.stopped)

    def test_auth_option_field_close_returns_to_auth_rows(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            auth_type="oauth2-client-credentials",
            auth_oauth_token_url="https://example.com/oauth/token",
            auth_oauth_client_id="client-id",
            auth_oauth_client_secret="client-secret",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_AUTH_SELECT"
        app.state.selected_auth_index = 4

        app.state.enter_home_auth_edit_mode()
        self.assertEqual(app.state.mode, "HOME_AUTH_LOCATION_EDIT")

        app.state.leave_home_auth_location_edit_mode()

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 4)

    def test_binary_body_editor_copy_is_path_oriented(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Upload", body_type="binary")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        self.assertEqual(app._body_editor_header_text(), "Binary File Path  [Upload]")
        self.assertEqual(
            app._body_editor_footer_text(),
            "Enter or paste a file path. Ctrl+S saves, Esc cancels.",
        )

    def test_graphql_body_editor_copy_is_graphql_oriented(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Graph", body_type="graphql")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        self.assertEqual(app._body_editor_header_text(), "GraphQL Editor  [Graph]")
        self.assertEqual(
            app._body_editor_footer_text(),
            "Edit the GraphQL document. Ctrl+S saves, Esc cancels.",
        )

    def test_copy_active_request_url_uses_resolved_url(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Health",
            url="{{BASE_URL}}/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.env_pairs = {"BASE_URL": "https://example.com"}

        with patch.object(app, "_copy_text", return_value=True), patch.object(
            app,
            "_refresh_command_line",
        ):
            app.action_copy_active_request_url()

        self.assertEqual(app.state.message, "Copied resolved URL.")

    def test_binary_body_uses_input_widget_not_textarea_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Upload",
            body_type="binary",
            body_text="/tmp/payload.bin",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.selected_body_index = 1

        app.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")

        # Binary body edit now uses a real Input widget (not edit_buffer).
        # The mode is set correctly; the render syncs the Input with body_text.
        self.assertEqual(app.state.mode, "HOME_BODY_EDIT")

    def test_binary_body_edit_command_line_shows_editing_hint(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Upload", body_type="binary")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.selected_body_index = 1
        app.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")

        rendered = build_command_line_text(app.state).plain

        self.assertIn("Editing path", rendered)

    def test_switching_between_raw_subtypes_restores_each_subtype_body(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Script",
            body_type="raw",
            raw_subtype="javascript",
            body_text="console.log('hi')",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        app.state.cycle_raw_subtype(-1)
        self.assertEqual(request.raw_subtype, "html")
        self.assertEqual(request.body_text, "")

        request.body_text = "<p>hello</p>"
        request.sync_active_body_text()

        app.state.cycle_raw_subtype(1)
        self.assertEqual(request.raw_subtype, "javascript")
        self.assertEqual(request.body_text, "console.log('hi')")

    def test_switching_between_raw_and_graphql_restores_each_body(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(
            name="Graph",
            body_type="raw",
            raw_subtype="javascript",
            body_text="console.log('hi')",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        app.state.cycle_body_type(1)
        self.assertEqual(request.body_type, "graphql")
        self.assertEqual(request.body_text, "")

        request.body_text = "query Health { health }"
        request.sync_active_body_text()

        app.state.cycle_body_type(-1)
        self.assertEqual(request.body_type, "raw")
        self.assertEqual(request.body_text, "console.log('hi')")

    def test_request_body_syntax_language_covers_graphql_and_raw_variants(self) -> None:
        self.assertEqual(
            request_body_syntax_language(RequestDefinition(body_type="graphql")),
            "graphql",
        )
        self.assertEqual(
            request_body_syntax_language(
                RequestDefinition(body_type="raw", raw_subtype="html")
            ),
            "html",
        )
        self.assertEqual(
            request_body_syntax_language(
                RequestDefinition(body_type="raw", raw_subtype="javascript")
            ),
            "javascript",
        )

    def test_detect_text_syntax_language_handles_html_javascript_and_graphql(self) -> None:
        self.assertEqual(
            detect_text_syntax_language("<!DOCTYPE html><html></html>"),
            "html",
        )
        self.assertEqual(
            detect_text_syntax_language("const api = () => fetch('/health');"),
            "javascript",
        )
        self.assertEqual(
            detect_text_syntax_language("query Health { health }"),
            "graphql",
        )

    def test_text_area_syntax_language_maps_graphql_to_supported_editor_language(self) -> None:
        self.assertEqual(text_area_syntax_language("graphql"), "piespector-graphql")
        self.assertEqual(text_area_syntax_language("html"), "html")

    def test_preview_syntax_language_uses_html_lexer_for_xml_preview(self) -> None:
        self.assertEqual(preview_syntax_language("xml"), "html")
        self.assertEqual(preview_syntax_language("javascript"), "javascript")

    def test_text_area_language_falls_back_to_plain_text_for_unknown_language(self) -> None:
        app = PiespectorApp()
        editor = FakeTextArea()

        app._set_text_area_language(editor, "unknown-language")

        self.assertIsNone(editor.language)


class AppMountedWidgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_tab_advances_focus_in_normal_mode(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            sidebar_tree = app.screen.query_one("#sidebar-tree")
            sidebar_tree.focus()
            await pilot.pause()

            self.assertIs(app.focused, sidebar_tree)

            await pilot.press("tab")
            await pilot.pause()

            self.assertIsNotNone(app.focused)
            self.assertIsNot(app.focused, sidebar_tree)

    async def test_home_focus_highlight_tracks_selected_section(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            url_bar = app.screen.query_one("#url-bar-container")
            sidebar_container = app.screen.query_one("#sidebar-container")
            request_panel = app.screen.query_one("#request-panel")
            response_panel = app.screen.query_one("#response-panel")

            self.assertTrue(sidebar_container.has_class("piespector-focus-frame"))
            self.assertFalse(url_bar.has_class("piespector-focus-frame"))
            self.assertFalse(request_panel.has_class("piespector-focus-frame"))
            self.assertFalse(response_panel.has_class("piespector-focus-frame"))
            self.assertFalse(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(response_panel.has_class("piespector-tab-select"))

            app.state.mode = "HOME_SECTION_SELECT"
            app._refresh_screen()
            await pilot.pause()

            self.assertTrue(request_panel.has_class("piespector-focus-frame"))
            self.assertTrue(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(response_panel.has_class("piespector-tab-select"))

            app.state.mode = "HOME_REQUEST_SELECT"
            app._refresh_screen()
            await pilot.pause()

            self.assertFalse(sidebar_container.has_class("piespector-focus-frame"))
            self.assertTrue(request_panel.has_class("piespector-focus-frame"))
            self.assertFalse(request_panel.has_class("piespector-tab-select"))

            app.state.mode = "HOME_RESPONSE_SELECT"
            app._refresh_screen()
            await pilot.pause()

            self.assertFalse(request_panel.has_class("piespector-focus-frame"))
            self.assertTrue(response_panel.has_class("piespector-focus-frame"))
            self.assertTrue(response_panel.has_class("piespector-tab-select"))

            app.state.mode = "HOME_REQUEST_METHOD_SELECT"
            app._refresh_screen()
            await pilot.pause()

            self.assertFalse(response_panel.has_class("piespector-focus-frame"))
            self.assertTrue(url_bar.has_class("piespector-focus-frame"))
            self.assertFalse(response_panel.has_class("piespector-tab-select"))

    async def test_section_select_k_returns_from_params_rows_to_tab_highlight(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="List",
            query_items=[RequestKeyValue(key="page", value="1")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_SECTION_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            request_panel = app.screen.query_one("#request-panel")
            table = app.screen.query_one("#request-params-table", DataTable)

            self.assertTrue(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(table.has_focus)

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_PARAMS_SELECT")
            self.assertTrue(table.has_focus)

            await pilot.press("k")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
            self.assertTrue(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(table.has_focus)

    async def test_jump_mode_tab_still_opens_home_collections(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        app.state.current_tab = "env"
        app.state.mode = "ENV_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            app.action_enter_jump_mode()
            await pilot.pause()

            await pilot.press("tab")
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "home")
            self.assertEqual(app.state.mode, "NORMAL")

    async def test_home_jump_mode_highlights_all_visible_jump_blocks(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            app.action_enter_jump_mode()
            await pilot.pause()

            home_screen = app._home_screen
            url_bar = home_screen.query_one("#url-bar-container")
            sidebar_container = home_screen.query_one("#sidebar-container")
            request_panel = home_screen.query_one("#request-panel")
            response_panel = home_screen.query_one("#response-panel")

            self.assertTrue(url_bar.has_class("piespector-focus-frame"))
            self.assertTrue(sidebar_container.has_class("piespector-focus-frame"))
            self.assertTrue(request_panel.has_class("piespector-focus-frame"))
            self.assertTrue(response_panel.has_class("piespector-focus-frame"))
            self.assertFalse(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(response_panel.has_class("piespector-tab-select"))

    async def test_jump_mode_uses_home_labels_and_removes_overlay_widgets(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app.action_enter_jump_mode()
            await pilot.pause()

            labels = list(app.screen.query(".jump-overlay__label"))
            rendered = {str(label.content) for label in labels}

            self.assertTrue(app.screen.is_modal)
            self.assertGreaterEqual(len(labels), 10)
            self.assertSetEqual(
                {"tab", "1", "2", "q", "w", "e", "r", "t", "a", "s"},
                rendered,
            )

    async def test_home_jump_overlay_selects_target_and_closes_modal(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)

            await pilot.press("r")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
            self.assertEqual(app.state.home_editor_tab, "headers")
            request_panel = app.screen.query_one("#request-panel")
            headers_table = app.screen.query_one("#request-headers-table", DataTable)
            self.assertTrue(request_panel.has_class("piespector-tab-select"))
            self.assertFalse(headers_table.has_focus)

    async def test_home_jump_overlay_escape_dismisses_jump_mode(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)
            self.assertEqual(app.state.mode, "JUMP")

            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertNotEqual(app.state.mode, "JUMP")

    async def test_home_jump_overlay_footer_uses_both_bottom_rows(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            overlay = app.screen
            footer = overlay.query_one("#jump-overlay-footer")
            dismiss = overlay.query_one("#jump-overlay-dismiss")
            home_screen = app.get_screen("home")
            command_line = home_screen.query_one("#command-line")
            status_line = home_screen.query_one("#status-line")

            self.assertEqual(footer.region.y, command_line.region.y)
            self.assertEqual(dismiss.region.y, status_line.region.y)
            self.assertLess(footer.region.y, dismiss.region.y)

    async def test_home_jump_overlay_tab_jumps_to_collections(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_SECTION_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)

            await pilot.press("tab")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.mode, "NORMAL")

    async def test_home_jump_overlay_positions_request_key_above_tab_row(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            labels = list(app.screen.query(".jump-overlay__label"))
            request_tab = app._home_screen.query_one("ContentTab")
            q_label = next(label for label in labels if str(label.content) == "q")

            self.assertLess(q_label.region.y, request_tab.region.y)

    async def test_home_jump_overlay_omits_top_bar_targets_without_active_request(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o")
            await pilot.pause()

            labels = {
                str(label.content)
                for label in app.screen.query(".jump-overlay__label")
            }

            self.assertNotIn("1", labels)
            self.assertNotIn("2", labels)
            self.assertIn("tab", labels)

    async def test_home_jump_overlay_can_reopen_from_url_edit(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+o", "2")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_URL_EDIT")
            self.assertFalse(app.screen.is_modal)
            inline_input = app.screen.query_one("#url-input", Input)
            self.assertTrue(inline_input.has_focus)

            original_value = inline_input.value
            await pilot.press("x")
            await pilot.pause()

            self.assertEqual(inline_input.value, f"{original_value}x")

            await pilot.press("ctrl+o")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)

    async def test_home_mode_hides_top_bar_subtitle(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            url_bar = app.screen.query_one("#url-bar-container")
            url_bar_subtitle = app.screen.query_one("#url-bar-subtitle", Static)

            self.assertFalse(url_bar_subtitle.display)
            self.assertEqual(url_bar.region.height, 5)

    async def test_home_top_bar_aligns_with_sidebar_border_and_uses_balanced_gaps(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            open_request_tabs = app.screen.query_one("#open-request-tabs")
            method_select = app.screen.query_one("#method-select", Select)
            url_line = app.screen.query_one("#url-line")
            home_workspace = app.screen.query_one("#home-workspace")
            sidebar_container = app.screen.query_one("#sidebar-container")
            sidebar_tree = app.screen.query_one("#sidebar-tree")
            active_tab = app.screen.query_one("#tabs-list > Tab")
            method_children = list(method_select.walk_children(with_self=False))
            method_label = next(
                child
                for child in method_children
                if getattr(child, "id", None) == "label"
            )

            gap_above_method_row = url_line.region.y - (
                open_request_tabs.region.y + open_request_tabs.region.height
            )
            gap_below_method_row = home_workspace.region.y - (
                url_line.region.y + url_line.region.height
            )

            self.assertEqual(gap_above_method_row, 0)
            self.assertEqual(gap_below_method_row, 1)
            self.assertEqual(open_request_tabs.region.x, method_select.region.x)
            self.assertEqual(open_request_tabs.region.x, sidebar_container.region.x + 1)
            self.assertEqual(method_select.region.x, sidebar_container.region.x + 1)
            self.assertGreater(sidebar_tree.region.x, sidebar_container.region.x)
            self.assertEqual(
                method_label.region.x,
                active_tab.region.x + active_tab.styles.padding.left,
            )

    async def test_request_params_tab_uses_datatable_and_tracks_cursor(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="List",
            query_items=[
                RequestKeyValue(key="page", value="1", enabled=True),
                RequestKeyValue(key="draft", value="true", enabled=False),
            ],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "params"
        app.state.mode = "HOME_PARAMS_SELECT"
        app.state.selected_param_index = 1

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            table = app.screen.query_one("#request-params-table", DataTable)
            self.assertTrue(table.display)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(table.cursor_row, 1)
            first_row = table.get_row_at(0)
            rendered_row = [getattr(cell, "plain", str(cell)) for cell in first_row]
            self.assertEqual(rendered_row[2], "page")
            self.assertEqual(rendered_row[3], "1")

            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(app.state.selected_param_index, 0)
            self.assertEqual(table.cursor_row, 0)

    async def test_request_headers_row_selected_enters_inline_input_mode(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            header_items=[RequestKeyValue(key="Accept", value="application/json")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "headers"
        app.state.mode = "HOME_HEADERS_SELECT"
        app.state.selected_header_index = 0

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            table = app.screen.query_one("#request-headers-table", DataTable)
            self.assertTrue(table.display)
            table.action_select_cursor()
            await pilot.pause()

            inline_input = app.screen.query_one("#request-headers-input", Input)
            self.assertEqual(app.state.mode, "HOME_HEADERS_EDIT")
            self.assertTrue(inline_input.display)
            self.assertEqual(inline_input.value, "Accept")

    async def test_request_name_input_submission_persists_request_name(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "request"
        app.state.mode = "HOME_REQUEST_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()

            inline_input = app.screen.query_one("#request-overview-input", Input)
            self.assertTrue(inline_input.display)
            inline_input.value = "Health Check"
            await inline_input.action_submit()
            await pilot.pause()

            self.assertEqual(request.name, "Health Check")
            self.assertEqual(app.state.mode, "HOME_REQUEST_SELECT")

    async def test_url_input_submission_persists_request_url(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_url_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            inline_input = app.screen.query_one("#url-input", Input)
            self.assertTrue(inline_input.display)
            self.assertTrue(inline_input.has_focus)
            inline_input.value = "https://example.com/ready"
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(request.url, "https://example.com/ready")
            self.assertEqual(app.state.mode, "NORMAL")

    async def test_url_input_escape_does_not_cancel_edit(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_url_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            inline_input = app.screen.query_one("#url-input", Input)
            self.assertTrue(inline_input.display)
            self.assertTrue(inline_input.has_focus)

            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_URL_EDIT")
            self.assertTrue(inline_input.display)

    async def test_ctrl_p_opens_command_palette(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()

            self.assertTrue(CommandPalette.is_open(app))
            self.assertIsInstance(app.screen.query_one(CommandInput), CommandInput)

    async def test_slash_opens_workspace_search_and_navigates_to_request(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        app._persist_requests = lambda: None
        app.state.current_tab = "env"
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        folder = FolderDefinition(folder_id="f1", name="Auth", collection_id=collection.collection_id)
        request = RequestDefinition(
            request_id="r1",
            name="OAuth Protected",
            collection_id=collection.collection_id,
            folder_id=folder.folder_id,
        )
        app.state.collections = [collection]
        app.state.folders = [folder]
        app.state.requests = [request]
        app.state.ensure_request_workspace()

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("/")
            await pilot.pause()

            command_input = app.screen.query_one(CommandInput)
            command_input.value = "dautho"
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "home")
            self.assertEqual(app.state.active_request_id, request.request_id)
            self.assertEqual(app.state.message, "Opened request OAuth Protected.")
            self.assertFalse(CommandPalette.is_open(app))

    async def test_command_palette_submission_runs_help_system_command(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            app.action_command_palette()
            await pilot.pause()

            command_input = app.screen.query_one(CommandInput)
            command_input.value = "help"
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "home")
            self.assertTrue(app.screen.query(PiespectorHelpPanel))
            self.assertIsInstance(
                app.screen.query_one(PiespectorHelpPanel),
                PiespectorHelpPanel,
            )

    async def test_command_palette_runs_typed_value_command(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        app._persist_requests = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            app.action_command_palette()
            await pilot.pause()

            command_input = app.screen.query_one(CommandInput)
            command_input.value = "new collection Desserts"
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual([collection.name for collection in app.state.collections], ["Desserts"])

    async def test_command_provider_does_not_shadow_exact_theme_system_command(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)):
            provider = PiespectorCommandProvider(app.screen)
            hits = [hit async for hit in provider.search("theme")]

            self.assertEqual(hits, [])

    async def test_command_provider_keeps_typed_value_command_fallback(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)):
            provider = PiespectorCommandProvider(app.screen)
            hits = [hit async for hit in provider.search("new collection Desserts")]

            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].text, "new collection Desserts")

    async def test_search_provider_matches_workspace_items_fuzzily(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        collection = CollectionDefinition(collection_id="c1", name="Desserts")
        folder = FolderDefinition(folder_id="f1", name="Auth", collection_id=collection.collection_id)
        nested_folder = FolderDefinition(
            folder_id="f2",
            name="Nested",
            collection_id=collection.collection_id,
            parent_folder_id=folder.folder_id,
        )
        request = RequestDefinition(
            request_id="r1",
            name="OAuth Protected",
            collection_id=collection.collection_id,
            folder_id=nested_folder.folder_id,
        )
        app.state.collections = [collection]
        app.state.folders = [folder, nested_folder]
        app.state.requests = [request]
        app.state.ensure_request_workspace()

        async with app.run_test(size=(140, 40)):
            provider = PiespectorSearchProvider(app.screen)
            hits = [hit async for hit in provider.search("dautho")]

            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].text, "Desserts / Auth / Nested / OAuth Protected")

    async def test_theme_picker_selection_refreshes_app_css(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            initial_background = app.stylesheet._variables.get("background")

            app.action_change_theme()
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(app.theme, "atom-one-light")
            self.assertNotEqual(app.stylesheet._variables.get("background"), initial_background)

    async def test_method_selector_hover_uses_theme_accent_outline(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            method_select = app.screen.query_one("#method-select", Select)
            current = method_select.query_one("SelectCurrent")

            await pilot.hover("#method-select", offset=(1, 0))
            await pilot.pause()

            self.assertTrue(current.mouse_hover)
            self.assertEqual(current.styles.outline_top[0], "solid")
            self.assertEqual(
                current.styles.outline_top[1],
                Color.parse(app.theme_variables["accent"]),
            )

    async def test_select_overlay_highlight_uses_blue_selection_fill(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            method_select = app.screen.query_one("#method-select", Select)
            overlay = method_select.query_one("SelectOverlay")
            style = overlay.get_component_rich_style("option-list--option-highlighted")

            self.assertEqual(
                style.bgcolor.name,
                app.theme_variables["accent-darken-2"].lower(),
            )

    async def test_open_request_tabs_underline_uses_theme_accent(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.open_request_ids = [request.request_id]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tabs = app.screen.query_one("#open-request-tabs", Tabs)
            underline = tabs.query_one(Underline)
            style = underline.get_component_rich_style("underline--bar")
            active_tab = tabs.query_one("#tabs-list > Tab.-active")

            self.assertEqual(style.color.name, app.theme_variables["accent"].lower())
            self.assertEqual(active_tab.styles.background.a, 0)

    async def test_home_response_viewer_opens_modal_and_closes_to_response_select(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            last_response=ResponseSummary(
                status_code=200,
                elapsed_ms=12.3,
                body_length=11,
                body_text='{"ok":true}',
                response_headers=[("Content-Type", "application/json")],
            ),
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_RESPONSE_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app._open_response_viewer(origin_mode="HOME_RESPONSE_SELECT")
            await pilot.pause()

            editor = app.screen.query_one("#response-modal-editor", TextArea)
            self.assertTrue(app.screen.is_modal)
            self.assertIn('"ok"', editor.text)

            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.mode, "HOME_RESPONSE_SELECT")

    async def test_home_response_summary_shows_values_without_labels(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            last_response=ResponseSummary(
                status_code=404,
                elapsed_ms=12.3,
                body_length=11,
                body_text='{"error":"missing"}',
            ),
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            response_summary = app.screen.query_one("#response-summary", Static)

            self.assertEqual(str(response_summary.content), "404 Not Found   12.3 ms   11 B")

    async def test_home_response_error_moves_to_subtitle_row(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            last_response=ResponseSummary(
                status_code=500,
                elapsed_ms=12.3,
                body_length=1,
                body_text="{",
                error="HTTP Error 500: Internal Server Error",
            ),
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            response_note = app.screen.query_one("#response-note", Static)
            response_subtitle = app.screen.query_one("#response-subtitle", Static)

            self.assertFalse(response_note.display)
            self.assertEqual(str(response_note.content), "")
            self.assertEqual(
                str(response_subtitle.content),
                "Body  |  Lines 1-1 of 1  |  Error: HTTP Error 500: Internal Server Error",
            )

    async def test_history_response_viewer_opens_modal(self) -> None:
        app = PiespectorApp()
        app._load_history = lambda: None
        app._load_request_workspace = lambda: None
        app.state.current_tab = "history"
        app.state.history_entries = [
            HistoryEntry(
                history_id="h1",
                source_request_name="Health",
                source_request_path="Demo / Health",
                method="GET",
                url="https://example.com/health",
                auth_type="none",
                auth_location="header",
                auth_name="Authorization",
                request_headers=[("Accept", "application/json")],
                response_headers=[("Content-Type", "application/json")],
                response_body='{"ok":true}',
                status_code=200,
                response_size=11,
            )
        ]
        app.state.mode = "HISTORY_RESPONSE_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app._open_history_response_viewer(origin_mode="HISTORY_RESPONSE_SELECT")
            await pilot.pause()

            editor = app.screen.query_one("#response-modal-editor", TextArea)
            self.assertTrue(app.screen.is_modal)
            self.assertIn('"ok"', editor.text)

    async def test_body_text_editor_escape_restores_home_screen_visibility(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="text",
            body_text="initial body",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            app._open_body_text_editor(origin_mode="HOME_BODY_SELECT")
            await pilot.pause()

            home_screen = app.screen.query_one("#home-screen")
            editor = app.screen.query_one("#body-editor", TextArea)
            self.assertTrue(home_screen.has_class("hidden"))
            self.assertFalse(editor.has_class("hidden"))

            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
            self.assertFalse(home_screen.has_class("hidden"))
            self.assertTrue(editor.has_class("hidden"))

    async def test_body_text_editor_ctrl_s_restores_home_screen_visibility(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="text",
            body_text="initial body",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            app._open_body_text_editor(origin_mode="HOME_BODY_SELECT")
            await pilot.pause()

            home_screen = app.screen.query_one("#home-screen")
            editor = app.screen.query_one("#body-editor", TextArea)
            editor.load_text("updated body")

            await pilot.press("ctrl+s")
            await pilot.pause()

            self.assertEqual(request.body_text, "updated body")
            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
            self.assertFalse(home_screen.has_class("hidden"))
            self.assertTrue(editor.has_class("hidden"))

    async def test_form_body_tab_uses_datatable_with_add_row(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="form-data",
            body_form_items=[RequestKeyValue(key="file", value="@payload.bin")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 1

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            table = app.screen.query_one("#request-body-table", DataTable)
            self.assertTrue(table.display)
            self.assertEqual(table.row_count, 2)
            last_row = table.get_row_at(1)
            rendered_row = [getattr(cell, "plain", str(cell)) for cell in last_row]
            self.assertEqual(rendered_row[0], "+")
            self.assertEqual(rendered_row[2], "Add field")

    async def test_selected_raw_body_preview_keeps_title_and_height(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="json",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 1

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            body_preview = app.screen.query_one("#request-body-preview", Static)
            self.assertTrue(body_preview.display)
            width = max(body_preview.size.width or body_preview.region.width, 40)
            before = render_plain(getattr(body_preview, "_Static__content"), width=width)
            self.assertIn("Raw JSON", before)

            app.state.selected_body_index = 2
            app._refresh_screen()
            await pilot.pause()

            after = render_plain(getattr(body_preview, "_Static__content"), width=width)
            self.assertIn("Raw JSON", after)
            self.assertEqual(len(after.splitlines()), len(before.splitlines()))

    async def test_switching_between_raw_requests_keeps_body_preview_size(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        first = RequestDefinition(
            request_id="r1",
            name="One",
            body_type="raw",
            raw_subtype="json",
            body_text='{"a":1}',
        )
        second = RequestDefinition(
            request_id="r2",
            name="Two",
            body_type="raw",
            raw_subtype="json",
            body_text='{"b":2}',
        )
        app.state.requests = [first, second]
        app.state.open_request_ids = [first.request_id, second.request_id]
        app.state.active_request_id = first.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 2

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            body_preview = app.screen.query_one("#request-body-preview", Static)
            width = max(body_preview.size.width or body_preview.region.width, 40)
            before = render_plain(getattr(body_preview, "_Static__content"), width=width)
            self.assertIn("Raw JSON", before)

            app.state.cycle_open_request(1)
            app._refresh_screen()
            await pilot.pause()

            after = render_plain(getattr(body_preview, "_Static__content"), width=width)
            self.assertIn("Raw JSON", after)
            self.assertEqual(len(after.splitlines()), len(before.splitlines()))

    async def test_closing_body_editor_does_not_resize_preview_on_followup_frame(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="json",
            body_text='{"test":"test"}',
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 2

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            body_preview = app.screen.query_one("#request-body-preview", Static)
            width = max(body_preview.size.width or body_preview.region.width, 40)
            before = render_plain(getattr(body_preview, "_Static__content"), width=width)

            app._open_body_text_editor(origin_mode="HOME_BODY_SELECT")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            after_close = render_plain(getattr(body_preview, "_Static__content"), width=width)
            await pilot.pause()
            after_settle = render_plain(getattr(body_preview, "_Static__content"), width=width)

            self.assertEqual(len(after_close.splitlines()), len(before.splitlines()))
            self.assertEqual(after_settle, after_close)

    async def test_jumping_to_body_does_not_schedule_followup_preview_refresh(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="json",
            body_text='{"test":"test"}',
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        scheduled: list[str] = []
        original_call_after_refresh = app.call_after_refresh

        def record_call_after_refresh(callback, *args, **kwargs):
            scheduled.append(getattr(callback, "__name__", repr(callback)))
            return original_call_after_refresh(callback, *args, **kwargs)

        app.call_after_refresh = record_call_after_refresh

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            scheduled.clear()
            await pilot.press("ctrl+o", "t")
            await pilot.pause()

            self.assertEqual(app.state.home_editor_tab, "body")
            self.assertNotIn("refresh_home_request_panel", scheduled)

            body_preview = app.screen.query_one("#request-body-preview", Static)
            width = max(body_preview.size.width or body_preview.region.width, 40)
            rendered = render_plain(getattr(body_preview, "_Static__content"), width=width)
            self.assertIn("Raw JSON", rendered)
            self.assertEqual(
                len(rendered.splitlines()),
                body_preview.size.height or body_preview.region.height,
            )

    async def test_body_key_value_navigation_with_j_keeps_selector_and_rows_in_sync(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="form-data",
            body_form_items=[RequestKeyValue(key="file", value="@payload.bin")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.enter_home_section_select_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            table = app.screen.query_one("#request-body-table", DataTable)
            self.assertEqual(app.state.selected_body_index, 0)
            self.assertFalse(table.has_focus)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
            self.assertEqual(app.state.selected_body_index, 0)
            self.assertFalse(table.has_focus)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.selected_body_index, 1)
            self.assertTrue(table.has_focus)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.selected_body_index, 2)
            self.assertTrue(table.has_focus)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.selected_body_index, 0)
            self.assertFalse(table.has_focus)

    async def test_body_key_value_navigation_with_k_returns_to_selector_then_section_select(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="form-data",
            body_form_items=[RequestKeyValue(key="file", value="@payload.bin")],
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.mode = "HOME_BODY_SELECT"
        app.state.selected_body_index = 2

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            table = app.screen.query_one("#request-body-table", DataTable)
            self.assertTrue(table.has_focus)

            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(app.state.selected_body_index, 1)
            self.assertTrue(table.has_focus)

            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(app.state.selected_body_index, 0)
            self.assertFalse(table.has_focus)

            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
            self.assertFalse(table.has_focus)

    async def test_status_bar_uses_footer_widget_for_mode_hints_and_env(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_SECTION_SELECT"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            footer = app.screen.query_one("#status-line")
            mode_label = app.screen.query_one("#footer-mode", Label)
            context_label = app.screen.query_one("#footer-context", Label)
            env_key = app.screen.query_one("#footer-env-key", Label)
            env_value = app.screen.query_one("#footer-env-value", Label)
            hint_items = list(footer.query(".piespector-footer__hint"))

            self.assertEqual(str(mode_label.content), "SELECT")
            self.assertIn("Health", str(context_label.content))
            self.assertTrue(env_key.display)
            self.assertEqual(str(env_value.content), app.state.active_env_label())
            self.assertGreater(len(hint_items), 0)
            self.assertGreater(env_value.region.x, hint_items[-1].region.x)

    async def test_method_select_change_persists_request_method(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)
            select.value = "POST"
            await pilot.pause()

            self.assertEqual(request.method, "POST")
            self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")

    async def test_method_select_uses_compact_top_bar_width(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="OPTIONS",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)

            self.assertLess(select.size.width, 20)

    async def test_method_select_accepts_j_to_move_down(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)
            self.assertTrue(select.expanded)

            await pilot.press("j", "enter")
            await pilot.pause()

            self.assertEqual(request.method, "POST")
            self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")

    async def test_method_select_accepts_k_to_move_up(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="POST",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)
            self.assertTrue(select.expanded)

            await pilot.press("k", "enter")
            await pilot.pause()

            self.assertEqual(request.method, "GET")
            self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")

    async def test_method_select_accepts_e_to_confirm_highlighted_option(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)
            self.assertTrue(select.expanded)

            await pilot.press("j", "e")
            await pilot.pause()

            self.assertEqual(request.method, "POST")
            self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")

    async def test_method_select_confirming_same_value_exits_edit_mode_and_clears_focus(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#method-select", Select)
            self.assertTrue(select.expanded)

            await pilot.press("e")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_REQUEST_METHOD_SELECT")
            self.assertFalse(select.expanded)
            self.assertFalse(select.has_focus_within)

            await pilot.press("j")
            await pilot.pause()

            self.assertFalse(select.expanded)
            self.assertEqual(request.method, "GET")

    async def test_method_select_does_not_keep_focus_after_jumping_to_body(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            body_type="raw",
            raw_subtype="json",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_home_method_select_mode(origin_mode="HOME_SECTION_SELECT")
        app.state.enter_home_method_edit_mode()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            method_select = app.screen.query_one("#method-select", Select)
            self.assertTrue(method_select.expanded)

            await pilot.press("j")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(method_select.expanded)

            await pilot.press("ctrl+o", "t")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
            self.assertEqual(app.state.home_editor_tab, "body")
            self.assertFalse(method_select.has_focus_within)
            self.assertFalse(method_select.expanded)

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")
            self.assertEqual(app.state.selected_body_index, 0)

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(app.state.selected_body_index, 1)
            self.assertEqual(request.method, "GET")
            self.assertFalse(method_select.expanded)

    async def test_auth_type_select_change_persists_request_auth_type(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health", auth_type="none")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"
        app.state.enter_home_auth_select_mode()
        app.state.enter_home_auth_type_edit_mode(origin_mode="HOME_AUTH_SELECT")

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#auth-type-select", Select)
            select.value = "bearer"
            await pilot.pause()

            self.assertEqual(request.auth_type, "bearer")
            self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")

    async def test_auth_option_select_change_persists_api_key_location(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            auth_type="api-key",
            auth_api_key_location="header",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "auth"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app.state.enter_home_auth_select_mode()
            app.state.selected_auth_index = 1
            app.state.enter_home_auth_edit_mode()
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#auth-option-select", Select)
            self.assertTrue(select.display)
            select.value = "query"
            await pilot.pause()

            self.assertEqual(request.auth_api_key_location, "query")
            self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")

    async def test_body_type_select_change_persists_request_body_type(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Upload", body_type="none")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"
        app.state.enter_home_body_select_mode()
        app.state.enter_home_body_type_edit_mode(origin_mode="HOME_BODY_SELECT")

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#body-type-select", Select)
            select.value = "raw"
            await pilot.pause()

            self.assertEqual(request.body_type, "raw")
            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")

    async def test_raw_subtype_select_change_persists_request_raw_subtype(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="json",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "body"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app.state.enter_home_body_select_mode()
            app.state.selected_body_index = 1
            app.state.enter_home_body_raw_type_edit_mode(origin_mode="HOME_BODY_SELECT")
            app._refresh_screen()
            await pilot.pause()

            select = app.screen.query_one("#body-raw-type-select", Select)
            self.assertTrue(select.display)
            select.value = "html"
            await pilot.pause()

            self.assertEqual(request.raw_subtype, "html")
            self.assertEqual(app.state.mode, "HOME_BODY_SELECT")

    async def test_request_tabbed_content_activation_updates_state(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        request = RequestDefinition(request_id="r1", name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.home_editor_tab = "request"

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            tabs = app.screen.query_one("#request-tabs", TabbedContent)
            tabs.active = "headers"
            await pilot.pause()

            self.assertEqual(app.state.home_editor_tab, "headers")

    async def test_response_tabs_activation_updates_state(self) -> None:
        app = PiespectorApp()

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tabs = app.screen.query_one("#response-tabs", Tabs)
            tabs.active = "headers"
            await pilot.pause()

            self.assertEqual(app.state.selected_home_response_tab, "headers")

    async def test_widget_tree_mounts_and_switches_screens(self) -> None:
        app = PiespectorApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            app._refresh_screen()
            self.assertEqual(app.screen.query_one("#home-screen").id, "home-screen")
            sidebar_tree = app.screen.query_one("#sidebar-tree")
            self.assertEqual(sidebar_tree.id, "sidebar-tree")
            self.assertTrue(sidebar_tree.can_focus)

            app.state.switch_tab("env", "Env")
            app._switch_screen_visibility()
            app._refresh_screen()
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#env-screen").id, "env-screen")

            app.state.switch_tab("history", "History")
            app._switch_screen_visibility()
            app._refresh_screen()
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#history-screen").id, "history-screen")

    async def test_repeated_home_refresh_does_not_duplicate_open_request_tabs(self) -> None:
        app = PiespectorApp()

        async with app.run_test() as pilot:
            request = RequestDefinition(
                request_id="r1",
                name="Health",
                method="GET",
                url="https://example.com/health",
            )
            app.state.collections = []
            app.state.folders = []
            app.state.requests = [request]
            app.state.collapsed_collection_ids = set()
            app.state.collapsed_folder_ids = set()
            app.state.open_request_ids = [request.request_id]
            app.state.active_request_id = request.request_id
            app.state.current_tab = "home"

            app._refresh_screen()
            await pilot.pause()
            app._refresh_screen()
            await pilot.pause()

            tabs = app.screen.query_one("#open-request-tabs")
            self.assertEqual(tabs.tab_count, 1)
            self.assertEqual(tabs.active, "open-req-r1")

    async def test_closing_last_open_request_hides_top_bar_tab_strip(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            method="GET",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.open_request_ids = [request.request_id]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tabs = app.screen.query_one("#open-request-tabs", Tabs)
            self.assertTrue(tabs.display)
            self.assertEqual(tabs.tab_count, 1)

            app.state.close_active_request()
            app._refresh_screen()
            await pilot.pause()

            self.assertFalse(tabs.display)
            self.assertEqual(tabs.tab_count, 0)

    async def test_home_layout_keeps_top_bar_above_workspace_and_footer_visible(self) -> None:
        app = PiespectorApp()
        app._load_request_workspace = lambda: None

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            home_screen = app.screen.query_one("#home-screen")
            url_bar = app.screen.query_one("#url-bar-container")
            open_request_tabs = app.screen.query_one("#open-request-tabs")
            home_workspace = app.screen.query_one("#home-workspace")
            sidebar_container = app.screen.query_one("#sidebar-container")
            sidebar_tree = app.screen.query_one("#sidebar-tree")
            request_panel = app.screen.query_one("#request-panel")
            request_tabs = app.screen.query_one("#request-tabs")
            request_title = app.screen.query_one("#request-title")
            response_panel = app.screen.query_one("#response-panel")
            response_tabs = app.screen.query_one("#response-tabs")
            response_summary = app.screen.query_one("#response-summary")
            response_title = app.screen.query_one("#response-title")
            status_line = app.screen.query_one("#status-line")
            command_line = app.screen.query_one("#command-line")
            footer = app.screen.query_one("Footer")

            self.assertGreater(url_bar.region.x, home_screen.region.x)
            self.assertLess(url_bar.region.width, home_screen.region.width)
            self.assertFalse(open_request_tabs.display)
            self.assertGreater(home_workspace.region.y, url_bar.region.y)
            self.assertGreater(sidebar_container.region.x, home_screen.region.x + 1)
            self.assertGreater(sidebar_tree.region.x, sidebar_container.region.x + 1)
            self.assertGreater(request_panel.region.x, sidebar_container.region.x)
            self.assertGreater(request_tabs.region.x, request_panel.region.x + 1)
            self.assertGreater(request_tabs.region.y, request_title.region.y)
            self.assertGreater(response_tabs.region.x, response_panel.region.x + 1)
            self.assertEqual(response_summary.region.y, response_tabs.region.y)
            self.assertGreater(response_summary.region.x, response_tabs.region.x)
            self.assertGreater(response_tabs.region.y, response_title.region.y)
            self.assertGreater(home_workspace.region.y, url_bar.region.y + 1)
            self.assertLess(command_line.region.y, status_line.region.y)
            self.assertEqual(status_line.region.y, footer.region.y)

    async def test_sidebar_tree_cursor_tracks_selection_without_rebuild(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        requests = [
            RequestDefinition(request_id="r1", name="One", method="GET"),
            RequestDefinition(request_id="r2", name="Two", method="GET"),
            RequestDefinition(request_id="r3", name="Three", method="GET"),
        ]
        app.state.collections = []
        app.state.folders = []
        app.state.requests = requests
        app.state.collapsed_collection_ids = set()
        app.state.collapsed_folder_ids = set()
        app.state.selected_sidebar_index = 0
        app.state.open_request_ids = [requests[0].request_id]
        app.state.active_request_id = requests[0].request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tree = app.screen.query_one("#sidebar-tree")
            self.assertFalse(tree.show_root)
            self.assertTrue(tree.can_focus)
            self.assertEqual(tree.cursor_line, 0)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 1)
            self.assertEqual(tree.cursor_line, 1)

            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 2)
            self.assertEqual(tree.cursor_line, 2)

    async def test_sidebar_tree_arrow_keys_do_not_change_home_selection(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        requests = [
            RequestDefinition(request_id="r1", name="One", method="GET"),
            RequestDefinition(request_id="r2", name="Two", method="GET"),
            RequestDefinition(request_id="r3", name="Three", method="GET"),
        ]
        app.state.collections = []
        app.state.folders = []
        app.state.requests = requests
        app.state.collapsed_collection_ids = set()
        app.state.collapsed_folder_ids = set()
        app.state.selected_sidebar_index = 0
        app.state.open_request_ids = [request.request_id for request in requests[:2]]
        app.state.active_request_id = requests[0].request_id

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tree = app.screen.query_one("#sidebar-tree")
            self.assertEqual(tree.cursor_line, 0)

            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 0)
            self.assertEqual(tree.cursor_line, 0)
            self.assertEqual(app.state.active_request_id, requests[0].request_id)

            await pilot.press("up")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 0)
            self.assertEqual(tree.cursor_line, 0)
            self.assertEqual(app.state.active_request_id, requests[0].request_id)

            await pilot.press("right")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 0)
            self.assertEqual(tree.cursor_line, 0)
            self.assertEqual(app.state.active_request_id, requests[0].request_id)

            await pilot.press("left")
            await pilot.pause()
            self.assertEqual(app.state.selected_sidebar_index, 0)
            self.assertEqual(tree.cursor_line, 0)
            self.assertEqual(app.state.active_request_id, requests[0].request_id)

    async def test_keys_panel_bindings_include_home_navigation_shortcuts(self) -> None:
        app = PiespectorApp()

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            bindings = app.screen.active_bindings

            self.assertEqual(bindings["j"].binding.description, "Browse Down")
            self.assertEqual(bindings["k"].binding.description, "Browse Up")
            self.assertEqual(bindings["J"].binding.description, "Next Folder")
            self.assertEqual(bindings["K"].binding.description, "Previous Folder")
            self.assertEqual(bindings["ctrl+j"].binding.description, "Next Collection")
            self.assertEqual(bindings["ctrl+k"].binding.description, "Previous Collection")

    async def test_sidebar_tree_j_k_variants_jump_folders_and_collections(self) -> None:
        app = PiespectorApp()
        app._persist_requests = lambda: None
        app._load_request_workspace = lambda: None
        first_collection = CollectionDefinition(collection_id="c1", name="Alpha")
        second_collection = CollectionDefinition(collection_id="c2", name="Beta")
        first_folder = FolderDefinition(
            folder_id="f1",
            name="One",
            collection_id=first_collection.collection_id,
        )
        second_folder = FolderDefinition(
            folder_id="f2",
            name="Two",
            collection_id=first_collection.collection_id,
            parent_folder_id=first_folder.folder_id,
        )
        third_folder = FolderDefinition(
            folder_id="f3",
            name="Three",
            collection_id=second_collection.collection_id,
        )
        app.state.collections = [first_collection, second_collection]
        app.state.folders = [first_folder, second_folder, third_folder]
        app.state.requests = [
            RequestDefinition(
                request_id="r1",
                name="Collection Request",
                method="GET",
                collection_id=first_collection.collection_id,
            ),
            RequestDefinition(
                request_id="r2",
                name="Nested Request",
                method="GET",
                collection_id=first_collection.collection_id,
                folder_id=second_folder.folder_id,
            ),
            RequestDefinition(
                request_id="r3",
                name="Second Collection Request",
                method="GET",
                collection_id=second_collection.collection_id,
            ),
        ]
        app.state.collapsed_collection_ids = set()
        app.state.collapsed_folder_ids = set()
        app.state.selected_sidebar_index = 0

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            tree = app.screen.query_one("#sidebar-tree")
            app.state._set_selected_sidebar_node("collection", first_collection.collection_id)
            app._refresh_viewport()
            app._sync_home_sidebar_cursor()
            await pilot.pause()
            self.assertEqual(tree.cursor_line, 0)

            await pilot.press("ctrl+j")
            await pilot.pause()
            selected = app.state.get_selected_sidebar_node()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.kind, "collection")
            self.assertEqual(selected.node_id, second_collection.collection_id)
            self.assertEqual(tree.cursor_line, app.state.selected_sidebar_index)

            await pilot.press("ctrl+k")
            await pilot.pause()
            selected = app.state.get_selected_sidebar_node()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.kind, "collection")
            self.assertEqual(selected.node_id, first_collection.collection_id)
            self.assertEqual(tree.cursor_line, app.state.selected_sidebar_index)

            await pilot.press("J")
            await pilot.pause()
            selected = app.state.get_selected_sidebar_node()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.kind, "folder")
            self.assertEqual(selected.node_id, first_folder.folder_id)
            self.assertEqual(tree.cursor_line, app.state.selected_sidebar_index)

            await pilot.press("J")
            await pilot.pause()
            selected = app.state.get_selected_sidebar_node()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.kind, "folder")
            self.assertEqual(selected.node_id, second_folder.folder_id)
            self.assertEqual(tree.cursor_line, app.state.selected_sidebar_index)
            self.assertNotIn(first_folder.folder_id, app.state.collapsed_folder_ids)

            await pilot.press("K")
            await pilot.pause()
            selected = app.state.get_selected_sidebar_node()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.kind, "folder")
            self.assertEqual(selected.node_id, first_folder.folder_id)
            self.assertEqual(tree.cursor_line, app.state.selected_sidebar_index)


if __name__ == "__main__":
    unittest.main()
