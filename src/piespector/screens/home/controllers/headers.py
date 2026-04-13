from __future__ import annotations

from textual import events

from piespector.domain.modes import MODE_HOME_HEADERS_EDIT, MODE_HOME_HEADERS_SELECT
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler
from piespector.screens.home.request.headers_pane import RequestHeadersPane


class HomeHeadersController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_HEADERS_SELECT: self.handle_home_headers_select_key,
            MODE_HOME_HEADERS_EDIT: self.handle_home_headers_edit_key,
        }

    def _headers_pane(self) -> RequestHeadersPane | None:
        home_screen = self.home_screen()
        if home_screen is None or not home_screen.is_mounted:
            return None
        return home_screen.query_one("#request-headers-pane", RequestHeadersPane)

    def handle_home_headers_select_key(self, event: events.Key) -> None:
        headers_pane = self._headers_pane()
        if headers_pane is not None:
            headers_pane.handle_select_key(event)

    def handle_home_headers_edit_key(self, event: events.Key) -> None:
        headers_pane = self._headers_pane()
        if headers_pane is not None:
            headers_pane.handle_edit_key(event)
