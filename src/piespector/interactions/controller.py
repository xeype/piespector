from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events

from piespector.commands import command_completion_matches, filesystem_path_completions, run_command
from piespector.domain.editor import TAB_HISTORY
from piespector.interactions.keys import (
    CONFIRM_ACCEPT_KEYS,
    CONFIRM_CANCEL_KEYS,
    COPY_KEYS,
    KEY_BACKSPACE,
    KEY_DELETE,
    KEY_END,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_HOME,
    KEY_TAB,
    LEFT_KEYS,
    PASTE_KEYS,
    RIGHT_KEYS,
)
from piespector.search import (
    activate_search_target,
    history_search_matches,
    resolve_search_target,
    search_matches,
)

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class InteractionController:
    """App-level key handling that is shared across screens."""

    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def handle_command_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_command_mode()
            self.app._reset_command_completion()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_TAB:
            anchor = self.app._command_completion_anchor or self.state.command_buffer
            matches = command_completion_matches(self.state, anchor)
            if matches:
                if self.app._command_completion_anchor != anchor:
                    self.app._command_completion_anchor = anchor
                    self.app._command_completion_index = 0
                else:
                    self.app._command_completion_index = (
                        self.app._command_completion_index + 1
                    ) % len(matches)
                self.state.command_buffer = matches[self.app._command_completion_index]
                self.app._refresh_command_line()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.app._reset_command_completion()
            self.run_command(self.state.command_buffer)
            event.stop()
            return

        if event.key == KEY_BACKSPACE:
            self.state.command_buffer = self.state.command_buffer[:-1]
            self.app._reset_command_completion()
            self.app._refresh_command_line()
            event.stop()
            return

        if event.key in PASTE_KEYS or event.character == "\x16":
            pasted = self.app._paste_text()
            if pasted is not None:
                self.state.command_buffer += self.app._normalize_pasted_inline_text(pasted)
                self.state.message = "Pasted."
            else:
                self.state.message = "Paste failed."
            self.app._reset_command_completion()
            self.app._refresh_command_line()
            event.stop()
            return

        if event.character and ord(event.character) < 32:
            event.stop()
            return

        if event.character:
            self.state.command_buffer += event.character
            self.app._reset_command_completion()
            self.app._refresh_command_line()
            event.stop()

    def handle_search_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.leave_search_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_TAB:
            anchor = self.state.search_anchor_buffer or self.state.command_buffer.strip()
            matches = (
                history_search_matches(self.state, anchor)
                if self.state.current_tab == TAB_HISTORY
                else search_matches(self.state, anchor)
            )
            if matches:
                if self.state.search_anchor_buffer != anchor:
                    self.state.search_anchor_buffer = anchor
                    self.state.search_completion_index = 0
                else:
                    self.state.search_completion_index = (
                        self.state.search_completion_index + 1
                    ) % len(matches)
                match = matches[self.state.search_completion_index]
                if self.state.current_tab == TAB_HISTORY:
                    parts = [match.method]
                    if match.status_code is not None:
                        parts.append(str(match.status_code))
                    elif match.error:
                        parts.append("ERR")
                    name = (
                        match.source_request_name.strip()
                        or match.source_request_path.strip()
                        or match.url.strip()
                    )
                    if name:
                        parts.append(name)
                    self.state.command_buffer = " ".join(parts)
                else:
                    self.state.command_buffer = match.display
                self.app._refresh_command_line()
            event.stop()
            return

        if event.key == KEY_ENTER:
            self.run_search(self.state.command_buffer)
            event.stop()
            return

        if event.key == KEY_BACKSPACE:
            self.state.command_buffer = self.state.command_buffer[:-1]
            self.state.search_anchor_buffer = ""
            self.state.search_completion_index = -1
            self.app._refresh_command_line()
            event.stop()
            return

        if event.character:
            self.state.command_buffer += event.character
            self.state.search_anchor_buffer = ""
            self.state.search_completion_index = -1
            self.app._refresh_command_line()
            event.stop()

    def handle_inline_edit_key(self, event: events.Key) -> bool:
        if event.key == KEY_TAB:
            if self.app._binary_path_edit_active():
                anchor = self.app._edit_path_completion_anchor or self.state.edit_buffer
                matches = filesystem_path_completions(anchor)
                if matches:
                    if self.app._edit_path_completion_anchor != anchor:
                        self.app._edit_path_completion_anchor = anchor
                        self.app._edit_path_completion_index = 0
                    else:
                        self.app._edit_path_completion_index = (
                            self.app._edit_path_completion_index + 1
                        ) % len(matches)
                    self.state.set_edit_buffer(
                        matches[self.app._edit_path_completion_index],
                        replace_on_next_input=False,
                    )
                    self.app._refresh_screen()
                event.stop()
                return True
            if self.state.autocomplete_edit_placeholder():
                self.app._refresh_screen()
            event.stop()
            return True

        if event.key in COPY_KEYS or event.character == "\x03":
            copied = self.app._copy_text(self.state.edit_buffer)
            self.state.message = "Copied field." if copied else "Copy failed."
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key in PASTE_KEYS or event.character == "\x16":
            pasted = self.app._paste_text()
            if pasted is not None:
                inline_value = self.app._normalize_pasted_inline_text(pasted)
                self.state.insert_edit_text(inline_value)
                self.state.message = "Pasted."
            else:
                self.state.message = "Paste failed."
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.character and ord(event.character) < 32:
            event.stop()
            return True

        if event.key == "left":
            self.state.move_edit_cursor(-1)
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == "right":
            self.state.move_edit_cursor(1)
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_HOME:
            self.state.move_edit_cursor_to_start()
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_END:
            self.state.move_edit_cursor_to_end()
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_BACKSPACE:
            self.state.backspace_edit_character()
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.key == KEY_DELETE:
            self.state.delete_edit_character()
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        if event.character:
            self.state.insert_edit_character(event.character)
            self.app._reset_edit_path_completion()
            self.app._refresh_screen()
            event.stop()
            return True

        return False

    def handle_confirm_key(self, event: events.Key) -> None:
        if event.key in CONFIRM_CANCEL_KEYS:
            self.state.leave_confirm_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key not in CONFIRM_ACCEPT_KEYS:
            return

        if self.state.confirm_action == "delete_collection":
            deleted = self.state.delete_selected_collection()
            if deleted is not None:
                self.app._persist_requests()
        elif self.state.confirm_action == "delete_folder":
            deleted = self.state.delete_selected_folder()
            if deleted is not None:
                self.app._persist_requests()

        self.state.leave_confirm_mode()
        self.app._refresh_screen()
        event.stop()

    def handle_help_view_key(self, event: events.Key) -> bool:
        if event.key == KEY_ESCAPE:
            self.state.leave_help_tab()
            self.app._refresh_screen()
            event.stop()
            return True
        return False

    def run_command(self, raw_command: str) -> None:
        before_env_pairs = dict(self.state.env_pairs)
        before_requests = [request.request_id for request in self.state.requests]
        outcome = run_command(self.state, raw_command)
        if outcome.save_env_pairs or self.state.env_pairs != before_env_pairs:
            self.app._persist_env_pairs()
        if outcome.save_requests or [request.request_id for request in self.state.requests] != before_requests:
            self.app._persist_requests()
        if outcome.send_request:
            self.app._send_selected_request()
            return
        if outcome.should_exit:
            self.app.exit()
            return
        self.app._refresh_screen()

    def run_search(self, raw_query: str) -> None:
        if self.state.current_tab == TAB_HISTORY:
            count = self.state.set_history_filter(raw_query)
            self.state.leave_search_mode()
            if self.state.history_filter_query:
                self.state.message = (
                    f"Filtered history to {count} entr{'y' if count == 1 else 'ies'}."
                    if count
                    else f"No history matches for {raw_query.strip()!r}."
                )
            else:
                self.state.message = "Cleared history filter."
            self.app._refresh_screen()
            return

        target = resolve_search_target(self.state, raw_query)
        self.state.leave_search_mode()
        if target is None:
            self.state.message = (
                f"No matches for {raw_query.strip()!r}."
                if raw_query.strip()
                else ""
            )
            self.app._refresh_screen()
            return
        if activate_search_target(self.state, target):
            self.app._persist_requests()
        else:
            self.state.message = f"Could not open {target.display}."
        self.app._refresh_screen()
