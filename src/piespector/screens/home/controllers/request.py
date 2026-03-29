from __future__ import annotations

from textual import events

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
)
from piespector.domain.modes import MODE_HOME_AUTH_SELECT, MODE_HOME_BODY_SELECT
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    OPEN_KEYS,
    PREVIOUS_KEYS,
    NEXT_KEYS,
    UP_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase


class HomeRequestController(HomeControllerBase):
    def _start_current_home_edit(self) -> None:
        if self.state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
            self.state.enter_home_params_edit_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
            self.state.enter_home_headers_edit_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
            if self.state.selected_auth_index == 0:
                self.state.enter_home_auth_type_edit_mode(origin_mode=MODE_HOME_AUTH_SELECT)
            else:
                self.state.enter_home_auth_edit_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_BODY:
            if self.state.selected_body_index == 0:
                self.state.enter_home_body_type_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
            else:
                request = self.state.get_active_request()
                if request is not None and request.body_type == "raw":
                    self.state.enter_home_body_raw_type_edit_mode(
                        origin_mode=MODE_HOME_BODY_SELECT
                    )
                    return
                self.state.enter_home_body_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
        else:
            self.state.enter_home_request_edit_mode()

    def handle_home_request_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.enter_home_section_select_mode()
            self.state.edit_buffer = ""
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.select_request_field(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_request_field(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self._start_current_home_edit()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_request_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_request_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            updated_field = self.state.save_selected_request_field()
            if updated_field is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        self.app._handle_inline_edit_key(event)

    def handle_home_request_method_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_request_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            updated_field = self.state.save_selected_request_method()
            if updated_field is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in PREVIOUS_KEYS:
            self.state.cycle_request_method(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in NEXT_KEYS:
            self.state.cycle_request_method(1)
            self.app._refresh_screen()
            event.stop()
