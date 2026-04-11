from __future__ import annotations

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text

from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist, RowKey

from piespector.domain.modes import MODE_HOME_PARAMS_EDIT, MODE_HOME_PARAMS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.rendering_helpers import render_placeholder_text
from piespector.ui.selection import effective_mode, selected_element_style


class RequestParamsTable(DataTable):
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {"request-params-table--add-row"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._add_row_key: RowKey | None = None

    def clear(self, columns: bool = False) -> RequestParamsTable:
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
                "request-params-table--add-row"
            ).rich_style
        return row_style


def refresh_request_params_table(
    table: RequestParamsTable,
    request: RequestDefinition,
    state: PiespectorState,
) -> None:
    mode = effective_mode(state)
    params = request.query_items
    state.clamp_selected_param_index()

    header_selected = mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_PARAMS_EDIT}
    key_header = Text(
        "Key",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_param_field_index == 0,
        ),
    )
    value_header = Text(
        "Value",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_param_field_index == 1,
        ),
    )

    table.clear(columns=True)
    table.add_columns("#", "On", key_header, value_header)

    for index, item in enumerate(params):
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]"),
            render_placeholder_text(item.key),
            render_placeholder_text(item.value, empty="-"),
        )

    add_row_key = table.add_row("+", "", Text("Add parameter"), "")
    table.set_add_row_key(add_row_key)

    if mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_PARAMS_EDIT}:
        table.cursor_type = "row"
        row_index = max(0, min(state.selected_param_index, table.row_count - 1))
        table.move_cursor(row=row_index, column=0, animate=False)
    else:
        table.cursor_type = "none"


def render_request_params_fallback(
    request: RequestDefinition,
    _state: PiespectorState,
) -> RenderableType:
    params = request.query_items
    if not params:
        return Text("No query params.")

    rendered = Text()
    for index, item in enumerate(params, start=1):
        status = "[x]" if item.enabled else "[ ]"
        rendered.append(f"{index:>2} {status} ")
        rendered.append_text(render_placeholder_text(item.key))
        rendered.append(" = ")
        rendered.append_text(render_placeholder_text(item.value, empty="-"))
        if index < len(params):
            rendered.append("\n")
    return rendered
