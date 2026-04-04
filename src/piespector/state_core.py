from __future__ import annotations

from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS, TAB_ORDER
from piespector.domain.modes import MODE_COMMAND, MODE_CONFIRM, MODE_JUMP, MODE_NORMAL


class CoreStateMixin:
    def enter_command_mode(self) -> None:
        self.command_context_mode = self.mode
        self.mode = MODE_COMMAND
        self.message = ""

    def leave_command_mode(self) -> None:
        self.mode = MODE_NORMAL

    def enter_jump_mode(self) -> None:
        self.jump_return_mode = self.mode
        self.mode = MODE_JUMP
        self.message = ""

    def leave_jump_mode(self) -> None:
        self.mode = self.jump_return_mode or MODE_NORMAL
        self.message = ""

    def enter_confirm_mode(
        self,
        *,
        prompt: str,
        action: str,
        target_id: str,
    ) -> None:
        self.mode = MODE_CONFIRM
        self.confirm_prompt = prompt
        self.confirm_action = action
        self.confirm_target_id = target_id

    def leave_confirm_mode(self) -> None:
        self.mode = MODE_NORMAL
        self.confirm_prompt = ""
        self.confirm_action = None
        self.confirm_target_id = None

    def switch_tab(self, tab_id: str, label: str | None = None) -> None:
        self.mode = MODE_NORMAL
        self.current_tab = tab_id
        if tab_id == TAB_HOME:
            self.ensure_request_workspace()
        if tab_id == TAB_HISTORY:
            self.clamp_selected_history_index()
        if tab_id == TAB_ENV:
            self.ensure_env_workspace()
        if label is not None:
            self.message = f"Switched to {label}."
        elif tab_id in TAB_LABELS:
            self.message = f"Switched to {TAB_LABELS[tab_id]}."

    def cycle_tab(self, step: int) -> None:
        current_tab = (
            self.help_return_tab
            if self.current_tab not in TAB_ORDER
            else self.current_tab
        )
        index = TAB_ORDER.index(current_tab)
        self.current_tab = TAB_ORDER[(index + step) % len(TAB_ORDER)]
        if self.current_tab == TAB_HOME:
            self.ensure_request_workspace()
        if self.current_tab == TAB_HISTORY:
            self.clamp_selected_history_index()

    def open_help_tab(self, *, source_mode: str) -> None:
        source_tab = self.help_source_tab if self.current_tab == TAB_HELP else self.current_tab
        return_tab = self.help_return_tab if self.current_tab == TAB_HELP else self.current_tab
        self.help_source_tab = source_tab
        self.help_return_tab = return_tab
        self.help_source_mode = source_mode
        self.current_tab = TAB_HELP
        self.mode = MODE_NORMAL
        self.message = ""

    def leave_help_tab(self) -> None:
        target_tab = self.help_return_tab if self.help_return_tab in TAB_ORDER else TAB_HOME
        self.switch_tab(target_tab)
        self.mode = MODE_NORMAL
        if self.current_tab == TAB_ENV:
            self.ensure_env_workspace()
