from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from piespector.app import PiespectorApp


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


class AppCommandModeTests(unittest.TestCase):
    def test_command_mode_ctrl_v_pastes_clipboard_text(self) -> None:
        app = PiespectorApp()
        app.state.enter_command_mode()
        app.state.command_buffer = "import "
        event = FakeKeyEvent("ctrl+v", "\x16")

        with patch.object(app, "_paste_text", return_value="/tmp/My File.json\n"), patch.object(
            app,
            "_refresh_command_line",
        ):
            app.interaction_controller.handle_command_key(event)

        self.assertEqual(app.state.command_buffer, "import /tmp/My File.json")
        self.assertEqual(app.state.message, "Pasted.")
        self.assertTrue(event.stopped)

    def test_command_mode_tab_cycles_import_path_matches(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.command_context_mode = "NORMAL"
        app.state.mode = "COMMAND"

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "alpha.env").write_text("A=1\n", encoding="utf-8")
            (root / "alpine.env").write_text("A=2\n", encoding="utf-8")
            with chdir(root), patch.object(app, "_refresh_command_line"):
                app.state.command_buffer = "import al"
                first_tab = FakeKeyEvent("tab")
                second_tab = FakeKeyEvent("tab")

                app.interaction_controller.handle_command_key(first_tab)
                first_completion = app.state.command_buffer

                app.interaction_controller.handle_command_key(second_tab)
                second_completion = app.state.command_buffer

        self.assertEqual(first_completion, "import alpha.env")
        self.assertEqual(second_completion, "import alpine.env")
        self.assertTrue(first_tab.stopped)
        self.assertTrue(second_tab.stopped)

    def test_history_response_select_j_cycles_detail_block(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "history"
        app.state.mode = "HISTORY_RESPONSE_SELECT"
        app.state.selected_history_detail_block = "request"
        event = FakeKeyEvent("j")

        with patch.object(app, "_refresh_viewport"):
            app.history_controller.handle_history_response_select_key(event)

        self.assertEqual(app.state.selected_history_detail_block, "response")
        self.assertTrue(event.stopped)

    def test_history_response_select_h_and_l_cycle_tabs(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "history"
        app.state.mode = "HISTORY_RESPONSE_SELECT"
        app.state.selected_history_detail_block = "response"
        app.state.selected_history_response_tab = "body"
        left_event = FakeKeyEvent("h")
        right_event = FakeKeyEvent("l")

        with patch.object(app, "_refresh_viewport"):
            app.history_controller.handle_history_response_select_key(left_event)
            left_tab = app.state.selected_history_response_tab
            app.history_controller.handle_history_response_select_key(right_event)

        self.assertEqual(left_tab, "headers")
        self.assertEqual(app.state.selected_history_response_tab, "body")
        self.assertTrue(left_event.stopped)
        self.assertTrue(right_event.stopped)

    def test_auth_select_escape_returns_to_auth_type_tabs(self) -> None:
        app = PiespectorApp()
        app.state.home_editor_tab = "auth"
        request = PiespectorApp().state.get_active_request()
        if request is None:
            from piespector.state import RequestDefinition

            request = RequestDefinition(auth_type="bearer", auth_bearer_token="token")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_AUTH_SELECT"
        app.state.selected_auth_index = 2
        event = FakeKeyEvent("escape")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.auth.handle_home_auth_select_key(event)

        self.assertEqual(app.state.mode, "HOME_AUTH_TYPE_EDIT")
        self.assertEqual(app.state.auth_type_label(), "Bearer Token")
        self.assertTrue(event.stopped)


if __name__ == "__main__":
    unittest.main()
