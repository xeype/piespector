from __future__ import annotations

from textual import events
from textual.app import ScreenStackError
from textual.css.query import NoMatches

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
)
from piespector.domain.modes import (
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
)
from piespector.interactions.keys import (
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    OPEN_KEYS,
    TAB_NEXT_KEYS,
    TAB_PREVIOUS_KEYS,
    TOGGLE_KEYS,
    UP_KEYS,
    DOWN_KEYS,
)
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler
from piespector.screens.home.request.body_pane import RequestBodyPane


class HomeRequestController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_REQUEST_SELECT: self.handle_home_request_select_key,
            MODE_HOME_REQUEST_EDIT: self.handle_home_request_edit_key,
            MODE_HOME_REQUEST_METHOD_SELECT: self.handle_home_request_method_select_key,
            MODE_HOME_REQUEST_METHOD_EDIT: self.handle_home_request_method_edit_key,
            MODE_HOME_URL_EDIT: self.handle_home_url_edit_key,
        }

    def _start_current_home_edit(self) -> bool:
        if self.state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
            self.state.enter_home_params_edit_mode()
            return False
        if self.state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
            self.state.enter_home_headers_edit_mode()
            return False
        if self.state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
            if self.state.selected_auth_index == 0:
                self.state.enter_home_auth_type_edit_mode(origin_mode=MODE_HOME_AUTH_SELECT)
            else:
                self.state.enter_home_auth_edit_mode()
            return False
        if self.state.home_editor_tab == HOME_EDITOR_TAB_BODY:
            return self._body_pane().start_current_edit(origin_mode=MODE_HOME_BODY_SELECT)
        if self.state.home_editor_tab == HOME_EDITOR_TAB_OPTIONS:
            self.state.toggle_active_options_field()
            return False
        self.state.enter_home_request_edit_mode()
        return False

    def _body_pane(self) -> RequestBodyPane:
        try:
            return self.app._query_current("#request-body-pane", RequestBodyPane)
        except (NoMatches, ScreenStackError):
            body_pane = RequestBodyPane()
            body_pane._piespector_app = self.app
            return body_pane

    def handle_home_request_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.enter_home_section_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            if self.state.selected_request_field_index <= 0:
                self.state.enter_home_section_select_mode()
                self.app._refresh_screen()
                event.stop()
                return
            self.state.select_request_field(-1)
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.select_request_field(1)
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

        if self.state.home_editor_tab == HOME_EDITOR_TAB_OPTIONS and event.key in TOGGLE_KEYS:
            self.state.toggle_active_options_field()
            self.app._refresh_home_request_panel()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self._start_current_home_edit():
                event.stop()
                return
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_request_edit_key(self, event: events.Key) -> None:
        request_input = self.live_input("#request-overview-input")
        if request_input is not None and request_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_request_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_request_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.state.save_selected_request_field()
            self.app._refresh_screen()
            event.stop()

    def handle_home_request_method_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_method_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.enter_home_method_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()

    def handle_home_request_method_edit_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_home_method_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        method_select = self.live_select("#method-select")
        if method_select is not None:
            if event.key in OPEN_KEYS:
                method_select.focus()
                if not method_select.expanded:
                    method_select.action_show_overlay()
                event.stop()
                return
            if event.key == KEY_SEND:
                self.app._send_selected_request()
                event.stop()

    def handle_home_url_edit_key(self, event: events.Key) -> None:
        url_input = self.live_input("#url-input")
        if url_input is not None and url_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_home_url_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_home_url_edit_mode()
            self.app._refresh_screen()
            event.stop()
