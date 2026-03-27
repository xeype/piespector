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
            app._handle_command_key(event)

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

                app._handle_command_key(first_tab)
                first_completion = app.state.command_buffer

                app._handle_command_key(second_tab)
                second_completion = app.state.command_buffer

        self.assertEqual(first_completion, "import alpha.env")
        self.assertEqual(second_completion, "import alpine.env")
        self.assertTrue(first_tab.stopped)
        self.assertTrue(second_tab.stopped)


if __name__ == "__main__":
    unittest.main()
