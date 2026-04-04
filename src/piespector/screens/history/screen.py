from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from piespector.domain.editor import HISTORY_DETAIL_BLOCK_RESPONSE, RESPONSE_TAB_BODY
from piespector.domain.modes import MODE_NORMAL
from piespector.screens.base import PiespectorScreen


class HistoryScreen(PiespectorScreen):
    selected_history_index = reactive(0)
    history_scroll_offset = reactive(0)
    selected_history_detail_block = reactive(HISTORY_DETAIL_BLOCK_RESPONSE)
    selected_history_request_tab = reactive(RESPONSE_TAB_BODY)
    selected_history_response_tab = reactive(RESPONSE_TAB_BODY)
    history_request_scroll_offset = reactive(0)
    history_response_scroll_offset = reactive(0)
    history_response_select_return_mode = reactive(MODE_NORMAL)

    def compose_workspace(self) -> ComposeResult:
        with Horizontal(id="history-screen"):
            with Vertical(id="history-sidebar-container"):
                yield DataTable(id="history-list", cursor_type="row", zebra_stripes=True)
                yield Static("", classes="panel-subtitle", id="history-sidebar-subtitle")
            with Vertical(id="history-detail-container"):
                yield Static("", id="history-detail")

    def on_mount(self) -> None:
        super().on_mount()
        history_list = self.query_one("#history-list", DataTable)
        history_list.add_columns("When", "Meta", "Name")
        self.disable_focus("history-list")
        self.query_one("#history-sidebar-container").border_title = "History"
        self.query_one("#history-detail-container").border_title = "Detail"
