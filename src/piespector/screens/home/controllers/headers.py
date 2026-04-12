from __future__ import annotations

from textual import events
from textual.app import ScreenStackError
from textual.css.query import NoMatches

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
        try:
            return self.app._query_current("#request-headers-pane", RequestHeadersPane)
        except (NoMatches, ScreenStackError):
            return None

    def handle_home_headers_select_key(self, event: events.Key) -> None:
        headers_pane = self._headers_pane()
        if headers_pane is not None:
            headers_pane.handle_select_key(event)

    def handle_home_headers_edit_key(self, event: events.Key) -> None:
        headers_pane = self._headers_pane()
        if headers_pane is not None:
            headers_pane.handle_edit_key(event)
