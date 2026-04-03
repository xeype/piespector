from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
from urllib import parse, request
from xml.etree import ElementTree

from piespector import __version__
from piespector.auth_provider import AuthProvider, build_auth_provider
from piespector.domain.requests import RequestDefinition
from piespector.placeholders import resolve_placeholders

DEFAULT_ACCEPT = "*/*"
DEFAULT_USER_AGENT = f"piespector/{__version__}"
MULTIPART_BOUNDARY = "piespector-boundary"


class RequestValidationError(ValueError):
    pass


def build_request(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    *,
    timeout_seconds: float = 15.0,
    urlopen=request.urlopen,
) -> request.Request:
    resolved_url = resolve_placeholders(definition.url, env_pairs)
    resolved_body = resolve_placeholders(definition.body_text, env_pairs)
    resolved_body_form_items = _resolve_body_form_items(definition, env_pairs)
    resolved_body_urlencoded_items = _resolve_body_urlencoded_items(definition, env_pairs)
    resolved_query_items = _resolve_request_query_items(definition, env_pairs)
    auth_provider = build_auth_provider(definition, env_pairs)

    final_url = _build_url(
        resolved_url,
        resolved_query_items + auth_provider.query_items(resolved_query_items),
    )
    validation_error = _validate_url(final_url)
    if validation_error is not None:
        raise RequestValidationError(validation_error)

    headers = _resolve_request_headers(definition, env_pairs)
    _apply_auth_headers(
        definition,
        headers,
        auth_provider,
        timeout_seconds=timeout_seconds,
        urlopen=urlopen,
    )

    body_validation_error = validate_raw_body(
        definition,
        resolved_body,
        headers,
    )
    if body_validation_error is not None:
        raise RequestValidationError(body_validation_error)

    _apply_default_request_headers(definition, headers)
    data = _build_request_body(
        definition,
        resolved_body,
        resolved_body_form_items,
        resolved_body_urlencoded_items,
        headers,
    )
    return request.Request(
        final_url,
        data=data,
        headers=headers,
        method=definition.method.upper() or "GET",
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
    auth_provider = build_auth_provider(definition, env_pairs)
    return _build_url(resolved_url, query_items + auth_provider.query_items(query_items))


def preview_auto_headers(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
) -> list[tuple[str, str, bool]]:
    explicit_headers = _resolve_request_headers(definition, env_pairs)
    auth_provider = build_auth_provider(definition, env_pairs)

    headers: list[tuple[str, str]] = []
    if not _has_header(explicit_headers, "Accept"):
        headers.append(("Accept", DEFAULT_ACCEPT))
    if not _has_header(explicit_headers, "User-Agent"):
        headers.append(("User-Agent", DEFAULT_USER_AGENT))

    content_type = _default_content_type(definition)
    if content_type is not None and not _has_header(explicit_headers, "Content-Type"):
        headers.append(("Content-Type", content_type))

    for key, value in auth_provider.preview_header_items():
        if not _has_header(explicit_headers, key):
            headers.append((key, value))

    return [
        (key, value, _is_auto_header_enabled(definition, key))
        for key, value in headers
    ]


def validate_raw_body(
    definition: RequestDefinition,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> str | None:
    payload = body_text.strip()
    if not payload:
        return None

    if definition.body_type == "graphql":
        return _validate_graphql_body(payload)

    if definition.body_type != "raw":
        return None

    if _raw_body_should_validate_as_json(definition, payload, headers):
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
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

    if definition.raw_subtype == "html":
        return _validate_html_body(payload)

    if definition.raw_subtype == "javascript":
        return _validate_javascript_body(payload)

    return None


class _BodyHtmlValidator(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.open_tags: list[tuple[str, tuple[int, int]]] = []
        self.error_message = ""

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag.lower() not in self.VOID_TAGS:
            self.open_tags.append((tag.lower(), self.getpos()))

    def handle_startendtag(self, tag: str, attrs) -> None:  # type: ignore[override]
        return None

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        normalized = tag.lower()
        if not self.open_tags:
            line, column = self.getpos()
            self.error_message = (
                f"Unexpected closing tag </{normalized}> at line {line}, column {column + 1}."
            )
            return
        open_tag, (line, column) = self.open_tags.pop()
        if open_tag != normalized:
            self.error_message = (
                f"Mismatched closing tag </{normalized}> at line {self.getpos()[0]}, "
                f"column {self.getpos()[1] + 1}; expected </{open_tag}> for "
                f"<{open_tag}> opened at line {line}, column {column + 1}."
            )

    def error(self, message: str) -> None:
        self.error_message = message


def _validate_html_body(body_text: str) -> str | None:
    parser = _BodyHtmlValidator()
    try:
        parser.feed(body_text)
        parser.close()
    except ValueError as exc:
        return f"Invalid HTML: {exc}."
    if parser.error_message:
        return f"Invalid HTML: {parser.error_message}"
    if parser.open_tags:
        tag, (line, column) = parser.open_tags[-1]
        return (
            f"Invalid HTML: unclosed tag <{tag}> opened at line {line}, "
            f"column {column + 1}."
        )
    return None


def _validate_javascript_body(body_text: str) -> str | None:
    return _validate_balanced_source(body_text, label="JavaScript", require_curly=False)


def _validate_graphql_body(body_text: str) -> str | None:
    if "{" not in body_text:
        return "Invalid GraphQL: expected a selection set starting with '{'."
    return _validate_balanced_source(body_text, label="GraphQL", require_curly=True)


def _validate_balanced_source(
    body_text: str,
    *,
    label: str,
    require_curly: bool,
) -> str | None:
    stack: list[tuple[str, int, int]] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    in_string = False
    string_quote = ""
    escaped = False
    in_line_comment = False
    in_block_comment = False
    in_template_expression = False
    line = 1
    column = 0
    index = 0
    saw_curly = False

    while index < len(body_text):
        char = body_text[index]
        column += 1

        if char == "\n":
            line += 1
            column = 0
            if in_line_comment:
                in_line_comment = False
            index += 1
            continue

        next_char = body_text[index + 1] if index + 1 < len(body_text) else ""

        if in_line_comment:
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                column += 1
            else:
                index += 1
            continue

        if in_string:
            if escaped:
                escaped = False
                index += 1
                continue
            if char == "\\":
                escaped = True
                index += 1
                continue
            if string_quote == "`" and char == "$" and next_char == "{":
                stack.append(("{", line, column + 1))
                saw_curly = True
                in_template_expression = True
                in_string = False
                string_quote = ""
                index += 2
                column += 1
                continue
            if char == string_quote:
                in_string = False
                string_quote = ""
            index += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            column += 1
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            column += 1
            continue

        if char in {'"', "'", "`"}:
            in_string = True
            string_quote = char
            index += 1
            continue

        if char in pairs:
            stack.append((char, line, column))
            if char == "{":
                saw_curly = True
            index += 1
            continue

        if char in pairs.values():
            if not stack:
                return f"Invalid {label}: unexpected {char!r} at line {line}, column {column}."
            opener, open_line, open_column = stack.pop()
            expected = pairs[opener]
            if char != expected:
                return (
                    f"Invalid {label}: unexpected {char!r} at line {line}, column {column}; "
                    f"expected {expected!r} for {opener!r} opened at line {open_line}, "
                    f"column {open_column}."
                )
            if in_template_expression and opener == "{":
                in_template_expression = False
                in_string = True
                string_quote = "`"
            index += 1
            continue

        index += 1

    if in_string:
        return f"Invalid {label}: unterminated string literal."
    if in_block_comment:
        return f"Invalid {label}: unterminated block comment."
    if stack:
        opener, open_line, open_column = stack[-1]
        return (
            f"Invalid {label}: unclosed {opener!r} opened at line {open_line}, "
            f"column {open_column}."
        )
    if require_curly and not saw_curly:
        return f"Invalid {label}: expected a selection set enclosed in braces."
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
    headers: dict[str, str],
    auth_provider: AuthProvider,
    *,
    timeout_seconds: float = 15.0,
    urlopen=request.urlopen,
) -> None:
    for key, value in auth_provider.resolve_header_items(
        timeout_seconds=timeout_seconds,
        urlopen=urlopen,
    ):
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
        if not _has_content_type(headers) and _is_auto_header_enabled(definition, "Content-Type"):
            headers["Content-Type"] = _default_raw_content_type(definition.raw_subtype)
        return resolved_body.encode("utf-8") if resolved_body else b""

    if definition.body_type == "graphql":
        if not _has_content_type(headers) and _is_auto_header_enabled(definition, "Content-Type"):
            headers["Content-Type"] = "application/graphql"
        return resolved_body.encode("utf-8") if resolved_body else b""

    if definition.body_type == "binary":
        if not _has_content_type(headers) and _is_auto_header_enabled(definition, "Content-Type"):
            headers["Content-Type"] = "application/octet-stream"
        return _read_binary_body(resolved_body)

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
    if raw_subtype == "html":
        return "text/html"
    if raw_subtype == "javascript":
        return "application/javascript"
    if raw_subtype == "text":
        return "text/plain"
    return "application/json"


def _default_content_type(definition: RequestDefinition) -> str | None:
    if definition.method.upper() == "GET":
        return None
    if definition.body_type == "raw":
        return _default_raw_content_type(definition.raw_subtype)
    if definition.body_type == "graphql":
        return "application/graphql"
    if definition.body_type == "binary":
        return "application/octet-stream"
    if definition.body_type == "form-data":
        return f"multipart/form-data; boundary={MULTIPART_BOUNDARY}"
    if definition.body_type == "x-www-form-urlencoded":
        return "application/x-www-form-urlencoded"
    return None


def _read_binary_body(path_text: str) -> bytes | None:
    candidate = path_text.strip()
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise ValueError(f"Binary body file does not exist: {path}.")
    if not path.is_file():
        raise ValueError(f"Binary body path is not a file: {path}.")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Could not read binary body file: {exc}.") from exc


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
