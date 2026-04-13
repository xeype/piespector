from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Static

from piespector.domain.editor import HOME_EDITOR_TAB_HEADERS
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
from piespector.placeholders import placeholder_match
from piespector.request_builder import preview_auto_headers
from piespector.screens.home import messages
from piespector.screens.home.request.header_editor import (
    RequestHeadersTable,
    refresh_request_headers_table,
)
from piespector.screens.home.selection import request_panel_selected
from piespector.ui.input import PiespectorInput

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestHeadersPane(Vertical):
    DEFAULT_CSS = """
    RequestHeadersPane {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._headers_env_completion_anchor = ""
        self._headers_env_completion_matches: list[str] = []
        self._headers_env_completion_index = -1

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

    def compose(self) -> ComposeResult:
        note = Static("", id="request-content-note")
        note.display = False
        yield note

        yield RequestHeadersTable(
            id="request-headers-table",
            cursor_type="row",
            zebra_stripes=True,
        )

        headers_input = PiespectorInput(
            "",
            id="request-headers-input",
            compact=True,
            select_on_focus=False,
        )
        headers_input.display = False
        yield headers_input
        yield Static("", id="headers-input-hint", classes="hidden")

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        note = self._note()
        headers_table = self._headers_table()
        headers_input = self._headers_input()

        if request is None:
            note.display = False
            self._sync_input_widget(headers_input, "", display=False)
            headers_table.clear(columns=True)
            headers_table.add_columns("Request")
            headers_table.add_row(messages.HOME_NO_ACTIVE_REQUEST)
            headers_table.cursor_type = "none"
            self._reset_completion()
            self._hide_hint()
            return

        note.update(Text(messages.HOME_HEADERS_FOOTER))
        note.display = True
        refresh_request_headers_table(headers_table, request, state)

        field_name, field_label = state.selected_header_field()
        if state.headers_creating_new:
            header_value = ""
        elif request.header_items and state.selected_header_index < len(request.header_items):
            item = request.header_items[state.selected_header_index]
            header_value = item.key if field_name == "key" else item.value
        else:
            header_value = ""

        editing = (
            state.home_editor_tab == HOME_EDITOR_TAB_HEADERS
            and state.mode == MODE_HOME_HEADERS_EDIT
        )
        self._sync_input_widget(
            headers_input,
            header_value,
            display=editing,
            placeholder=f"Header {field_label.lower()}",
            focus_token=(
                (
                    "headers",
                    request.request_id,
                    state.headers_creating_new,
                    state.selected_header_index,
                    state.selected_header_field_index,
                )
                if editing
                else None
            ),
        )
        if not editing:
            self._reset_completion()

        headers_table_selected = (
            state.home_editor_tab == HOME_EDITOR_TAB_HEADERS
            and request_panel_selected(state)
            and state.mode == MODE_HOME_HEADERS_SELECT
        )
        if headers_table_selected and headers_table.can_focus and not headers_table.has_focus:
            headers_table.focus()
        elif not headers_table_selected and headers_table.has_focus:
            app = headers_table.app
            if app is not None:
                app.set_focus(None)
            else:
                headers_table.blur()

        self._sync_hint(state)

    def refresh_hint_from_state(self) -> None:
        state = self._state
        if state is None:
            return
        self._sync_hint(state)

    def handle_input_key(self, event: events.Key) -> bool:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_HEADERS_EDIT:
            return False

        headers_input = self._headers_input()
        if not headers_input.display or event.key != "tab":
            return False

        match = placeholder_match(
            headers_input.value,
            headers_input.cursor_position,
            sorted(app.state.env_pairs),
        )
        if match is not None:
            anchor = self._headers_env_completion_anchor
            stored = self._headers_env_completion_matches
            if anchor and match.prefix in stored:
                matches = stored
                new_index = (self._headers_env_completion_index + 1) % len(matches)
            else:
                anchor = match.prefix
                matches = [key for key in sorted(app.state.env_pairs) if key.startswith(anchor)]
                new_index = 0
            if matches:
                self._headers_env_completion_anchor = anchor
                self._headers_env_completion_matches = matches
                self._headers_env_completion_index = new_index
                suggestion = matches[new_index]
                before = headers_input.value[: match.start]
                after = headers_input.value[match.end :]
                completed = f"{before}{{{{{suggestion}}}}}{after}"
                headers_input.value = completed
                headers_input.cursor_position = len(before) + 2 + len(suggestion)
                self.call_after_refresh(self.refresh_hint_from_state)

        event.stop()
        return True

    def handle_select_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        total_rows = self._header_row_count()

        if event.key == KEY_ESCAPE:
            app.state.enter_home_section_select_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            if total_rows <= 0 or app.state.selected_header_index <= 0:
                app.state.enter_home_section_select_mode()
                app._refresh_screen()
                event.stop()
                return
            app.state.select_header_row(-1, total_rows)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            app.state.select_header_row(1, total_rows)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key in TAB_PREVIOUS_KEYS:
            app.home_controller.headers.move_request_block(-1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in TAB_NEXT_KEYS:
            app.home_controller.headers.move_request_block(1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in FIELD_PREVIOUS_KEYS:
            app.state.cycle_header_field(-1)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key in FIELD_NEXT_KEYS:
            app.state.cycle_header_field(1)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key == KEY_ADD:
            app.state.enter_home_headers_edit_mode(creating=True)
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SPACE:
            if self._selected_row_is_add():
                return
            if self._selected_row_is_auto():
                header_name = self._selected_auto_header_name()
                if header_name is not None:
                    app.state.toggle_auto_header(header_name)
                    app.state.clamp_selected_header_index(self._header_row_count())
                app._refresh_screen()
                event.stop()
                return
            app.state.toggle_selected_header()
            app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            if self._selected_row_is_add():
                app.state.enter_home_headers_edit_mode(creating=True)
                app._refresh_screen()
                event.stop()
                return
            if self._selected_row_is_auto():
                app.state.message = messages.HOME_AUTO_HEADER_EDIT
                app._refresh_screen()
                event.stop()
                return
            app.state.enter_home_headers_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            if self._selected_row_is_add():
                return
            if self._selected_row_is_auto():
                app.state.message = messages.HOME_AUTO_HEADER_DELETE
                app._refresh_screen()
                event.stop()
                return
            app.state.delete_selected_header()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            app._send_selected_request()
            event.stop()

    def handle_edit_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        headers_input = self._headers_input()
        if headers_input.display:
            if event.key == KEY_ESCAPE:
                app.state.leave_home_headers_edit_mode()
                app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            app.state.leave_home_headers_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            app.state.save_selected_header_field()
            app._refresh_screen()
            event.stop()

    def _note(self) -> Static:
        return self.query_one("#request-content-note", Static)

    def _headers_table(self) -> RequestHeadersTable:
        return self.query_one("#request-headers-table", RequestHeadersTable)

    def _headers_input(self) -> Input:
        return self.query_one("#request-headers-input", Input)

    def _headers_hint(self) -> Static:
        return self.query_one("#headers-input-hint", Static)

    def _header_row_count(self) -> int:
        state = self._state
        request = None if state is None else state.get_active_request()
        if request is None:
            return 0
        return len(request.header_items) + len(preview_auto_headers(request, state.env_pairs))

    def _selected_row_is_add(self) -> bool:
        state = self._state
        request = None if state is None else state.get_active_request()
        if request is None:
            return True
        auto_headers = preview_auto_headers(request, state.env_pairs)
        total = len(request.header_items) + len(auto_headers)
        return state.selected_header_index >= total

    def _selected_row_is_auto(self) -> bool:
        state = self._state
        request = None if state is None else state.get_active_request()
        if request is None:
            return False
        return (
            not self._selected_row_is_add()
            and state.selected_header_index >= len(request.header_items)
        )

    def _selected_auto_header_name(self) -> str | None:
        state = self._state
        request = None if state is None else state.get_active_request()
        if request is None:
            return None
        auto_index = state.selected_header_index - len(request.header_items)
        auto_headers = preview_auto_headers(request, state.env_pairs)
        if auto_index < 0 or auto_index >= len(auto_headers):
            return None
        return auto_headers[auto_index][0]

    def _sync_hint(self, state: PiespectorState) -> None:
        headers_input = self._headers_input()
        headers_hint = self._headers_hint()

        if state.mode == MODE_HOME_HEADERS_EDIT and headers_input.display:
            match = placeholder_match(
                headers_input.value,
                headers_input.cursor_position,
                sorted(state.env_pairs),
            )
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = headers_input.cursor_screen_offset
                headers_hint.update(match.suggestion)
                headers_hint.offset = (cursor_offset.x, cursor_offset.y + 1)
                headers_hint.remove_class("hidden")
                return

        headers_hint.add_class("hidden")

    def _hide_hint(self) -> None:
        self._headers_hint().add_class("hidden")

    def _reset_completion(self) -> None:
        self._headers_env_completion_anchor = ""
        self._headers_env_completion_matches = []
        self._headers_env_completion_index = -1

    def _sync_input_widget(
        self,
        input_widget: Input,
        value: str,
        *,
        display: bool,
        placeholder: str = "",
        focus_token: object | None = None,
    ) -> None:
        input_widget.display = display
        input_widget.placeholder = placeholder

        if not display:
            if input_widget.has_focus:
                input_widget.blur()
            input_widget._piespector_focus_token = None
            return

        if focus_token is None:
            if input_widget.value != value:
                input_widget.value = value
            return

        if getattr(input_widget, "_piespector_focus_token", None) == focus_token:
            return

        input_widget._piespector_focus_token = focus_token
        input_widget.value = value
        input_widget.cursor_position = len(value)
        input_widget.focus()

    @on(DataTable.RowHighlighted, "#request-headers-table")
    def _on_headers_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        app = self._owner_app()
        if app is None or event.cursor_row < 0:
            return
        if app.state.selected_header_index != event.cursor_row:
            app.state.selected_header_index = event.cursor_row

    @on(DataTable.RowSelected, "#request-headers-table")
    def _on_headers_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self._owner_app()
        if app is None or event.cursor_row < 0:
            return

        if app.state.selected_header_index != event.cursor_row:
            app.state.selected_header_index = event.cursor_row

        request = app.state.get_active_request()
        if request is None:
            return

        auto_headers = preview_auto_headers(request, app.state.env_pairs)
        total = len(request.header_items) + len(auto_headers)
        if event.cursor_row >= total:
            app.state.enter_home_headers_edit_mode(creating=True)
        elif app.state.selected_header_index >= len(request.header_items):
            app.state.message = messages.HOME_AUTO_HEADER_EDIT
        else:
            app.state.enter_home_headers_edit_mode()

        app._refresh_screen()
        event.stop()

    @on(Input.Submitted, "#request-headers-input")
    def _on_headers_input_submitted(self, event: Input.Submitted) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_HEADERS_EDIT:
            return

        app.state.save_selected_header_field(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    @on(Input.Changed, "#request-headers-input")
    def _on_headers_input_changed(self, event: Input.Changed) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_HEADERS_EDIT:
            return

        text = event.value
        cursor = event.input.cursor_position
        if cursor >= 2 and text[cursor - 2 : cursor] == "{{" and text[cursor : cursor + 2] != "}}":
            event.input.value = text[:cursor] + "}}" + text[cursor:]
            event.input.cursor_position = cursor

        self.call_after_refresh(self.refresh_hint_from_state)
