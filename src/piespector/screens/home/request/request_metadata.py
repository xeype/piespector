from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.table import Table

from piespector.domain.modes import (
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_SELECT,
)
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode, selected_element_style


def request_label(request: RequestDefinition | None) -> str:
    if request is None:
        return "No request"
    return request.name or "Unnamed request"


def render_request_overview_fields(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    mode = effective_mode(state)
    table = Table(
        expand=True,
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("Field", width=12)
    table.add_column("Value", ratio=1)

    for index, (field_name, label) in enumerate(state.current_request_fields()):
        value = str(getattr(request, field_name) or "-").replace("\n", "\\n")
        row_style = selected_element_style(
            state,
            selected=(
                mode in {MODE_HOME_REQUEST_SELECT, MODE_HOME_REQUEST_EDIT}
                and index == state.selected_request_field_index
            ),
        )
        table.add_row(label, value, style=row_style)

    return table
