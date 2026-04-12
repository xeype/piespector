from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from piespector.screens.home import messages
from piespector.screens.home.request.request_options import render_request_options_editor

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestOptionsPane(Vertical):
    DEFAULT_CSS = """
    RequestOptionsPane {
        height: 1fr;
        layout: vertical;
    }
    """

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    def compose(self) -> ComposeResult:
        yield Static("", id="request-options-content")

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        content = self.query_one("#request-options-content", Static)

        if request is None:
            content.update(Text(messages.HOME_NO_ACTIVE_REQUEST))
            return

        content.update(render_request_options_editor(request, state))
