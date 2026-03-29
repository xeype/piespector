from __future__ import annotations

import json
import textwrap

from pygments.style import Style as PygmentsStyle
from rich import box
from rich.console import RenderableType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from piespector.domain.requests import RequestDefinition
from piespector.ui import rich_styles as ui_styles
from piespector.ui.syntax_theme import (
    GRAPHQL_TOKEN_STYLE_OVERRIDES,
    MONOKAI_TOKEN_STYLES,
    SYNTAX_BACKGROUND,
)


class PiespectorMonokaiStyle(PygmentsStyle):
    background_color = SYNTAX_BACKGROUND
    default_style = ""
    styles = MONOKAI_TOKEN_STYLES


class PiespectorGraphQLStyle(PiespectorMonokaiStyle):
    styles = {
        **PiespectorMonokaiStyle.styles,
        **GRAPHQL_TOKEN_STYLE_OVERRIDES,
    }


SYNTAX_THEME = PiespectorMonokaiStyle
GRAPHQL_SYNTAX_THEME = PiespectorGraphQLStyle


def request_body_syntax_language(request: RequestDefinition | None) -> str | None:
    if request is None:
        return None
    if request.body_type == "graphql":
        return "graphql"
    if request.body_type != "raw":
        return None
    if request.raw_subtype == "text":
        return None
    return request.raw_subtype


def text_area_syntax_language(language: str | None) -> str | None:
    if language == "graphql":
        return "piespector-graphql"
    return language


def syntax_theme_for_language(language: str | None) -> type[PygmentsStyle]:
    if language == "graphql":
        return GRAPHQL_SYNTAX_THEME
    return SYNTAX_THEME


def preview_syntax_language(language: str | None) -> str | None:
    if language == "xml":
        return "html"
    return language


def detect_text_syntax_language(body_text: str) -> str | None:
    stripped = body_text.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    if stripped[0] in "[{":
        return "json"
    if lowered.startswith(("query ", "mutation ", "subscription ", "fragment ")):
        return "graphql"
    if lowered.startswith(("function ", "const ", "let ", "var ", "import ", "export ", "class ")):
        return "javascript"
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        return "html"
    if lowered.startswith("<?xml"):
        return "xml"
    if stripped.startswith("<"):
        if any(marker in lowered for marker in ("<head", "<body", "<div", "<span", "<script", "<style")):
            return "html"
        return "xml"
    return None


def format_response_body(body_text: str) -> str:
    stripped = body_text.strip()
    if not stripped:
        return ""

    if stripped[0] in "[{":
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return body_text
        return json.dumps(payload, indent=2, ensure_ascii=False)

    return body_text


def response_body_lines(body_text: str, viewport_width: int | None) -> list[str]:
    formatted = format_response_body(body_text)
    if not formatted:
        return ["-"]

    wrap_width = max((viewport_width or 100) - 8, 32)
    lines: list[str] = []
    for raw_line in formatted.splitlines():
        wrapped = textwrap.wrap(
            raw_line,
            width=wrap_width,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines or ["-"]


def response_header_row_count(headers: list[tuple[str, str]]) -> int:
    return max(len(headers), 1)


def render_response_body(
    body_text: str,
    viewport_width: int | None,
    start: int,
    end: int,
) -> RenderableType:
    formatted = format_response_body(body_text)
    if not formatted:
        return Text("-", style=ui_styles.TEXT_PRIMARY)

    language = detect_text_syntax_language(formatted)
    if language is not None:
        return Syntax(
            formatted,
            preview_syntax_language(language) or language,
            theme=syntax_theme_for_language(language),
            line_numbers=False,
            line_range=(start + 1, end),
            word_wrap=True,
            code_width=max((viewport_width or 100) - 8, 24),
            indent_guides=True,
        )

    return Text(
        "\n".join(response_body_lines(body_text, viewport_width)[start:end]),
        style=ui_styles.TEXT_PRIMARY,
    )


def render_response_headers(
    headers: list[tuple[str, str]],
    start: int,
    end: int,
) -> RenderableType:
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=ui_styles.secondary_style(bold=True),
        border_style=ui_styles.BORDER,
        row_styles=[ui_styles.ROW_ALT_ONE, ui_styles.ROW_ALT_TWO],
        padding=(0, 1),
    )
    table.add_column("Header", width=22, style=ui_styles.warning_style(bold=True), no_wrap=True)
    table.add_column("Value", ratio=1, style=ui_styles.TEXT_PRIMARY)

    visible_headers = headers[start:end]
    if not visible_headers:
        table.add_row("-", "-")
        return table

    for key, value in visible_headers:
        table.add_row(key, value or "-")
    return table
