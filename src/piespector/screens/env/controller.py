from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.widgets import Input
from piespector.interactions.keys import (
    KEY_ADD,
    KEY_DELETE_ROW,
    KEY_ENTER,
    KEY_ESCAPE,
    DOWN_KEYS,
    LEFT_KEYS,
    NEXT_KEYS,
    OPEN_KEYS,
    PREVIOUS_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class EnvController:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def handle_env_view_key(self, event: events.Key) -> bool:
        if event.key in LEFT_KEYS:
            self.state.select_env_set(-1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in RIGHT_KEYS:
            self.state.select_env_set(1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_ADD:
            self.state.enter_env_create_mode()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in DOWN_KEYS:
            self.state.select_env_row(1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in UP_KEYS:
            self.state.select_env_row(-1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in OPEN_KEYS:
            self.state.enter_env_select_mode()
            self.app._refresh_screen()
            event.stop()
            return True

        return False

    def handle_env_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_env_interaction()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in PREVIOUS_KEYS:
            self.state.cycle_env_field(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in NEXT_KEYS:
            self.state.cycle_env_field(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.state.enter_env_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ADD:
            self.state.enter_env_create_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            deleted_key = self.state.delete_selected_env_item()
            if deleted_key is not None:
                self.app._persist_env_pairs()
            self.app._refresh_screen()
            event.stop()
            return

    def _env_input(self) -> Input | None:
        try:
            return self.app._query_current("#env-field-input", Input)
        except Exception:
            return None

    def handle_env_edit_key(self, event: events.Key) -> None:
        env_input = self._env_input()
        if env_input is not None and env_input.display:
            if event.key == KEY_ESCAPE:
                self.state.leave_env_edit_mode()
                self.app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            self.state.leave_env_edit_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            updated_key = self.state.save_selected_env_field()
            if updated_key is not None:
                self.app._persist_env_pairs()
            self.app._refresh_screen()
            event.stop()
