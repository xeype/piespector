from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Static

from piespector.domain.editor import HOME_EDITOR_TAB_PARAMS
from piespector.domain.modes import MODE_HOME_PARAMS_EDIT, MODE_HOME_PARAMS_SELECT
from piespector.placeholders import placeholder_match
from piespector.screens.home import messages
from piespector.screens.home.request.query_editor import (
    RequestParamsTable,
    refresh_request_params_table,
)
from piespector.screens.home.selection import request_panel_selected
from piespector.ui.input import PiespectorInput

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestParamsPane(Vertical):
    DEFAULT_CSS = """
    RequestParamsPane {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._params_env_completion_anchor = ""
        self._params_env_completion_matches: list[str] = []
        self._params_env_completion_index = -1

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
        yield RequestParamsTable(
            id="request-params-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        params_input = PiespectorInput(
            "",
            id="request-params-input",
            compact=True,
            select_on_focus=False,
        )
        params_input.display = False
        yield params_input
        yield Static("", id="params-input-hint", classes="hidden")

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        params_table = self._params_table()
        params_input = self._params_input()

        if request is None:
            self._sync_input_widget(params_input, "", display=False)
            params_table.clear(columns=True)
            params_table.add_columns("Request")
            params_table.add_row(messages.HOME_NO_ACTIVE_REQUEST)
            params_table.cursor_type = "none"
            self._reset_completion()
            self._hide_hint()
            return

        refresh_request_params_table(params_table, request, state)
        field_name, field_label = state.selected_param_field()
        if state.params_creating_new:
            param_value = ""
        elif request.query_items and state.selected_param_index < len(request.query_items):
            item = request.query_items[state.selected_param_index]
            param_value = item.key if field_name == "key" else item.value
        else:
            param_value = ""

        editing = (
            state.home_editor_tab == HOME_EDITOR_TAB_PARAMS
            and state.mode == MODE_HOME_PARAMS_EDIT
        )
        self._sync_input_widget(
            params_input,
            param_value,
            display=editing,
            placeholder=f"Param {field_label.lower()}",
            focus_token=(
                (
                    "params",
                    request.request_id,
                    state.params_creating_new,
                    state.selected_param_index,
                    state.selected_param_field_index,
                )
                if editing
                else None
            ),
        )
        if not editing:
            self._reset_completion()

        params_table_selected = (
            state.home_editor_tab == HOME_EDITOR_TAB_PARAMS
            and request_panel_selected(state)
            and state.mode == MODE_HOME_PARAMS_SELECT
        )
        if params_table_selected and params_table.can_focus and not params_table.has_focus:
            params_table.focus()
        elif not params_table_selected and params_table.has_focus:
            app = params_table.app
            if app is not None:
                app.set_focus(None)
            else:
                params_table.blur()

        self._sync_hint(state)

    def refresh_hint_from_state(self) -> None:
        state = self._state
        if state is None:
            return
        self._sync_hint(state)

    def handle_input_key(self, event: events.Key) -> bool:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_PARAMS_EDIT:
            return False

        params_input = self._params_input()
        if not params_input.display or event.key != "tab":
            return False

        match = placeholder_match(
            params_input.value,
            params_input.cursor_position,
            sorted(app.state.env_pairs),
        )
        if match is not None:
            anchor = self._params_env_completion_anchor
            stored = self._params_env_completion_matches
            if anchor and match.prefix in stored:
                matches = stored
                new_index = (self._params_env_completion_index + 1) % len(matches)
            else:
                anchor = match.prefix
                matches = [key for key in sorted(app.state.env_pairs) if key.startswith(anchor)]
                new_index = 0
            if matches:
                self._params_env_completion_anchor = anchor
                self._params_env_completion_matches = matches
                self._params_env_completion_index = new_index
                suggestion = matches[new_index]
                before = params_input.value[: match.start]
                after = params_input.value[match.end :]
                completed = f"{before}{{{{{suggestion}}}}}{after}"
                params_input.value = completed
                params_input.cursor_position = len(before) + 2 + len(suggestion)
                self.call_after_refresh(self.refresh_hint_from_state)

        event.stop()
        return True

    def _params_table(self) -> RequestParamsTable:
        return self.query_one("#request-params-table", RequestParamsTable)

    def _params_input(self) -> Input:
        return self.query_one("#request-params-input", Input)

    def _params_hint(self) -> Static:
        return self.query_one("#params-input-hint", Static)

    def _sync_hint(self, state: PiespectorState) -> None:
        params_input = self._params_input()
        params_hint = self._params_hint()

        if state.mode == MODE_HOME_PARAMS_EDIT and params_input.display:
            match = placeholder_match(
                params_input.value,
                params_input.cursor_position,
                sorted(state.env_pairs),
            )
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = params_input.cursor_screen_offset
                params_hint.update(match.suggestion)
                params_hint.offset = (cursor_offset.x, cursor_offset.y + 1)
                params_hint.remove_class("hidden")
                return

        params_hint.add_class("hidden")

    def _hide_hint(self) -> None:
        self._params_hint().add_class("hidden")

    def _reset_completion(self) -> None:
        self._params_env_completion_anchor = ""
        self._params_env_completion_matches = []
        self._params_env_completion_index = -1

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

    @on(DataTable.RowHighlighted, "#request-params-table")
    def _on_params_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        app = self._owner_app()
        if app is None or event.cursor_row < 0:
            return
        if app.state.selected_param_index != event.cursor_row:
            app.state.selected_param_index = event.cursor_row

    @on(DataTable.RowSelected, "#request-params-table")
    def _on_params_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self._owner_app()
        if app is None or event.cursor_row < 0:
            return

        if app.state.selected_param_index != event.cursor_row:
            app.state.selected_param_index = event.cursor_row

        request = app.state.get_active_request()
        params = request.query_items if request is not None else []
        if event.cursor_row >= len(params):
            app.state.enter_home_params_edit_mode(creating=True)
        else:
            app.state.enter_home_params_edit_mode()

        app._refresh_screen()
        event.stop()

    @on(Input.Submitted, "#request-params-input")
    def _on_params_input_submitted(self, event: Input.Submitted) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_PARAMS_EDIT:
            return

        app.state.save_selected_param_field(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    @on(Input.Changed, "#request-params-input")
    def _on_params_input_changed(self, event: Input.Changed) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_PARAMS_EDIT:
            return

        text = event.value
        cursor = event.input.cursor_position
        if cursor >= 2 and text[cursor - 2 : cursor] == "{{" and text[cursor : cursor + 2] != "}}":
            event.input.value = text[:cursor] + "}}" + text[cursor:]
            event.input.cursor_position = cursor

        self.call_after_refresh(self.refresh_hint_from_state)
