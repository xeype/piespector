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
class RequestKeyValue:
    key: str
    value: str = ""
    enabled: bool = True


@dataclass
class RequestDefinition:
    request_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    collection_id: str | None = None
    folder_id: str | None = None
    query_items: list[RequestKeyValue] = field(default_factory=list)
    header_items: list[RequestKeyValue] = field(default_factory=list)
    auth_type: str = "none"
    auth_basic_username: str = ""
    auth_basic_password: str = ""
    auth_bearer_prefix: str = "Bearer"
    auth_bearer_token: str = ""
    auth_api_key_name: str = "X-API-Key"
    auth_api_key_value: str = ""
    auth_api_key_location: str = "header"
    auth_cookie_name: str = "session"
    auth_cookie_value: str = ""
    auth_custom_header_name: str = "X-Auth-Token"
    auth_custom_header_value: str = ""
    auth_oauth_token_url: str = ""
    auth_oauth_client_id: str = ""
    auth_oauth_client_secret: str = ""
    auth_oauth_client_authentication: str = "basic-header"
    auth_oauth_header_prefix: str = "Bearer"
    auth_oauth_scope: str = ""
    transient: bool = False
    body_type: str = "none"
    raw_subtype: str = "json"
    body_text: str = ""
    raw_body_texts: dict[str, str] = field(default_factory=dict)
    graphql_body_text: str = ""
    binary_file_path: str = ""
    body_form_items: list[RequestKeyValue] = field(default_factory=list)
    body_urlencoded_items: list[RequestKeyValue] = field(default_factory=list)
    body_form_text: str = ""
    disabled_auto_headers: list[str] = field(default_factory=list)
    last_response: ResponseSummary | None = None

    def __post_init__(self) -> None:
        self.restore_active_body_text(seed_from_body_text=True)

    def sync_active_body_text(self) -> None:
        if self.body_type == "raw":
            self.raw_body_texts[self.raw_subtype] = self.body_text
            return
        if self.body_type == "graphql":
            self.graphql_body_text = self.body_text
            return
        if self.body_type == "binary":
            self.binary_file_path = self.body_text

    def restore_active_body_text(self, *, seed_from_body_text: bool = False) -> None:
        if self.body_type == "raw":
            existing = self.raw_body_texts.get(self.raw_subtype)
            if existing is None and seed_from_body_text and self.body_text:
                self.raw_body_texts[self.raw_subtype] = self.body_text
                return
            self.body_text = existing or ""
            return
        if self.body_type == "graphql":
            if not self.graphql_body_text and seed_from_body_text and self.body_text:
                self.graphql_body_text = self.body_text
                return
            self.body_text = self.graphql_body_text
            return
        if self.body_type == "binary":
            if not self.binary_file_path and seed_from_body_text and self.body_text:
                self.binary_file_path = self.body_text
                return
            self.body_text = self.binary_file_path
            return
        self.body_text = ""


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
