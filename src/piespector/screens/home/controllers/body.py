from __future__ import annotations

from textual import events
from textual.app import ScreenStackError
from textual.css.query import NoMatches

from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler
from piespector.screens.home.request.body_pane import RequestBodyPane


class HomeBodyController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_BODY_SELECT: self.handle_home_body_select_key,
            MODE_HOME_BODY_TYPE_EDIT: self.handle_home_body_type_edit_key,
            MODE_HOME_BODY_RAW_TYPE_EDIT: self.handle_home_body_raw_type_edit_key,
            MODE_HOME_BODY_EDIT: self.handle_home_body_edit_key,
        }

    def _body_pane(self) -> RequestBodyPane:
        try:
            return self.app._query_current("#request-body-pane", RequestBodyPane)
        except (NoMatches, ScreenStackError):
            body_pane = RequestBodyPane()
            body_pane._piespector_app = self.app
            return body_pane

    def handle_home_body_select_key(self, event: events.Key) -> None:
        self._body_pane().handle_select_key(event)

    def handle_home_body_type_edit_key(self, event: events.Key) -> None:
        self._body_pane().handle_type_edit_key(event)

    def handle_home_body_raw_type_edit_key(self, event: events.Key) -> None:
        self._body_pane().handle_raw_type_edit_key(event)

    def handle_home_body_edit_key(self, event: events.Key) -> None:
        self._body_pane().handle_edit_key(event)
