from __future__ import annotations

from textual import events

from piespector.domain.modes import (
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
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
from piespector.screens.home.controllers.base import HomeControllerBase


class HomeBodyController(HomeControllerBase):
    def handle_home_body_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_body_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.select_body_row(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_body_row(1)
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

        if event.key == KEY_ADD:
            if (
                self.state.get_active_request() is not None
                and self.state.get_active_request().body_type
                in {"form-data", "x-www-form-urlencoded"}
            ):
                self.state.enter_home_body_edit_mode(
                    creating=True,
                    origin_mode=MODE_HOME_BODY_SELECT,
                )
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_SPACE:
            toggled_key = self.state.toggle_selected_body_field()
            if toggled_key is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            request = self.state.get_active_request()
            if self.state.selected_body_index == 0:
                self.state.enter_home_body_type_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
            else:
                if request is not None and request.body_type == "raw" and self.state.selected_body_index == 1:
                    self.state.enter_home_body_raw_type_edit_mode(
                        origin_mode=MODE_HOME_BODY_SELECT
                    )
                    self.app._refresh_screen()
                    event.stop()
                    return
                self.state.enter_home_body_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            deleted_key = self.state.delete_selected_body_field()
            if deleted_key is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_body_type_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_body_type_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        body_type_select = self.live_select("#body-type-select")
        if body_type_select is not None:
            if event.key in OPEN_KEYS:
                body_type_select.focus()
                if not body_type_select.expanded:
                    body_type_select.action_show_overlay()
                event.stop()
                return
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            if self.state.cycle_body_type(-1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            request = self.state.get_active_request()
            if request is None:
                self.state.leave_home_body_type_edit_mode()
                self.app._refresh_screen()
                event.stop()
                return

            self.state.selected_body_index = 0
            self.state.mode = MODE_HOME_BODY_SELECT
            self.state.message = ""
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            if self.state.cycle_body_type(1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()

    def handle_home_body_raw_type_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_body_raw_type_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        raw_type_select = self.live_select("#body-raw-type-select")
        if raw_type_select is not None and raw_type_select.display:
            if event.key in OPEN_KEYS:
                raw_type_select.focus()
                if not raw_type_select.expanded:
                    raw_type_select.action_show_overlay()
                event.stop()
                return
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            if self.state.cycle_raw_subtype(-1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            if self.state.cycle_raw_subtype(1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.mode = MODE_HOME_BODY_SELECT
            self.state.message = ""
            self.app._refresh_screen()
            event.stop()

    def handle_home_body_edit_key(self, event: events.Key) -> None:
        body_input = self.live_input("#request-body-input")
        if body_input is not None and body_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_body_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_body_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            saved_key = self.state.save_body_selection()
            if saved_key is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
