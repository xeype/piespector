from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from piespector.domain.modes import MODE_HOME_HEADERS_EDIT, MODE_HOME_HEADERS_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.http_client import preview_auto_headers
from piespector.screens.home import messages, styles
from piespector.state import PiespectorState


def render_request_headers_table(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)
    state.clamp_selected_header_index(len(headers) + len(auto_headers))

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
    if state.mode in {MODE_HOME_HEADERS_SELECT, MODE_HOME_HEADERS_EDIT}:
        if state.selected_header_field_index == 0:
            key_header = Text("Key", style=styles.pill_style(styles.TEXT_URL))
        else:
            value_header = Text("Value", style=styles.pill_style(styles.TEXT_URL))
    table.add_column("#", width=4, justify="right", style=f"bold {styles.TEXT_MUTED}")
    table.add_column("On", width=6, justify="center", style=f"bold {styles.TEXT_SECONDARY}")
    table.add_column(key_header, ratio=2, style=f"bold {styles.TEXT_WARNING}")
    table.add_column(value_header, ratio=3, style=styles.TEXT_PRIMARY)

    for index, item in enumerate(headers):
        row_style = None
        if state.mode in {MODE_HOME_HEADERS_SELECT, MODE_HOME_HEADERS_EDIT} and index == state.selected_header_index:
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

    for auto_index, (key, value, enabled) in enumerate(auto_headers, start=len(headers)):
        row_style = None
        if state.mode in {MODE_HOME_HEADERS_SELECT, MODE_HOME_HEADERS_EDIT} and auto_index == state.selected_header_index:
            row_style = styles.pill_style(styles.TEXT_WARNING)
        table.add_row(
            "auto",
            Text("[x]" if enabled else "[ ]", style=f"bold {styles.TEXT_WARNING}"),
            Text(key, style=f"bold {styles.TEXT_AUTO_HEADER_KEY}"),
            Text(value or "-", style=styles.TEXT_AUTO_HEADER_VALUE),
            style=row_style or styles.ROW_AUTO_HEADER,
        )

    footer = Text(messages.HOME_HEADERS_FOOTER, style=styles.TEXT_MUTED)
    return Group(table, footer)
