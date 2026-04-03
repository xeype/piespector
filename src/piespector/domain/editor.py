from __future__ import annotations

TAB_HOME = "home"
TAB_ENV = "env"
TAB_HISTORY = "history"
TAB_HELP = "help"

TAB_ORDER = (TAB_HOME, TAB_ENV, TAB_HISTORY)
TAB_LABELS = {
    TAB_HOME: "Home",
    TAB_ENV: "Env",
    TAB_HISTORY: "History",
    TAB_HELP: "Help",
}

HOME_SIDEBAR_LABEL = "Collections"
HOME_SIDEBAR_JUMP_KEY = "tab"

HOME_EDITOR_TAB_REQUEST = "request"
HOME_EDITOR_TAB_AUTH = "auth"
HOME_EDITOR_TAB_PARAMS = "params"
HOME_EDITOR_TAB_HEADERS = "headers"
HOME_EDITOR_TAB_BODY = "body"

REQUEST_EDITOR_TABS: tuple[tuple[str, str], ...] = (
    (HOME_EDITOR_TAB_REQUEST, "Request"),
    (HOME_EDITOR_TAB_AUTH, "Auth"),
    (HOME_EDITOR_TAB_PARAMS, "Params"),
    (HOME_EDITOR_TAB_HEADERS, "Headers"),
    (HOME_EDITOR_TAB_BODY, "Body"),
)
REQUEST_EDITOR_TAB_LABELS = dict(REQUEST_EDITOR_TABS)
REQUEST_EDITOR_JUMP_BINDINGS: tuple[tuple[str, str], ...] = (
    (HOME_EDITOR_TAB_REQUEST, "q"),
    (HOME_EDITOR_TAB_AUTH, "w"),
    (HOME_EDITOR_TAB_PARAMS, "e"),
    (HOME_EDITOR_TAB_HEADERS, "r"),
    (HOME_EDITOR_TAB_BODY, "t"),
)
REQUEST_EDITOR_TAB_TO_JUMP_KEY = dict(REQUEST_EDITOR_JUMP_BINDINGS)
REQUEST_EDITOR_JUMP_KEY_TO_TAB = {
    key: tab_id for tab_id, key in REQUEST_EDITOR_JUMP_BINDINGS
}

AUTH_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "No Auth"),
    ("basic", "Basic Auth"),
    ("bearer", "Bearer Token"),
    ("api-key", "API Key"),
    ("cookie", "Cookie Auth"),
    ("custom-header", "Custom Header"),
    ("oauth2-client-credentials", "OAuth 2.0"),
)

AUTH_API_KEY_LOCATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("header", "Header"),
    ("query", "Query"),
)

AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("basic-header", "Basic Auth header"),
    ("body", "Send creds in body"),
)

BODY_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("form-data", "Form-Data"),
    ("x-www-form-urlencoded", "x-www-form-urlencoded"),
    ("raw", "Raw"),
    ("graphql", "GraphQL"),
    ("binary", "Binary"),
)

RAW_SUBTYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("text", "Text"),
    ("json", "JSON"),
    ("xml", "XML"),
    ("html", "HTML"),
    ("javascript", "JavaScript"),
)

BODY_TEXT_EDITOR_TYPES = frozenset({"raw", "graphql"})
BODY_KEY_VALUE_TYPES = frozenset({"form-data", "x-www-form-urlencoded"})

TOP_BAR_METHOD_JUMP_KEY = "1"
TOP_BAR_URL_JUMP_KEY = "2"
TOP_BAR_JUMP_KEY_TO_TARGET = {
    TOP_BAR_METHOD_JUMP_KEY: "method",
    TOP_BAR_URL_JUMP_KEY: "url",
}

RESPONSE_TAB_BODY = "body"
RESPONSE_TAB_HEADERS = "headers"
RESPONSE_TABS: tuple[tuple[str, str], ...] = (
    (RESPONSE_TAB_BODY, "Body"),
    (RESPONSE_TAB_HEADERS, "Headers"),
)
RESPONSE_TAB_LABELS = dict(RESPONSE_TABS)
RESPONSE_JUMP_BINDINGS: tuple[tuple[str, str], ...] = (
    (RESPONSE_TAB_BODY, "a"),
    (RESPONSE_TAB_HEADERS, "s"),
)
RESPONSE_TAB_TO_JUMP_KEY = dict(RESPONSE_JUMP_BINDINGS)
RESPONSE_JUMP_KEY_TO_TAB = {
    key: tab_id for tab_id, key in RESPONSE_JUMP_BINDINGS
}

HISTORY_DETAIL_BLOCK_REQUEST = "request"
HISTORY_DETAIL_BLOCK_RESPONSE = "response"
HISTORY_DETAIL_BLOCKS = (
    HISTORY_DETAIL_BLOCK_REQUEST,
    HISTORY_DETAIL_BLOCK_RESPONSE,
)

REQUEST_FIELDS_BY_EDITOR_TAB: dict[str, tuple[tuple[str, str], ...]] = {
    HOME_EDITOR_TAB_REQUEST: (
        ("name", "Name"),
    ),
    HOME_EDITOR_TAB_AUTH: (("auth_type", "Type"),),
    HOME_EDITOR_TAB_PARAMS: (("query_text", "Params"),),
    HOME_EDITOR_TAB_HEADERS: (("headers_text", "Headers"),),
    HOME_EDITOR_TAB_BODY: (("body_type", "Body Type"), ("body_text", "Body")),
}

REQUEST_FIELDS: tuple[tuple[str, str], ...] = tuple(
    field
    for tab_id, _label in REQUEST_EDITOR_TABS
    for field in REQUEST_FIELDS_BY_EDITOR_TAB[tab_id]
)
