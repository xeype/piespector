from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.app import ScreenStackError

from piespector.domain.editor import (
    REQUEST_EDITOR_JUMP_KEY_TO_TAB,
    RESPONSE_JUMP_KEY_TO_TAB,
    TAB_LABELS,
    TAB_HOME,
    TOP_BAR_JUMP_KEY_TO_TARGET,
)
from piespector.domain.modes import (
    MODE_HOME_SECTION_SELECT,
    MODE_JUMP,
    MODE_NORMAL,
)
from piespector.interactions.keys import (
    KEY_TAB,
    KEY_ESCAPE,
)
from piespector.ui.jump_overlay import JumpOverlay

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class InteractionController:
    """App-level key handling that is shared across screens."""

    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

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
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        self.state.set_home_editor_tab(tab_id)
        self.state.enter_home_section_select_mode()

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


class EventRouter:
    """Routes application key events to the appropriate controller."""

    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def handle_key(self, event: events.Key) -> None:
        current_screen = self._current_screen()
        if current_screen is not None and current_screen.is_modal:
            if isinstance(current_screen, JumpOverlay):
                current_screen.on_key(event)
            return

        if self.state.mode == MODE_JUMP:
            self.app.interaction_controller.handle_jump_key(event)
            return

        if self.state.current_tab == TAB_HOME:
            if self.app.home_controller.handle_request_response_shortcuts(event):
                return
            if (
                self.state.mode == MODE_NORMAL
                and self.app.home_controller.handle_home_view_key(event)
            ):
                return
            self.app.home_controller.dispatch_key(self.state.mode, event)

    def _current_screen(self):
        try:
            return self.app.screen
        except ScreenStackError:
            return None
