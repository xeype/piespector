from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.widgets import Static

from piespector.domain.editor import HISTORY_DETAIL_BLOCK_REQUEST
from piespector.domain.modes import MODE_HISTORY_RESPONSE_SELECT
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_EDIT,
    KEY_ESCAPE,
    KEY_SCROLL_DOWN,
    KEY_SCROLL_UP,
    KEY_SEARCH,
    LEFT_KEYS,
    OPEN_KEYS,
    RESPONSE_SCROLL_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)
from piespector.screens.home.render import response_scroll_step

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class HistoryController:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def handle_history_view_key(self, event: events.Key) -> bool:
        if event.key == KEY_SEARCH:
            self.state.enter_search_mode()
            self.state.command_buffer = self.state.history_filter_query
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in DOWN_KEYS:
            self.state.select_history_entry(1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in UP_KEYS:
            self.state.select_history_entry(-1)
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in OPEN_KEYS:
            self.state.enter_history_response_select_mode()
            self.app._refresh_screen()
            event.stop()
            return True

        return False

    def handle_history_response_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_history_response_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            self.state.cycle_history_detail_block(-1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            self.state.cycle_history_detail_block(1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key in LEFT_KEYS:
            if self.state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                self.state.cycle_history_request_tab(-1)
            else:
                self.state.cycle_history_response_tab(-1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            if self.state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                self.state.cycle_history_request_tab(1)
            else:
                self.state.cycle_history_response_tab(1)
            self.app._refresh_viewport()
            event.stop()
            return

        if event.key == KEY_EDIT:
            self.app._open_history_response_viewer(origin_mode=MODE_HISTORY_RESPONSE_SELECT)
            event.stop()
            return

        if event.key in RESPONSE_SCROLL_KEYS:
            step_size = response_scroll_step(
                self.app.query_one("#viewport", Static).size.height
            )
            step = step_size if event.key == KEY_SCROLL_DOWN else -step_size
            if self.state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                self.state.scroll_history_request(step)
            else:
                self.state.scroll_history_response(step)
            self.app._refresh_viewport()
            event.stop()
