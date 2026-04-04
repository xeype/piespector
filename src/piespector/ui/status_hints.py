from __future__ import annotations

from piespector.domain.editor import BODY_KEY_VALUE_TYPES, TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME
from piespector.domain.modes import (
    INLINE_EDIT_MODES,
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_JUMP,
)
from piespector.interactions.keys import KEY_COMMAND_PALETTE, KEY_WORKSPACE_SEARCH
from piespector.state import PiespectorState

HintItem = tuple[str, str]

MODE_HINTS: dict[str, tuple[HintItem, ...]] = {
    MODE_CONFIRM: (("y", "confirm"), ("n", "cancel"), ("esc", "cancel")),
    MODE_COMMAND: (("enter", "run"), ("esc", "cancel")),
    MODE_HOME_SECTION_SELECT: (
        ("h/l", "sections"),
        ("j/k", "enter"),
        ("e", "open"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HOME_REQUEST_SELECT: (
        ("h/l", "tabs"),
        ("j/k", "fields"),
        ("e", "edit"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HOME_AUTH_SELECT: (
        ("h/l", "tabs"),
        ("j/k", "rows"),
        ("e", "edit"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HOME_PARAMS_SELECT: (
        ("h/l", "tabs"),
        ("j/k", "rows"),
        ("H/L", "fields"),
        ("space", "toggle"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HOME_HEADERS_SELECT: (
        ("h/l", "tabs"),
        ("j/k", "rows"),
        ("H/L", "fields"),
        ("space", "toggle"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HOME_BODY_TYPE_EDIT: (
        ("up/down", "type"),
        ("enter", "confirm"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_BODY_RAW_TYPE_EDIT: (
        ("up/down", "raw"),
        ("enter", "confirm"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_BODY_TEXTAREA: (("ctrl+s", "save"), ("esc", "cancel")),
    MODE_HOME_REQUEST_METHOD_SELECT: (
        ("e", "open"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_REQUEST_METHOD_EDIT: (
        ("up/down", "method"),
        ("enter", "confirm"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "cancel"),
    ),
    MODE_HOME_AUTH_TYPE_EDIT: (
        ("up/down", "type"),
        ("enter", "confirm"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_RESPONSE_SELECT: (
        ("h/l", "tabs"),
        ("j/k", "scroll"),
        ("e", "viewer"),
        ("ctrl+u/d", "scroll"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_ENV_SELECT: (
        ("h/l", "fields"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    MODE_HISTORY_RESPONSE_SELECT: (
        ("j/k", "blocks"),
        ("h/l", "tabs"),
        ("e", "viewer"),
        ("ctrl+u/d", "scroll"),
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
}

TAB_HINTS: dict[str, tuple[HintItem, ...]] = {
    TAB_HOME: (
        ("j/k", "browse"),
        ("J/K", "folders"),
        ("ctrl+j/k", "collections"),
        ("h/l", "pinned"),
        ("c", "close"),
        (KEY_WORKSPACE_SEARCH, "search"),
        ("s", "send"),
        ("e", "pin/expand"),
        ("esc", "collapse"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    TAB_ENV: (
        ("j/k", "envs"),
        ("e", "table"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    TAB_HISTORY: (
        ("j/k", "entries"),
        ("r", "replay"),
        ("e", "inspect"),
        (KEY_WORKSPACE_SEARCH, "workspace"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
    TAB_HELP: (
        ("esc", "back"),
        (KEY_COMMAND_PALETTE, "commands"),
    ),
}


def status_hint_items(state: PiespectorState) -> list[HintItem]:
    if state.mode == MODE_JUMP:
        return []

    if state.mode == MODE_HOME_BODY_SELECT:
        hints: list[HintItem] = [
            ("h/l", "tabs"),
            ("j/k", "rows"),
            ("space", "toggle"),
            ("e", "edit"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (KEY_COMMAND_PALETTE, "commands"),
        ]
        request = state.get_active_request()
        if request is not None and request.body_type in BODY_KEY_VALUE_TYPES:
            hints.insert(3, ("a", "add"))
            hints.insert(4, ("H/L", "fields"))
            hints.insert(5, ("d", "delete"))
        else:
            hints = [item for item in hints if item[0] != "space"]
        return hints

    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT:
        field = state.selected_auth_field()
        label = (
            "client auth"
            if field is not None and field[0] == "auth_oauth_client_authentication"
            else "location"
        )
        return [
            ("j/k", label),
            ("left/right", label),
            ("e", "close"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode == MODE_HOME_URL_EDIT:
        return [("enter", "save"), ("tab", "complete"), ("ctrl+v", "paste")]

    if state.mode in INLINE_EDIT_MODES:
        return [("enter", "save"), ("ctrl+v", "paste"), ("esc", "cancel")]

    if state.mode in MODE_HINTS:
        return list(MODE_HINTS[state.mode])

    return list(TAB_HINTS.get(state.current_tab, ()))
