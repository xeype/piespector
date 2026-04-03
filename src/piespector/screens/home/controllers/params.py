from __future__ import annotations

from textual import events

from piespector.domain.modes import MODE_HOME_PARAMS_EDIT, MODE_HOME_PARAMS_SELECT
from piespector.interactions.keys import (
    ARROW_LEFT_KEYS,
    ARROW_RIGHT_KEYS,
    DOWN_KEYS,
    KEY_ADD,
    KEY_DELETE_ROW,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    KEY_SPACE,
    OPEN_KEYS,
    TAB_NEXT_KEYS,
    TAB_PREVIOUS_KEYS,
    UP_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler


class HomeParamsController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_PARAMS_SELECT: self.handle_home_params_select_key,
            MODE_HOME_PARAMS_EDIT: self.handle_home_params_edit_key,
        }

    def handle_home_params_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.enter_home_section_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.select_param_row(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_param_row(1)
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

        if event.key in ARROW_LEFT_KEYS:
            self.state.cycle_param_field(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in ARROW_RIGHT_KEYS:
            self.state.cycle_param_field(1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key == KEY_ADD:
            self.state.enter_home_params_edit_mode(creating=True)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SPACE:
            self.state.toggle_selected_param()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.enter_home_params_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            self.state.delete_selected_param()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_params_edit_key(self, event: events.Key) -> None:
        params_input = self.live_input("#request-params-input")
        if params_input is not None and params_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_params_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_params_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.state.save_selected_param_field()
            self.app._refresh_screen()
            event.stop()
