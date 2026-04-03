from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from textual.widgets import DataTable

from piespector.domain.editor import BODY_KEY_VALUE_TYPES
from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages
from piespector.screens.home.request.dropdown import render_dropdown_value
from piespector.screens.home.request.request_metadata import request_label
from piespector.ui.rendering_helpers import (
    preview_syntax_language,
    request_body_syntax_language,
)
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode


def body_context_label(state: PiespectorState) -> str:
    mode = effective_mode(state)
    request = state.get_active_request()
    request_name = request_label(request)
    if request is None:
        return "Body"

    if mode == MODE_HOME_BODY_TYPE_EDIT:
        return f"{request_name} / Body / {state.body_type_label(request.body_type)}"

    if request.body_type == "raw":
        return f"{request_name} / Body / Raw / {state.raw_subtype_label(request.raw_subtype)}"

    if request.body_type == "graphql":
        return f"{request_name} / Body / GraphQL"

    if request.body_type == "binary":
        return f"{request_name} / Body / Binary"

    return f"{request_name} / Body / {state.body_type_label(request.body_type)}"


def render_request_body_selector(request: RequestDefinition, state: PiespectorState) -> Text:
    mode = effective_mode(state)
    return render_dropdown_value(
        state.body_type_label(request.body_type),
        selected=(
            mode == MODE_HOME_BODY_TYPE_EDIT
            or (
                mode in {MODE_HOME_BODY_SELECT, MODE_HOME_BODY_EDIT}
                and state.selected_body_index == 0
            )
        ),
        subject=state,
    )


def render_request_body_editor(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    selector = render_request_body_selector(request, state)
    if request.body_type in BODY_KEY_VALUE_TYPES:
        return Group(selector, render_body_items_fallback(request, state))
    return Group(selector, render_request_body_preview(request, state, viewport_width))


def refresh_request_body_table(
    table: DataTable,
    request: RequestDefinition,
    state: PiespectorState,
) -> None:
    items = state.get_active_request_body_items()
    add_label = "Add field" if request.body_type == "form-data" else "Add parameter"
    state.clamp_selected_body_index()

    table.clear(columns=True)
    table.add_columns("#", "On", "Key", "Value")

    for index, item in enumerate(items, start=1):
        table.add_row(
            str(index),
            Text("[x]" if item.enabled else "[ ]"),
            Text(item.key),
            Text(item.value or "-"),
        )

    table.add_row("+", "", Text(add_label), "")

    if state.selected_body_index == 0:
        table.cursor_type = "none"
        return

    table.cursor_type = "row"
    row_index = max(0, min(state.selected_body_index - 1, table.row_count - 1))
    table.move_cursor(row=row_index, column=0, animate=False)


def render_body_items_fallback(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    items = state.get_active_request_body_items()
    add_label = "Add field" if request.body_type == "form-data" else "Add parameter"
    rendered = Text()

    if not items:
        rendered.append(add_label)
        return rendered

    for index, item in enumerate(items, start=1):
        status = "[x]" if item.enabled else "[ ]"
        rendered.append(f"{index:>2} {status} {item.key}")
        rendered.append(f" = {item.value or '-'}")
        if index < len(items):
            rendered.append("\n")
    return rendered


def render_request_body_preview(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
    *,
    include_raw_selector: bool = True,
) -> RenderableType:
    if request.body_type == "none":
        empty = Text()
        empty.append(messages.HOME_NO_BODY)
        return Panel(empty)

    return render_body_text_preview(
        request,
        state,
        viewport_width,
        include_raw_selector=include_raw_selector,
    )


def render_body_text_preview(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
    *,
    include_raw_selector: bool = True,
) -> RenderableType:
    mode = effective_mode(state)
    content: list[RenderableType] = []
    if request.body_type == "raw" and include_raw_selector:
        content.append(
            render_dropdown_value(
                state.raw_subtype_label(request.raw_subtype),
                selected=(
                    mode == MODE_HOME_BODY_RAW_TYPE_EDIT
                    or (
                        mode in {MODE_HOME_BODY_SELECT, MODE_HOME_BODY_EDIT}
                        and state.selected_body_index == 1
                    )
                ),
                subject=state,
            )
        )

    value = request.body_text
    preview = value or ""
    line_limit = 8
    preview_lines = preview.splitlines() or [preview]
    visible_preview = "\n".join(preview_lines[:line_limit])
    if len(preview_lines) > line_limit:
        visible_preview += "\n..."

    renderable: RenderableType
    stripped = value.strip()
    language = request_body_syntax_language(request)
    preview_language = preview_syntax_language(language)
    if language is not None and stripped:
        renderable = Syntax(
            visible_preview,
            preview_language or language,
            line_numbers=False,
            word_wrap=True,
            code_width=max((viewport_width or 100) - 10, 24),
            indent_guides=True,
        )
    else:
        if request.body_type == "binary":
            empty_label = messages.HOME_NO_BINARY_PATH
        else:
            empty_label = messages.HOME_NO_BODY_TEXT
        renderable = Text(visible_preview or empty_label)

    if request.body_type == "graphql":
        title = "GraphQL"
    elif request.body_type == "binary":
        title = "Binary File"
    else:
        title = f"Raw {request.raw_subtype.upper()}"

    content.append(Panel(renderable, title=title))
    return Group(*content)
