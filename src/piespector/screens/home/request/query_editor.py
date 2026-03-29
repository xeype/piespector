from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from piespector.domain.modes import MODE_HOME_PARAMS_EDIT, MODE_HOME_PARAMS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import styles
from piespector.screens.home.request.url_bar import render_request_url_preview
from piespector.state import PiespectorState


def render_request_params_table(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    params = request.query_items

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=f"bold {styles.TEXT_SECONDARY}",
        border_style=styles.SUB_BORDER,
        row_styles=[styles.ROW_ALT_ONE, styles.ROW_ALT_TWO],
        padding=(0, 1),
    )
    key_header = Text("Key", style=f"bold {styles.TEXT_WARNING}")
    value_header = Text("Value", style=f"bold {styles.TEXT_PRIMARY}")
    if state.mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_PARAMS_EDIT}:
        if state.selected_param_field_index == 0:
            key_header = Text("Key", style=styles.pill_style(styles.TEXT_URL))
        else:
            value_header = Text("Value", style=styles.pill_style(styles.TEXT_URL))
    table.add_column("#", width=4, justify="right", style=f"bold {styles.TEXT_MUTED}")
    table.add_column("On", width=6, justify="center", style=f"bold {styles.TEXT_SECONDARY}")
    table.add_column(key_header, ratio=2, style=f"bold {styles.TEXT_WARNING}")
    table.add_column(value_header, ratio=3, style=styles.TEXT_PRIMARY)

    for index, item in enumerate(params):
        row_style = None
        if state.mode in {MODE_HOME_PARAMS_SELECT, MODE_HOME_PARAMS_EDIT} and index == state.selected_param_index:
            row_style = styles.pill_style(styles.TEXT_SUCCESS)
        key_style = f"bold {styles.TEXT_WARNING}" if item.enabled else styles.TEXT_MUTED
        value_style = styles.TEXT_PRIMARY if item.enabled else styles.TEXT_MUTED
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]", style=f"bold {styles.TEXT_PRIMARY}"),
            Text(item.key, style=key_style),
            Text(item.value or "-", style=value_style),
            style=row_style,
        )

    footer = Text()
    footer.append("Composed URL: ", style=f"bold {styles.TEXT_MUTED}")
    footer.append(render_request_url_preview(request, state) or "-", style=styles.TEXT_URL)
    return Group(table, footer)
