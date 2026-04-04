from __future__ import annotations

from textual import events

from piespector.domain.modes import MODE_HOME_HEADERS_EDIT, MODE_HOME_HEADERS_SELECT
from piespector.interactions.keys import (
    DOWN_KEYS,
    FIELD_NEXT_KEYS,
    FIELD_PREVIOUS_KEYS,
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
from piespector.request_builder import preview_auto_headers
from piespector.screens.home import messages
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler


class HomeHeadersController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_HEADERS_SELECT: self.handle_home_headers_select_key,
            MODE_HOME_HEADERS_EDIT: self.handle_home_headers_edit_key,
        }

    def header_row_count(self) -> int:
        request = self.state.get_active_request()
        if request is None:
            return 0
        return len(request.header_items) + len(
            preview_auto_headers(request, self.state.env_pairs)
        )

    def selected_header_row_is_add(self) -> bool:
        request = self.state.get_active_request()
        if request is None:
            return True
        auto_headers = preview_auto_headers(request, self.state.env_pairs)
        total = len(request.header_items) + len(auto_headers)
        return self.state.selected_header_index >= total

    def selected_header_row_is_auto(self) -> bool:
        request = self.state.get_active_request()
        if request is None:
            return False
        return (
            not self.selected_header_row_is_add()
            and self.state.selected_header_index >= len(request.header_items)
        )

    def selected_auto_header_name(self) -> str | None:
        request = self.state.get_active_request()
        if request is None:
            return None
        auto_index = self.state.selected_header_index - len(request.header_items)
        auto_headers = preview_auto_headers(request, self.state.env_pairs)
        if auto_index < 0 or auto_index >= len(auto_headers):
            return None
        return auto_headers[auto_index][0]

    def handle_home_headers_select_key(self, event: events.Key) -> None:
        total_rows = self.header_row_count()

        if event.key == KEY_ESCAPE:
            self.state.enter_home_section_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            if total_rows <= 0 or self.state.selected_header_index <= 0:
                self.state.enter_home_section_select_mode()
                self.app._refresh_screen()
                event.stop()
                return
            self.state.select_header_row(-1, total_rows)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_header_row(1, total_rows)
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

        if event.key in FIELD_PREVIOUS_KEYS:
            self.state.cycle_header_field(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in FIELD_NEXT_KEYS:
            self.state.cycle_header_field(1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key == KEY_ADD:
            self.state.enter_home_headers_edit_mode(creating=True)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SPACE:
            if self.selected_header_row_is_add():
                return
            if self.selected_header_row_is_auto():
                header_name = self.selected_auto_header_name()
                if header_name is not None:
                    self.state.toggle_auto_header(header_name)
                    self.state.clamp_selected_header_index(self.header_row_count())
                self.app._refresh_screen()
                event.stop()
                return
            self.state.toggle_selected_header()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self.selected_header_row_is_add():
                self.state.enter_home_headers_edit_mode(creating=True)
                self.app._refresh_screen()
                event.stop()
                return
            if self.selected_header_row_is_auto():
                self.state.message = messages.HOME_AUTO_HEADER_EDIT
                self.app._refresh_screen()
                event.stop()
                return
            self.state.enter_home_headers_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            if self.selected_header_row_is_add():
                return
            if self.selected_header_row_is_auto():
                self.state.message = messages.HOME_AUTO_HEADER_DELETE
                self.app._refresh_screen()
                event.stop()
                return
            self.state.delete_selected_header()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_headers_edit_key(self, event: events.Key) -> None:
        headers_input = self.live_input("#request-headers-input")
        if headers_input is not None and headers_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_headers_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_headers_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.state.save_selected_header_field()
            self.app._refresh_screen()
            event.stop()
