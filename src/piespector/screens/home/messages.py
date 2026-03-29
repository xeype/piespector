from __future__ import annotations

from piespector.domain.editor import BODY_KEY_VALUE_TYPES, RESPONSE_TAB_BODY
from piespector.domain.modes import (
    HOME_MODES,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState

HOME_EMPTY_MESSAGE = "No collections or requests yet."
HOME_EMPTY_CREATE_COLLECTION = ":new collection NAME"
HOME_EMPTY_CREATE_REQUEST = ":new"
HOME_NO_ACTIVE_REQUEST = "No active request."
HOME_NO_RESPONSE = "No response yet. Use :send."
HOME_SENDING_REQUEST = "Sending request..."
HOME_REQUEST_IN_PROGRESS = "Request in progress"
HOME_NO_AUTH = "No authorization configured."
HOME_NO_BODY = "No request body."
HOME_NO_BINARY_PATH = "No binary file path."
HOME_NO_BODY_TEXT = "No body."
HOME_SELECT_REQUEST_FIRST = "Select a request first."
HOME_RESPONSE_VIEWER_BODY_ONLY = "Switch to Body to open the response viewer."
HOME_AUTO_HEADER_EDIT = (
    "Auto header selected. Press space to toggle it, or add an explicit header to override it."
)
HOME_AUTO_HEADER_DELETE = (
    "Auto header selected. Press space to toggle it or override it explicitly."
)
HOME_HEADERS_FOOTER = (
    "Headers sent with the request. Explicit headers override inferred defaults."
)


def home_editor_subtitle(state: PiespectorState) -> str:
    if state.mode == MODE_HOME_SECTION_SELECT:
        return "h/l sections   e open"
    if state.mode == MODE_HOME_REQUEST_SELECT:
        return "j/k fields   e edit"
    if state.mode == MODE_HOME_AUTH_SELECT:
        return "j/k rows   e edit"
    if state.mode == MODE_HOME_AUTH_TYPE_EDIT:
        return "h/l type   e open"
    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT:
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            return "h/l client auth   e open"
        return "h/l location   e open"
    if state.mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_HEADERS_SELECT}:
        return "j/k rows   space toggle   e edit   a add   d delete"
    if state.mode == MODE_HOME_BODY_SELECT:
        request = state.get_active_request()
        if request is not None and request.body_type in BODY_KEY_VALUE_TYPES:
            return "j/k rows   space toggle   e edit   a add   d delete"
        return "e edit"
    if state.mode == MODE_HOME_BODY_TYPE_EDIT:
        return "h/l type   e open"
    if state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
        return "h/l raw   e open"
    if state.mode == MODE_HOME_REQUEST_METHOD_EDIT:
        return "h/l method"
    return ""


def home_sidebar_caption(state: PiespectorState, start: int, end: int, total: int) -> str:
    parts = [f"Rows {start + 1}-{end} of {total}"]
    if total > end or start > 0:
        parts.append("PageUp/PageDown")
    parts.append("j/k browse")
    parts.append("h/l opened")
    parts.append(":new")
    parts.append(":new collection NAME")
    parts.append(":new folder NAME")
    parts.append(":del")
    if state.mode in HOME_MODES and state.mode != MODE_NORMAL:
        parts.append("edit mode")
    return "  |  ".join(parts)


def response_caption(
    start: int,
    end: int,
    total: int,
    shortcuts_enabled: bool,
    response_tab: str = RESPONSE_TAB_BODY,
    response_selected: bool = False,
    unit_label: str = "Lines",
) -> str:
    parts = [response_tab.title(), f"{unit_label} {start + 1}-{end} of {total}"]
    if response_selected:
        parts.append("h/l tabs")
        if response_tab == RESPONSE_TAB_BODY:
            parts.append("e viewer")
    if shortcuts_enabled and (total > end or start > 0):
        parts.append("ctrl+u up")
        parts.append("ctrl+d down")
    return "  |  ".join(parts)


def auth_footer_text(state: PiespectorState, request: RequestDefinition) -> str:
    if request.auth_type == "api-key" and request.auth_api_key_location == "query":
        return "API key will be appended to the request URL as a query parameter."
    if request.auth_type == "cookie":
        return "Cookie auth is sent as a Cookie header."
    if request.auth_type == "custom-header":
        return "Custom header auth is inferred at send time. Explicit headers override it."
    if request.auth_type == "oauth2-client-credentials":
        client_auth_label = state.auth_oauth_client_authentication_label(
            request.auth_oauth_client_authentication
        ).lower()
        return (
            "OAuth 2.0 client credentials fetches a bearer token from the token URL "
            f"at send time using {client_auth_label}."
        )
    return "Auth headers are inferred at send time. Explicit headers override inferred auth."
