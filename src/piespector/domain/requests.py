from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ResponseSummary:
    status_code: int | None = None
    elapsed_ms: float | None = None
    body_length: int = 0
    body_text: str = ""
    error: str = ""
    response_headers: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class EnvVariable:
    key: str
    value: str = ""
    sensitive: bool = False
    description: str = ""


@dataclass
class RequestKeyValue:
    key: str
    value: str = ""
    enabled: bool = True


@dataclass
class RequestAuth:
    type: str = "none"
    basic_username: str = ""
    basic_password: str = ""
    bearer_prefix: str = "Bearer"
    bearer_token: str = ""
    api_key_name: str = "X-API-Key"
    api_key_value: str = ""
    api_key_location: str = "header"
    cookie_name: str = "session"
    cookie_value: str = ""
    custom_header_name: str = "X-Auth-Token"
    custom_header_value: str = ""
    oauth_token_url: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_client_authentication: str = "basic-header"
    oauth_header_prefix: str = "Bearer"
    oauth_scope: str = ""


@dataclass
class RequestBody:
    type: str = "none"
    raw_subtype: str = "json"
    text: str = ""
    raw_texts: dict[str, str] = field(default_factory=dict)
    graphql_text: str = ""
    binary_file_path: str = ""
    form_items: list[RequestKeyValue] = field(default_factory=list)
    urlencoded_items: list[RequestKeyValue] = field(default_factory=list)

    def sync_active_text(self) -> None:
        if self.type == "raw":
            self.raw_texts[self.raw_subtype] = self.text
            return
        if self.type == "graphql":
            self.graphql_text = self.text
            return
        if self.type == "binary":
            self.binary_file_path = self.text

    def restore_active_text(self, *, seed_from_text: bool = False) -> None:
        if self.type == "raw":
            existing = self.raw_texts.get(self.raw_subtype)
            if existing is None and seed_from_text and self.text:
                self.raw_texts[self.raw_subtype] = self.text
                return
            self.text = existing or ""
            return
        if self.type == "graphql":
            if not self.graphql_text and seed_from_text and self.text:
                self.graphql_text = self.text
                return
            self.text = self.graphql_text
            return
        if self.type == "binary":
            if not self.binary_file_path and seed_from_text and self.text:
                self.binary_file_path = self.text
                return
            self.text = self.binary_file_path
            return
        self.text = ""


_AUTH_LEGACY_FIELDS = {
    "auth_type": "type",
    "auth_basic_username": "basic_username",
    "auth_basic_password": "basic_password",
    "auth_bearer_prefix": "bearer_prefix",
    "auth_bearer_token": "bearer_token",
    "auth_api_key_name": "api_key_name",
    "auth_api_key_value": "api_key_value",
    "auth_api_key_location": "api_key_location",
    "auth_cookie_name": "cookie_name",
    "auth_cookie_value": "cookie_value",
    "auth_custom_header_name": "custom_header_name",
    "auth_custom_header_value": "custom_header_value",
    "auth_oauth_token_url": "oauth_token_url",
    "auth_oauth_client_id": "oauth_client_id",
    "auth_oauth_client_secret": "oauth_client_secret",
    "auth_oauth_client_authentication": "oauth_client_authentication",
    "auth_oauth_header_prefix": "oauth_header_prefix",
    "auth_oauth_scope": "oauth_scope",
}

_BODY_LEGACY_FIELDS = {
    "body_type": "type",
    "raw_subtype": "raw_subtype",
    "body_text": "text",
    "raw_body_texts": "raw_texts",
    "graphql_body_text": "graphql_text",
    "binary_file_path": "binary_file_path",
    "body_form_items": "form_items",
    "body_urlencoded_items": "urlencoded_items",
}

_MISSING = object()


