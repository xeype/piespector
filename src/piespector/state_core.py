from __future__ import annotations

from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS, TAB_ORDER
from piespector.domain.modes import MODE_COMMAND, MODE_CONFIRM, MODE_NORMAL, MODE_SEARCH
from piespector.placeholders import apply_placeholder_completion, auto_pair_placeholder, placeholder_match


class CoreStateMixin:
    def enter_command_mode(self) -> None:
        self.command_context_mode = self.mode
        self.mode = MODE_COMMAND
        self.command_buffer = ""
        self.message = ""

    def leave_command_mode(self) -> None:
        self.mode = MODE_NORMAL
        self.command_buffer = ""

    def enter_search_mode(self) -> None:
        self.mode = MODE_SEARCH
        self.command_buffer = ""
        self.search_anchor_buffer = ""
        self.search_completion_index = -1
        self.message = ""

    def leave_search_mode(self) -> None:
        self.mode = MODE_NORMAL
        self.command_buffer = ""
        self.search_anchor_buffer = ""
        self.search_completion_index = -1

    def _clamp_edit_cursor_index(self) -> None:
        self.edit_cursor_index = max(0, min(self.edit_cursor_index, len(self.edit_buffer)))

    def set_edit_buffer(self, value: str, *, replace_on_next_input: bool) -> None:
        self.edit_buffer = value
        self.edit_cursor_index = len(value)
        self.replace_on_next_input = replace_on_next_input

    def clear_edit_buffer(self) -> None:
        self.edit_buffer = ""
        self.edit_cursor_index = 0
        self.replace_on_next_input = False

    def insert_edit_character(self, character: str) -> None:
        if self.replace_on_next_input:
            self.clear_edit_buffer()
        self._clamp_edit_cursor_index()
        if character == "{":
            paired = auto_pair_placeholder(self.edit_buffer, self.edit_cursor_index)
            if paired is not None:
                self.edit_buffer, self.edit_cursor_index = paired
                return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + character
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index += len(character)

    def insert_edit_text(self, value: str) -> None:
        if not value:
            return
        if self.replace_on_next_input:
            self.clear_edit_buffer()
        self._clamp_edit_cursor_index()
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + value
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index += len(value)

    def backspace_edit_character(self) -> None:
        if self.replace_on_next_input:
            self.replace_on_next_input = False
        self._clamp_edit_cursor_index()
        if self.edit_cursor_index <= 0:
            return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index - 1]
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index -= 1

    def delete_edit_character(self) -> None:
        if self.replace_on_next_input:
            self.replace_on_next_input = False
        self._clamp_edit_cursor_index()
        if self.edit_cursor_index >= len(self.edit_buffer):
            return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + self.edit_buffer[self.edit_cursor_index + 1 :]
        )

    def move_edit_cursor(self, step: int) -> int:
        self._clamp_edit_cursor_index()
        self.edit_cursor_index = max(
            0,
            min(self.edit_cursor_index + step, len(self.edit_buffer)),
        )
        return self.edit_cursor_index

    def move_edit_cursor_to_start(self) -> None:
        self.edit_cursor_index = 0

    def move_edit_cursor_to_end(self) -> None:
        self.edit_cursor_index = len(self.edit_buffer)

    def placeholder_completion_hint(self) -> str | None:
        match = placeholder_match(
            self.edit_buffer,
            self.edit_cursor_index,
            sorted(self.env_pairs),
        )
        if match is None or match.suggestion == match.prefix:
            return None
        return match.suggestion

    def autocomplete_edit_placeholder(self) -> bool:
        completed = apply_placeholder_completion(
            self.edit_buffer,
            self.edit_cursor_index,
            sorted(self.env_pairs),
        )
        if completed is None:
            return False
        self.edit_buffer, self.edit_cursor_index = completed
        return True

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
        self.current_tab = tab_id
        self.clear_edit_buffer()
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
