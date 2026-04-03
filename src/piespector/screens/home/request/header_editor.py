from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from textual.widgets import DataTable

from piespector.domain.modes import MODE_HOME_HEADERS_EDIT, MODE_HOME_HEADERS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.request_builder import preview_auto_headers
from piespector.screens.home import messages
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode, selected_element_style


def refresh_request_headers_table(
    table: DataTable,
    request: RequestDefinition,
    state: PiespectorState,
) -> None:
    mode = effective_mode(state)
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)
    total_count = len(headers) + len(auto_headers)
    state.clamp_selected_header_index(total_count)

    header_selected = mode in {MODE_HOME_HEADERS_SELECT, MODE_HOME_HEADERS_EDIT}
    key_header = Text(
        "Key",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_header_field_index == 0,
        ),
    )
    value_header = Text(
        "Value",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_header_field_index == 1,
        ),
    )

    table.clear(columns=True)
    table.add_columns("#", "On", key_header, value_header)

    for index, item in enumerate(headers):
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]"),
            Text(item.key),
            Text(item.value or "-"),
        )

    for key, value, enabled in auto_headers:
        table.add_row(
            "auto",
            Text("[x]" if enabled else "[ ]"),
            Text(key),
            Text(value or "-"),
        )

    table.cursor_type = "row" if total_count else "none"
    if total_count:
        table.move_cursor(row=state.selected_header_index, column=0, animate=False)


def render_request_headers_fallback(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    rendered = Text()
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)

    if not headers and not auto_headers:
        rendered.append("No headers.")
    else:
        rows: list[Text] = []
        for index, item in enumerate(headers, start=1):
            status = "[x]" if item.enabled else "[ ]"
            row = Text()
            row.append(f"{index:>2} {status} {item.key}")
            row.append(f" = {item.value or '-'}")
            rows.append(row)
        for key, value, enabled in auto_headers:
            row = Text()
            row.append("auto ")
            row.append("[x]" if enabled else "[ ]")
            row.append(f" {key}")
            row.append(f" = {value or '-'}")
            rows.append(row)
        for index, row in enumerate(rows):
            rendered.append_text(row)
            if index < len(rows) - 1:
                rendered.append("\n")

    footer = Text(messages.HOME_HEADERS_FOOTER)
    return Group(rendered, footer)
