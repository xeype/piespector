from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_SEARCH,
)
from piespector.state import PiespectorState

CommandLineTone = Literal["primary", "warning", "danger"]
CompletionKind = Literal["command", "search", "path"]


@dataclass(frozen=True)
class CommandLineContent:
    text: str
    tone: CommandLineTone = "primary"
    use_edit_buffer: bool = False
    completion_kind: CompletionKind | None = None


def command_line_content(state: PiespectorState) -> CommandLineContent | None:
    if state.mode == MODE_CONFIRM:
        return CommandLineContent(state.confirm_prompt, tone="warning")

    if state.mode == MODE_COMMAND:
        return CommandLineContent(
            f":{state.command_buffer}",
            completion_kind="command",
        )

    if state.mode == MODE_SEARCH:
        return CommandLineContent(
            f"Search {state.command_buffer}",
            completion_kind="search",
        )

    if state.mode == MODE_HOME_REQUEST_EDIT:
        _field_name, label = state.selected_request_field()
        return CommandLineContent(f"Edit {label}=", use_edit_buffer=True)

    if state.mode == MODE_HOME_REQUEST_METHOD_EDIT:
        return CommandLineContent(f"Method {state.edit_buffer or 'GET'}  h/l change, Enter save")

    if state.mode == MODE_HOME_AUTH_EDIT:
        field = state.selected_auth_field()
        label = field[1] if field is not None else "Auth"
        return CommandLineContent(f"Edit {label}=", use_edit_buffer=True)

    if state.mode == MODE_HOME_AUTH_TYPE_EDIT:
        return CommandLineContent("Auth type: h/l change, e open")

    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT:
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            return CommandLineContent("OAuth client auth: h/l change, e open")
        return CommandLineContent("API key location: h/l change, e open")

    if state.mode == MODE_HOME_PARAMS_EDIT:
        if state.params_creating_new:
            return CommandLineContent("New key=", use_edit_buffer=True)
        item = state.get_active_request_params()
        selected_key = (
            item[state.selected_param_index].key
            if item and state.selected_param_index < len(item)
            else ""
        )
        field_name, _field_label = state.selected_param_field()
        label = "Edit key=" if field_name == "key" else f"Edit {selected_key}="
        return CommandLineContent(label, use_edit_buffer=True)

    if state.mode == MODE_HOME_HEADERS_EDIT:
        if state.headers_creating_new:
            return CommandLineContent("New key=", use_edit_buffer=True)
        item = state.get_active_request_headers()
        selected_key = (
            item[state.selected_header_index].key
            if item and state.selected_header_index < len(item)
            else ""
        )
        field_name, _field_label = state.selected_header_field()
        label = "Edit key=" if field_name == "key" else f"Edit {selected_key}="
        return CommandLineContent(label, use_edit_buffer=True)

    if state.mode == MODE_HOME_BODY_TYPE_EDIT:
        return CommandLineContent("Body type: h/l change, e open")

    if state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
        return CommandLineContent("Raw type: h/l change, e open")

    if state.mode == MODE_HOME_BODY_TEXTAREA:
        if state.message:
            return CommandLineContent(state.message, tone="danger")
        return CommandLineContent("Raw body editor")

    if state.mode == MODE_HOME_BODY_EDIT:
        request = state.get_active_request()
        return CommandLineContent(
            "Path " if request is not None and request.body_type == "binary" else "Body ",
            use_edit_buffer=True,
            completion_kind="path"
            if request is not None and request.body_type == "binary"
            else None,
        )

    if state.mode == MODE_ENV_EDIT:
        if state.env_creating_new:
            return CommandLineContent("New key=", use_edit_buffer=True)
        item = state.get_selected_env_item()
        key = item[0] if item is not None else ""
        field_name, _field_label = state.selected_env_field()
        label = "Edit key=" if field_name == "key" else f"Edit {key}="
        return CommandLineContent(label, use_edit_buffer=True)

    if state.message:
        return CommandLineContent(state.message)

    return None
