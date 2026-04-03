from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Select

from piespector.domain.modes import MODE_ENV_EDIT
from piespector.screens.base import PiespectorScreen
from piespector.ui.input import PiespectorInput
from piespector.ui.select import PiespectorSelect


class EnvScreen(PiespectorScreen):
    selected_env_index = reactive(0)
    selected_env_field_index = reactive(0)
    env_scroll_offset = reactive(0)
    env_creating_new = reactive(False)

    def compose_workspace(self) -> ComposeResult:
        with Vertical(id="env-screen"):
            yield PiespectorSelect([], id="env-select", allow_blank=True)
            yield DataTable(id="env-table", cursor_type="row", zebra_stripes=True)
            yield PiespectorInput(
                "",
                id="env-field-input",
                compact=True,
                select_on_focus=False,
            )

    def on_mount(self) -> None:
        super().on_mount()
        env_table = self.query_one("#env-table", DataTable)
        env_table.add_columns("#", "Key", "Value")
        self.disable_focus("env-table")
        self.query_one("#env-field-input").display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app = self.app
        if app is None or event.input.id != "env-field-input" or app.state.mode != MODE_ENV_EDIT:
            return
        event.stop()
        changed = app.state.save_selected_env_field(event.value)
        if changed is not None:
            app._persist_env_pairs()
        app.set_focus(None)
        app._refresh_screen()
