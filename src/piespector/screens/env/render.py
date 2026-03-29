from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import TAB_ENV
from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL
from piespector.state import PiespectorState
from piespector.ui import rich_styles as ui_styles


def env_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 20
    return max(viewport_height - 6, 1)


def render_env_viewport(
    state: PiespectorState, viewport_height: int | None
) -> RenderableType:
    selector = Text()
    for index, env_name in enumerate(state.env_names):
        if index:
            selector.append(" ")
        is_active = env_name == state.selected_env_name
        selector.append(
            f" {env_name} ",
            style=(
                ui_styles.pill_style(ui_styles.TEXT_URL)
                if is_active
                else ui_styles.pill_style(ui_styles.PILL_INACTIVE, foreground=ui_styles.TEXT_SECONDARY)
            ),
        )

    items = state.get_env_items()
    if not items:
        empty = Text()
        empty.append("No registered values.\n", style=ui_styles.primary_style(bold=True))
        empty.append("Use ", style=ui_styles.TEXT_MUTED)
        empty.append(":set KEY=value", style=ui_styles.success_style(bold=True))
        empty.append(" to add one.", style=ui_styles.TEXT_MUTED)
        return Panel(
            Group(selector, Align.left(empty)),
            title="Env",
            border_style=ui_styles.BORDER,
            box=box.ROUNDED,
            padding=(1, 2),
            subtitle=env_caption(state, 0, 0, 0),
            subtitle_align="left",
        )

    visible_rows = env_visible_rows(viewport_height)
    state.clamp_env_scroll_offset(visible_rows)
    start = state.env_scroll_offset
    end = min(start + visible_rows, len(items))
    visible_items = items[start:end]

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=ui_styles.secondary_style(bold=True),
        border_style=ui_styles.SUB_BORDER,
        row_styles=[ui_styles.ROW_ALT_ONE, ui_styles.ROW_ALT_TWO],
        padding=(0, 1),
    )
    key_header = Text("Key", style=ui_styles.warning_style(bold=True))
    value_header = Text("Value", style=ui_styles.primary_style(bold=True))
    if state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT}:
        if state.selected_env_field_index == 0:
            key_header = Text("Key", style=ui_styles.pill_style(ui_styles.TEXT_URL))
        else:
            value_header = Text("Value", style=ui_styles.pill_style(ui_styles.TEXT_URL))
    table.add_column("#", width=4, justify="right", style=ui_styles.muted_style(bold=True))
    table.add_column(key_header, ratio=2, style=ui_styles.warning_style(bold=True))
    table.add_column(value_header, ratio=3, style=ui_styles.TEXT_PRIMARY)

    for index, (key, value) in enumerate(visible_items, start=start):
        row_style = None
        if state.current_tab == TAB_ENV and index == state.selected_env_index:
            row_style = ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
        table.add_row(str(index + 1), key, value, style=row_style)

    return Panel(
        Group(selector, table),
        title="Env",
        subtitle=env_caption(state, start, end, len(items)),
        subtitle_align="left",
        border_style=ui_styles.BORDER,
        box=box.ROUNDED,
    )


def env_caption(state: PiespectorState, start: int, end: int, total: int) -> str:
    parts = [f"Env {state.active_env_label()}"]
    if total > 0:
        parts.append(f"Rows {start + 1}-{end} of {total}")
    if state.mode == MODE_NORMAL:
        parts.append("h/l envs")
        parts.append("j/k rows")
    if state.mode == MODE_ENV_SELECT:
        parts.append("h/l fields")
    if state.mode == MODE_ENV_EDIT:
        parts.append("enter save")
    parts.append("a add")
    parts.append(":new NAME")
    parts.append(":rename NAME")
    parts.append(":del")
    parts.append(":set KEY=value")
    parts.append(":edit")
    parts.append(":del KEY")
    return "  |  ".join(parts)
