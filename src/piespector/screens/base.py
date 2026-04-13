from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Static

from piespector import commands as command_actions
from piespector.domain.modes import COMMAND_BLOCKED_MODES, MODE_NORMAL
from piespector.interactions.keys import KEY_WORKSPACE_SEARCH
from piespector.search import activate_search_target
from piespector.ui.command_line_content import build_command_line_text
from piespector.ui.command_palette import (
    PiespectorCommandProvider,
    PiespectorSearchProvider,
)
from piespector.ui.footer import PiespectorFooter
from piespector.ui.status_content import status_bar_content


class PiespectorScreen(Screen[None]):
    COMMANDS = {PiespectorCommandProvider}
    BINDINGS = [
        Binding(KEY_WORKSPACE_SEARCH, "search_workspace", "Search", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="workspace"):
                yield from self.compose_workspace()
            with Horizontal(id="command-line"):
                yield Static("", id="command-line-content")
            yield PiespectorFooter(id="status-line")

    def compose_workspace(self) -> ComposeResult:
        raise NotImplementedError

    def on_mount(self) -> None:
        pass

    def refresh_from_state(self) -> None:
        pass

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    @property
    def _state(self):
        app = self._owner_app()
        return None if app is None else app.state

    def command_context_tab(self) -> str:
        state = self._state
        return "" if state is None else state.current_tab

    def command_context_mode(self) -> str:
        state = self._state
        return MODE_NORMAL if state is None else state.mode

    def command_palette_commands(self):
        state = self._state
        if state is None:
            return []
        return command_actions.command_palette_commands(
            state,
            context_tab=self.command_context_tab(),
            context_mode=self.command_context_mode(),
        )

    def command_completion_matches(self, raw_buffer: str) -> list[str]:
        state = self._state
        if state is None:
            return []
        return command_actions.command_completion_matches(
            state,
            raw_buffer,
            context_tab=self.command_context_tab(),
            context_mode=self.command_context_mode(),
        )

    def execute_command(self, raw_command: str) -> None:
        state = self._state
        if state is None:
            return
        outcome = command_actions.run_command(
            state,
            raw_command,
            context_tab=self.command_context_tab(),
            context_mode=self.command_context_mode(),
        )
        if state.mode != MODE_NORMAL:
            state.mode = MODE_NORMAL
        self._handle_command_outcome(outcome)

    def _handle_command_outcome(
        self,
        outcome: command_actions.CommandOutcome,
    ) -> None:
        app = self._owner_app()
        if app is None:
            return
        if outcome.should_exit:
            app.exit()
            return
        if outcome.send_request:
            app._send_selected_request()
            return
        app._refresh_screen()

    def screen_widgets_ready(self) -> bool:
        if not self.is_mounted:
            return False
        try:
            self.query_one("#workspace")
            self.query_one("#status-line", PiespectorFooter)
            self.query_one("#command-line")
            self.query_one("#command-line-content", Static)
        except NoMatches:
            return False
        return True

    def refresh_status_line(self) -> None:
        state = self._state
        if state is None or not self.screen_widgets_ready():
            return
        footer = self.query_one("#status-line", PiespectorFooter)
        footer.set_status_content(status_bar_content(state))

    def refresh_command_line(self) -> None:
        state = self._state
        if state is None or not self.screen_widgets_ready():
            return
        command_content = self.query_one("#command-line-content", Static)
        command_content.update(build_command_line_text(state))

    def search_palette_providers(self):
        return [PiespectorSearchProvider]

    def search_palette_placeholder(self) -> str:
        return "Search collections, folders, and requests…"

    def search_palette_id(self) -> str:
        return "--workspace-search"

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "search_workspace":
            state = self._state
            if state is None:
                return False
            return state.mode not in COMMAND_BLOCKED_MODES
        return True

    def action_search_workspace(self) -> None:
        app = self._owner_app()
        if app is None:
            return
        app.open_palette(
            providers=self.search_palette_providers(),
            placeholder=self.search_palette_placeholder(),
            palette_id=self.search_palette_id(),
        )

    def open_search_target(self, target) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None:
            return
        state.mode = MODE_NORMAL
        if not activate_search_target(state, target):
            state.message = f"Could not open {target.display}."
        app._refresh_screen()

    def disable_focus(self, *widget_ids: str) -> None:
        for widget_id in widget_ids:
            try:
                self.query_one(f"#{widget_id}").can_focus = False
            except NoMatches:
                pass
