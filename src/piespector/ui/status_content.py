from __future__ import annotations

from dataclasses import dataclass

from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_EDIT,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_URL_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_JUMP,
    MODE_NORMAL,
    display_mode,
)
from piespector.screens.home.request.request_body import body_context_label
from piespector.screens.home.request.request_metadata import request_label
from piespector.state import PiespectorState
from piespector.ui.status_hints import HintItem, status_hint_items

STATUS_ENV_BADGE_LABEL = "env"
STATUS_DISPLAY_EDIT = "EDIT"
STATUS_DISPLAY_SELECT = "SELECT"
STATUS_CONTEXT_COLLECTIONS = "Collections"
STATUS_CONTEXT_DELETE = "Delete"
STATUS_CONTEXT_HISTORY = "History"
STATUS_CONTEXT_REQUEST = "Request"
STATUS_CONTEXT_URL = "URL"
STATUS_CONTEXT_AUTH = "Auth"
STATUS_CONTEXT_PARAMS = "Params"
STATUS_CONTEXT_HEADERS = "Headers"
STATUS_CONTEXT_RESPONSE = "Response"


@dataclass(frozen=True)
class StatusBarContent:
    mode_label: str
    context_label: str
    hints: tuple[HintItem, ...]
    env_label: str | None


def mode_and_context(state: PiespectorState) -> tuple[str, str]:
    if state.mode == MODE_JUMP:
        if state.current_tab == TAB_HOME:
            return (MODE_JUMP, f"{TAB_LABELS[TAB_HOME]} / {request_label(state.get_active_request())}")
        return (MODE_JUMP, TAB_LABELS.get(state.current_tab, state.current_tab.title()))

    if state.current_tab == TAB_HELP:
        if state.mode == MODE_COMMAND:
            return (MODE_COMMAND, TAB_LABELS[TAB_HELP])
        return (MODE_NORMAL, TAB_LABELS[TAB_HELP])

    if state.current_tab == TAB_ENV:
        env_label = state.active_env_label()
        item = state.get_selected_env_item()
        env_key = item[0] if item is not None else "No values"
        _field_name, field_label = state.selected_env_field()
        if state.mode == MODE_ENV_EDIT:
            if state.env_creating_new:
                return (STATUS_DISPLAY_EDIT, f"Env / {env_label} / New / Key")
            return (STATUS_DISPLAY_EDIT, f"Env / {env_label} / {env_key} / {field_label}")
        if state.mode == MODE_ENV_SELECT:
            return (STATUS_DISPLAY_SELECT, f"Env / {env_label} / {env_key} / {field_label}")
        if state.mode == MODE_COMMAND:
            return (MODE_COMMAND, f"Env / {env_label}")
        return (MODE_NORMAL, f"Env / {env_label}")

    if state.current_tab == TAB_HISTORY:
        entry = state.get_selected_history_entry()
        history_label = (
            entry.source_request_name.strip()
            or entry.source_request_path.strip()
            or STATUS_CONTEXT_HISTORY
        ) if entry is not None else STATUS_CONTEXT_HISTORY
        if state.mode == MODE_COMMAND:
            return (MODE_COMMAND, STATUS_CONTEXT_HISTORY)
        if state.mode == MODE_HISTORY_RESPONSE_SELECT:
            return (STATUS_DISPLAY_SELECT, f"History / {history_label} / {STATUS_CONTEXT_RESPONSE}")
        return (MODE_NORMAL, f"History / {history_label}")

    request = state.get_active_request()
    current_request_label = request_label(request)

    if state.mode == MODE_CONFIRM:
        node = state.get_selected_sidebar_node()
        if node is not None:
            return (MODE_CONFIRM, f"{STATUS_CONTEXT_DELETE} / {node.label}")
        return (MODE_CONFIRM, STATUS_CONTEXT_DELETE)
    if state.mode == MODE_COMMAND:
        return (MODE_COMMAND, f"{state.current_tab.title()} / {current_request_label}")
    if state.mode == MODE_HOME_SECTION_SELECT:
        current_section = state.home_editor_tab.replace("-", " ").title()
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {current_section}")
    if state.mode == MODE_HOME_REQUEST_METHOD_SELECT:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_REQUEST} / Method")
    if state.mode == MODE_HOME_URL_EDIT:
        return (STATUS_DISPLAY_EDIT, f"{current_request_label} / {STATUS_CONTEXT_REQUEST} / {STATUS_CONTEXT_URL}")
    if state.mode in {MODE_HOME_REQUEST_EDIT, MODE_HOME_REQUEST_METHOD_EDIT}:
        return (STATUS_DISPLAY_EDIT, f"{current_request_label} / {STATUS_CONTEXT_REQUEST}")
    if state.mode == MODE_HOME_REQUEST_SELECT:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_REQUEST}")
    if state.mode == MODE_HOME_AUTH_EDIT:
        return (STATUS_DISPLAY_EDIT, f"{current_request_label} / {STATUS_CONTEXT_AUTH}")
    if state.mode in {MODE_HOME_AUTH_SELECT, MODE_HOME_AUTH_TYPE_EDIT, MODE_HOME_AUTH_LOCATION_EDIT}:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_AUTH}")
    if state.mode == MODE_HOME_PARAMS_EDIT:
        return (STATUS_DISPLAY_EDIT, f"{current_request_label} / {STATUS_CONTEXT_PARAMS}")
    if state.mode == MODE_HOME_PARAMS_SELECT:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_PARAMS}")
    if state.mode == MODE_HOME_HEADERS_EDIT:
        return (STATUS_DISPLAY_EDIT, f"{current_request_label} / {STATUS_CONTEXT_HEADERS}")
    if state.mode == MODE_HOME_HEADERS_SELECT:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_HEADERS}")
    if state.mode == MODE_HOME_RESPONSE_SELECT:
        return (STATUS_DISPLAY_SELECT, f"{current_request_label} / {STATUS_CONTEXT_RESPONSE}")
    if state.mode in {
        MODE_HOME_BODY_EDIT,
        MODE_HOME_BODY_TYPE_EDIT,
        MODE_HOME_BODY_RAW_TYPE_EDIT,
        MODE_HOME_BODY_TEXTAREA,
    }:
        return (STATUS_DISPLAY_EDIT, body_context_label(state))
    if state.mode == MODE_HOME_BODY_SELECT:
        return (STATUS_DISPLAY_SELECT, body_context_label(state))
    return (MODE_NORMAL, STATUS_CONTEXT_COLLECTIONS)


def status_bar_content(state: PiespectorState) -> StatusBarContent:
    mode_label, context_label = mode_and_context(state)
    return StatusBarContent(
        mode_label=display_mode(mode_label),
        context_label=context_label,
        hints=tuple(status_hint_items(state)),
        env_label=state.active_env_label() if state.current_tab == TAB_HOME else None,
    )
