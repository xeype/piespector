from __future__ import annotations

import re

from piespector.domain.requests import RequestDefinition
from piespector.placeholders import resolve_placeholders


PLACEHOLDER_VALUE_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}")


def is_placeholder_reference(value: str) -> bool:
    return bool(PLACEHOLDER_VALUE_RE.fullmatch(value.strip()))


def mask_secret_display(value: str) -> str:
    if not value:
        return "-"
    if is_placeholder_reference(value):
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(len(value) - 4, 4)}{value[-4:]}"


def mask_auth_header_display(header_name: str, value: str) -> str:
    normalized = header_name.strip().lower()
    if normalized == "authorization":
        prefix, separator, token = value.partition(" ")
        if separator:
            return f"{prefix}{separator}{mask_secret_display(token)}"
        return mask_secret_display(value)

    if normalized == "cookie":
        cookie_name, separator, cookie_value = value.partition("=")
        if separator:
            return f"{cookie_name}{separator}{mask_secret_display(cookie_value)}"
        return mask_secret_display(value)

    return mask_secret_display(value)


def is_sensitive_header_name(header_name: str) -> bool:
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


def mask_header_display(header_name: str, value: str) -> str:
    if not is_sensitive_header_name(header_name):
        return value or "-"
    return mask_auth_header_display(header_name, value)


def auth_preview_header_display_overrides(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> dict[str, str]:
    if definition.auth_type == "bearer":
        return _bearer_preview_display_overrides(definition, env_pairs)
    if definition.auth_type == "api-key" and definition.auth_api_key_location == "header":
        return _single_header_preview_override(
            resolve_placeholders(definition.auth_api_key_name, env_pairs).strip(),
            definition.auth_api_key_value,
        )
    if definition.auth_type == "cookie":
        return _cookie_preview_display_overrides(definition, env_pairs)
    if definition.auth_type == "custom-header":
        return _single_header_preview_override(
            resolve_placeholders(definition.auth_custom_header_name, env_pairs).strip(),
            definition.auth_custom_header_value,
        )
    return {}


def _single_header_preview_override(header_name: str, raw_value: str) -> dict[str, str]:
    if not header_name or not is_placeholder_reference(raw_value):
        return {}
    return {header_name.strip().lower(): raw_value.strip()}


def _bearer_preview_display_overrides(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> dict[str, str]:
    prefix = definition.auth_bearer_prefix
    token = definition.auth_bearer_token
    if not is_placeholder_reference(prefix) and not is_placeholder_reference(token):
        return {}

    prefix_display = _resolve_preview_part(prefix, env_pairs)
    token_display = _resolve_preview_part(token, env_pairs)
    if not token_display:
        return {}
    if prefix_display:
        return {"authorization": f"{prefix_display} {token_display}"}
    return {"authorization": token_display}


def _cookie_preview_display_overrides(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> dict[str, str]:
    cookie_name = resolve_placeholders(definition.auth_cookie_name, env_pairs).strip()
    cookie_value = definition.auth_cookie_value
    if not cookie_name or not is_placeholder_reference(cookie_value):
        return {}
    return {"cookie": f"{cookie_name}={cookie_value.strip()}"}


def _resolve_preview_part(raw_value: str, env_pairs: dict[str, str]) -> str:
    if is_placeholder_reference(raw_value):
        return raw_value.strip()
    return resolve_placeholders(raw_value, env_pairs).strip()
