from __future__ import annotations

import base64
import errno
import json
import re
import socket
import ssl
from time import perf_counter
from urllib import error, parse, request
from xml.etree import ElementTree

from piespector import __version__
from piespector.state import RequestDefinition, ResponseSummary

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
DEFAULT_ACCEPT = "*/*"
DEFAULT_USER_AGENT = f"piespector/{__version__}"
MULTIPART_BOUNDARY = "piespector-boundary"


def perform_request(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    timeout_seconds: float = 15.0,
) -> ResponseSummary:
    started = perf_counter()

    resolved_url = resolve_placeholders(definition.url, env_pairs)
    resolved_body = resolve_placeholders(definition.body_text, env_pairs)
    resolved_body_form_items = [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.body_form_items
        if item.enabled and item.key.strip()
    ]
    resolved_body_urlencoded_items = [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.body_urlencoded_items
        if item.enabled and item.key.strip()
    ]
    resolved_query_items = [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.query_items
        if item.enabled and item.key.strip()
    ]
    resolved_auth_query_items = _resolve_auth_query_items(
        definition,
        env_pairs,
        resolved_query_items,
    )
    resolved_header_items = _resolve_request_headers(definition, env_pairs)
    _apply_auth_headers(definition, env_pairs, resolved_header_items)

    try:
        final_url = _build_url(resolved_url, resolved_query_items + resolved_auth_query_items)
        validation_error = _validate_url(final_url)
        if validation_error is not None:
            return ResponseSummary(
                elapsed_ms=(perf_counter() - started) * 1000,
                error=validation_error,
            )

        body_validation_error = validate_raw_body(
            definition,
            resolved_body,
            resolved_header_items,
        )
        if body_validation_error is not None:
            return ResponseSummary(
                elapsed_ms=(perf_counter() - started) * 1000,
                error=body_validation_error,
            )

        headers = resolved_header_items
        _apply_default_request_headers(definition, headers)
        data = _build_request_body(
            definition,
            resolved_body,
            resolved_body_form_items,
            resolved_body_urlencoded_items,
            headers,
        )
        req = request.Request(
            final_url,
            data=data,
            headers=headers,
            method=definition.method.upper() or "GET",
        )

        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw_body = response.read()
            elapsed_ms = (perf_counter() - started) * 1000
            return ResponseSummary(
                status_code=response.status,
                elapsed_ms=elapsed_ms,
                body_length=len(raw_body),
                body_text=_decode_body(raw_body, response.headers.get_content_charset()),
                response_headers=_header_items(response.headers.items()),
            )
    except error.HTTPError as exc:
        raw_body = exc.read()
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            status_code=exc.code,
            elapsed_ms=elapsed_ms,
            body_length=len(raw_body),
            body_text=_decode_body(raw_body, exc.headers.get_content_charset()),
            error=str(exc),
            response_headers=_header_items(exc.headers.items()),
        )
    except error.URLError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc.reason),
        )
    except TimeoutError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )
    except ssl.SSLError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )
    except ValueError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_value_error(exc),
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )


