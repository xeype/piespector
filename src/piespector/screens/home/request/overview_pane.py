from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Static

from piespector.domain.editor import HOME_EDITOR_TAB_REQUEST, REQUEST_FIELDS_BY_EDITOR_TAB
from piespector.domain.modes import MODE_HOME_REQUEST_EDIT
from piespector.screens.home import messages
from piespector.screens.home.request.request_metadata import render_request_overview_fields
from piespector.ui.input import PiespectorInput

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestOverviewPane(Vertical):
    DEFAULT_CSS = """
    RequestOverviewPane {
        height: 1fr;
        layout: vertical;
    }
    """

    class FieldSaved(Message):
        def __init__(self, overview_pane: RequestOverviewPane, value: str) -> None:
            super().__init__()
            self.overview_pane = overview_pane
            self.value = value

        @property
        def control(self) -> RequestOverviewPane:
            return self.overview_pane

    def compose(self) -> ComposeResult:
        request_input = PiespectorInput(
            "",
            id="request-overview-input",
            compact=True,
            select_on_focus=False,
        )
        request_input.display = False

        yield Static("", id="request-overview-content")
        yield request_input

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        content = self.query_one("#request-overview-content", Static)
        request_input = self.query_one("#request-overview-input", Input)
        request_fields = REQUEST_FIELDS_BY_EDITOR_TAB[HOME_EDITOR_TAB_REQUEST]

        if request is None:
            content.update(Text(messages.HOME_NO_ACTIVE_REQUEST))
            self._sync_input_widget(request_input, "", display=False)
            return

        content.update(
            render_request_overview_fields(
                request,
                state,
                fields=request_fields,
            )
        )
        selected_index = max(0, min(state.selected_request_field_index, len(request_fields) - 1))
        field_name, field_label = request_fields[selected_index]
        editing = (
            state.home_editor_tab == HOME_EDITOR_TAB_REQUEST
            and state.mode == MODE_HOME_REQUEST_EDIT
        )
        self._sync_input_widget(
            request_input,
            str(getattr(request, field_name) or ""),
            display=editing,
            placeholder=field_label,
            focus_token=(
                ("request", request.request_id, selected_index)
                if editing
                else None
            ),
        )

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

    @on(Input.Submitted, "#request-overview-input")
    def _on_request_overview_input_submitted(self, event: Input.Submitted) -> None:
        self.post_message(self.FieldSaved(self, event.value))
        event.stop()
