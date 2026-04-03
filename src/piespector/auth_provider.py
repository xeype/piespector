from __future__ import annotations

import base64
from dataclasses import dataclass
import errno
import json
import socket
import ssl
from typing import Callable
from urllib import error, parse, request

from piespector import __version__
from piespector.domain.requests import RequestDefinition
from piespector.placeholders import resolve_placeholders

DEFAULT_USER_AGENT = f"piespector/{__version__}"

UrlopenCallable = Callable[..., object]


class AuthProvider:
    def preview_header_items(self) -> list[tuple[str, str]]:
        return []

    def resolve_header_items(
        self,
        *,
        timeout_seconds: float = 15.0,
        urlopen: UrlopenCallable = request.urlopen,
    ) -> list[tuple[str, str]]:
        return self.preview_header_items()

    def query_items(
        self,
        explicit_query_items: list[tuple[str, str]] | None = None,
    ) -> list[tuple[str, str]]:
        return []


class NoAuthProvider(AuthProvider):
    pass


@dataclass(frozen=True)
class BasicAuthProvider(AuthProvider):
    username: str
    password: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if not self.username and not self.password:
            return []
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode(
            "ascii"
        )
        return [("Authorization", f"Basic {token}")]


@dataclass(frozen=True)
class BearerAuthProvider(AuthProvider):
    prefix: str
    token: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if not self.token:
            return []
        return [("Authorization", _authorization_header_value(self.prefix, self.token))]


@dataclass(frozen=True)
class ApiKeyAuthProvider(AuthProvider):
    name: str
    value: str
    location: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if self.location != "header" or not self.name:
            return []
        return [(self.name, self.value)]

    def query_items(
        self,
        explicit_query_items: list[tuple[str, str]] | None = None,
    ) -> list[tuple[str, str]]:
        if self.location != "query" or not self.name:
            return []
        explicit_keys = {item_key for item_key, _item_value in (explicit_query_items or [])}
        if self.name in explicit_keys:
            return []
        return [(self.name, self.value)]


@dataclass(frozen=True)
class CookieAuthProvider(AuthProvider):
    name: str
    value: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if not self.name:
            return []
        return [("Cookie", f"{self.name}={self.value}")]


@dataclass(frozen=True)
class CustomHeaderAuthProvider(AuthProvider):
    name: str
    value: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if not self.name:
            return []
        return [(self.name, self.value)]


@dataclass(frozen=True)
class OAuthClientCredentialsAuthProvider(AuthProvider):
    token_url: str
    client_id: str
    client_secret: str
    client_authentication: str
    header_prefix: str
    scope: str

    def preview_header_items(self) -> list[tuple[str, str]]:
        if not self.token_url or not self.client_id:
            return []
        return [
            (
                "Authorization",
                _authorization_header_value(self.header_prefix, "<oauth2-token>"),
            )
        ]

    def resolve_header_items(
        self,
        *,
        timeout_seconds: float = 15.0,
        urlopen: UrlopenCallable = request.urlopen,
    ) -> list[tuple[str, str]]:
        if not self.token_url or not self.client_id:
            return []
        token_type, access_token = _fetch_oauth_client_credentials_token(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            client_authentication=self.client_authentication or "basic-header",
            scope=self.scope,
            timeout_seconds=timeout_seconds,
            urlopen=urlopen,
        )
        return [
            (
                "Authorization",
                _authorization_header_value(self.header_prefix or token_type, access_token),
            )
        ]


