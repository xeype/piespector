from __future__ import annotations

from rich.style import Style
from rich.text import Text
from urllib import parse

from piespector.domain.requests import RequestDefinition
from piespector.placeholders import PLACEHOLDER_HIGHLIGHT_COLOR, PLACEHOLDER_RE

_URL_SCHEME_COLOR = "#5fd7ff"
_URL_AUTHORITY_COLOR = "#5fafff"
_URL_PATH_COLOR = "#87ff87"
_URL_QUERY_KEY_COLOR = "#ffd75f"
_URL_QUERY_VALUE_COLOR = "#ffaf5f"
_URL_FRAGMENT_COLOR = "#5fffff"
_URL_SEPARATOR_COLOR = "#7f8c8d"
_URL_PLACEHOLDER_COLOR = PLACEHOLDER_HIGHLIGHT_COLOR


def render_request_url_display(
    request: RequestDefinition,
    *,
    clickable: bool = False,
) -> Text:
    url_template = preview_request_url_template(request)
    if not url_template:
        return Text("No URL set")
    return _render_highlighted_url(url_template, clickable=clickable)


def preview_request_url_template(request: RequestDefinition) -> str:
    query_items = _request_query_items_template(request)
    return _build_url_template(
        request.url,
        query_items + _auth_query_items_template(request, query_items),
    )


def _request_query_items_template(request: RequestDefinition) -> list[tuple[str, str]]:
    return [
        (item.key, item.value)
        for item in request.query_items
        if item.enabled and item.key.strip()
    ]


def _auth_query_items_template(
    request: RequestDefinition,
    explicit_query_items: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    if request.auth_type != "api-key" or request.auth_api_key_location != "query":
        return []

    key = request.auth_api_key_name.strip()
    if not key:
        return []

    explicit_keys = {item_key for item_key, _item_value in explicit_query_items}
    if key in explicit_keys:
        return []

    return [(key, request.auth_api_key_value)]


def _build_url_template(url: str, query_items: list[tuple[str, str]]) -> str:
    if not query_items:
        return url

    query = "&".join(f"{key}={value}" for key, value in query_items)
    if not query:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query}"


def _render_highlighted_url(url: str, *, clickable: bool) -> Text:
    parts = parse.urlsplit(url)
    text = Text()

    if parts.scheme:
        _append_url_part(text, parts.scheme, color=_URL_SCHEME_COLOR, clickable=clickable)
        _append_url_part(text, "://", color=_URL_SEPARATOR_COLOR, clickable=clickable)
        _append_url_part(text, parts.netloc, color=_URL_AUTHORITY_COLOR, clickable=clickable)
        _append_url_part(text, parts.path, color=_URL_PATH_COLOR, clickable=clickable)
    else:
        _append_url_part(text, parts.path, color=_URL_PATH_COLOR, clickable=clickable)

    if parts.query:
        _append_url_part(text, "?", color=_URL_SEPARATOR_COLOR, clickable=clickable)
        _append_query(text, parts.query, clickable=clickable)

    if parts.fragment:
        _append_url_part(text, "#", color=_URL_SEPARATOR_COLOR, clickable=clickable)
        _append_url_part(text, parts.fragment, color=_URL_FRAGMENT_COLOR, clickable=clickable)

    return text


def _append_query(text: Text, query: str, *, clickable: bool) -> None:
    for index, pair in enumerate(query.split("&")):
        if index:
            _append_url_part(text, "&", color=_URL_SEPARATOR_COLOR, clickable=clickable)
        if "=" not in pair:
            _append_url_part(text, pair, color=_URL_QUERY_KEY_COLOR, clickable=clickable)
            continue
        key, value = pair.split("=", 1)
        _append_url_part(text, key, color=_URL_QUERY_KEY_COLOR, clickable=clickable)
        _append_url_part(text, "=", color=_URL_SEPARATOR_COLOR, clickable=clickable)
        _append_url_part(text, value, color=_URL_QUERY_VALUE_COLOR, clickable=clickable)


def _append_url_part(
    text: Text,
    value: str,
    *,
    color: str,
    clickable: bool,
) -> None:
    if not value:
        return

    style = (
        Style(color=color, meta={"@click": "app.copy_active_request_url"})
        if clickable
        else Style(color=color)
    )
    placeholder_style = (
        Style(color=_URL_PLACEHOLDER_COLOR, meta={"@click": "app.copy_active_request_url"})
        if clickable
        else Style(color=_URL_PLACEHOLDER_COLOR)
    )

    start = 0
    for match in PLACEHOLDER_RE.finditer(value):
        if match.start() > start:
            text.append(value[start : match.start()], style=style)
        text.append(
            match.group(0),
            style=placeholder_style,
        )
        start = match.end()

    if start < len(value):
        text.append(value[start:], style=style)
