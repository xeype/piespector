from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from piespector.domain.modes import (
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_SELECT,
)
from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode, selected_element_style


def render_request_options_editor(
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

    row_style = selected_element_style(
        state,
        selected=(
            mode in {MODE_HOME_REQUEST_SELECT, MODE_HOME_REQUEST_EDIT}
            and state.selected_request_field_index == 0
        ),
    )
    checkbox = Text("[x] Enabled" if request.verify_ssl else "[ ] Disabled")
    table.add_row("Verify SSL", checkbox, style=row_style)

    return table
