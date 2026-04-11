from __future__ import annotations

from rich.console import Group, RenderableType
from rich.style import Style
from rich.text import Text

from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist, RowKey

from piespector.domain.modes import MODE_HOME_HEADERS_EDIT, MODE_HOME_HEADERS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.request_builder import preview_auto_headers
from piespector.secrets import auth_preview_header_display_overrides, mask_header_display
from piespector.screens.home import messages
from piespector.state import PiespectorState
from piespector.ui.rendering_helpers import render_placeholder_text
from piespector.ui.selection import effective_mode, selected_element_style


class RequestHeadersTable(DataTable):
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {"request-headers-table--add-row"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._add_row_key: RowKey | None = None

    def clear(self, columns: bool = False) -> RequestHeadersTable:
        self._add_row_key = None
        return super().clear(columns=columns)

    def set_add_row_key(self, row_key: RowKey | None) -> None:
        self._add_row_key = row_key
        self.refresh()

    def _get_row_style(self, row_index: int, base_style: Style) -> Style:
        row_style = super()._get_row_style(row_index, base_style)
        if self._add_row_key is None:
            return row_style
        try:
            add_row_index = self.get_row_index(self._add_row_key)
        except RowDoesNotExist:
            self._add_row_key = None
            return row_style
        if row_index == add_row_index:
            row_style += self.get_component_styles(
                "request-headers-table--add-row"
            ).rich_style
        return row_style


def refresh_request_headers_table(
    table: RequestHeadersTable,
    request: RequestDefinition,
    state: PiespectorState,
) -> None:
    mode = effective_mode(state)
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)
    auth_display_overrides = auth_preview_header_display_overrides(request, state.env_pairs)
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
        display_value = mask_header_display(item.key, item.value)
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]"),
            render_placeholder_text(item.key),
            render_placeholder_text(display_value),
        )

    for key, value, enabled in auto_headers:
        display_value = auth_display_overrides.get(
            key.strip().lower(),
            mask_header_display(key, value),
        )
        table.add_row(
            "auto",
            Text("[x]" if enabled else "[ ]"),
            render_placeholder_text(key),
            render_placeholder_text(display_value),
        )

    add_row_key = table.add_row("+", "", Text("Add header"), "")
    table.set_add_row_key(add_row_key)

    if mode in {MODE_HOME_HEADERS_SELECT, MODE_HOME_HEADERS_EDIT}:
        table.cursor_type = "row"
        row_index = max(0, min(state.selected_header_index, table.row_count - 1))
        table.move_cursor(row=row_index, column=0, animate=False)
    else:
        table.cursor_type = "none"


def render_request_headers_fallback(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    rendered = Text()
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)
    auth_display_overrides = auth_preview_header_display_overrides(request, state.env_pairs)

    if not headers and not auto_headers:
        rendered.append("No headers.")
    else:
        rows: list[Text] = []
        for index, item in enumerate(headers, start=1):
            status = "[x]" if item.enabled else "[ ]"
            row = Text()
            row.append(f"{index:>2} {status} ")
            row.append_text(render_placeholder_text(item.key))
            row.append(" = ")
            row.append_text(
                render_placeholder_text(mask_header_display(item.key, item.value))
            )
            rows.append(row)
        for key, value, enabled in auto_headers:
            row = Text()
            row.append("auto ")
            row.append("[x]" if enabled else "[ ]")
            row.append(" ")
            row.append_text(render_placeholder_text(key))
            display_value = auth_display_overrides.get(
                key.strip().lower(),
                mask_header_display(key, value),
            )
            row.append(" = ")
            row.append_text(render_placeholder_text(display_value))
            rows.append(row)
        for index, row in enumerate(rows):
            rendered.append_text(row)
            if index < len(rows) - 1:
                rendered.append("\n")

    footer = Text(messages.HOME_HEADERS_FOOTER)
    return Group(rendered, footer)
