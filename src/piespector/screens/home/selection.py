from __future__ import annotations

from dataclasses import dataclass

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
)
from piespector.domain.modes import (
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
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_JUMP,
    MODE_NORMAL,
)
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode

REQUEST_TAB_SELECTED_MODES = {
    HOME_EDITOR_TAB_REQUEST: frozenset(
        {
            MODE_HOME_SECTION_SELECT,
            MODE_HOME_REQUEST_SELECT,
            MODE_HOME_REQUEST_EDIT,
            MODE_HOME_URL_EDIT,
        }
    ),
    HOME_EDITOR_TAB_AUTH: frozenset(
        {
            MODE_HOME_SECTION_SELECT,
            MODE_HOME_AUTH_SELECT,
            MODE_HOME_AUTH_EDIT,
            MODE_HOME_AUTH_TYPE_EDIT,
            MODE_HOME_AUTH_LOCATION_EDIT,
        }
    ),
    HOME_EDITOR_TAB_PARAMS: frozenset(
        {
            MODE_HOME_SECTION_SELECT,
            MODE_HOME_PARAMS_SELECT,
            MODE_HOME_PARAMS_EDIT,
        }
    ),
    HOME_EDITOR_TAB_HEADERS: frozenset(
        {
            MODE_HOME_SECTION_SELECT,
            MODE_HOME_HEADERS_SELECT,
            MODE_HOME_HEADERS_EDIT,
        }
    ),
    HOME_EDITOR_TAB_BODY: frozenset(
        {
            MODE_HOME_SECTION_SELECT,
            MODE_HOME_BODY_SELECT,
            MODE_HOME_BODY_TYPE_EDIT,
            MODE_HOME_BODY_RAW_TYPE_EDIT,
            MODE_HOME_BODY_EDIT,
            MODE_HOME_BODY_TEXTAREA,
        }
    ),
}

REQUEST_PANEL_MODES = frozenset().union(*REQUEST_TAB_SELECTED_MODES.values())


@dataclass(frozen=True)
class HomeSelection:
    mode: str
    panel: str
    request_tab_select: bool
    method_selected: bool
    auth_type_selected: bool
    auth_option_selected: bool
    body_type_selected: bool
    body_raw_type_selected: bool


def home_selection(state: PiespectorState) -> HomeSelection:
    mode = effective_mode(state)
    method_selected = mode in {
        MODE_HOME_REQUEST_METHOD_SELECT,
        MODE_HOME_REQUEST_METHOD_EDIT,
    }

    if mode == MODE_NORMAL:
        panel = "sidebar"
    elif method_selected or mode == MODE_HOME_URL_EDIT:
        panel = "topbar"
    elif mode in REQUEST_PANEL_MODES:
        panel = "request"
    elif mode == MODE_HOME_RESPONSE_SELECT:
        panel = "response"
    else:
        panel = "sidebar"

    return HomeSelection(
        mode=mode,
        panel=panel,
        request_tab_select=mode == MODE_HOME_SECTION_SELECT,
        method_selected=method_selected,
        auth_type_selected=mode == MODE_HOME_AUTH_TYPE_EDIT
        or (mode == MODE_HOME_AUTH_SELECT and state.selected_auth_index == 0),
        auth_option_selected=mode == MODE_HOME_AUTH_LOCATION_EDIT,
        body_type_selected=mode == MODE_HOME_BODY_TYPE_EDIT
        or (mode == MODE_HOME_BODY_SELECT and state.selected_body_index == 0),
        body_raw_type_selected=mode == MODE_HOME_BODY_RAW_TYPE_EDIT
        or (mode == MODE_HOME_BODY_SELECT and state.selected_body_index == 1),
    )


def home_highlighted_panels(state: PiespectorState) -> frozenset[str]:
    if state.mode != MODE_JUMP:
        return frozenset({home_selection(state).panel})

    highlighted_panels = {"sidebar"}
    if state.get_active_request() is not None:
        highlighted_panels.update({"topbar", "request", "response"})
    return frozenset(highlighted_panels)


def request_panel_selected(state: PiespectorState) -> bool:
    return home_selection(state).panel == "request"
