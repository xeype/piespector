from __future__ import annotations

from piespector.domain.editor import BODY_KEY_VALUE_TYPES, RESPONSE_TAB_BODY
from piespector.domain.modes import (
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_SECTION_SELECT,
)
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode

HOME_EMPTY_MESSAGE = "No collections or requests yet."
HOME_EMPTY_CREATE_COLLECTION = "new collection NAME"
HOME_EMPTY_CREATE_REQUEST = "new"
HOME_NO_ACTIVE_REQUEST = "No active request."
HOME_NO_RESPONSE = "No response yet. Press s to send the active request."
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


def home_render_mode(state: PiespectorState) -> str:
    return effective_mode(state)


def home_editor_subtitle(state: PiespectorState) -> str:
    mode = home_render_mode(state)
    if mode == MODE_HOME_SECTION_SELECT:
        return "h/l sections   j/k enter   e open"
    if mode == MODE_HOME_REQUEST_SELECT:
        return "h/l tabs   j/k fields   e edit"
    if mode == MODE_HOME_AUTH_SELECT:
        return "h/l tabs   j/k rows   e edit"
    if mode == MODE_HOME_AUTH_TYPE_EDIT:
        return "up/down type   e/enter confirm   esc back"
    if mode == MODE_HOME_AUTH_LOCATION_EDIT:
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            return "up/down client auth   e/enter confirm   esc back"
        return "up/down location   e/enter confirm   esc back"
    if mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_HEADERS_SELECT}:
        return "h/l tabs   j/k rows   H/L field   space toggle   e edit   a add   d delete"
    if mode == MODE_HOME_BODY_SELECT:
        request = state.get_active_request()
        if request is not None and request.body_type in BODY_KEY_VALUE_TYPES:
            return "h/l tabs   j/k rows   H/L field   space toggle   e edit   a add   d delete"
        return "h/l tabs   j/k rows   e edit"
    if mode == MODE_HOME_BODY_TYPE_EDIT:
        return "up/down type   e/enter confirm   esc back"
    if mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
        return "up/down raw   e/enter confirm   esc back"
    if mode == MODE_HOME_REQUEST_METHOD_SELECT:
        return "e open   esc back"
    if mode == MODE_HOME_REQUEST_METHOD_EDIT:
        return "up/down method   e/enter confirm   esc back"
    return ""


def home_sidebar_caption(state: PiespectorState, start: int, end: int, total: int) -> str:
    del state
    if total <= 0:
        return "Rows 0-0 of 0"
    return f"Rows {start + 1}-{end} of {total}"


def response_caption(
    start: int,
    end: int,
    total: int,
    shortcuts_enabled: bool,
    response_tab: str = RESPONSE_TAB_BODY,
    response_selected: bool = False,
    unit_label: str = "Lines",
    error: str | None = None,
) -> str:
    parts = [response_tab.title(), f"{unit_label} {start + 1}-{end} of {total}"]
    if error:
        parts.append(f"Error: {error}")
    if response_selected:
        parts.append("h/l tabs")
        parts.append("j/k scroll")
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