def preview_effective_headers(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    explicit_headers = _resolve_request_headers(definition, env_pairs)
    effective_headers = dict(explicit_headers)
    auto_headers = preview_auto_headers(definition, env_pairs)
    inferred_headers = {
        key: value
        for key, value, enabled in auto_headers
        if enabled
    }
    for key, value in inferred_headers.items():
        effective_headers[key] = value
    return effective_headers, inferred_headers


def preview_request_url(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> str:
    resolved_url = resolve_placeholders(definition.url, env_pairs)
    query_items = _resolve_request_query_items(definition, env_pairs)
    auth_query_items = _resolve_auth_query_items(definition, env_pairs, query_items)
    return _build_url(resolved_url, query_items + auth_query_items)


def preview_auto_headers(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str, bool]]:
    explicit_headers = _resolve_request_headers(definition, env_pairs)
    resolved_body = resolve_placeholders(definition.body_text, env_pairs)
    resolved_body_form_items = _resolve_body_form_items(definition, env_pairs)
    resolved_body_urlencoded_items = _resolve_body_urlencoded_items(definition, env_pairs)

    headers: list[tuple[str, str]] = []
    if not _has_header(explicit_headers, "Accept"):
        headers.append(("Accept", DEFAULT_ACCEPT))
    if not _has_header(explicit_headers, "User-Agent"):
        headers.append(("User-Agent", DEFAULT_USER_AGENT))

    content_type = _default_content_type(
        definition,
        resolved_body,
        resolved_body_form_items,
        resolved_body_urlencoded_items,
    )
    if content_type is not None and not _has_header(explicit_headers, "Content-Type"):
        headers.append(("Content-Type", content_type))

    for key, value in _resolve_auth_header_items(definition, env_pairs):
        if not _has_header(explicit_headers, key):
            headers.append((key, value))

    return [
        (key, value, _is_auto_header_enabled(definition, key))
        for key, value in headers
    ]


def resolve_placeholders(text: str, env_pairs: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return env_pairs.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(replace, text)


def validate_raw_body(
    definition: RequestDefinition,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> str | None:
    if definition.body_type != "raw":
        return None

    payload = body_text.strip()
    if not payload:
        return None

    if _raw_body_should_validate_as_json(definition, payload, headers):
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            return (
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
            )
        return None

    if _raw_body_should_validate_as_xml(definition, payload, headers):
        try:
            ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            line, column = getattr(exc, "position", (None, None))
            if line is not None and column is not None:
                return f"Invalid XML at line {line}, column {column + 1}: {exc}."
            return f"Invalid XML: {exc}."

    return None


def _resolve_body_form_items(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str]]:
    return [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.body_form_items
        if item.enabled and item.key.strip()
    ]


def _resolve_body_urlencoded_items(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str]]:
    return [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.body_urlencoded_items
        if item.enabled and item.key.strip()
    ]


def _resolve_request_query_items(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str]]:
    return [
        (
            resolve_placeholders(item.key, env_pairs),
            resolve_placeholders(item.value, env_pairs),
        )
        for item in definition.query_items
        if item.enabled and item.key.strip()
    ]


def _resolve_auth_header_items(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str]]:
    if definition.auth_type == "basic":
        username = resolve_placeholders(definition.auth_basic_username, env_pairs)
        password = resolve_placeholders(definition.auth_basic_password, env_pairs)
        if not username and not password:
            return []
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return [("Authorization", f"Basic {token}")]

    if definition.auth_type == "bearer":
        token = resolve_placeholders(definition.auth_bearer_token, env_pairs).strip()
        if not token:
            return []
        return [("Authorization", f"Bearer {token}")]

    if definition.auth_type == "api-key" and definition.auth_api_key_location == "header":
        key = resolve_placeholders(definition.auth_api_key_name, env_pairs).strip()
        value = resolve_placeholders(definition.auth_api_key_value, env_pairs)
        if not key:
            return []
        return [(key, value)]

    return []


