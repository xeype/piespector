from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from textual.widgets import DataTable, Input, Select, Static

from piespector.domain.editor import TAB_ENV
from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL
from piespector.state import PiespectorState
from piespector.ui.selection import selected_element_style


def env_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 20
    return max(viewport_height - 6, 1)


# ================================================================
#  Widget-based refresh
# ================================================================

def _sync_env_input(
    env_input: Input,
    state: PiespectorState,
) -> None:
    if state.mode != MODE_ENV_EDIT:
        env_input.display = False
        if env_input.has_focus:
            env_input.blur()
        env_input._piespector_focus_token = None
        return

    item = state.get_selected_env_item()
    field_name, field_label = state.selected_env_field()
    if state.env_creating_new:
        initial_value = ""
    elif item is not None:
        key, value = item
        initial_value = key if field_name == "key" else value
    else:
        initial_value = ""

    focus_token = (
        "env-field",
        state.selected_env_name,
        state.selected_env_index,
        state.selected_env_field_index,
        state.env_creating_new,
    )
    env_input.display = True
    env_input.placeholder = f"Env {field_label.lower()}"
    if getattr(env_input, "_piespector_focus_token", None) == focus_token:
        return
    env_input._piespector_focus_token = focus_token
    env_input.value = initial_value
    env_input.cursor_position = len(initial_value)
    env_input.focus()


def refresh_env_widgets(
    state: PiespectorState,
    env_select: Select,
    env_table: DataTable,
    env_input: Input | None = None,
) -> None:
    # Update env selector
    options = [(name, name) for name in state.env_names]
    env_select.set_options(options)
    if state.selected_env_name in state.env_names:
        env_select.value = state.selected_env_name

    # Update env table
    env_table.clear()
    items = state.get_env_items()

    for index, (key, value) in enumerate(items):
        env_table.add_row(str(index + 1), key, value)

    # Set cursor to selected row
    if items and state.selected_env_index < len(items):
        env_table.move_cursor(row=state.selected_env_index)

    # Sync env field input
    if env_input is not None:
        _sync_env_input(env_input, state)


# ================================================================
#  Legacy Rich rendering (kept for test compatibility)
# ================================================================

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
            style=selected_element_style(state, selected=is_active),
        )

    items = state.get_env_items()
    if not items:
        empty = Text()
        empty.append("No registered values.\n")
        empty.append("Open the Command Palette with Ctrl+P, then run ")
        empty.append("set KEY=value")
        empty.append(" to add one.")
        return Panel(
            Group(selector, Align.left(empty)),
            title="Env",
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
        box=box.SIMPLE,
        show_header=True,
        padding=(0, 1),
    )
    header_selected = state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT}
    key_header = Text(
        "Key",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_env_field_index == 0,
        ),
    )
    value_header = Text(
        "Value",
        style=selected_element_style(
            state,
            selected=header_selected and state.selected_env_field_index == 1,
        ),
    )
    table.add_column("#", width=4, justify="right")
    table.add_column(key_header, ratio=2)
    table.add_column(value_header, ratio=3)

    for index, (key, value) in enumerate(visible_items, start=start):
        row_style = selected_element_style(
            state,
            selected=state.current_tab == TAB_ENV and index == state.selected_env_index,
        )
        table.add_row(str(index + 1), key, value, style=row_style)

    return Panel(
        Group(selector, table),
        title="Env",
        subtitle=env_caption(state, start, end, len(items)),
        subtitle_align="left",
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
    parts.append("ctrl+p commands")
    return "  |  ".join(parts)
