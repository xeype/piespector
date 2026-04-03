from __future__ import annotations

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCKS,
    HISTORY_DETAIL_BLOCK_RESPONSE,
    RESPONSE_TAB_BODY,
    RESPONSE_TABS,
)
from piespector.domain.modes import (
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_NORMAL,
)
from piespector.domain.history import HistoryEntry, history_entry_matches


class HistoryStateMixin:
    def get_selected_history_entry(self) -> HistoryEntry | None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            return None
        self.clamp_selected_history_index()
        return visible_entries[self.selected_history_index]

    def visible_history_entries(self, raw_query: str | None = None) -> list[HistoryEntry]:
        query = self.history_filter_query if raw_query is None else raw_query
        return [
            entry
            for entry in self.history_entries
            if history_entry_matches(entry, query)
        ]

    def clamp_selected_history_index(self) -> None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            self.selected_history_index = 0
            self.history_scroll_offset = 0
            return
        self.selected_history_index = max(
            0, min(self.selected_history_index, len(visible_entries) - 1)
        )

    def clamp_history_scroll_offset(self, visible_rows: int) -> None:
        max_offset = max(len(self.visible_history_entries()) - max(visible_rows, 1), 0)
        self.history_scroll_offset = max(0, min(self.history_scroll_offset, max_offset))

    def select_history_entry(self, step: int) -> None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            self.selected_history_index = 0
            return
        self.selected_history_index = (
            self.selected_history_index + step
        ) % len(visible_entries)

    def ensure_history_selection_visible(self, visible_rows: int) -> None:
        self.clamp_selected_history_index()
        if self.selected_history_index < self.history_scroll_offset:
            self.history_scroll_offset = self.selected_history_index
        elif self.selected_history_index >= self.history_scroll_offset + visible_rows:
            self.history_scroll_offset = self.selected_history_index - visible_rows + 1
        self.clamp_history_scroll_offset(visible_rows)

    def prepend_history_entry(self, entry: HistoryEntry) -> None:
        self.history_entries.insert(0, entry)
        self.selected_history_index = 0
        self.history_scroll_offset = 0

    def set_history_filter(self, raw_query: str) -> int:
        self.history_filter_query = raw_query.strip()
        self.selected_history_index = 0
        self.history_scroll_offset = 0
        self.clamp_selected_history_index()
        return len(self.visible_history_entries())

    def cycle_history_detail_block(self, step: int) -> None:
        blocks = HISTORY_DETAIL_BLOCKS
        current = (
            self.selected_history_detail_block
            if self.selected_history_detail_block in blocks
            else HISTORY_DETAIL_BLOCK_RESPONSE
        )
        index = blocks.index(current)
        self.selected_history_detail_block = blocks[(index + step) % len(blocks)]

    def cycle_history_request_tab(self, step: int) -> None:
        tabs = [tab_id for tab_id, _label in RESPONSE_TABS]
        current = (
            self.selected_history_request_tab
            if self.selected_history_request_tab in tabs
            else RESPONSE_TAB_BODY
        )
        index = tabs.index(current)
        self.selected_history_request_tab = tabs[(index + step) % len(tabs)]
        self.history_request_scroll_offset = 0

    def cycle_history_response_tab(self, step: int) -> None:
        tabs = [tab_id for tab_id, _label in RESPONSE_TABS]
        current = (
            self.selected_history_response_tab
            if self.selected_history_response_tab in tabs
            else RESPONSE_TAB_BODY
        )
        index = tabs.index(current)
        self.selected_history_response_tab = tabs[(index + step) % len(tabs)]
        self.history_response_scroll_offset = 0

    def enter_history_response_select_mode(self, origin_mode: str | None = None) -> bool:
        if self.get_selected_history_entry() is None:
            self.message = "No history entry selected."
            return False
        self.history_response_select_return_mode = origin_mode or self.mode
        self.mode = MODE_HISTORY_RESPONSE_SELECT
        self.message = ""
        return True

    def leave_history_response_select_mode(self) -> None:
        self.mode = self.history_response_select_return_mode or MODE_NORMAL
        self.message = ""

    def scroll_history_request(self, step: int) -> None:
        self.history_request_scroll_offset = max(
            0, self.history_request_scroll_offset + step
        )

    def scroll_history_response(self, step: int) -> None:
        self.history_response_scroll_offset = max(
            0, self.history_response_scroll_offset + step
        )

    def clamp_history_request_scroll_offset(
        self,
        total_rows: int,
        visible_rows: int,
    ) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.history_request_scroll_offset = max(
            0,
            min(self.history_request_scroll_offset, max_offset),
        )

    def clamp_history_response_scroll_offset(
        self,
        total_rows: int,
        visible_rows: int,
    ) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.history_response_scroll_offset = max(
            0,
            min(self.history_response_scroll_offset, max_offset),
        )