def build_auth_provider(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> AuthProvider:
    if definition.auth_type == "basic":
        return BasicAuthProvider(
            username=resolve_placeholders(definition.auth_basic_username, env_pairs),
            password=resolve_placeholders(definition.auth_basic_password, env_pairs),
        )

    if definition.auth_type == "bearer":
        return BearerAuthProvider(
            prefix=resolve_placeholders(definition.auth_bearer_prefix, env_pairs).strip(),
            token=resolve_placeholders(definition.auth_bearer_token, env_pairs).strip(),
        )

    if definition.auth_type == "api-key":
        return ApiKeyAuthProvider(
            name=resolve_placeholders(definition.auth_api_key_name, env_pairs).strip(),
            value=resolve_placeholders(definition.auth_api_key_value, env_pairs),
            location=definition.auth_api_key_location,
        )

    if definition.auth_type == "cookie":
        return CookieAuthProvider(
            name=resolve_placeholders(definition.auth_cookie_name, env_pairs).strip(),
            value=resolve_placeholders(definition.auth_cookie_value, env_pairs),
        )

    if definition.auth_type == "custom-header":
        return CustomHeaderAuthProvider(
            name=resolve_placeholders(definition.auth_custom_header_name, env_pairs).strip(),
            value=resolve_placeholders(definition.auth_custom_header_value, env_pairs),
        )

    if definition.auth_type == "oauth2-client-credentials":
        return OAuthClientCredentialsAuthProvider(
            token_url=resolve_placeholders(definition.auth_oauth_token_url, env_pairs).strip(),
            client_id=resolve_placeholders(definition.auth_oauth_client_id, env_pairs).strip(),
            client_secret=resolve_placeholders(definition.auth_oauth_client_secret, env_pairs),
            client_authentication=resolve_placeholders(
                definition.auth_oauth_client_authentication,
                env_pairs,
            ).strip()
            or "basic-header",
            header_prefix=resolve_placeholders(
                definition.auth_oauth_header_prefix,
                env_pairs,
            ).strip(),
            scope=resolve_placeholders(definition.auth_oauth_scope, env_pairs).strip(),
        )

    return NoAuthProvider()


def _authorization_header_value(prefix: str, token: str) -> str:
    normalized_prefix = prefix.strip()
    if not normalized_prefix:
        return token
    return f"{normalized_prefix} {token}"


def _fetch_oauth_client_credentials_token(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    client_authentication: str,
    scope: str,
    timeout_seconds: float,
    urlopen: UrlopenCallable,
) -> tuple[str, str]:
    payload = {"grant_type": "client_credentials"}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if client_authentication == "body":
        payload["client_id"] = client_id
        payload["client_secret"] = client_secret
    else:
        basic_token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode(
            "ascii"
        )
        headers["Authorization"] = f"Basic {basic_token}"
    if scope:
        payload["scope"] = scope
    data = parse.urlencode(payload).encode("utf-8")
    oauth_request = request.Request(
        token_url,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(oauth_request, timeout=timeout_seconds) as response:
            raw_body = response.read()
    except error.HTTPError as exc:
        raw_body = exc.read()
        detail = _oauth_error_detail(raw_body) or str(exc)
        raise ValueError(f"OAuth token request failed: {detail}.") from exc
    except error.URLError as exc:
        raise ValueError(
            f"OAuth token request failed: {_friendly_request_error(exc.reason)}"
        ) from exc
    except TimeoutError as exc:
        raise ValueError(
            f"OAuth token request failed: {_friendly_request_error(exc)}"
        ) from exc
    except ssl.SSLError as exc:
        raise ValueError(
            f"OAuth token request failed: {_friendly_request_error(exc)}"
        ) from exc

    try:
        payload = json.loads(_decode_body(raw_body, "utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("OAuth token response is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("OAuth token response must be a JSON object.")
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("OAuth token response did not include access_token.")
    token_type = str(payload.get("token_type", "Bearer")).strip() or "Bearer"
    return token_type, access_token


def _oauth_error_detail(raw_body: bytes) -> str:
    if not raw_body:
        return ""
    try:
        payload = json.loads(_decode_body(raw_body, "utf-8"))
    except json.JSONDecodeError:
        return _decode_body(raw_body, "utf-8").strip()
    if not isinstance(payload, dict):
        return ""
    error_code = str(payload.get("error", "")).strip()
    error_description = str(payload.get("error_description", "")).strip()
    if error_code and error_description:
        return f"{error_code}: {error_description}"
    return error_description or error_code


def _friendly_request_error(exc: object) -> str:
    if isinstance(exc, socket.gaierror):
        return "DNS lookup failed: could not resolve the host name."

    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "Request timed out: the server did not respond in time."

    if isinstance(exc, ssl.SSLError):
        return "SSL error: could not establish a secure connection."

    if isinstance(exc, ConnectionRefusedError):
        return "Connection refused: the server is not accepting connections."

    if isinstance(exc, OSError):
        if exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return "Network unavailable: could not reach the remote host."
        if exc.errno == errno.ECONNRESET:
            return "Connection reset by peer."
        if exc.errno == errno.ECONNREFUSED:
            return "Connection refused: the server is not accepting connections."

    message = str(exc).strip()
    if not message:
        return "Network error: request could not be completed."
    return f"Network error: {message}"


def _decode_body(raw_body: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        return raw_body.decode(encoding)
    except UnicodeDecodeError:
        return raw_body.decode("utf-8", errors="replace")
