from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text

from piespector.domain.editor import (
    BODY_KEY_VALUE_TYPES,
    HOME_SIDEBAR_JUMP_KEY,
    HOME_SIDEBAR_LABEL,
    REQUEST_EDITOR_JUMP_BINDINGS,
    REQUEST_EDITOR_TAB_LABELS,
    RESPONSE_JUMP_BINDINGS,
    RESPONSE_TAB_LABELS,
    TAB_HOME,
    TAB_HISTORY,
)
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_EDIT,
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_URL_EDIT,
    MODE_JUMP,
)
from piespector.state import PiespectorState

@dataclass(frozen=True)
class CommandLineContent:
    text: str
    tone: str = "primary"


def command_line_content(state: PiespectorState) -> CommandLineContent | None:
    if state.mode == MODE_JUMP:
        if state.current_tab == TAB_HOME:
            return CommandLineContent("Press a key to jump", tone="primary")
        collections_target = f"{HOME_SIDEBAR_JUMP_KEY} {HOME_SIDEBAR_LABEL}"
        request_targets = "  ".join(
            f"{key} {REQUEST_EDITOR_TAB_LABELS[tab_id]}"
            for tab_id, key in REQUEST_EDITOR_JUMP_BINDINGS
        )
        response_targets = "  ".join(
            f"{key} {RESPONSE_TAB_LABELS[tab_id]}"
            for tab_id, key in RESPONSE_JUMP_BINDINGS
        )
        return CommandLineContent(
            (
                f"Jump: {collections_target}  |  Request: {request_targets}  |  "
                f"Response: {response_targets}  |  Esc cancel"
            ),
            tone="primary",
        )

    if state.mode == MODE_CONFIRM:
        return CommandLineContent(state.confirm_prompt, tone="warning")

    if state.mode == MODE_HOME_REQUEST_EDIT:
        _field_name, label = state.selected_request_field()
        return CommandLineContent(f"Editing {label}. Enter saves, Esc cancels.")

    if state.mode == MODE_HOME_REQUEST_METHOD_SELECT:
        return CommandLineContent("Method selector: e or Enter open, Esc back")

    if state.mode == MODE_HOME_REQUEST_METHOD_EDIT:
        return CommandLineContent(
            "Method: up/down choose, e or Enter confirm, Esc back"
        )

    if state.mode == MODE_HOME_URL_EDIT:
        return CommandLineContent("Editing URL. Enter saves.")

    if state.mode == MODE_HOME_AUTH_EDIT:
        field = state.selected_auth_field()
        label = field[1] if field is not None else "Auth"
        return CommandLineContent(f"Editing {label}. Enter saves, Esc cancels.")

    if state.mode == MODE_HOME_AUTH_TYPE_EDIT:
        return CommandLineContent("Auth type: up/down choose, e or Enter confirm, Esc back")

    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT:
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            return CommandLineContent("OAuth client auth: up/down choose, e or Enter confirm, Esc back")
        return CommandLineContent("API key location: up/down choose, e or Enter confirm, Esc back")

    if state.mode == MODE_HOME_PARAMS_EDIT:
        if state.params_creating_new:
            return CommandLineContent("New param key. Enter saves, Esc cancels.")
        _field_name, field_label = state.selected_param_field()
        return CommandLineContent(
            f"Editing param {field_label.lower()}. Enter saves, Esc cancels."
        )

    if state.mode == MODE_HOME_HEADERS_EDIT:
        if state.headers_creating_new:
            return CommandLineContent("New header key. Enter saves, Esc cancels.")
        _field_name, field_label = state.selected_header_field()
        return CommandLineContent(
            f"Editing header {field_label.lower()}. Enter saves, Esc cancels."
        )

    if state.mode == MODE_HOME_BODY_TYPE_EDIT:
        return CommandLineContent("Body type: up/down choose, e or Enter confirm, Esc back")

    if state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
        return CommandLineContent("Raw type: up/down choose, e or Enter confirm, Esc back")

    if state.mode == MODE_HOME_BODY_TEXTAREA:
        if state.message:
            return CommandLineContent(state.message, tone="danger")
        return CommandLineContent("Raw body editor")

    if state.mode == MODE_HOME_BODY_EDIT:
        request = state.get_active_request()
        if request is not None and request.body_type in BODY_KEY_VALUE_TYPES:
            if state.body_creating_new:
                return CommandLineContent("New body key. Enter saves, Esc cancels.")
            _field_name, field_label = state.selected_body_field()
            return CommandLineContent(
                f"Editing body {field_label.lower()}. Enter saves, Esc cancels."
            )
        return CommandLineContent(
            "Editing path. Enter saves, Esc cancels."
            if request is not None and request.body_type == "binary"
            else "Editing body. Enter saves, Esc cancels."
        )

    if state.mode == MODE_ENV_EDIT:
        if state.env_creating_new:
            return CommandLineContent("New env key. Enter saves, Esc cancels.")
        item = state.get_selected_env_item()
        key = item[0] if item is not None else ""
        field_name, _field_label = state.selected_env_field()
        label = "Editing key. Enter saves, Esc cancels." if field_name == "key" else f"Editing {key}. Enter saves, Esc cancels."
        return CommandLineContent(label)

    if state.message:
        return CommandLineContent(state.message)

    return None


def build_command_line_text(state: PiespectorState) -> Text:
    text = Text()
    content = command_line_content(state)
    if content is None:
        return text

    text.append(content.text)
    return text
