from __future__ import annotations

from textual import events
from textual.widgets import Static

from piespector.domain.editor import RESPONSE_TAB_BODY
from piespector.domain.modes import MODE_HOME_RESPONSE_SELECT, REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.interactions.keys import (
    KEY_ESCAPE,
    KEY_SCROLL_DOWN,
    KEY_VIEW,
    LEFT_KEYS,
    OPEN_KEYS,
    RESPONSE_SCROLL_KEYS,
    RIGHT_KEYS,
)
from piespector.screens.home import messages
from piespector.screens.home.controllers.base import HomeControllerBase
from piespector.screens.home.render import response_scroll_step


class HomeResponseController(HomeControllerBase):
    def handle_request_response_shortcuts(self, event: events.Key) -> bool:
        if self.state.mode in REQUEST_RESPONSE_SHORTCUT_MODES and event.key == KEY_VIEW:
            if self.state.enter_home_response_select_mode():
                self.app._refresh_screen()
            else:
                self.app._refresh_command_line()
            event.stop()
            return True

        if self.state.mode not in REQUEST_RESPONSE_SHORTCUT_MODES | {MODE_HOME_RESPONSE_SELECT}:
            return False

        if event.key in RESPONSE_SCROLL_KEYS:
            response_step = response_scroll_step(
                self.app.query_one("#viewport", Static).size.height
            )
            self.state.scroll_response(
                response_step if event.key == KEY_SCROLL_DOWN else -response_step
            )
            self.app._refresh_viewport()
            event.stop()
            return True

        return False

    def handle_home_response_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_response_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in LEFT_KEYS:
            self.state.cycle_home_response_tab(-1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            self.state.cycle_home_response_tab(1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self.state.selected_home_response_tab != RESPONSE_TAB_BODY:
                self.state.message = messages.HOME_RESPONSE_VIEWER_BODY_ONLY
                self.app._refresh_screen()
                event.stop()
                return
            self.app._open_response_viewer(origin_mode=MODE_HOME_RESPONSE_SELECT)
            event.stop()
