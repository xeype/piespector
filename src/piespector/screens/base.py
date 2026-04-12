from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Static

from piespector.ui.footer import PiespectorFooter
from piespector.ui.overlays import build_input_hint_widgets


class PiespectorScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="workspace"):
                yield from self.compose_workspace()
                for widget in build_input_hint_widgets():
                    yield widget
            with Horizontal(id="command-line"):
                yield Static("", id="command-line-content")
            yield PiespectorFooter(id="status-line")

    def compose_workspace(self) -> ComposeResult:
        raise NotImplementedError

    def on_mount(self) -> None:
        pass

    def disable_focus(self, *widget_ids: str) -> None:
        for widget_id in widget_ids:
            try:
                self.query_one(f"#{widget_id}").can_focus = False
            except NoMatches:
                pass
