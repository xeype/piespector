from __future__ import annotations

from datetime import datetime
from urllib import parse

from piespector.http_client import preview_effective_headers, preview_request_url, resolve_placeholders
from piespector.state import HistoryEntry, RequestDefinition, ResponseSummary

BODY_STORAGE_LIMIT = 1_048_576
SENSITIVE_HEADER_MARKER = "<redacted>"
TRUNCATION_MARKER = "\n… [truncated in history]"


def build_history_entry(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    response: ResponseSummary,
    source_request_path: str,
) -> HistoryEntry:
    final_url = preview_request_url(definition, env_pairs)
    effective_headers, _auto_headers = preview_effective_headers(definition, env_pairs)
    request_headers = _redact_headers(effective_headers.items())
    request_body = _request_body_snapshot(definition, env_pairs)
    response_body = _history_body_snapshot(response.body_text)
    auth_type, auth_location, auth_name = _history_auth_snapshot(definition, env_pairs)

    return HistoryEntry(
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        source_request_id=definition.request_id,
        source_request_name=definition.name,
        source_request_path=source_request_path,
        method=definition.method.upper() or "GET",
        url=final_url,
        auth_type=auth_type,
        auth_location=auth_location,
        auth_name=auth_name,
        request_headers=request_headers,
        request_body=request_body,
        request_body_type=definition.body_type,
        status_code=response.status_code,
        elapsed_ms=response.elapsed_ms,
        response_size=response.body_length,
        response_headers=_redact_headers(response.response_headers),
        response_body=response_body,
        error=response.error,
    )


def _history_auth_snapshot(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> tuple[str, str, str]:
    if definition.auth_type == "basic":
        return ("basic", "header", "Authorization")
    if definition.auth_type == "bearer":
        return ("bearer", "header", "Authorization")
    if definition.auth_type == "api-key":
        resolved_name = resolve_placeholders(definition.auth_api_key_name, env_pairs).strip()
        return ("api-key", definition.auth_api_key_location, resolved_name)
    return ("none", "", "")


def _request_body_snapshot(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> str:
    if definition.method.upper() == "GET" or definition.body_type == "none":
        return ""

    if definition.body_type == "raw":
        body = resolve_placeholders(definition.body_text, env_pairs)
        return _history_body_snapshot(body)

    if definition.body_type == "x-www-form-urlencoded":
        body_items = [
            (
                resolve_placeholders(item.key, env_pairs),
                resolve_placeholders(item.value, env_pairs),
            )
            for item in definition.body_urlencoded_items
            if item.enabled and item.key.strip()
        ]
        return _history_body_snapshot(parse.urlencode(body_items))

    if definition.body_type == "form-data":
        body_lines = [
            f"{resolve_placeholders(item.key, env_pairs)}={resolve_placeholders(item.value, env_pairs)}"
            for item in definition.body_form_items
            if item.enabled and item.key.strip()
        ]
        return _history_body_snapshot("\n".join(body_lines))

    return _history_body_snapshot(resolve_placeholders(definition.body_text, env_pairs))


def _history_body_snapshot(body_text: str) -> str:
    if len(body_text) <= BODY_STORAGE_LIMIT:
        return body_text
    return body_text[:BODY_STORAGE_LIMIT] + TRUNCATION_MARKER


def _redact_headers(headers: object) -> list[tuple[str, str]]:
    redacted: list[tuple[str, str]] = []
    for key, value in headers:
        if _is_sensitive_header_name(str(key)):
            redacted.append((str(key), SENSITIVE_HEADER_MARKER))
        else:
            redacted.append((str(key), str(value)))
    return redacted


def _is_sensitive_header_name(header_name: str) -> bool:
    normalized = header_name.strip().lower()
    if not normalized:
        return False
    if normalized in {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
    }:
        return True
    return any(
        token in normalized
        for token in ("token", "secret", "session", "apikey")
    )
