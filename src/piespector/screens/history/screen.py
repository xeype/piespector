from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_REQUEST,
    HISTORY_DETAIL_BLOCK_RESPONSE,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
    TAB_HOME,
    TAB_LABELS,
)
from piespector.domain.modes import MODE_HISTORY_RESPONSE_SELECT, MODE_NORMAL
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_EDIT,
    KEY_ESCAPE,
    KEY_SCROLL_DOWN,
    KEY_SCROLL_UP,
    LEFT_KEYS,
    OPEN_KEYS,
    RESPONSE_SCROLL_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)
from piespector.screens.base import PiespectorScreen
from piespector.screens.history import render as history_render
from piespector.ui.body_editor_modal import BodyEditorModal
from piespector.ui.command_palette import PiespectorHistorySearchProvider
from piespector.ui.rendering_helpers import (
    detect_text_syntax_language,
    format_response_body,
    text_area_syntax_language,
)
from piespector.ui.selection import FOCUS_FRAME_CLASS

KEY_REPLAY = "r"

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class HistoryScreen(PiespectorScreen):
    selected_history_index = reactive(0)
    history_scroll_offset = reactive(0)
    selected_history_detail_block = reactive(HISTORY_DETAIL_BLOCK_RESPONSE)
    selected_history_request_tab = reactive(RESPONSE_TAB_BODY)
    selected_history_response_tab = reactive(RESPONSE_TAB_BODY)
    history_request_scroll_offset = reactive(0)
    history_response_scroll_offset = reactive(0)
    history_response_select_return_mode = reactive(MODE_NORMAL)

    def search_palette_providers(self):
        return [PiespectorHistorySearchProvider]

    def search_palette_placeholder(self) -> str:
        return "Search history by method, name, URL, status…"

    def search_palette_id(self) -> str:
        return "--history-search"

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    @property
    def _state(self) -> PiespectorState | None:
        app = self._owner_app()
        return None if app is None else app.state

    def on_key(self, event: events.Key) -> None:
        state = self._state
        if state is None:
            return
        if state.mode == MODE_NORMAL:
            self.handle_view_key(event)
            return
        if state.mode == MODE_HISTORY_RESPONSE_SELECT:
            self.handle_response_select_key(event)

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
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        state.ensure_history_selection_visible(self.history_visible_rows())
        self._refresh_history_list(state)
        self._refresh_detail(state)
        self._sync_focus(state)

    def watch_selected_history_index(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        self._sync_history_cursor()
        self._refresh_detail(state)

    def watch_selected_history_detail_block(self) -> None:
        self._refresh_detail_from_watch()

    def watch_selected_history_request_tab(self) -> None:
        self._refresh_detail_from_watch()

    def watch_selected_history_response_tab(self) -> None:
        self._refresh_detail_from_watch()

    def _refresh_detail_from_watch(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        self._refresh_detail(state)

    def history_visible_rows(self) -> int:
        history_list = self.query_one("#history-list", DataTable)
        return max(history_list.size.height - 2, 6) if history_list.size.height else 14

    def detail_visible_rows(self) -> int:
        detail = self.query_one("#history-detail", Static)
        if detail.size.height:
            return max((detail.size.height - 10) // 2, 4)
        return 8

    def detail_scroll_step(self) -> int:
        detail = self.query_one("#history-detail", Static)
        return max(detail.size.height // 4, 1) if detail.size.height else 4

    def handle_view_key(self, event: events.Key) -> bool:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return False

        if event.key in DOWN_KEYS:
            state.select_history_entry(1)
            app._refresh_screen()
            event.stop()
            return True

        if event.key in UP_KEYS:
            state.select_history_entry(-1)
            app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_REPLAY:
            replayed = state.replay_selected_history_entry()
            if replayed is not None:
                state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
            app._refresh_screen()
            event.stop()
            return True

        if event.key in OPEN_KEYS:
            state.enter_history_response_select_mode()
            app._refresh_screen()
            event.stop()
            return True

        return False

    def handle_response_select_key(self, event: events.Key) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return

        if event.key == KEY_ESCAPE:
            state.leave_history_response_select_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            state.cycle_history_detail_block(-1)
            app._refresh_viewport()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            state.cycle_history_detail_block(1)
            app._refresh_viewport()
            event.stop()
            return

        if event.key in LEFT_KEYS:
            if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                state.cycle_history_request_tab(-1)
            else:
                state.cycle_history_response_tab(-1)
            app._refresh_viewport()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                state.cycle_history_request_tab(1)
            else:
                state.cycle_history_response_tab(1)
            app._refresh_viewport()
            event.stop()
            return

        if event.key == KEY_EDIT:
            self.open_response_viewer(origin_mode=MODE_HISTORY_RESPONSE_SELECT)
            event.stop()
            return

        if event.key in RESPONSE_SCROLL_KEYS:
            step_size = self.detail_scroll_step()
            step = step_size if event.key == KEY_SCROLL_DOWN else -step_size
            if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
                state.scroll_history_request(step)
            else:
                state.scroll_history_response(step)
            app._refresh_viewport()
            event.stop()

    def open_response_viewer(self, origin_mode: str | None = None) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return

        entry = state.get_selected_history_entry()
        if entry is None:
            state.message = "No history entry selected."
            app._refresh_screen()
            return

        if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
            if state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
                language = None
                content = "\n".join(
                    f"{key}: {value}" for key, value in entry.request_headers
                ) or "-"
            else:
                body_text = format_response_body(entry.request_body)
                language = text_area_syntax_language(
                    detect_text_syntax_language(body_text)
                )
                content = body_text or entry.request_body or ""
        elif state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
            language = None
            content = "\n".join(
                f"{key}: {value}" for key, value in entry.response_headers
            ) or "-"
        else:
            body_text = format_response_body(entry.response_body)
            language = text_area_syntax_language(
                detect_text_syntax_language(body_text)
            )
            content = body_text or entry.response_body or ""

        entry_name = entry.source_request_name.strip() or entry.source_request_path.strip() or "History"
        app.push_screen(
            BodyEditorModal.viewer(
                title=f"History Viewer  [{entry_name}]",
                footer=f"{app.response_copy_hint} copies selection/all   Esc closes",
                body=content,
                language=language,
            ),
            self._handle_response_viewer_closed,
        )

    def _handle_response_viewer_closed(self, _result: None) -> None:
        app = self._owner_app()
        if app is None:
            return
        app.set_focus(None)
        app._refresh_screen()

    def navigate_to_history_entry(self, history_id: str) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return
        for index, entry in enumerate(state.history_entries):
            if entry.history_id == history_id:
                state.history_filter_query = ""
                state.selected_history_index = index
                state.history_scroll_offset = 0
                break
        app._refresh_screen()

    def _refresh_history_list(self, state: PiespectorState) -> None:
        history_list = self.query_one("#history-list", DataTable)
        entries = state.visible_history_entries()
        data_signature = tuple(
            (
                entry.history_id,
                entry.created_at,
                entry.method,
                entry.status_code,
                entry.source_request_name,
                entry.source_request_path,
                entry.url,
            )
            for entry in entries
        )
        if getattr(history_list, "_piespector_signature", None) != data_signature:
            history_list._piespector_signature = data_signature
            history_list.clear()
            for entry in entries:
                status = str(entry.status_code) if entry.status_code is not None else "ERR"
                meta = Text()
                meta.append(entry.method, style=history_render.method_color(entry.method))
                meta.append(f" {status}")
                history_list.add_row(
                    history_render.history_time_label(entry.created_at),
                    meta,
                    history_render.history_entry_name(entry),
                )

        self.query_one("#history-sidebar-subtitle", Static).update(
            history_render.history_sidebar_subtitle(
                len(state.history_entries),
                len(entries),
                state.history_filter_query,
            )
        )
        self._sync_history_cursor()

    def _sync_history_cursor(self) -> None:
        history_list = self.query_one("#history-list", DataTable)
        if history_list.row_count <= 0:
            return
        row_index = max(0, min(self.selected_history_index, history_list.row_count - 1))
        history_list.move_cursor(row=row_index, column=0, animate=False)

    def _refresh_detail(self, state: PiespectorState) -> None:
        detail = self.query_one("#history-detail", Static)
        detail_container = self.query_one("#history-detail-container")
        entry = state.get_selected_history_entry()
        detail_width = detail.size.width or detail_container.size.width or None
        detail_rows = self.detail_visible_rows()

        request_total = (
            history_render.history_block_total(
                state.selected_history_request_tab,
                entry.request_headers,
                entry.request_body,
                detail_width,
            )
            if entry is not None
            else 0
        )
        response_total = (
            history_render.history_block_total(
                state.selected_history_response_tab,
                entry.response_headers,
                entry.response_body,
                detail_width,
            )
            if entry is not None
            else 0
        )
        state.clamp_history_request_scroll_offset(request_total, detail_rows)
        state.clamp_history_response_scroll_offset(response_total, detail_rows)
        request_start = state.history_request_scroll_offset
        response_start = state.history_response_scroll_offset
        request_end = min(request_start + detail_rows, request_total)
        response_end = min(response_start + detail_rows, response_total)

        detail.update(
            history_render.render_history_detail_content(
                state,
                entry,
                request_start=request_start,
                request_end=request_end,
                response_start=response_start,
                response_end=response_end,
                viewport_width=detail_width,
            )
        )
        detail_container.border_subtitle = (
            history_render.history_detail_subtitle(
                state,
                request_start=request_start,
                request_end=request_end,
                request_total=request_total,
                response_start=response_start,
                response_end=response_end,
                response_total=response_total,
            )
            if entry is not None
            else ""
        )

    def _sync_focus(self, state: PiespectorState) -> None:
        self.query_one("#history-sidebar-container").set_class(
            state.mode == MODE_NORMAL,
            FOCUS_FRAME_CLASS,
        )
        self.query_one("#history-detail-container").set_class(
            state.mode == MODE_HISTORY_RESPONSE_SELECT,
            FOCUS_FRAME_CLASS,
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        app = self._owner_app()
        if app is None or event.control.id != "history-list" or event.cursor_row < 0:
            return
        if app.state.selected_history_index == event.cursor_row:
            return
        app.state.selected_history_index = event.cursor_row
        app._refresh_screen()
