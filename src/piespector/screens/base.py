from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Input, Static

from piespector.ui.overlays import build_overlay_widgets
from piespector.ui.footer import PiespectorFooter
from piespector.ui.input import PiespectorInput


class PiespectorScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="workspace"):
                yield from self.compose_workspace()
                for widget in build_overlay_widgets():
                    yield widget
            with Horizontal(id="command-line"):
                yield Static(":", id="command-prompt")
                yield Static("", id="command-line-content")
                yield PiespectorInput(
                    "",
                    id="command-input",
                    placeholder="Command",
                    compact=True,
                    select_on_focus=False,
                )
            yield PiespectorFooter(id="status-line")

    def compose_workspace(self) -> ComposeResult:
        raise NotImplementedError

    def on_mount(self) -> None:
        app = self.app
        if app is not None:
            app.overlay_controller.register_text_area_languages(self)
        self.query_one("#command-prompt", Static).display = False
        self.query_one("#command-input", Input).display = False

    def disable_focus(self, *widget_ids: str) -> None:
        for widget_id in widget_ids:
            try:
                self.query_one(f"#{widget_id}").can_focus = False
            except NoMatches:
                pass
