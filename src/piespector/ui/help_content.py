from __future__ import annotations

from piespector.domain.editor import TAB_ENV, TAB_HISTORY, TAB_HOME
from piespector.domain.modes import (
    HOME_MODES,
    MODE_ENV_EDIT,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HISTORY_RESPONSE_TEXTAREA,
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_RESPONSE_TEXTAREA,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)

HELP_TITLE = "Help"
HELP_SUBTITLE_SUFFIX = "reference"
HELP_SECTION_COMMANDS = "Page Commands"
HELP_SECTION_KEYS = "Keys"
HELP_SECTION_IMPORTS = "Import / Export"
HELP_INTRO_CONTEXT = "Context"
HELP_INTRO_OPENED_FROM = "Opened from"
HELP_INTRO_ESCAPE = "Esc"
HELP_INTRO_ESCAPE_SUFFIX = "returns to the previous tab."

HELP_IMPORT_EXPORT_LINES: tuple[str, ...] = (
    "Home: export PATH writes collections, import PATH adds collections as new copies",
    "Env: export PATH writes env data, import PATH creates new env set(s)",
    "Tab completes import/export paths in command mode",
)

HOME_HELP_KEY_LINES = {
    MODE_NORMAL: (
        "Normal: j/k sidebar, h/l opened, e open request editor or toggle folders/collections, s search, : command, Esc collapse",
        "PageUp/PageDown scroll the sidebar list.",
    ),
    MODE_HOME_SECTION_SELECT: (
        "Sections: h/l sections, e or Enter open, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_REQUEST_SELECT: (
        "Request rows: j/k fields, e or Enter edit, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_REQUEST_EDIT: (
        "Request edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
    ),
    MODE_HOME_REQUEST_METHOD_EDIT: (
        "Method edit: h/l or j/k cycle methods, Enter save, Esc cancel",
    ),
    MODE_HOME_AUTH_SELECT: (
        "Auth rows: j/k rows, e or Enter edit, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_AUTH_EDIT: (
        "Auth edit: Enter save, Esc cancel, Tab path completion for file-path fields, ctrl+c copy, ctrl+v paste",
    ),
    MODE_HOME_AUTH_TYPE_EDIT: (
        "Auth type: h/l or j/k cycle auth type, e or Enter open rows, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_AUTH_LOCATION_EDIT: (
        "Auth option: h/l or j/k cycle value, e or Enter close, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_PARAMS_SELECT: (
        "Params: j/k rows, h/l fields, e or Enter edit, a add, d delete, space toggle, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_PARAMS_EDIT: (
        "Param edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
    ),
    MODE_HOME_HEADERS_SELECT: (
        "Headers: j/k rows, h/l fields, e or Enter edit, a add, d delete, space toggle explicit or auto headers, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_HEADERS_EDIT: (
        "Header edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
    ),
    MODE_HOME_BODY_SELECT: (
        "Body: j/k rows, e or Enter open or edit, a add for form bodies, d delete, space toggle, s send, v response, ctrl+u/d response scroll, Esc back",
    ),
    MODE_HOME_BODY_TYPE_EDIT: (
        "Body type: h/l cycle body types, e or Enter open the active type, Esc back",
    ),
    MODE_HOME_BODY_RAW_TYPE_EDIT: (
        "Raw subtype: h/l cycle subtypes, e or Enter open the editor, Esc back",
    ),
    MODE_HOME_BODY_EDIT: (
        "Body edit: Enter save, Esc cancel, Tab placeholder or path completion, ctrl+c copy, ctrl+v paste",
    ),
    MODE_HOME_RESPONSE_SELECT: (
        "Response: h/l body or headers, e or Enter open the body viewer, ctrl+u/d scroll, Esc back",
    ),
    MODE_HOME_RESPONSE_TEXTAREA: (
        "Response viewer: copy selection or full body with the shown shortcut, Esc closes",
    ),
}

ENV_HELP_KEY_LINES = {
    MODE_NORMAL: (
        "Env: h/l env sets, j/k rows, e or Enter open key-value fields, a add, : command",
        "Import creates new env sets instead of merging into the selected one.",
    ),
    MODE_ENV_SELECT: (
        "Env rows: h/l or j/k key-value fields, e or Enter edit, a add, d delete, Esc back",
        "Import creates new env sets instead of merging into the selected one.",
    ),
    MODE_ENV_EDIT: (
        "Env edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
    ),
}

HISTORY_HELP_KEY_LINES = {
    MODE_NORMAL: (
        "History: j/k entries, s filter, e or Enter detail mode, : command",
    ),
    MODE_HISTORY_RESPONSE_SELECT: (
        "Detail mode: j/k request-response blocks, h/l body-headers tabs, ctrl+u/d scroll the selected block, e opens the viewer, Esc back",
    ),
    MODE_HISTORY_RESPONSE_TEXTAREA: (
        "Response viewer: copy selection or full body with the shown shortcut, Esc closes",
    ),
}

DEFAULT_HELP_KEY_LINES = ("Esc returns to the previous tab.",)


def help_command_context_mode(source_tab: str, source_mode: str) -> str:
    if source_tab != TAB_HOME:
        return MODE_NORMAL
    if source_mode in HOME_MODES:
        return source_mode
    return MODE_NORMAL


def help_key_lines(source_tab: str, source_mode: str) -> tuple[str, ...]:
    if source_tab == TAB_HOME:
        return HOME_HELP_KEY_LINES.get(source_mode, HOME_HELP_KEY_LINES[MODE_NORMAL])
    if source_tab == TAB_ENV:
        return ENV_HELP_KEY_LINES.get(source_mode, ENV_HELP_KEY_LINES[MODE_NORMAL])
    if source_tab == TAB_HISTORY:
        return HISTORY_HELP_KEY_LINES.get(source_mode, HISTORY_HELP_KEY_LINES[MODE_NORMAL])
    return DEFAULT_HELP_KEY_LINES
