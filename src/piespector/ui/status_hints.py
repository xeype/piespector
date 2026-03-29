from __future__ import annotations

from piespector.domain.editor import BODY_KEY_VALUE_TYPES, TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME
from piespector.domain.modes import (
    INLINE_EDIT_MODES,
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HISTORY_RESPONSE_TEXTAREA,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_RESPONSE_TEXTAREA,
    MODE_HOME_SECTION_SELECT,
    MODE_SEARCH,
)
from piespector.interactions.keys import response_copy_hint_items
from piespector.state import PiespectorState

HintItem = tuple[str, str]

MODE_HINTS: dict[str, tuple[HintItem, ...]] = {
    MODE_CONFIRM: (("y", "confirm"), ("n", "cancel"), ("esc", "cancel")),
    MODE_COMMAND: (("enter", "run"), ("esc", "cancel")),
    MODE_HOME_SECTION_SELECT: (
        ("h/l", "sections"),
        ("e", "open"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HOME_REQUEST_SELECT: (
        ("j/k", "fields"),
        ("e", "edit"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HOME_AUTH_SELECT: (
        ("j/k", "rows"),
        ("e", "edit"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HOME_PARAMS_SELECT: (
        ("j/k", "rows"),
        ("h/l", "fields"),
        ("space", "toggle"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HOME_HEADERS_SELECT: (
        ("j/k", "rows"),
        ("h/l", "fields"),
        ("space", "toggle"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HOME_BODY_TYPE_EDIT: (
        ("h/l", "type"),
        ("e", "open"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_BODY_RAW_TYPE_EDIT: (
        ("h/l", "raw"),
        ("e", "open"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_BODY_TEXTAREA: (("ctrl+s", "save"), ("esc", "cancel")),
    MODE_HOME_REQUEST_METHOD_EDIT: (
        ("h/l", "method"),
        ("enter", "save"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "cancel"),
    ),
    MODE_HOME_AUTH_TYPE_EDIT: (
        ("h/l", "type"),
        ("e", "open"),
        ("s", "send"),
        ("v", "response"),
        ("ctrl+u/d", "response"),
        ("esc", "back"),
    ),
    MODE_HOME_RESPONSE_SELECT: (
        ("h/l", "tabs"),
        ("e", "viewer"),
        ("ctrl+u/d", "scroll"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_ENV_SELECT: (
        ("h/l", "fields"),
        ("e", "edit"),
        ("a", "add"),
        ("d", "delete"),
        ("esc", "back"),
        (":", "command"),
    ),
    MODE_HISTORY_RESPONSE_SELECT: (
        ("j/k", "blocks"),
        ("h/l", "tabs"),
        ("e", "viewer"),
        ("ctrl+u/d", "scroll"),
        ("esc", "back"),
        (":", "command"),
    ),
}

TAB_HINTS: dict[str, tuple[HintItem, ...]] = {
    TAB_HOME: (
        ("j/k", "sidebar"),
        ("h/l", "opened"),
        ("s", "search"),
        ("e", "open/edit"),
        ("esc", "collapse"),
        (":", "command"),
    ),
    TAB_ENV: (
        ("h/l", "envs"),
        ("j/k", "rows"),
        ("a", "add"),
        ("e", "edit"),
        (":", "command"),
    ),
    TAB_HISTORY: (
        ("j/k", "entries"),
        ("s", "search"),
        ("e", "response"),
        (":", "command"),
    ),
    TAB_HELP: (
        ("esc", "back"),
        (":", "command"),
    ),
}


def status_hint_items(state: PiespectorState) -> list[HintItem]:
    if state.mode == MODE_SEARCH:
        return [
            ("tab", "complete"),
            ("enter", "filter" if state.current_tab == TAB_HISTORY else "open"),
            ("esc", "cancel"),
        ]

    if state.mode == MODE_HOME_BODY_SELECT:
        hints: list[HintItem] = [
            ("j/k", "rows"),
            ("space", "toggle"),
            ("e", "edit"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]
        request = state.get_active_request()
        if request is not None and request.body_type in BODY_KEY_VALUE_TYPES:
            hints.insert(3, ("a", "add"))
            hints.insert(4, ("d", "delete"))
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
            ("h/l", label),
            ("e", "open"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode in {MODE_HOME_RESPONSE_TEXTAREA, MODE_HISTORY_RESPONSE_TEXTAREA}:
        return response_copy_hint_items()

    if state.mode in INLINE_EDIT_MODES:
        return [("enter", "save"), ("ctrl+c/v", "copy/paste"), ("esc", "cancel")]

    if state.mode in MODE_HINTS:
        return list(MODE_HINTS[state.mode])

    return list(TAB_HINTS.get(state.current_tab, ()))