@dataclass(init=False)
class RequestDefinition:
    request_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    collection_id: str | None = None
    folder_id: str | None = None
    query_items: list[RequestKeyValue] = field(default_factory=list)
    header_items: list[RequestKeyValue] = field(default_factory=list)
    auth: RequestAuth = field(default_factory=RequestAuth)
    body: RequestBody = field(default_factory=RequestBody)
    description: str = ""
    transient: bool = False
    disabled_auto_headers: list[str] = field(default_factory=list)
    verify_ssl: bool = False
    follow_redirects: bool = True
    last_response: ResponseSummary | None = None

    def __init__(self, **kwargs) -> None:
        self.request_id = kwargs.pop("request_id", uuid4().hex)
        self.name = kwargs.pop("name", "New Request")
        self.method = kwargs.pop("method", "GET")
        self.url = kwargs.pop("url", "")
        self.collection_id = kwargs.pop("collection_id", None)
        self.folder_id = kwargs.pop("folder_id", None)
        self.query_items = kwargs.pop("query_items", [])
        self.header_items = kwargs.pop("header_items", [])

        auth = kwargs.pop("auth", None)
        if auth is None:
            self.auth = RequestAuth()
        elif isinstance(auth, RequestAuth):
            self.auth = auth
        else:
            raise TypeError("auth must be a RequestAuth instance")

        body = kwargs.pop("body", None)
        if body is None:
            self.body = RequestBody()
        elif isinstance(body, RequestBody):
            self.body = body
        else:
            raise TypeError("body must be a RequestBody instance")

        self.description = kwargs.pop("description", "")
        self.transient = kwargs.pop("transient", False)
        self.disabled_auto_headers = kwargs.pop("disabled_auto_headers", [])
        self.verify_ssl = bool(kwargs.pop("verify_ssl", False))
        self.follow_redirects = bool(kwargs.pop("follow_redirects", True))
        self.last_response = kwargs.pop("last_response", None)

        self._apply_legacy_kwargs(kwargs)
        self.restore_active_body_text(seed_from_body_text=True)

    def _apply_legacy_kwargs(self, kwargs: dict[str, object]) -> None:
        for legacy_name, nested_name in _AUTH_LEGACY_FIELDS.items():
            value = kwargs.pop(legacy_name, _MISSING)
            if value is not _MISSING:
                setattr(self.auth, nested_name, value)

        for legacy_name, nested_name in _BODY_LEGACY_FIELDS.items():
            value = kwargs.pop(legacy_name, _MISSING)
            if value is not _MISSING:
                setattr(self.body, nested_name, value)

        body_form_text = kwargs.pop("body_form_text", _MISSING)
        if body_form_text is not _MISSING and not self.body.form_items:
            self.body.form_items = [
                RequestKeyValue(key=key, value=value)
                for key, value in parse_query_text(str(body_form_text))
                if key.strip()
            ]

        body_urlencoded_text = kwargs.pop("body_urlencoded_text", _MISSING)
        if body_urlencoded_text is not _MISSING and not self.body.urlencoded_items:
            self.body.urlencoded_items = [
                RequestKeyValue(key=key, value=value)
                for key, value in parse_query_text(str(body_urlencoded_text))
                if key.strip()
            ]

        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected request argument(s): {unexpected}")

    def sync_active_body_text(self) -> None:
        self.body.sync_active_text()

    def restore_active_body_text(self, *, seed_from_body_text: bool = False) -> None:
        self.body.restore_active_text(seed_from_text=seed_from_body_text)


def _nested_field_property(container_name: str, field_name: str) -> property:
    def getter(self: RequestDefinition):
        return getattr(getattr(self, container_name), field_name)

    def setter(self: RequestDefinition, value) -> None:
        setattr(getattr(self, container_name), field_name, value)

    return property(getter, setter)


def _body_items_text_property(items_field_name: str) -> property:
    def getter(self: RequestDefinition) -> str:
        items = getattr(self.body, items_field_name)
        return format_query_text(
            [(item.key, item.value) for item in items if item.key]
        )

    def setter(self: RequestDefinition, value: str) -> None:
        setattr(
            self.body,
            items_field_name,
            [
                RequestKeyValue(key=key, value=item_value)
                for key, item_value in parse_query_text(str(value))
                if key.strip()
            ],
        )

    return property(getter, setter)


for _legacy_name, _nested_name in _AUTH_LEGACY_FIELDS.items():
    setattr(RequestDefinition, _legacy_name, _nested_field_property("auth", _nested_name))
for _legacy_name, _nested_name in _BODY_LEGACY_FIELDS.items():
    setattr(RequestDefinition, _legacy_name, _nested_field_property("body", _nested_name))
RequestDefinition.body_form_text = _body_items_text_property("form_items")
RequestDefinition.body_urlencoded_text = _body_items_text_property("urlencoded_items")

del _legacy_name
del _nested_name


def parse_query_text(query_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for chunk in query_text.replace("\n", "&").split("&"):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        key = key.strip()
        value = value.strip()
        if key:
            items.append((key, value))
    return items


def format_query_text(items: list[tuple[str, str]]) -> str:
    return "&".join(f"{key}={value}" if value else key for key, value in items if key)


def parse_headers_text(headers_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for chunk in headers_text.replace(";", "\n").splitlines():
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            key, value = item.split(":", 1)
        elif "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        key = key.strip()
        value = value.strip()
        if key:
            items.append((key, value))
    return items


def format_headers_text(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"{key}: {value}" if value else key for key, value in items if key
    )
