from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import BODY_KEY_VALUE_TYPES, BODY_TYPE_OPTIONS, RAW_SUBTYPE_OPTIONS
from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages, styles
from piespector.screens.home.request.request_metadata import request_label
from piespector.ui.rendering_helpers import (
    preview_syntax_language,
    request_body_syntax_language,
    syntax_theme_for_language,
)
from piespector.state import PiespectorState


def body_context_label(state: PiespectorState) -> str:
    request = state.get_active_request()
    request_name = request_label(request)
    if request is None:
        return "Body"

    if state.mode == MODE_HOME_BODY_TYPE_EDIT:
        return f"{request_name} / Body / {state.body_type_label(request.body_type)}"

    if request.body_type == "raw":
        return f"{request_name} / Body / Raw / {state.raw_subtype_label(request.raw_subtype)}"

    if request.body_type == "graphql":
        return f"{request_name} / Body / GraphQL"

    if request.body_type == "binary":
        return f"{request_name} / Body / Binary"

    return f"{request_name} / Body / {state.body_type_label(request.body_type)}"


def render_request_body_editor(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    selector = Text()
    for index, (value, label) in enumerate(BODY_TYPE_OPTIONS):
        if index:
            selector.append(" ")
        is_active = request.body_type == value
        is_selected = (
            state.mode == MODE_HOME_BODY_TYPE_EDIT
            and state.selected_body_index == 0
            and is_active
        )
        style = (
            styles.pill_style(styles.TEXT_WARNING)
            if is_selected
            else styles.pill_style(styles.TEXT_URL)
            if is_active
            else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
        )
        selector.append(f" {label} ", style=style)
    if request.body_type == "none":
        empty = Text()
        empty.append(messages.HOME_NO_BODY, style=f"bold {styles.TEXT_PRIMARY}")
        return Group(selector, Panel(empty, border_style=styles.SUB_BORDER, box=box.SIMPLE_HEAVY))

    if request.body_type in BODY_KEY_VALUE_TYPES:
        return Group(selector, render_body_key_value_table(request, state))

    return Group(selector, render_body_text_editor(request, state, viewport_width))


def render_body_key_value_table(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    items = state.get_active_request_body_items()
    add_label = "Add field" if request.body_type == "form-data" else "Add parameter"

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=f"bold {styles.TEXT_SECONDARY}",
        border_style=styles.SUB_BORDER,
        row_styles=[styles.ROW_ALT_ONE, styles.ROW_ALT_TWO],
        padding=(0, 1),
    )
    table.add_column("#", width=4, justify="right", style=f"bold {styles.TEXT_MUTED}")
    table.add_column("On", width=6, justify="center", style=f"bold {styles.TEXT_SECONDARY}")
    table.add_column("Key", ratio=2, style=f"bold {styles.TEXT_WARNING}")
    table.add_column("Value", ratio=3, style=styles.TEXT_PRIMARY)

    for index, item in enumerate(items, start=1):
        row_style = None
        if state.mode in {MODE_HOME_BODY_SELECT, MODE_HOME_BODY_EDIT} and state.selected_body_index == index:
            row_style = styles.pill_style(styles.TEXT_SUCCESS)
        key_style = f"bold {styles.TEXT_WARNING}" if item.enabled else styles.TEXT_MUTED
        value_style = styles.TEXT_PRIMARY if item.enabled else styles.TEXT_MUTED
        table.add_row(
            str(index),
            Text("[x]" if item.enabled else "[ ]", style=f"bold {styles.TEXT_PRIMARY}"),
            Text(item.key, style=key_style),
            Text(item.value or "-", style=value_style),
            style=row_style,
        )

    add_style = None
    if state.mode in {MODE_HOME_BODY_SELECT, MODE_HOME_BODY_EDIT} and state.selected_body_index == len(items) + 1:
        add_style = styles.pill_style(styles.TEXT_WARNING)
    table.add_row("+", "", add_label, "", style=add_style)

    return table


def render_body_text_editor(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    subtype_selector: RenderableType = Text()
    if request.body_type == "raw":
        subtype_selector = Text()
        for index, (value, label) in enumerate(RAW_SUBTYPE_OPTIONS):
            if index:
                subtype_selector.append(" ")
            is_active = request.raw_subtype == value
            is_selected = state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT and is_active
            style = (
                styles.pill_style(styles.TEXT_WARNING)
                if is_selected
                else styles.pill_style(styles.TEXT_URL)
                if is_active
                else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
            )
            subtype_selector.append(f" {label} ", style=style)
    value = request.body_text
    preview = value or ""
    line_limit = 8
    preview_lines = preview.splitlines() or [preview]
    visible_preview = "\n".join(preview_lines[:line_limit])
    if len(preview_lines) > line_limit:
        visible_preview += "\n..."

    border_style = (
        styles.TEXT_WARNING
        if state.mode in {MODE_HOME_BODY_SELECT, MODE_HOME_BODY_EDIT} and state.selected_body_index == 1
        else styles.SUB_BORDER
    )

    renderable: RenderableType
    stripped = value.strip()
    language = request_body_syntax_language(request)
    preview_language = preview_syntax_language(language)
    if language is not None and stripped:
        renderable = Syntax(
            visible_preview,
            preview_language or language,
            theme=syntax_theme_for_language(language),
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
        renderable = Text(visible_preview or empty_label, style=styles.TEXT_PRIMARY)

    if request.body_type == "graphql":
        title = "GraphQL"
    elif request.body_type == "binary":
        title = "Binary File"
    else:
        title = f"Raw {request.raw_subtype.upper()}"

    return Group(
        subtype_selector,
        Panel(
            renderable,
            title=title,
            border_style=border_style,
            box=box.SIMPLE_HEAVY,
        ),
    )
