from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events

from piespector.commands import run_command
from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    REQUEST_EDITOR_JUMP_KEY_TO_TAB,
    RESPONSE_JUMP_KEY_TO_TAB,
    TAB_LABELS,
    TAB_HOME,
    TOP_BAR_JUMP_KEY_TO_TARGET,
)
from piespector.domain.modes import MODE_HOME_SECTION_SELECT, MODE_NORMAL
from piespector.interactions.keys import (
    CONFIRM_ACCEPT_KEYS,
    CONFIRM_CANCEL_KEYS,
    KEY_ESCAPE,
    KEY_TAB,
    LEFT_KEYS,
    RIGHT_KEYS,
)
from piespector.search import activate_search_target

if TYPE_CHECKING:
    from piespector.app import PiespectorApp
    from piespector.search import SearchTarget


class InteractionController:
    """App-level key handling that is shared across screens."""

    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def handle_command_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_command_mode()
            self.app._refresh_screen()
            event.stop()

    def handle_confirm_key(self, event: events.Key) -> None:
        if event.key in CONFIRM_CANCEL_KEYS:
            self.state.leave_confirm_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key not in CONFIRM_ACCEPT_KEYS:
            return

        if self.state.confirm_action == "delete_collection":
            deleted = self.state.delete_selected_collection()
            if deleted is not None:
                self.app._persist_requests()
        elif self.state.confirm_action == "delete_folder":
            deleted = self.state.delete_selected_folder()
            if deleted is not None:
                self.app._persist_requests()

        self.state.leave_confirm_mode()
        self.app._refresh_screen()
        event.stop()

    def handle_jump_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_jump_mode()
            self.app._refresh_jump_state()
            event.stop()
            return

        if event.key == KEY_TAB:
            self.state.leave_jump_mode()
            self.activate_jump_target("collections")
            self.app._refresh_screen()
            event.stop()
            return

        jump_key = (event.character or event.key or "").lower()
        target = self.jump_target_for_key(jump_key)
        if target is not None:
            self.state.leave_jump_mode()
            self.activate_jump_target(target)
            self.app._refresh_screen()
            event.stop()
            return

        event.stop()

    def jump_target_for_key(self, jump_key: str) -> str | None:
        if jump_key in REQUEST_EDITOR_JUMP_KEY_TO_TAB:
            return f"request:{REQUEST_EDITOR_JUMP_KEY_TO_TAB[jump_key]}"
        if jump_key in RESPONSE_JUMP_KEY_TO_TAB:
            return f"response:{RESPONSE_JUMP_KEY_TO_TAB[jump_key]}"
        if jump_key in TOP_BAR_JUMP_KEY_TO_TARGET:
            return f"topbar:{TOP_BAR_JUMP_KEY_TO_TARGET[jump_key]}"
        return None

    def activate_jump_target(self, target: str) -> bool:
        if target == "collections":
            self._open_home_collections_jump_target()
            return True
        if target.startswith("request:"):
            self._open_home_jump_target(target.split(":", 1)[1])
            return True
        if target.startswith("response:"):
            self._open_home_response_jump_target(target.split(":", 1)[1])
            return True
        if target.startswith("topbar:"):
            self._open_home_top_bar_jump_target(target.split(":", 1)[1])
            return True
        return False

    def _open_home_collections_jump_target(self) -> None:
        self.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        self.state.mode = MODE_NORMAL
        self.state.message = ""

    def _open_home_jump_target(self, tab_id: str) -> None:
        self.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        self.state.set_home_editor_tab(tab_id)
        if tab_id == HOME_EDITOR_TAB_REQUEST:
            self.state.enter_home_request_select_mode()
            return
        if tab_id == HOME_EDITOR_TAB_AUTH:
            self.state.enter_home_auth_select_mode()
            return
        if tab_id == HOME_EDITOR_TAB_PARAMS:
            self.state.enter_home_params_select_mode()
            return
        if tab_id == HOME_EDITOR_TAB_HEADERS:
            self.state.enter_home_headers_select_mode()
            return
        self.state.enter_home_body_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)

    def _open_home_top_bar_jump_target(self, target: str) -> None:
        self.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        if target == "method":
            self.state.enter_home_method_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)
        elif target == "url":
            self.state.enter_home_url_edit_mode()

    def _open_home_response_jump_target(self, tab_id: str) -> None:
        self.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        self.state.selected_home_response_tab = tab_id
        self.state.enter_home_response_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)

    def run_command(self, raw_command: str) -> None:
        before_env_pairs = dict(self.state.env_pairs)
        before_requests = [request.request_id for request in self.state.requests]
        outcome = run_command(self.state, raw_command)
        if outcome.save_env_pairs or self.state.env_pairs != before_env_pairs:
            self.app._persist_env_pairs()
        if outcome.save_requests or [request.request_id for request in self.state.requests] != before_requests:
            self.app._persist_requests()
        if outcome.send_request:
            self.app._send_selected_request()
            return
        if outcome.should_exit:
            self.app.exit()
            return
        self.app._refresh_screen()

    def open_search_target(self, target: SearchTarget) -> None:
        self.state.mode = MODE_NORMAL
        if activate_search_target(self.state, target):
            self.app._persist_requests()
        else:
            self.state.message = f"Could not open {target.display}."
        self.app._refresh_screen()
