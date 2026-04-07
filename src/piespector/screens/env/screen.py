from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.style import Style
from textual.widgets import DataTable, Input, Static, Tree
from textual.widgets._data_table import RowDoesNotExist, RowKey

from piespector.domain.modes import MODE_ENV_EDIT, MODE_ENV_SELECT
from piespector.screens.base import PiespectorScreen
from piespector.ui.input import PiespectorInput
from piespector.widget.tree import PiespectorTree


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
