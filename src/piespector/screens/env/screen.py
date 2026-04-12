from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.style import Style
from textual.widgets import DataTable, Input, Static, Tree
from textual.widgets._data_table import RowDoesNotExist, RowKey

from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT, MODE_NORMAL
from piespector.interactions.keys import (
    KEY_ADD,
    KEY_DELETE_ROW,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SPACE,
    DOWN_KEYS,
    LEFT_KEYS,
    OPEN_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
)
from piespector.screens.base import PiespectorScreen
from piespector.ui.input import PiespectorInput
from piespector.ui.selection import FOCUS_FRAME_CLASS, selected_element_style
from piespector.widget.tree import (
    PiespectorTree,
    move_cursor as tree_move_cursor,
    rebuild as rebuild_tree,
)

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class EnvVariablesTable(DataTable):
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {"env-table--add-row"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._add_row_key: RowKey | None = None

    def clear(self, columns: bool = False) -> EnvVariablesTable:
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
            row_style += self.get_component_styles("env-table--add-row").rich_style
        return row_style


class EnvScreen(PiespectorScreen):
    selected_env_index = reactive(0)
    selected_env_field_index = reactive(0)
    env_scroll_offset = reactive(0)
    env_creating_new = reactive(False)

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    @property
    def _state(self) -> PiespectorState | None:
        app = self._owner_app()
        return None if app is None else app.state

    def _env_sidebar_tree(self) -> PiespectorTree | None:
        if not self.is_mounted:
            return None
        try:
            return self.query_one("#env-sidebar-tree", PiespectorTree)
        except NoMatches:
            return None

    def _env_input(self) -> Input | None:
        if not self.is_mounted:
            return None
        try:
            return self.query_one("#env-field-input", Input)
        except NoMatches:
            return None

    def on_key(self, event: events.Key) -> None:
        state = self._state
        if state is None:
            return
        if state.mode == MODE_NORMAL:
            self.handle_view_key(event)
            return
        if state.mode == MODE_ENV_SELECT:
            self.handle_select_key(event)
            return
        if state.mode == MODE_ENV_EDIT:
            self.handle_edit_key(event)

    def handle_view_key(self, event: events.Key) -> bool:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return False

        if event.key in DOWN_KEYS:
            tree = self._env_sidebar_tree()
            if tree is not None:
                tree.action_cursor_down()
            else:
                state.select_env_set(1)
                app._refresh_screen()
            event.stop()
            return True

        if event.key in UP_KEYS:
            tree = self._env_sidebar_tree()
            if tree is not None:
                tree.action_cursor_up()
            else:
                state.select_env_set(-1)
                app._refresh_screen()
            event.stop()
            return True

        if event.key in OPEN_KEYS:
            state.enter_env_select_mode()
            app._refresh_screen()
            event.stop()
            return True

        return False

    def handle_select_key(self, event: events.Key) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return

        if event.key == KEY_ESCAPE:
            state.leave_env_interaction()
            app._refresh_screen()
            event.stop()
            return

        if event.key in LEFT_KEYS:
            state.cycle_env_field(-1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in RIGHT_KEYS:
            state.cycle_env_field(1)
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SPACE:
            state.toggle_selected_env_sensitive()
            app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            state.enter_env_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ADD:
            state.enter_env_create_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            state.delete_selected_env_item()
            app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            state.select_env_row(1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            state.select_env_row(-1)
            app._refresh_screen()
            event.stop()

    def handle_edit_key(self, event: events.Key) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return

        env_input = self._env_input()
        if env_input is not None and env_input.display:
            if event.key == KEY_ESCAPE:
                state.leave_env_edit_mode()
                app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            state.leave_env_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            state.save_selected_env_field()
            app._refresh_screen()
            event.stop()

    def compose_workspace(self) -> ComposeResult:
        with Horizontal(id="env-screen"):
            with Vertical(id="env-sidebar-container"):
                yield Static("Environments", classes="panel-title", id="env-sidebar-title")
                yield PiespectorTree("Environments", id="env-sidebar-tree")
                yield Static("", classes="panel-subtitle", id="env-sidebar-subtitle")
            with Vertical(id="env-main"):
                yield EnvVariablesTable(
                    id="env-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )
                yield PiespectorInput(
                    "",
                    id="env-field-input",
                    compact=True,
                    select_on_focus=False,
                )

    def on_mount(self) -> None:
        super().on_mount()
        tree = self.query_one("#env-sidebar-tree", PiespectorTree)
        tree.show_root = False
        tree.focus()
        self.disable_focus("env-table")
        self.query_one("#env-field-input").display = False
        self.query_one("#env-sidebar-container").border_title = "Environments"
        self.refresh_from_state()

    def env_visible_rows(self) -> int:
        try:
            table = self.query_one("#env-table", DataTable)
            return max(table.size.height - 2, 1)
        except Exception:
            return 20

    def refresh_from_state(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        state.ensure_env_workspace()
        state.ensure_env_selection_visible(self.env_visible_rows())
        self._refresh_sidebar_tree(state)
        self._sync_sidebar_cursor(state)
        self._refresh_table(state)
        self._sync_input(state)
        self._sync_focus(state)

    def watch_selected_env_index(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        self._sync_table_cursor()
        self._sync_input(state)

    def watch_selected_env_field_index(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        self._refresh_table(state)
        self._sync_input(state)

    def watch_env_creating_new(self) -> None:
        if not self.is_mounted:
            return
        state = self._state
        if state is None:
            return
        self._sync_input(state)

    def _refresh_sidebar_tree(self, state: PiespectorState) -> None:
        tree = self.query_one("#env-sidebar-tree", PiespectorTree)
        env_names = state.env_names
        rebuild_tree(
            tree,
            tuple(env_names),
            lambda t: [t.root.add_leaf(name, data=index) for index, name in enumerate(env_names)],
        )

    def _sync_sidebar_cursor(self, state: PiespectorState) -> None:
        env_names = state.env_names
        if not env_names:
            return
        try:
            selected_index = env_names.index(state.selected_env_name)
        except ValueError:
            selected_index = 0
        tree_move_cursor(self.query_one("#env-sidebar-tree", PiespectorTree), selected_index)

    def _refresh_table(self, state: PiespectorState) -> None:
        table = self.query_one("#env-table", EnvVariablesTable)
        items = state.get_env_items()
        state.clamp_selected_env_index()

        header_selected = state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT}
        field_index = self.selected_env_field_index

        data_signature = tuple(
            (item.key, item.value, item.sensitive, item.description) for item in items
        )
        header_signature = (header_selected, field_index)
        full_signature = (data_signature, header_signature)

        if getattr(table, "_piespector_signature", None) != full_signature:
            table._piespector_signature = full_signature

            table.clear(columns=True)
            table.add_columns(
                "#",
                Text(
                    "Variable",
                    style=selected_element_style(state, selected=header_selected and field_index == 0),
                ),
                Text(
                    "Value",
                    style=selected_element_style(state, selected=header_selected and field_index == 1),
                ),
                Text(
                    "Description",
                    style=selected_element_style(state, selected=header_selected and field_index == 2),
                ),
                Text(
                    "Sensitive",
                    style=selected_element_style(state, selected=header_selected and field_index == 3),
                ),
            )

            for index, item in enumerate(items):
                value_display = "••••••" if item.sensitive else (item.value or "-")
                table.add_row(
                    str(index + 1),
                    Text(item.key),
                    Text(value_display),
                    Text(item.description or ""),
                    Text("[x]" if item.sensitive else "[ ]"),
                )

            table.set_add_row_key(table.add_row("+", Text("Add variable"), "", "", ""))

        self._sync_table_cursor()

    def _sync_table_cursor(self) -> None:
        table = self.query_one("#env-table", EnvVariablesTable)
        table.cursor_type = "row"
        if table.row_count <= 0:
            return
        row_index = max(0, min(self.selected_env_index, table.row_count - 1))
        table.move_cursor(row=row_index, column=0, animate=False)

    def _sync_input(self, state: PiespectorState) -> None:
        env_input = self.query_one("#env-field-input", Input)
        if state.mode != MODE_ENV_EDIT:
            env_input.display = False
            if env_input.has_focus:
                env_input.blur()
            env_input._piespector_focus_token = None
            return

        item = state.get_selected_env_item()
        field_name, field_label = state.selected_env_field()
        if self.env_creating_new:
            initial_value = ""
        elif item is None:
            initial_value = ""
        elif field_name == "key":
            initial_value = item.key
        elif field_name == "value":
            initial_value = item.value
        elif field_name == "description":
            initial_value = item.description
        else:
            initial_value = ""

        focus_token = (
            "env-field",
            state.selected_env_name,
            self.selected_env_index,
            self.selected_env_field_index,
            self.env_creating_new,
        )
        env_input.display = True
        env_input.placeholder = f"Env {field_label.lower()}"
        if getattr(env_input, "_piespector_focus_token", None) == focus_token:
            return
        env_input._piespector_focus_token = focus_token
        env_input.value = initial_value
        env_input.cursor_position = len(initial_value)
        env_input.focus()

    def _sync_focus(self, state: PiespectorState) -> None:
        tree = self.query_one("#env-sidebar-tree", PiespectorTree)
        if state.mode == MODE_NORMAL and not tree.has_focus:
            tree.focus()
        elif state.mode != MODE_NORMAL and tree.has_focus:
            tree.blur()
        self.query_one("#env-sidebar-container").set_class(
            state.mode == MODE_NORMAL,
            FOCUS_FRAME_CLASS,
        )
        self.query_one("#env-main").set_class(
            state.mode in {MODE_ENV_SELECT, MODE_ENV_EDIT},
            FOCUS_FRAME_CLASS,
        )

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        app = self.app
        if app is None or event.control.id != "env-sidebar-tree":
            return
        index = event.node.data
        if not isinstance(index, int):
            return
        tree = event.control
        if isinstance(tree, PiespectorTree) and tree.sync_state.ignore_highlight_index == index:
            tree.sync_state.ignore_highlight_index = None
            return
        env_names = app.state.env_names
        if 0 <= index < len(env_names):
            app.state.select_env_by_name(env_names[index])
            app._refresh_screen()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self.app
        if app is None or event.control.id != "env-table":
            return
        items = app.state.get_env_items()
        if event.cursor_row >= len(items):
            app.state.enter_env_create_mode()
        else:
            app.state.enter_env_edit_mode()
        app._refresh_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app = self.app
        if app is None or event.input.id != "env-field-input" or app.state.mode != MODE_ENV_EDIT:
            return
        event.stop()
        result = app.state.save_selected_env_field(event.value)
        if result is not None:
            app.set_focus(None)
        else:
            # Save failed — reset focus token so _sync_env_input re-focuses the input
            event.input._piespector_focus_token = None
        app._refresh_screen()
