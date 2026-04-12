from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Static

from piespector.domain.editor import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_TYPE_EDIT,
)
from piespector.placeholders import placeholder_match
from piespector.screens.home import messages
from piespector.screens.home.request.request_auth import (
    auth_option_select_context,
    render_request_auth_editor,
)
from piespector.screens.home.selection import home_selection
from piespector.ui.input import PiespectorInput
from piespector.ui.selection import set_selected
from piespector.widget.select import (
    PiespectorSelect,
    SelectionChanged,
    deactivate,
    option_list,
    sync,
)

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestAuthPane(Vertical):
    DEFAULT_CSS = """
    RequestAuthPane {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._auth_env_completion_anchor = ""
        self._auth_env_completion_matches: list[str] = []
        self._auth_env_completion_index = -1

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
        auth_option_label = Static("", id="auth-option-label")
        auth_option_label.display = False

        auth_option_select = PiespectorSelect(
            option_list(*AUTH_API_KEY_LOCATION_OPTIONS),
            id="auth-option-select",
            allow_blank=False,
            value=AUTH_API_KEY_LOCATION_OPTIONS[0][0],
            compact=True,
        )
        auth_option_select.display = False

        auth_field_input = PiespectorInput(
            "",
            id="auth-field-input",
            compact=True,
            select_on_focus=False,
        )
        auth_field_input.display = False

        yield PiespectorSelect(
            option_list(*AUTH_TYPE_OPTIONS),
            id="auth-type-select",
            allow_blank=False,
            value=AUTH_TYPE_OPTIONS[0][0],
            compact=True,
        )
        yield auth_option_label
        yield auth_option_select
        yield Static("", id="request-auth-content")
        yield auth_field_input
        yield Static("", id="auth-field-input-hint", classes="hidden")

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        auth_type_select = self._auth_type_select()
        auth_option_label = self._auth_option_label()
        auth_option_select = self._auth_option_select()
        auth_content = self._auth_content()
        auth_field_input = self._auth_field_input()
        selection = home_selection(state)
        auth_tab_active = state.home_editor_tab == HOME_EDITOR_TAB_AUTH

        set_selected(auth_type_select, selection.auth_type_selected)
        set_selected(auth_option_select, selection.auth_option_selected)

        if request is None:
            auth_content.update(Text(messages.HOME_NO_ACTIVE_REQUEST))
            deactivate(auth_type_select)
            auth_type_select.display = False
            auth_option_label.display = False
            deactivate(auth_option_select)
            auth_option_select.display = False
            self._sync_input_widget(auth_field_input, "", display=False)
            self._reset_auth_completion()
            self._hide_hint()
            return

        sync(
            auth_type_select,
            option_list(*AUTH_TYPE_OPTIONS),
            request.auth_type,
            display=auth_tab_active,
            auto_open_token=(
                ("auth-type", request.request_id, state.mode)
                if auth_tab_active and state.mode == MODE_HOME_AUTH_TYPE_EDIT
                else None
            ),
        )

        option_context = auth_option_select_context(request, state)
        if auth_tab_active and option_context is not None:
            label, options, current_value = option_context
            auth_option_label.update(label)
            auth_option_label.display = True
            sync(
                auth_option_select,
                option_list(*options),
                current_value,
                display=True,
                auto_open_token=(
                    (
                        "auth-option",
                        request.request_id,
                        state.selected_auth_index,
                        state.mode,
                    )
                    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT
                    else None
                ),
            )
        else:
            auth_option_label.display = False
            deactivate(auth_option_select)
            auth_option_select.display = False

        auth_content.update(
            render_request_auth_editor(
                request,
                state,
                include_type_selector=False,
            )
        )

        auth_field = state.selected_auth_field()
        editing = auth_tab_active and auth_field is not None and state.mode == MODE_HOME_AUTH_EDIT
        if editing:
            field_name, field_label = auth_field
            self._sync_input_widget(
                auth_field_input,
                str(getattr(request, field_name) or ""),
                display=True,
                placeholder=f"Auth {field_label.lower()}",
                focus_token=(
                    "auth-field",
                    request.request_id,
                    state.selected_auth_index,
                    field_name,
                ),
            )
        else:
            self._sync_input_widget(auth_field_input, "", display=False)
            self._reset_auth_completion()

        self._sync_hint(state)

    def refresh_hint_from_state(self) -> None:
        state = self._state
        if state is None:
            return
        self._sync_hint(state)

    def _auth_type_select(self) -> PiespectorSelect:
        return self.query_one("#auth-type-select", PiespectorSelect)

    def _auth_option_label(self) -> Static:
        return self.query_one("#auth-option-label", Static)

    def _auth_option_select(self) -> PiespectorSelect:
        return self.query_one("#auth-option-select", PiespectorSelect)

    def _auth_content(self) -> Static:
        return self.query_one("#request-auth-content", Static)

    def _auth_field_input(self) -> Input:
        return self.query_one("#auth-field-input", Input)

    def _auth_hint(self) -> Static:
        return self.query_one("#auth-field-input-hint", Static)

    def _sync_hint(self, state: PiespectorState) -> None:
        auth_field_input = self._auth_field_input()
        auth_hint = self._auth_hint()

        if state.mode == MODE_HOME_AUTH_EDIT and auth_field_input.display:
            match = placeholder_match(
                auth_field_input.value,
                auth_field_input.cursor_position,
                sorted(state.env_pairs),
            )
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = auth_field_input.cursor_screen_offset
                auth_hint.update(match.suggestion)
                auth_hint.offset = (cursor_offset.x, cursor_offset.y + 1)
                auth_hint.remove_class("hidden")
                return

        auth_hint.add_class("hidden")

    def _hide_hint(self) -> None:
        self._auth_hint().add_class("hidden")

    def _reset_auth_completion(self) -> None:
        self._auth_env_completion_anchor = ""
        self._auth_env_completion_matches = []
        self._auth_env_completion_index = -1

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

    @on(SelectionChanged, "#auth-type-select")
    def _on_auth_type_selected(self, event: SelectionChanged) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_AUTH_TYPE_EDIT:
            return

        app.state.save_home_auth_type_selection(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    @on(SelectionChanged, "#auth-option-select")
    def _on_auth_option_selected(self, event: SelectionChanged) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_AUTH_LOCATION_EDIT:
            return

        app.state.save_home_auth_option_selection(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    @on(Input.Submitted, "#auth-field-input")
    def _on_auth_field_submitted(self, event: Input.Submitted) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_AUTH_EDIT:
            return

        app.state.save_selected_auth_field(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    @on(Input.Changed, "#auth-field-input")
    def _on_auth_field_changed(self, event: Input.Changed) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_AUTH_EDIT:
            return

        text = event.value
        cursor = event.input.cursor_position
        if cursor >= 2 and text[cursor - 2 : cursor] == "{{" and text[cursor : cursor + 2] != "}}":
            event.input.value = text[:cursor] + "}}" + text[cursor:]
            event.input.cursor_position = cursor

        self.call_after_refresh(self.refresh_hint_from_state)

    def handle_input_key(self, event: events.Key) -> bool:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_AUTH_EDIT:
            return False

        auth_field_input = self._auth_field_input()
        if not auth_field_input.display:
            return False

        if event.key == "tab":
            match = placeholder_match(
                auth_field_input.value,
                auth_field_input.cursor_position,
                sorted(app.state.env_pairs),
            )
            if match is not None:
                anchor = self._auth_env_completion_anchor
                stored = self._auth_env_completion_matches
                if anchor and match.prefix in stored:
                    matches = stored
                    new_index = (self._auth_env_completion_index + 1) % len(matches)
                else:
                    anchor = match.prefix
                    matches = [key for key in sorted(app.state.env_pairs) if key.startswith(anchor)]
                    new_index = 0
                if matches:
                    self._auth_env_completion_anchor = anchor
                    self._auth_env_completion_matches = matches
                    self._auth_env_completion_index = new_index
                    suggestion = matches[new_index]
                    before = auth_field_input.value[: match.start]
                    after = auth_field_input.value[match.end :]
                    completed = f"{before}{{{{{suggestion}}}}}{after}"
                    auth_field_input.value = completed
                    auth_field_input.cursor_position = len(before) + 2 + len(suggestion)
                    self.call_after_refresh(self.refresh_hint_from_state)

            event.stop()
            return True

        return False