def _resolve_auth_query_items(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    explicit_query_items: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    if definition.auth_type != "api-key" or definition.auth_api_key_location != "query":
        return []
    key = resolve_placeholders(definition.auth_api_key_name, env_pairs).strip()
    if not key:
        return []
    explicit_keys = {item_key for item_key, _item_value in (explicit_query_items or [])}
    if key in explicit_keys:
        return []
    value = resolve_placeholders(definition.auth_api_key_value, env_pairs)
    return [(key, value)]


def _resolve_request_headers(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> dict[str, str]:
    return {
        resolve_placeholders(item.key, env_pairs).strip(): resolve_placeholders(
            item.value, env_pairs
        ).strip()
        for item in definition.header_items
        if item.enabled and resolve_placeholders(item.key, env_pairs).strip()
    }


def _apply_default_request_headers(
    definition: RequestDefinition,
    headers: dict[str, str],
) -> None:
    if _is_auto_header_enabled(definition, "Accept") and not _has_header(headers, "Accept"):
        headers["Accept"] = DEFAULT_ACCEPT
    if _is_auto_header_enabled(definition, "User-Agent") and not _has_header(headers, "User-Agent"):
        headers["User-Agent"] = DEFAULT_USER_AGENT


def _apply_auth_headers(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    headers: dict[str, str],
) -> None:
    for key, value in _resolve_auth_header_items(definition, env_pairs):
        if _has_header(headers, key) or not _is_auto_header_enabled(definition, key):
            continue
        headers[key] = value


def _build_request_body(
    definition: RequestDefinition,
    resolved_body: str,
    resolved_body_form_items: list[tuple[str, str]],
    resolved_body_urlencoded_items: list[tuple[str, str]],
    headers: dict[str, str],
) -> bytes | None:
    if definition.method.upper() == "GET":
        return None

    if definition.body_type == "none":
        return None

    if definition.body_type == "raw":
        if (
            not _has_content_type(headers)
            and _is_auto_header_enabled(definition, "Content-Type")
        ):
            headers["Content-Type"] = _default_raw_content_type(definition.raw_subtype)
        return resolved_body.encode("utf-8") if resolved_body else b""

    if definition.body_type == "form-data":
        if not _has_content_type(headers) and _is_auto_header_enabled(definition, "Content-Type"):
            headers["Content-Type"] = f"multipart/form-data; boundary={MULTIPART_BOUNDARY}"
        return _encode_multipart_form_data(resolved_body_form_items, MULTIPART_BOUNDARY)

    if definition.body_type == "x-www-form-urlencoded":
        if not _has_content_type(headers) and _is_auto_header_enabled(definition, "Content-Type"):
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return parse.urlencode(resolved_body_urlencoded_items).encode("utf-8")

    return resolved_body.encode("utf-8") if resolved_body else None


def _validate_url(url: str) -> str | None:
    candidate = url.strip()
    if not candidate:
        return "Invalid URL: enter a full http:// or https:// address."

    for character in candidate:
        if ord(character) < 32 or ord(character) == 127:
            return "Invalid URL: contains control characters. Re-enter or paste the value again."

    parsed = parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        if not parsed.scheme:
            return "Invalid URL: use a full http:// or https:// address."
        return f"Invalid URL: unsupported scheme '{parsed.scheme}'. Use http or https."

    if not parsed.netloc:
        return "Invalid URL: missing host name."

    return None


def _build_url(url: str, query_items: list[tuple[str, str]]) -> str:
    if not query_items:
        return url

    encoded_query = parse.urlencode(query_items)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{encoded_query}" if encoded_query else url


def _friendly_value_error(exc: ValueError) -> str:
    message = str(exc)
    if "unknown url type" in message.lower():
        return "Invalid URL: use a full http:// or https:// address."
    return f"Invalid request: {message}"


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


def _has_content_type(headers: dict[str, str]) -> bool:
    return _has_header(headers, "Content-Type")


def _has_header(headers: dict[str, str], header_name: str) -> bool:
    expected = header_name.lower()
    return any(key.lower() == expected for key in headers)


def _is_auto_header_enabled(definition: RequestDefinition, header_name: str) -> bool:
    expected = header_name.lower()
    return all(name.lower() != expected for name in definition.disabled_auto_headers)


def _raw_body_should_validate_as_json(
    definition: RequestDefinition,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> bool:
    stripped = body_text.strip()
    if not stripped:
        return False
    if definition.raw_subtype == "json":
        return True
    if headers is None:
        return False
    for key, value in headers.items():
        if key.lower() == "content-type" and "json" in value.lower():
            return True
    return False


def _raw_body_should_validate_as_xml(
    definition: RequestDefinition,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> bool:
    stripped = body_text.strip()
    if not stripped:
        return False
    if definition.raw_subtype == "xml":
        return True
    if headers is None:
        return False
    for key, value in headers.items():
        if key.lower() == "content-type" and "xml" in value.lower():
            return True
    return False


def _default_raw_content_type(raw_subtype: str) -> str:
    if raw_subtype == "xml":
        return "application/xml"
    if raw_subtype == "text":
        return "text/plain"
    return "application/json"


def _default_content_type(
    definition: RequestDefinition,
    resolved_body: str,
    resolved_body_form_items: list[tuple[str, str]],
    resolved_body_urlencoded_items: list[tuple[str, str]],
) -> str | None:
    if definition.method.upper() == "GET":
        return None
    if definition.body_type == "raw":
        return _default_raw_content_type(definition.raw_subtype)
    if definition.body_type == "form-data":
        return f"multipart/form-data; boundary={MULTIPART_BOUNDARY}"
    if definition.body_type == "x-www-form-urlencoded":
        return "application/x-www-form-urlencoded"
    return None


def _encode_multipart_form_data(
    fields: list[tuple[str, str]],
    boundary: str,
) -> bytes:
    lines: list[str] = []
    for key, value in fields:
        lines.extend(
            [
                f"--{boundary}",
                f'Content-Disposition: form-data; name="{key}"',
                "",
                value,
            ]
        )
    lines.append(f"--{boundary}--")
    lines.append("")
    return "\r\n".join(lines).encode("utf-8")


def _decode_body(raw_body: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        return raw_body.decode(encoding)
    except UnicodeDecodeError:
        return raw_body.decode("utf-8", errors="replace")


def response_preview(body_text: str, limit: int = 600) -> str:
    if len(body_text) <= limit:
        return body_text
    return body_text[:limit] + "\n…"


def _header_items(headers: object) -> list[tuple[str, str]]:
    return [(str(key), str(value)) for key, value in headers]
