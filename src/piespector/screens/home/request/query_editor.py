from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text

from textual.widgets import DataTable

from piespector.domain.modes import MODE_HOME_PARAMS_EDIT, MODE_HOME_PARAMS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode, selected_element_style


def refresh_request_params_table(
    table: DataTable,
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
            Text(item.key),
            Text(item.value or "-"),
        )

    table.cursor_type = "row" if params else "none"
    if params:
        table.move_cursor(row=state.selected_param_index, column=0, animate=False)


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
        rendered.append(f"{index:>2} {status} {item.key}")
        rendered.append(f" = {item.value or '-'}")
        if index < len(params):
            rendered.append("\n")
    return rendered
