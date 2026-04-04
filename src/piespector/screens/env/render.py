from __future__ import annotations

from rich.text import Text

from textual.widgets import DataTable, Input, Tree
from textual.widgets._data_table import RowKey

from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL
from piespector.state import PiespectorState
from piespector.ui.selection import FOCUS_FRAME_CLASS, selected_element_style


# ================================================================
#  Sidebar tree
# ================================================================

def refresh_env_sidebar_tree(
    tree: Tree,
    state: PiespectorState,
) -> None:
    signature = tuple(state.env_names)
    if getattr(tree, "_piespector_signature", None) == signature:
        return
    tree._piespector_signature = signature
    tree.clear()
    tree.root.expand()
    for index, env_name in enumerate(state.env_names):
        tree.root.add_leaf(env_name, data=index)


def sync_env_sidebar_cursor(
    tree: Tree,
    state: PiespectorState,
) -> None:
    env_names = state.env_names
    if not env_names:
        return
    try:
        selected_index = env_names.index(state.selected_env_name)
    except ValueError:
        selected_index = 0
    tree._piespector_ignore_highlight_index = selected_index
    tree.cursor_line = selected_index
    tree.scroll_to_line(selected_index, animate=False)


# ================================================================
#  Variables table
# ================================================================

def refresh_env_table(
    table: DataTable,
    state: PiespectorState,
) -> None:
    from piespector.screens.env.screen import EnvVariablesTable
    items = state.get_env_items()
    state.clamp_selected_env_index()

    header_selected = state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT}
    fi = state.selected_env_field_index

    # Signature covers data + header highlight state; skip full rebuild on pure cursor moves
    data_signature = tuple(
        (v.key, v.value, v.sensitive, v.description) for v in items
    )
    header_signature = (header_selected, fi)
    full_signature = (data_signature, header_signature)

    if getattr(table, "_piespector_signature", None) != full_signature:
        table._piespector_signature = full_signature

        var_header = Text(
            "Variable",
            style=selected_element_style(state, selected=header_selected and fi == 0),
        )
        val_header = Text(
            "Value",
            style=selected_element_style(state, selected=header_selected and fi == 1),
        )
        desc_header = Text(
            "Description",
            style=selected_element_style(state, selected=header_selected and fi == 2),
        )
        sen_header = Text(
            "Sensitive",
            style=selected_element_style(state, selected=header_selected and fi == 3),
        )

        table.clear(columns=True)
        table.add_columns("#", var_header, val_header, desc_header, sen_header)

        for index, item in enumerate(items):
            val_display = "••••••" if item.sensitive else (item.value or "-")
            table.add_row(
                str(index + 1),
                Text(item.key),
                Text(val_display),
                Text(item.description or ""),
                Text("[x]" if item.sensitive else "[ ]"),
            )

        add_row_key = table.add_row("+", Text("Add variable"), "", "", "")
        if isinstance(table, EnvVariablesTable):
            table.set_add_row_key(add_row_key)

    table.cursor_type = "row"
    row_index = max(0, min(state.selected_env_index, table.row_count - 1))
    table.move_cursor(row=row_index, column=0, animate=False)


# ================================================================
#  Input sync
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
        if field_name == "key":
            initial_value = item.key
        elif field_name == "value":
            initial_value = item.value
        elif field_name == "description":
            initial_value = item.description
        else:
            initial_value = ""
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


# ================================================================
#  Master refresh
# ================================================================

def refresh_env_widgets(
    state: PiespectorState,
    env_tree: Tree,
    env_table: DataTable,
    env_input: Input | None = None,
    env_sidebar_container=None,
    env_main=None,
) -> None:
    refresh_env_sidebar_tree(env_tree, state)
    sync_env_sidebar_cursor(env_tree, state)
    refresh_env_table(env_table, state)
    if env_input is not None:
        _sync_env_input(env_input, state)
    if env_sidebar_container is not None:
        env_sidebar_container.set_class(state.mode == MODE_NORMAL, FOCUS_FRAME_CLASS)
    if env_main is not None:
        env_main.set_class(state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT}, FOCUS_FRAME_CLASS)


# ================================================================
#  Subtitle helpers
# ================================================================

def env_sidebar_subtitle(state: PiespectorState) -> str:
    parts = []
    if state.mode == MODE_NORMAL:
        parts.append("j/k envs")
        parts.append("e table")
        parts.append("ctrl+p commands")
    return "  |  ".join(parts)


def env_table_subtitle(state: PiespectorState) -> str:
    parts = []
    if state.mode == MODE_ENV_SELECT:
        parts.append("h/l fields")
        parts.append("e edit")
        parts.append("a add")
        parts.append("d del")
        parts.append("Esc back")
    elif state.mode == MODE_ENV_EDIT:
        parts.append("enter save")
        parts.append("Esc cancel")
    return "  |  ".join(parts)
