from __future__ import annotations

from textual import events

from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
)
from piespector.interactions.keys import (
    ARROW_LEFT_KEYS,
    ARROW_RIGHT_KEYS,
    DOWN_KEYS,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    OPEN_KEYS,
    TAB_NEXT_KEYS,
    TAB_PREVIOUS_KEYS,
    UP_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler


class HomeAuthController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_AUTH_SELECT: self.handle_home_auth_select_key,
            MODE_HOME_AUTH_EDIT: self.handle_home_auth_edit_key,
            MODE_HOME_AUTH_TYPE_EDIT: self.handle_home_auth_type_edit_key,
            MODE_HOME_AUTH_LOCATION_EDIT: self.handle_home_auth_location_edit_key,
        }

    def handle_home_auth_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.enter_home_section_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            if self.state.selected_auth_index <= 0:
                self.state.enter_home_section_select_mode()
                self.app._refresh_screen()
                event.stop()
                return
            self.state.select_auth_row(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_auth_row(1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in TAB_PREVIOUS_KEYS:
            self.move_request_block(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in TAB_NEXT_KEYS:
            self.move_request_block(1)
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
        auth_input = self.live_input("#auth-field-input")
        if auth_input is not None and auth_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_auth_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_auth_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.state.save_selected_auth_field()
            self.app._refresh_screen()
            event.stop()

    def handle_home_auth_type_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_auth_type_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        auth_type_select = self.live_select("#auth-type-select")
        if auth_type_select is not None:
            if event.key in OPEN_KEYS:
                auth_type_select.focus()
                if not auth_type_select.expanded:
                    auth_type_select.action_show_overlay()
                event.stop()
                return
            if event.key == KEY_SEND:
                self.app._send_selected_request()
                event.stop()
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            self.state.cycle_auth_type(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            self.state.cycle_auth_type(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.leave_home_auth_type_edit_mode()
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

        auth_option_select = self.live_select("#auth-option-select")
        if auth_option_select is not None and auth_option_select.display:
            if event.key in OPEN_KEYS:
                auth_option_select.focus()
                if not auth_option_select.expanded:
                    auth_option_select.action_show_overlay()
                event.stop()
                return
            if event.key == KEY_SEND:
                self.app._send_selected_request()
                event.stop()
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                self.state.cycle_auth_oauth_client_authentication(-1)
            else:
                self.state.cycle_auth_api_key_location(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                self.state.cycle_auth_oauth_client_authentication(1)
            else:
                self.state.cycle_auth_api_key_location(1)
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
