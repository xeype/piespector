from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector.app import PiespectorApp
from piespector.rendering import (
    detect_text_syntax_language,
    preview_syntax_language,
    render_command_line,
    request_body_syntax_language,
    syntax_theme_for_language,
    text_area_syntax_language,
)
from piespector.state import RequestDefinition
from textual.widgets._text_area import LanguageDoesNotExist


@contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


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


class AppUiTests(unittest.TestCase):
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
        app.state.set_edit_buffer("new-token", replace_on_next_input=False)
        app.state.save_selected_auth_field()

        self.assertEqual(app.state.mode, "HOME_AUTH_SELECT")
        self.assertEqual(app.state.selected_auth_index, 2)
        self.assertEqual(request.auth_bearer_token, "new-token")

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

    def test_binary_body_uses_inline_edit_buffer_not_textarea_mode(self) -> None:
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

        self.assertEqual(app.state.mode, "HOME_BODY_EDIT")
        self.assertEqual(app.state.edit_buffer, "/tmp/payload.bin")

    def test_binary_body_tab_completes_path_inline(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Upload", body_type="binary")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.selected_body_index = 1
        app.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "payload-a.bin").write_bytes(b"a")
            (root / "payload-b.bin").write_bytes(b"b")
            with chdir(root):
                app.state.set_edit_buffer("payload-", replace_on_next_input=False)
                first_tab = FakeKeyEvent("tab")
                second_tab = FakeKeyEvent("tab")

                with patch.object(app, "_refresh_screen"):
                    app._handle_inline_edit_key(first_tab)
                    first_completion = app.state.edit_buffer

                    app._handle_inline_edit_key(second_tab)
                    second_completion = app.state.edit_buffer

        self.assertEqual(first_completion, "payload-a.bin")
        self.assertEqual(second_completion, "payload-b.bin")
        self.assertTrue(first_tab.stopped)
        self.assertTrue(second_tab.stopped)

    def test_binary_body_command_line_shows_path_hint(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Upload", body_type="binary")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.selected_body_index = 1
        app.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "payload-a.bin").write_bytes(b"a")
            (root / "payload-b.bin").write_bytes(b"b")
            with chdir(root):
                app.state.set_edit_buffer("payload-", replace_on_next_input=False)
                rendered = render_command_line(app.state).plain

        self.assertIn("Path payload-|a.bin", rendered)
        self.assertIn("(+1 more)", rendered)

    def test_import_command_line_shows_path_hint(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.mode = "COMMAND"
        app.state.command_context_mode = "NORMAL"

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "My Env.env").write_text("A=1\n", encoding="utf-8")
            with chdir(root):
                app.state.command_buffer = 'import "My'
                rendered = render_command_line(app.state).plain

        self.assertIn(':import "My Env.env"', rendered)

    def test_import_command_line_shows_multiple_path_matches(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.mode = "COMMAND"
        app.state.command_context_mode = "NORMAL"

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "alpha.env").write_text("A=1\n", encoding="utf-8")
            (root / "alpine.env").write_text("A=2\n", encoding="utf-8")
            with chdir(root):
                app.state.command_buffer = "import al"
                rendered = render_command_line(app.state).plain

        self.assertIn(":import alpha.env", rendered)
        self.assertIn("(+1 more)", rendered)

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

    def test_syntax_theme_for_language_uses_graphql_specific_preview_theme(self) -> None:
        graphql_theme = syntax_theme_for_language("graphql")
        javascript_theme = syntax_theme_for_language("javascript")

        self.assertNotEqual(graphql_theme, javascript_theme)

    def test_preview_syntax_language_uses_html_lexer_for_xml_preview(self) -> None:
        self.assertEqual(preview_syntax_language("xml"), "html")
        self.assertEqual(preview_syntax_language("javascript"), "javascript")

    def test_text_area_language_falls_back_to_plain_text_for_unknown_language(self) -> None:
        app = PiespectorApp()
        editor = FakeTextArea()

        app._set_text_area_language(editor, "unknown-language")

        self.assertIsNone(editor.language)


if __name__ == "__main__":
    unittest.main()
