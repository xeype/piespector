from __future__ import annotations

from textual import events

from piespector.domain.modes import MODE_HOME_AUTH_SELECT, MODE_HOME_SECTION_SELECT
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    LEFT_KEYS,
    OPEN_KEYS,
    PREVIOUS_KEYS,
    NEXT_KEYS,
    UP_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase


class HomeAuthController(HomeControllerBase):
    def handle_home_auth_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.enter_home_auth_type_edit_mode(origin_mode=MODE_HOME_SECTION_SELECT)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.select_auth_row(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_auth_row(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self.state.selected_auth_index == 0:
                self.state.enter_home_auth_type_edit_mode(origin_mode=MODE_HOME_AUTH_SELECT)
            else:
                self.state.enter_home_auth_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_auth_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_auth_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            updated_field = self.state.save_selected_auth_field()
            if updated_field is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        self.app._handle_inline_edit_key(event)

    def handle_home_auth_type_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_auth_type_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in PREVIOUS_KEYS:
            if self.state.cycle_auth_type(-1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in NEXT_KEYS:
            if self.state.cycle_auth_type(1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self.state.auth_fields():
                self.state.selected_auth_index = 1
            else:
                self.state.selected_auth_index = 0
            self.state.mode = MODE_HOME_AUTH_SELECT
            self.state.message = ""
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_auth_location_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_auth_location_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in PREVIOUS_KEYS:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                updated = self.state.cycle_auth_oauth_client_authentication(-1)
            else:
                updated = self.state.cycle_auth_api_key_location(-1)
            if updated is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in NEXT_KEYS:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                updated = self.state.cycle_auth_oauth_client_authentication(1)
            else:
                updated = self.state.cycle_auth_api_key_location(1)
            if updated is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.leave_home_auth_location_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()
