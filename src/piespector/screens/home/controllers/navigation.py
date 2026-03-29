from __future__ import annotations

from textual import events

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
)
from piespector.domain.modes import MODE_HOME_SECTION_SELECT, MODE_NORMAL
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_EDIT,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_SEARCH,
    KEY_SEND,
    LEFT_KEYS,
    OPEN_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)
from piespector.screens.home import messages
from piespector.screens.home.controllers.base import HomeControllerBase


class HomeNavigationController(HomeControllerBase):
    def handle_home_view_key(self, event: events.Key) -> bool:
        visible_rows = self.app._home_request_list_visible_rows()

        if event.key == KEY_SEARCH:
            self.state.enter_search_mode()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in LEFT_KEYS:
            self.state.cycle_open_request(-1)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key in RIGHT_KEYS:
            self.state.cycle_open_request(1)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key in DOWN_KEYS:
            self.state.select_request(1)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key in UP_KEYS:
            self.state.select_request(-1)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key == KEY_ESCAPE:
            if self.state.collapse_selected_context():
                self.app._persist_requests()
                self.app._refresh_viewport()
                event.stop()
                return True
            return False

        if event.key == KEY_PAGE_DOWN:
            self.state.scroll_request_window(visible_rows, visible_rows)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key == KEY_PAGE_UP:
            self.state.scroll_request_window(-visible_rows, visible_rows)
            self.app._refresh_viewport()
            event.stop()
            return True

        if event.key == KEY_EDIT:
            if self.state.get_selected_request() is None:
                if self.state.toggle_selected_sidebar_node():
                    self.app._persist_requests()
                    self.app._refresh_viewport()
                    event.stop()
                    return True
                self.state.message = messages.HOME_SELECT_REQUEST_FIRST
                self.app._refresh_screen()
                event.stop()
                return True
            self.state.enter_home_section_select_mode()
            self.app._refresh_screen()
            event.stop()
            return True

        return False

    def enter_current_home_value_select_mode(self) -> None:
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        if self.state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
            self.state.enter_home_params_select_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
            self.state.enter_home_headers_select_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
            self.state.enter_home_auth_type_edit_mode(origin_mode=MODE_HOME_SECTION_SELECT)
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_BODY:
            self.state.enter_home_body_type_edit_mode(origin_mode=MODE_HOME_SECTION_SELECT)
        else:
            self.state.enter_home_request_select_mode()

    def handle_home_section_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.mode = MODE_NORMAL
            self.state.edit_buffer = ""
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in LEFT_KEYS:
            self.state.cycle_home_editor_tab(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            self.state.cycle_home_editor_tab(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.enter_current_home_value_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()
