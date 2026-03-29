from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.table import Table

from piespector.domain.modes import (
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import styles
from piespector.screens.home.request.method_selection import render_method_selector_value
from piespector.state import PiespectorState


def request_label(request: RequestDefinition | None) -> str:
    if request is None:
        return "No request"
    return request.name or "Unnamed request"


def render_request_overview_fields(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        border_style=styles.SUB_BORDER,
        padding=(0, 1),
    )
    table.add_column("Field", width=12, style=f"bold {styles.TEXT_SECONDARY}")
    table.add_column("Value", ratio=1, style=styles.TEXT_PRIMARY)

    for index, (field_name, label) in enumerate(state.current_request_fields()):
        if field_name == "method":
            value = render_method_selector_value(request, state)
        else:
            value = str(getattr(request, field_name) or "-").replace("\n", "\\n")
        row_style = None
        if (
            state.mode in {MODE_HOME_REQUEST_SELECT, MODE_HOME_REQUEST_EDIT, MODE_HOME_REQUEST_METHOD_EDIT}
            and index == state.selected_request_field_index
        ):
            row_style = styles.pill_style(styles.TEXT_WARNING)
        table.add_row(label, value, style=row_style)

    return table
