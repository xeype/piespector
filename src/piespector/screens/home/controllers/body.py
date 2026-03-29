from __future__ import annotations

from textual import events

from piespector.domain.editor import BODY_TEXT_EDITOR_TYPES
from piespector.domain.modes import (
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_ADD,
    KEY_DELETE_ROW,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    KEY_SPACE,
    LEFT_KEYS,
    OPEN_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase


class HomeBodyController(HomeControllerBase):
    def handle_home_body_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_body_select_mode()
            self.state.edit_buffer = ""
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.select_body_row(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_body_row(1)
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
            if (
                request is not None
                and request.body_type in {"form-data", "x-www-form-urlencoded"}
                and self.state.selected_body_index <= 0
            ):
                self.state.selected_body_index = 1

            if self.state.selected_body_index == 0:
                self.state.enter_home_body_type_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
            else:
                if request is not None and request.body_type == "raw":
                    self.state.enter_home_body_raw_type_edit_mode(
                        origin_mode=MODE_HOME_BODY_SELECT
                    )
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

        if event.key in LEFT_KEYS:
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

            if request.body_type == "raw":
                self.state.enter_home_body_raw_type_edit_mode(
                    origin_mode=MODE_HOME_BODY_TYPE_EDIT
                )
                self.app._refresh_screen()
                event.stop()
                return

            if request.body_type in BODY_TEXT_EDITOR_TYPES:
                self.app._open_body_text_editor(origin_mode=MODE_HOME_BODY_TYPE_EDIT)
                event.stop()
                return

            if request.body_type == "binary":
                self.state.selected_body_index = 1
                self.state.enter_home_body_edit_mode(origin_mode=MODE_HOME_BODY_TYPE_EDIT)
                self.app._refresh_screen()
                event.stop()
                return

            if request.body_type in {"form-data", "x-www-form-urlencoded"}:
                items = self.state.get_active_request_body_items()
                self.state.selected_body_index = 1
                self.state.enter_home_body_select_mode(
                    origin_mode=MODE_HOME_BODY_TYPE_EDIT
                )
                if not items:
                    self.state.selected_body_index = 1
                self.app._refresh_screen()
                event.stop()
                return

            self.state.leave_home_body_type_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
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

        if event.key in LEFT_KEYS:
            if self.state.cycle_raw_subtype(-1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            if self.state.cycle_raw_subtype(1) is not None:
                self.app._persist_requests()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.app._open_body_text_editor(origin_mode=MODE_HOME_BODY_RAW_TYPE_EDIT)
            event.stop()

    def handle_home_body_edit_key(self, event: events.Key) -> None:
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
            return

        self.app._handle_inline_edit_key(event)
