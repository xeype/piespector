from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import platform
import shutil
import subprocess

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.binding import Binding
from textual import work
from textual._tree_sitter import get_language
from textual.widgets import Static, TextArea
from textual.widgets._text_area import LanguageDoesNotExist

from piespector.commands import (
    command_completion,
    command_completion_matches,
    filesystem_path_completions,
    run_command,
)
from piespector.formatting import format_bytes
from piespector.history import build_history_entry
from piespector.http_client import perform_request, preview_auto_headers, validate_raw_body
from piespector.placeholders import (
    apply_placeholder_completion,
    auto_pair_placeholder,
    placeholder_match,
)
from piespector.rendering import (
    detect_text_syntax_language,
    format_response_body,
    render_command_line,
    request_body_syntax_language,
    render_status_line,
    render_viewport,
    response_scroll_step,
    text_area_syntax_language,
)
from piespector.search import (
    activate_search_target,
    history_search_matches,
    request_path,
    resolve_search_target,
    search_completion,
    search_matches,
)
from piespector.scrollbars import ThinScrollBarRender
from piespector.state import BODY_TEXT_EDITOR_TYPES, PiespectorState
from piespector.storage import (
    app_data_dir,
    append_history_entry,
    env_workspace_path,
    history_file_path,
    load_env_workspace,
    load_history_entries,
    load_request_workspace,
    requests_file_path,
    save_env_workspace,
    save_history_entries,
    ensure_parent_dir,
    save_request_workspace,
)
from piespector.ui import APP_BINDINGS, APP_CSS


class BodyTextEditor(TextArea):
    BINDINGS = [
        Binding("ctrl+s", "save_body", "Save", show=False),
        Binding("escape", "cancel_body", "Cancel", show=False),
    ]

    def action_save_body(self) -> None:
        app = self.app
        if isinstance(app, PiespectorApp):
            app._close_body_text_editor(save=True)

    def action_cancel_body(self) -> None:
        app = self.app
        if isinstance(app, PiespectorApp):
            app._close_body_text_editor(save=False)

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if event.key == "ctrl+s":
            self.action_save_body()
            event.stop()
            return
        if event.key == "escape":
            self.action_cancel_body()
            event.stop()
            return
        if isinstance(app, PiespectorApp):
            if event.key == "tab" and app._autocomplete_body_editor_placeholder():
                event.stop()
                return
            if event.character == "{":
                app.call_after_refresh(app._postprocess_body_editor_brace)
                return
            app.call_after_refresh(app._refresh_overlay_editors)


class ResponseViewer(TextArea):
    BINDINGS = [
        Binding("escape", "close_response", "Close", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("read_only", True)
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        self.vertical_scrollbar.renderer = ThinScrollBarRender
        self.horizontal_scrollbar.renderer = ThinScrollBarRender

    def action_close_response(self) -> None:
        app = self.app
        if isinstance(app, PiespectorApp):
            app._close_response_viewer()

    def action_copy_response(self) -> None:
        app = self.app
        if isinstance(app, PiespectorApp):
            content = self.selected_text or self.text
            copied = app._copy_text(content)
            if copied:
                app.state.message = (
                    "Copied selection."
                    if self.selected_text
                    else "Copied full response."
                )
            else:
                app.state.message = "Copy failed."
            app._refresh_command_line()

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if isinstance(app, PiespectorApp) and event.key in app.response_copy_keys:
            self.action_copy_response()
            event.stop()
            return
        if event.key == "escape":
            self.action_close_response()
            event.stop()
            return


class PiespectorApp(App[None]):
    """Minimal terminal UI skeleton with a Vim-like layout."""

    ENABLE_COMMAND_PALETTE = False
    REQUEST_TIMEOUT_SECONDS = 15.0
    theme = "atom-one-dark"
    CSS = APP_CSS
    BINDINGS = APP_BINDINGS
    REQUEST_RESPONSE_SHORTCUT_MODES = frozenset(
        {
            "HOME_SECTION_SELECT",
            "HOME_REQUEST_SELECT",
            "HOME_REQUEST_METHOD_EDIT",
            "HOME_AUTH_SELECT",
            "HOME_AUTH_TYPE_EDIT",
            "HOME_AUTH_LOCATION_EDIT",
            "HOME_PARAMS_SELECT",
            "HOME_HEADERS_SELECT",
            "HOME_BODY_SELECT",
            "HOME_BODY_TYPE_EDIT",
            "HOME_BODY_RAW_TYPE_EDIT",
        }
    )
    GRAPHQL_TEXTAREA_LANGUAGE = "piespector-graphql"
    GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY = """
[
  "{"
  "}"
] @punctuation.bracket

((identifier) @keyword
 (#match? @keyword "^(query|mutation|subscription|fragment|on)$"))

((identifier) @class
 (#match? @class "^[A-Z][A-Za-z0-9_]*$"))

((identifier) @function
 (#match? @function "^[a-z_][A-Za-z0-9_]*$"))
"""

    def __init__(self) -> None:
        super().__init__()
        self.state = PiespectorState()
        self._legacy_env_workspace_path = Path.cwd() / ".piespector.env.json"
        self._legacy_env_file_path = Path.cwd() / ".env"
        self._legacy_requests_file_path = Path.cwd() / ".piespector.requests.json"
        self._legacy_history_file_path = Path.cwd() / ".piespector.history.jsonl"
        self._env_workspace_path = env_workspace_path()
        self._requests_file_path = requests_file_path()
        self._history_file_path = history_file_path()
        self._log_file_path = app_data_dir() / ".piespector.log"
        self.response_copy_keys = self._response_copy_keys()
        self.response_copy_hint = self._response_copy_hint()
        self._command_completion_anchor = ""
        self._command_completion_index = -1
        self._edit_path_completion_anchor = ""
        self._edit_path_completion_index = -1

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="workspace"):
                yield Static("", id="viewport")
                yield Static("", id="body-editor-header", classes="hidden")
                yield BodyTextEditor(
                    "",
                    id="body-editor",
                    language="json",
                    theme="monokai",
                    soft_wrap=False,
                    show_line_numbers=True,
                    tab_behavior="indent",
                    classes="hidden",
                )
                yield Static("", id="body-editor-hint", classes="hidden")
                yield Static("", id="body-editor-footer", classes="hidden")
                yield Static("", id="response-viewer-header", classes="hidden")
                yield ResponseViewer(
                    "",
                    id="response-viewer",
                    language=None,
                    theme="monokai",
                    soft_wrap=False,
                    show_line_numbers=True,
                    classes="hidden",
                )
                yield Static("", id="response-viewer-footer", classes="hidden")
            yield Static("", id="status-line")
            yield Static("", id="command-line")

    def on_mount(self) -> None:
        self._register_text_area_languages()
        env_workspace_source = self._env_workspace_path
        legacy_env_path: Path | None = self._legacy_env_file_path
        if (
            not self._env_workspace_path.exists()
            and self._legacy_env_workspace_path.exists()
        ):
            env_workspace_source = self._legacy_env_workspace_path
            legacy_env_path = None
        env_names, env_sets, selected_env_name = load_env_workspace(
            env_workspace_source,
            legacy_env_path,
        )
        self.state.env_names = env_names
        self.state.env_sets = env_sets
        self.state.selected_env_name = selected_env_name
        self.state.ensure_env_workspace()
        if env_workspace_source != self._env_workspace_path:
            save_env_workspace(
                self._env_workspace_path,
                self.state.env_names,
                self.state.env_sets,
                self.state.selected_env_name,
            )
        history_source_path = self._history_file_path
        if (
            not self._history_file_path.exists()
            and self._legacy_history_file_path.exists()
        ):
            history_source_path = self._legacy_history_file_path
        self.state.history_entries = load_history_entries(history_source_path)
        if history_source_path != self._history_file_path:
            save_history_entries(self._history_file_path, self.state.history_entries)
        requests_source_path = self._requests_file_path
        if (
            not self._requests_file_path.exists()
            and self._legacy_requests_file_path.exists()
        ):
            requests_source_path = self._legacy_requests_file_path
        (
            collections,
            folders,
            requests,
            collapsed_collection_ids,
            collapsed_folder_ids,
        ) = load_request_workspace(requests_source_path)
        self.state.collections = collections
        self.state.folders = folders
        self.state.requests = requests
        self.state.collapsed_collection_ids = collapsed_collection_ids
        self.state.collapsed_folder_ids = collapsed_folder_ids
        self.state.ensure_request_workspace()
        if requests_source_path != self._requests_file_path:
            save_request_workspace(
                self._requests_file_path,
                self.state.collections,
                self.state.folders,
                self.state.requests,
                self.state.collapsed_collection_ids,
                self.state.collapsed_folder_ids,
            )
        if self.state.requests and self.state.get_active_request() is None:
            self.state.open_selected_request()
        self.set_interval(0.12, self._tick_request_loader)
        self._refresh_screen()
        self.call_after_refresh(self._refresh_screen)

    def on_resize(self) -> None:
        self._refresh_screen()

    def on_key(self, event: events.Key) -> None:
        if self.state.mode == "CONFIRM":
            self._handle_confirm_key(event)
            return

        if self.state.mode == "COMMAND":
            self._handle_command_key(event)
            return

        if self.state.mode == "SEARCH":
            self._handle_search_key(event)
            return

        if self.state.current_tab == "home":
            if self._handle_request_response_shortcuts(event):
                return
            if self.state.mode == "NORMAL" and self._handle_home_view_key(event):
                return
            if self.state.mode == "HOME_SECTION_SELECT":
                self._handle_home_section_select_key(event)
                return
            if self.state.mode == "HOME_REQUEST_SELECT":
                self._handle_home_request_select_key(event)
                return
            if self.state.mode == "HOME_REQUEST_EDIT":
                self._handle_home_request_edit_key(event)
                return
            if self.state.mode == "HOME_REQUEST_METHOD_EDIT":
                self._handle_home_request_method_edit_key(event)
                return
            if self.state.mode == "HOME_AUTH_SELECT":
                self._handle_home_auth_select_key(event)
                return
            if self.state.mode == "HOME_AUTH_EDIT":
                self._handle_home_auth_edit_key(event)
                return
            if self.state.mode == "HOME_AUTH_TYPE_EDIT":
                self._handle_home_auth_type_edit_key(event)
                return
            if self.state.mode == "HOME_AUTH_LOCATION_EDIT":
                self._handle_home_auth_location_edit_key(event)
                return
            if self.state.mode == "HOME_PARAMS_SELECT":
                self._handle_home_params_select_key(event)
                return
            if self.state.mode == "HOME_PARAMS_EDIT":
                self._handle_home_params_edit_key(event)
                return
            if self.state.mode == "HOME_HEADERS_SELECT":
                self._handle_home_headers_select_key(event)
                return
            if self.state.mode == "HOME_HEADERS_EDIT":
                self._handle_home_headers_edit_key(event)
                return
            if self.state.mode == "HOME_BODY_SELECT":
                self._handle_home_body_select_key(event)
                return
            if self.state.mode == "HOME_BODY_TYPE_EDIT":
                self._handle_home_body_type_edit_key(event)
                return
            if self.state.mode == "HOME_BODY_RAW_TYPE_EDIT":
                self._handle_home_body_raw_type_edit_key(event)
                return
            if self.state.mode == "HOME_BODY_EDIT":
                self._handle_home_body_edit_key(event)
                return
            if self.state.mode == "HOME_RESPONSE_SELECT":
                self._handle_home_response_select_key(event)
                return
            if self.state.mode == "HOME_RESPONSE_TEXTAREA":
                return

        if self.state.current_tab == "env":
            if self.state.mode == "NORMAL" and self._handle_env_view_key(event):
                return
            if self.state.mode == "ENV_SELECT":
                self._handle_env_select_key(event)
                return
            if self.state.mode == "ENV_EDIT":
                self._handle_env_edit_key(event)
                return

        if self.state.current_tab == "history":
            if self.state.mode == "NORMAL" and self._handle_history_view_key(event):
                return
            if self.state.mode == "HISTORY_RESPONSE_SELECT":
                self._handle_history_response_select_key(event)
                return

        if self.state.current_tab == "help":
            if self.state.mode == "NORMAL" and self._handle_help_view_key(event):
                return

    def _handle_command_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_command_mode()
            self._reset_command_completion()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "tab":
            anchor = self._command_completion_anchor or self.state.command_buffer
            matches = command_completion_matches(self.state, anchor)
            if matches:
                if self._command_completion_anchor != anchor:
                    self._command_completion_anchor = anchor
                    self._command_completion_index = 0
                else:
                    self._command_completion_index = (
                        self._command_completion_index + 1
                    ) % len(matches)
                self.state.command_buffer = matches[self._command_completion_index]
                self._refresh_command_line()
            event.stop()
            return

        if event.key == "enter":
            self._reset_command_completion()
            self._run_command(self.state.command_buffer)
            event.stop()
            return

        if event.key == "backspace":
            self.state.command_buffer = self.state.command_buffer[:-1]
            self._reset_command_completion()
            self._refresh_command_line()
            event.stop()
            return

        if (
            event.key in {"ctrl+v", "ctrl+shift+v", "shift+insert"}
            or event.character == "\x16"
        ):
            pasted = self._paste_text()
            if pasted is not None:
                self.state.command_buffer += self._normalize_pasted_inline_text(pasted)
                self.state.message = "Pasted."
            else:
                self.state.message = "Paste failed."
            self._reset_command_completion()
            self._refresh_command_line()
            event.stop()
            return

        if event.character and ord(event.character) < 32:
            event.stop()
            return

        if event.character:
            self.state.command_buffer += event.character
            self._reset_command_completion()
            self._refresh_command_line()
            event.stop()

    def _handle_search_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_search_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "tab":
            anchor = self.state.search_anchor_buffer or self.state.command_buffer.strip()
            matches = (
                history_search_matches(self.state, anchor)
                if self.state.current_tab == "history"
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
                if self.state.current_tab == "history":
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
                self._refresh_command_line()
            event.stop()
            return

        if event.key == "enter":
            self._run_search(self.state.command_buffer)
            event.stop()
            return

        if event.key == "backspace":
            self.state.command_buffer = self.state.command_buffer[:-1]
            self.state.search_anchor_buffer = ""
            self.state.search_completion_index = -1
            self._refresh_command_line()
            event.stop()
            return

        if event.character:
            self.state.command_buffer += event.character
            self.state.search_anchor_buffer = ""
            self.state.search_completion_index = -1
            self._refresh_command_line()
            event.stop()

    def _handle_inline_edit_key(self, event: events.Key) -> bool:
        if event.key == "tab":
            if self._binary_path_edit_active():
                anchor = self._edit_path_completion_anchor or self.state.edit_buffer
                matches = filesystem_path_completions(anchor)
                if matches:
                    if self._edit_path_completion_anchor != anchor:
                        self._edit_path_completion_anchor = anchor
                        self._edit_path_completion_index = 0
                    else:
                        self._edit_path_completion_index = (
                            self._edit_path_completion_index + 1
                        ) % len(matches)
                    self.state.set_edit_buffer(
                        matches[self._edit_path_completion_index],
                        replace_on_next_input=False,
                    )
                    self._refresh_screen()
                event.stop()
                return True
            if self.state.autocomplete_edit_placeholder():
                self._refresh_screen()
            event.stop()
            return True

        if event.key in {"ctrl+c", "ctrl+insert"} or event.character == "\x03":
            copied = self._copy_text(self.state.edit_buffer)
            self.state.message = "Copied field." if copied else "Copy failed."
            self._refresh_screen()
            event.stop()
            return True

        if (
            event.key in {"ctrl+v", "ctrl+shift+v", "shift+insert"}
            or event.character == "\x16"
        ):
            pasted = self._paste_text()
            if pasted is not None:
                inline_value = self._normalize_pasted_inline_text(pasted)
                self.state.insert_edit_text(inline_value)
                self.state.message = "Pasted."
            else:
                self.state.message = "Paste failed."
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.character and ord(event.character) < 32:
            event.stop()
            return True

        if event.key in {"left"}:
            self.state.move_edit_cursor(-1)
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"right"}:
            self.state.move_edit_cursor(1)
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.key == "home":
            self.state.move_edit_cursor_to_start()
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.key == "end":
            self.state.move_edit_cursor_to_end()
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.key == "backspace":
            self.state.backspace_edit_character()
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.key == "delete":
            self.state.delete_edit_character()
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        if event.character:
            self.state.insert_edit_character(event.character)
            self._reset_edit_path_completion()
            self._refresh_screen()
            event.stop()
            return True

        return False

    def _body_editor_cursor_index(self) -> int:
        editor = self.query_one("#body-editor", TextArea)
        row, column = editor.cursor_location
        lines = editor.text.splitlines(keepends=True)
        if editor.text.endswith("\n"):
            lines.append("")
        if not lines:
            return 0
        row = max(0, min(row, len(lines) - 1))
        return sum(len(lines[index]) for index in range(row)) + column

    def _body_editor_location_from_index(self, text: str, index: int) -> tuple[int, int]:
        index = max(0, min(index, len(text)))
        row = 0
        column = 0
        current = 0
        for chunk in text.splitlines(keepends=True):
            next_current = current + len(chunk)
            if index <= next_current:
                row, column = row, index - current
                return (row, column)
            current = next_current
            row += 1
        return (row, index - current)

    def _autocomplete_body_editor_placeholder(self) -> bool:
        editor = self.query_one("#body-editor", TextArea)
        cursor_index = self._body_editor_cursor_index()
        completed = apply_placeholder_completion(
            editor.text,
            cursor_index,
            sorted(self.state.env_pairs),
        )
        if completed is None:
            return False
        text, new_cursor_index = completed
        editor.load_text(text)
        editor.move_cursor(self._body_editor_location_from_index(text, new_cursor_index))
        self._refresh_overlay_editors()
        return True

    def _auto_pair_body_editor_placeholder(self) -> bool:
        editor = self.query_one("#body-editor", TextArea)
        cursor_index = self._body_editor_cursor_index()
        text = editor.text
        cursor_index = max(0, min(cursor_index, len(text)))
        if cursor_index >= 2 and text[cursor_index - 2 : cursor_index] == "{{":
            if text[cursor_index : cursor_index + 2] == "}}":
                return False
            updated = text[:cursor_index] + "}}" + text[cursor_index:]
            editor.load_text(updated)
            editor.move_cursor(
                self._body_editor_location_from_index(updated, cursor_index)
            )
            self._refresh_overlay_editors()
            return True
        return False

    def _postprocess_body_editor_brace(self) -> None:
        if not self._auto_pair_body_editor_placeholder():
            self._refresh_overlay_editors()

    def _handle_home_view_key(self, event: events.Key) -> bool:
        visible_rows = self._home_request_list_visible_rows()

        if event.key == "s":
            self.state.enter_search_mode()
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"left", "h"}:
            self.state.cycle_open_request(-1)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key in {"right", "l"}:
            self.state.cycle_open_request(1)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key in {"down", "j"}:
            self.state.select_request(1)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key in {"up", "k"}:
            self.state.select_request(-1)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key == "escape":
            if self.state.collapse_selected_context():
                self._persist_requests()
                self._refresh_viewport()
                event.stop()
                return True
            return False

        if event.key == "pagedown":
            self.state.scroll_request_window(visible_rows, visible_rows)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key == "pageup":
            self.state.scroll_request_window(-visible_rows, visible_rows)
            self._refresh_viewport()
            event.stop()
            return True

        if event.key == "e":
            if self.state.get_selected_request() is None:
                if self.state.toggle_selected_sidebar_node():
                    self._persist_requests()
                    self._refresh_viewport()
                    event.stop()
                    return True
                self.state.message = "Select a request first."
                self._refresh_screen()
                event.stop()
                return True
            self.state.enter_home_section_select_mode()
            self._refresh_screen()
            event.stop()
            return True

        return False

    def _handle_request_response_shortcuts(self, event: events.Key) -> bool:
        if self.state.mode in self.REQUEST_RESPONSE_SHORTCUT_MODES and event.key == "v":
            if self.state.enter_home_response_select_mode():
                self._refresh_screen()
            else:
                self._refresh_command_line()
            event.stop()
            return True

        if self.state.mode not in self.REQUEST_RESPONSE_SHORTCUT_MODES | {"HOME_RESPONSE_SELECT"}:
            return False

        if event.key in {"ctrl+d", "ctrl+u"}:
            response_step = response_scroll_step(
                self.query_one("#viewport", Static).size.height
            )
            self.state.scroll_response(
                response_step if event.key == "ctrl+d" else -response_step
            )
            self._refresh_viewport()
            event.stop()
            return True

        return False

    def _handle_home_response_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_response_select_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            self.state.cycle_home_response_tab(-1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key in {"right", "l"}:
            self.state.cycle_home_response_tab(1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            if self.state.selected_home_response_tab != "body":
                self.state.message = "Switch to Body to open the response viewer."
                self._refresh_screen()
                event.stop()
                return
            self._open_response_viewer(origin_mode="HOME_RESPONSE_SELECT")
            event.stop()
            return

    def _handle_confirm_key(self, event: events.Key) -> None:
        if event.key in {"escape", "n"}:
            self.state.leave_confirm_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key not in {"y", "enter"}:
            return

        if self.state.confirm_action == "delete_collection":
            deleted = self.state.delete_selected_collection()
            if deleted is not None:
                self._persist_requests()
        elif self.state.confirm_action == "delete_folder":
            deleted = self.state.delete_selected_folder()
            if deleted is not None:
                self._persist_requests()

        self.state.leave_confirm_mode()
        self._refresh_screen()
        event.stop()

    def _enter_current_home_value_select_mode(self) -> None:
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        if self.state.home_editor_tab == "params":
            self.state.enter_home_params_select_mode()
        elif self.state.home_editor_tab == "headers":
            self.state.enter_home_headers_select_mode()
        elif self.state.home_editor_tab == "auth":
            self.state.enter_home_auth_type_edit_mode(origin_mode="HOME_SECTION_SELECT")
        elif self.state.home_editor_tab == "body":
            self.state.enter_home_body_type_edit_mode(origin_mode="HOME_SECTION_SELECT")
        else:
            self.state.enter_home_request_select_mode()

    def _handle_home_section_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.mode = "NORMAL"
            self.state.edit_buffer = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            self.state.cycle_home_editor_tab(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l"}:
            self.state.cycle_home_editor_tab(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self._enter_current_home_value_select_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _start_current_home_edit(self) -> None:
        if self.state.home_editor_tab == "params":
            self.state.enter_home_params_edit_mode()
        elif self.state.home_editor_tab == "headers":
            self.state.enter_home_headers_edit_mode()
        elif self.state.home_editor_tab == "auth":
            if self.state.selected_auth_index == 0:
                self.state.enter_home_auth_type_edit_mode(origin_mode="HOME_AUTH_SELECT")
            else:
                self.state.enter_home_auth_edit_mode()
        elif self.state.home_editor_tab == "body":
            if self.state.selected_body_index == 0:
                self.state.enter_home_body_type_edit_mode(origin_mode="HOME_BODY_SELECT")
            else:
                request = self.state.get_active_request()
                if request is not None and request.body_type == "raw":
                    self.state.enter_home_body_raw_type_edit_mode(
                        origin_mode="HOME_BODY_SELECT"
                    )
                    return
                self.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")
        else:
            self.state.enter_home_request_edit_mode()

    def _handle_home_request_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.enter_home_section_select_mode()
            self.state.edit_buffer = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.select_request_field(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.select_request_field(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self._start_current_home_edit()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_request_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_request_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            updated_field = self.state.save_selected_request_field()
            if updated_field is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _handle_home_request_method_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_request_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            updated_field = self.state.save_selected_request_method()
            if updated_field is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h", "up", "k"}:
            self.state.cycle_request_method(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l", "down", "j"}:
            self.state.cycle_request_method(1)
            self._refresh_screen()
            event.stop()
            return

    def _handle_home_auth_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.enter_home_auth_type_edit_mode(origin_mode="HOME_SECTION_SELECT")
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.select_auth_row(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.select_auth_row(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            if self.state.selected_auth_index == 0:
                self.state.enter_home_auth_type_edit_mode(origin_mode="HOME_AUTH_SELECT")
            else:
                self.state.enter_home_auth_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_auth_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_auth_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            updated_field = self.state.save_selected_auth_field()
            if updated_field is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _handle_home_auth_type_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_auth_type_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h", "up", "k"}:
            if self.state.cycle_auth_type(-1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l", "down", "j"}:
            if self.state.cycle_auth_type(1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            if self.state.auth_fields():
                self.state.selected_auth_index = 1
            else:
                self.state.selected_auth_index = 0
            self.state.mode = "HOME_AUTH_SELECT"
            self.state.message = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_auth_location_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_auth_location_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h", "up", "k"}:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                updated = self.state.cycle_auth_oauth_client_authentication(-1)
            else:
                updated = self.state.cycle_auth_api_key_location(-1)
            if updated is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l", "down", "j"}:
            field = self.state.selected_auth_field()
            if field is not None and field[0] == "auth_oauth_client_authentication":
                updated = self.state.cycle_auth_oauth_client_authentication(1)
            else:
                updated = self.state.cycle_auth_api_key_location(1)
            if updated is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self.state.leave_home_auth_location_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_params_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.enter_home_section_select_mode()
            self.state.edit_buffer = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.select_param_row(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.select_param_row(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            self.state.cycle_param_field(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l"}:
            self.state.cycle_param_field(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key == "a":
            self.state.enter_home_params_edit_mode(creating=True)
            self._refresh_screen()
            event.stop()
            return

        if event.key == "space":
            toggled_key = self.state.toggle_selected_param()
            if toggled_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self.state.enter_home_params_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "d":
            deleted_key = self.state.delete_selected_param()
            if deleted_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_params_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_params_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            saved_key = self.state.save_selected_param_field()
            if saved_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _handle_home_headers_select_key(self, event: events.Key) -> None:
        total_rows = self._header_row_count()

        if event.key == "escape":
            self.state.enter_home_section_select_mode()
            self.state.edit_buffer = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.select_header_row(-1, total_rows)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.select_header_row(1, total_rows)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            self.state.cycle_header_field(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l"}:
            self.state.cycle_header_field(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key == "a":
            self.state.enter_home_headers_edit_mode(creating=True)
            self._refresh_screen()
            event.stop()
            return

        if event.key == "space":
            if self._selected_header_row_is_auto():
                header_name = self._selected_auto_header_name()
                if header_name is not None:
                    self.state.toggle_auto_header(header_name)
                    self.state.clamp_selected_header_index(self._header_row_count())
                    self._persist_requests()
                self._refresh_screen()
                event.stop()
                return
            toggled_key = self.state.toggle_selected_header()
            if toggled_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            if self._selected_header_row_is_auto():
                self.state.message = (
                    "Auto header selected. Press space to toggle it, or add an explicit header to override it."
                )
                self._refresh_screen()
                event.stop()
                return
            self.state.enter_home_headers_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "d":
            if self._selected_header_row_is_auto():
                self.state.message = "Auto header selected. Press space to toggle it or override it explicitly."
                self._refresh_screen()
                event.stop()
                return
            deleted_key = self.state.delete_selected_header()
            if deleted_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_headers_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_headers_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            saved_key = self.state.save_selected_header_field()
            if saved_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _header_row_count(self) -> int:
        request = self.state.get_active_request()
        if request is None:
            return 0
        return len(request.header_items) + len(
            preview_auto_headers(request, self.state.env_pairs)
        )

    def _selected_header_row_is_auto(self) -> bool:
        request = self.state.get_active_request()
        if request is None:
            return False
        return self.state.selected_header_index >= len(request.header_items)

    def _selected_auto_header_name(self) -> str | None:
        request = self.state.get_active_request()
        if request is None:
            return None
        auto_index = self.state.selected_header_index - len(request.header_items)
        auto_headers = preview_auto_headers(request, self.state.env_pairs)
        if auto_index < 0 or auto_index >= len(auto_headers):
            return None
        return auto_headers[auto_index][0]

    def _handle_home_body_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_body_select_mode()
            self.state.edit_buffer = ""
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.select_body_row(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.select_body_row(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key == "a":
            if (
                self.state.get_active_request() is not None
                and self.state.get_active_request().body_type
                in {"form-data", "x-www-form-urlencoded"}
            ):
                self.state.enter_home_body_edit_mode(
                    creating=True,
                    origin_mode="HOME_BODY_SELECT",
                )
                self._refresh_screen()
                event.stop()
            return

        if event.key == "space":
            toggled_key = self.state.toggle_selected_body_field()
            if toggled_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            request = self.state.get_active_request()
            if (
                request is not None
                and request.body_type in {"form-data", "x-www-form-urlencoded"}
                and self.state.selected_body_index <= 0
            ):
                self.state.selected_body_index = 1

            if self.state.selected_body_index == 0:
                self.state.enter_home_body_type_edit_mode(origin_mode="HOME_BODY_SELECT")
            else:
                if request is not None and request.body_type == "raw":
                    self.state.enter_home_body_raw_type_edit_mode(
                        origin_mode="HOME_BODY_SELECT"
                    )
                    event.stop()
                    return
                self.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_SELECT")
            self._refresh_screen()
            event.stop()
            return

        if event.key == "d":
            deleted_key = self.state.delete_selected_body_field()
            if deleted_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "s":
            self._send_selected_request()
            event.stop()
            return

    def _handle_home_body_type_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_body_type_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            if self.state.cycle_body_type(-1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            request = self.state.get_active_request()
            if request is None:
                self.state.leave_home_body_type_edit_mode()
                self._refresh_screen()
                event.stop()
                return

            if request.body_type == "raw":
                self.state.enter_home_body_raw_type_edit_mode(
                    origin_mode="HOME_BODY_TYPE_EDIT"
                )
                self._refresh_screen()
                event.stop()
                return

            if request.body_type in BODY_TEXT_EDITOR_TYPES:
                self._open_body_text_editor(origin_mode="HOME_BODY_TYPE_EDIT")
                event.stop()
                return

            if request.body_type == "binary":
                self.state.selected_body_index = 1
                self.state.enter_home_body_edit_mode(origin_mode="HOME_BODY_TYPE_EDIT")
                self._refresh_screen()
                event.stop()
                return

            if request.body_type in {"form-data", "x-www-form-urlencoded"}:
                items = self.state.get_active_request_body_items()
                self.state.selected_body_index = 1
                self.state.enter_home_body_select_mode(
                    origin_mode="HOME_BODY_TYPE_EDIT"
                )
                if not items:
                    self.state.selected_body_index = 1
                self._refresh_screen()
                event.stop()
                return

            self.state.leave_home_body_type_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l"}:
            if self.state.cycle_body_type(1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

    def _handle_home_body_raw_type_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_body_raw_type_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h"}:
            if self.state.cycle_raw_subtype(-1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l"}:
            if self.state.cycle_raw_subtype(1) is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self._open_body_text_editor(origin_mode="HOME_BODY_RAW_TYPE_EDIT")
            event.stop()
            return

    def _handle_home_body_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_home_body_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            saved_key = self.state.save_body_selection()
            if saved_key is not None:
                self._persist_requests()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _handle_env_view_key(self, event: events.Key) -> bool:
        if event.key in {"left", "h"}:
            self.state.select_env_set(-1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"right", "l"}:
            self.state.select_env_set(1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key == "a":
            self.state.enter_env_create_mode()
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"down", "j"}:
            self.state.select_env_row(1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"up", "k"}:
            self.state.select_env_row(-1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"e", "enter"}:
            self.state.enter_env_select_mode()
            self._refresh_screen()
            event.stop()
            return True

        return False

    def _handle_env_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_env_interaction()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"left", "h", "up", "k"}:
            self.state.cycle_env_field(-1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"right", "l", "down", "j"}:
            self.state.cycle_env_field(1)
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"e", "enter"}:
            self.state.enter_env_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "a":
            self.state.enter_env_create_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "d":
            deleted_key = self.state.delete_selected_env_item()
            if deleted_key is not None:
                self._persist_env_pairs()
            self._refresh_screen()
            event.stop()
            return

    def _handle_env_edit_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_env_edit_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key == "enter":
            updated_key = self.state.save_selected_env_field()
            if updated_key is not None:
                self._persist_env_pairs()
            self._refresh_screen()
            event.stop()
            return

        self._handle_inline_edit_key(event)

    def _handle_history_view_key(self, event: events.Key) -> bool:
        if event.key == "s":
            self.state.enter_search_mode()
            self.state.command_buffer = self.state.history_filter_query
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"down", "j"}:
            self.state.select_history_entry(1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"up", "k"}:
            self.state.select_history_entry(-1)
            self._refresh_screen()
            event.stop()
            return True

        if event.key in {"enter", "e"}:
            self.state.enter_history_response_select_mode()
            self._refresh_screen()
            event.stop()
            return True

        return False

    def _handle_history_response_select_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.state.leave_history_response_select_mode()
            self._refresh_screen()
            event.stop()
            return

        if event.key in {"up", "k"}:
            self.state.cycle_history_detail_block(-1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key in {"down", "j"}:
            self.state.cycle_history_detail_block(1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key in {"left", "h"}:
            if self.state.selected_history_detail_block == "request":
                self.state.cycle_history_request_tab(-1)
            else:
                self.state.cycle_history_response_tab(-1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key in {"right", "l"}:
            if self.state.selected_history_detail_block == "request":
                self.state.cycle_history_request_tab(1)
            else:
                self.state.cycle_history_response_tab(1)
            self._refresh_viewport()
            event.stop()
            return

        if event.key == "e":
            self._open_history_response_viewer(origin_mode="HISTORY_RESPONSE_SELECT")
            event.stop()
            return

        if event.key in {"ctrl+d", "ctrl+u"}:
            response_step = response_scroll_step(
                self.query_one("#viewport", Static).size.height
            )
            step = response_step if event.key == "ctrl+d" else -response_step
            if self.state.selected_history_detail_block == "request":
                self.state.scroll_history_request(step)
            else:
                self.state.scroll_history_response(step)
            self._refresh_viewport()
            event.stop()
            return

    def _handle_help_view_key(self, event: events.Key) -> bool:
        if event.key == "escape":
            self.state.leave_help_tab()
            self._refresh_screen()
            event.stop()
            return True
        return False

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.state.mode in {"CONFIRM", "COMMAND", "SEARCH", "HOME_REQUEST_EDIT", "HOME_REQUEST_METHOD_EDIT", "HOME_AUTH_EDIT", "HOME_AUTH_TYPE_EDIT", "HOME_AUTH_LOCATION_EDIT", "HOME_PARAMS_EDIT", "HOME_HEADERS_EDIT", "HOME_BODY_TYPE_EDIT", "HOME_BODY_RAW_TYPE_EDIT", "HOME_BODY_EDIT", "HOME_BODY_TEXTAREA", "HOME_RESPONSE_TEXTAREA", "HISTORY_RESPONSE_TEXTAREA", "ENV_EDIT"} and action == "enter_command_mode":
            return False

        if self.state.mode != "NORMAL" and action in {
            "show_home",
            "show_env",
            "show_history",
            "previous_tab",
            "next_tab",
        }:
            return False
        return True

    def action_enter_command_mode(self) -> None:
        self.state.enter_command_mode()
        self._refresh_screen()

    def action_show_home(self) -> None:
        self.state.switch_tab("home", "Home")
        self._refresh_screen()

    def action_show_env(self) -> None:
        self.state.switch_tab("env", "Env")
        self._refresh_screen()

    def action_show_history(self) -> None:
        self.state.switch_tab("history", "History")
        self._refresh_screen()

    def action_previous_tab(self) -> None:
        self.state.cycle_tab(-1)
        self._refresh_screen()

    def action_next_tab(self) -> None:
        self.state.cycle_tab(1)
        self._refresh_screen()

    def _run_command(self, raw_command: str) -> None:
        before_env_pairs = dict(self.state.env_pairs)
        before_requests = [request.request_id for request in self.state.requests]
        outcome = run_command(self.state, raw_command)
        if outcome.save_env_pairs or self.state.env_pairs != before_env_pairs:
            self._persist_env_pairs()
        if outcome.save_requests or [request.request_id for request in self.state.requests] != before_requests:
            self._persist_requests()
        if outcome.send_request:
            self._send_selected_request()
            return
        if outcome.should_exit:
            self.exit()
            return
        self._refresh_screen()

    def _run_search(self, raw_query: str) -> None:
        if self.state.current_tab == "history":
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
            self._refresh_screen()
            return

        target = resolve_search_target(self.state, raw_query)
        self.state.leave_search_mode()
        if target is None:
            self.state.message = (
                f"No matches for {raw_query.strip()!r}."
                if raw_query.strip()
                else ""
            )
            self._refresh_screen()
            return
        if activate_search_target(self.state, target):
            self._persist_requests()
        else:
            self.state.message = f"Could not open {target.display}."
        self._refresh_screen()

    def _send_selected_request(self) -> None:
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request()
        request = self.state.get_active_request()
        if request is None:
            self.state.message = "No request selected."
            self._refresh_screen()
            return
        self.state.pending_request_id = request.request_id
        self.state.pending_request_spinner_tick = 0
        self.state.response_scroll_offset = 0
        request_definition = deepcopy(request)
        request_env_pairs = dict(self.state.env_pairs)
        source_request_path = request_path(self.state, request)
        self._append_request_log(
            f"START {request.method} {request.url or '<empty-url>'} name={request.name!r}"
        )
        self._refresh_screen()
        self._perform_request_in_worker(
            request.request_id,
            request_definition,
            request_env_pairs,
            source_request_path,
        )

    @work(thread=True, exclusive=True, group="request-send", exit_on_error=False)
    def _perform_request_in_worker(
        self,
        request_id: str,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
    ) -> None:
        response = perform_request(
            definition,
            env_pairs,
            timeout_seconds=self.REQUEST_TIMEOUT_SECONDS,
        )
        self.call_from_thread(
            self._apply_request_result,
            request_id,
            definition,
            env_pairs,
            source_request_path,
            response,
        )

    def _apply_request_result(
        self,
        request_id: str,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
        response,
    ) -> None:
        request = self.state.get_request_by_id(request_id)
        self.state.pending_request_id = None
        self.state.pending_request_spinner_tick = 0
        self._record_history_entry(definition, env_pairs, source_request_path, response)
        if request is None:
            self._append_request_log(
                f"END missing-request id={request_id} error={response.error or '<none>'}"
            )
            self._refresh_screen()
            return

        request.last_response = response
        self.state.response_scroll_offset = 0
        if response.error and response.status_code is None:
            self.state.message = f"Request failed: {response.error}"
            self._append_request_log(
                f"END {request.method} {request.url or '<empty-url>'} failed error={response.error!r}"
            )
        else:
            status = response.status_code or "-"
            self.state.message = f"Response {status} in {response.elapsed_ms or 0:.1f} ms."
            self._append_request_log(
                f"END {request.method} {request.url or '<empty-url>'} status={status} elapsed_ms={response.elapsed_ms or 0:.1f} size={format_bytes(response.body_length)}"
            )
        self._refresh_screen()

    def _refresh_screen(self) -> None:
        self._refresh_overlay_editors()
        self._refresh_viewport()
        self._refresh_status_line()
        self._refresh_command_line()

    def _tick_request_loader(self) -> None:
        if self.state.pending_request_id is None:
            return
        self.state.pending_request_spinner_tick = (
            self.state.pending_request_spinner_tick + 1
        ) % 4
        self._refresh_viewport()

    def _refresh_viewport(self) -> None:
        viewport = self.query_one("#viewport", Static)
        if self.state.current_tab == "home":
            self.state.ensure_request_workspace()
            visible_rows = self._home_request_list_visible_rows()
            self.state.ensure_request_selection_visible(visible_rows)
        if self.state.current_tab == "env":
            visible_rows = self._env_visible_rows()
            self.state.ensure_env_selection_visible(visible_rows)
        if self.state.current_tab == "history":
            visible_rows = self._history_visible_rows()
            self.state.ensure_history_selection_visible(visible_rows)
        viewport.update(render_viewport(self.state, viewport.size.height, viewport.size.width))

    def _refresh_overlay_editors(self) -> None:
        viewport = self.query_one("#viewport", Static)
        body_header = self.query_one("#body-editor-header", Static)
        body_editor = self.query_one("#body-editor", TextArea)
        body_hint = self.query_one("#body-editor-hint", Static)
        body_footer = self.query_one("#body-editor-footer", Static)
        response_header = self.query_one("#response-viewer-header", Static)
        response_editor = self.query_one("#response-viewer", TextArea)
        response_footer = self.query_one("#response-viewer-footer", Static)

        if self.state.mode == "HOME_BODY_TEXTAREA":
            body_header.update(self._body_editor_header_text())
            cursor_index = self._body_editor_cursor_index()
            match = placeholder_match(body_editor.text, cursor_index, sorted(self.state.env_pairs))
            body_footer.update(self._body_editor_footer_text())
            viewport.add_class("hidden")
            body_header.remove_class("hidden")
            body_editor.remove_class("hidden")
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = body_editor.cursor_screen_offset
                body_hint.update(match.suggestion)
                body_hint.offset = (
                    body_editor.region.x + cursor_offset.x + 1,
                    body_editor.region.y + cursor_offset.y,
                )
                body_hint.remove_class("hidden")
            else:
                body_hint.add_class("hidden")
            body_footer.remove_class("hidden")
            response_header.add_class("hidden")
            response_editor.add_class("hidden")
            response_footer.add_class("hidden")
            body_editor.disabled = False
            response_editor.disabled = True
            if not body_editor.has_focus:
                body_editor.focus()
            return

        if self.state.mode == "HOME_RESPONSE_TEXTAREA":
            request = self.state.get_active_request()
            response = request.last_response if request is not None else None
            request_name = request.name if request is not None else "Request"
            status = response.status_code if response is not None else "-"
            elapsed = f"{response.elapsed_ms or 0:.1f} ms" if response is not None else "-"
            response_header.update(f"Response Viewer  [{request_name}]")
            response_footer.update(
                f"Status {status}   Time {elapsed}   {self.response_copy_hint} copies selection/all   Esc closes"
            )
            viewport.add_class("hidden")
            body_header.add_class("hidden")
            body_editor.add_class("hidden")
            body_hint.add_class("hidden")
            body_footer.add_class("hidden")
            response_header.remove_class("hidden")
            response_editor.remove_class("hidden")
            response_footer.remove_class("hidden")
            body_editor.disabled = True
            response_editor.disabled = False
            if not response_editor.has_focus:
                response_editor.focus()
            return

        if self.state.mode == "HISTORY_RESPONSE_TEXTAREA":
            entry = self.state.get_selected_history_entry()
            entry_name = (
                entry.source_request_name.strip()
                or entry.source_request_path.strip()
                or "History"
            ) if entry is not None else "History"
            response_header.update(f"History Viewer  [{entry_name}]")
            response_footer.update(
                f"{self.response_copy_hint} copies selection/all   Esc closes"
            )
            viewport.add_class("hidden")
            body_header.add_class("hidden")
            body_editor.add_class("hidden")
            body_hint.add_class("hidden")
            body_footer.add_class("hidden")
            response_header.remove_class("hidden")
            response_editor.remove_class("hidden")
            response_footer.remove_class("hidden")
            body_editor.disabled = True
            response_editor.disabled = False
            if not response_editor.has_focus:
                response_editor.focus()
            return

        viewport.remove_class("hidden")
        body_header.add_class("hidden")
        body_editor.add_class("hidden")
        body_hint.add_class("hidden")
        body_footer.add_class("hidden")
        response_header.add_class("hidden")
        response_editor.add_class("hidden")
        response_footer.add_class("hidden")
        body_editor.disabled = True
        response_editor.disabled = True

    def _refresh_status_line(self) -> None:
        self.query_one("#status-line", Static).update(render_status_line(self.state))

    def _refresh_command_line(self) -> None:
        self.query_one("#command-line", Static).update(render_command_line(self.state))

    def _env_visible_rows(self) -> int:
        viewport = self.query_one("#viewport", Static)
        return max(viewport.size.height - 6, 1)

    def _history_visible_rows(self) -> int:
        viewport = self.query_one("#viewport", Static)
        return max(viewport.size.height - 6, 6)

    def _home_request_list_visible_rows(self) -> int:
        viewport = self.query_one("#viewport", Static)
        return max(viewport.size.height - 8, 6)

    def _persist_env_pairs(self) -> None:
        save_env_workspace(
            self._env_workspace_path,
            self.state.env_names,
            self.state.env_sets,
            self.state.selected_env_name,
        )

    def _persist_requests(self) -> None:
        save_request_workspace(
            self._requests_file_path,
            self.state.collections,
            self.state.folders,
            self.state.requests,
            self.state.collapsed_collection_ids,
            self.state.collapsed_folder_ids,
        )

    def _record_history_entry(
        self,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
        response,
    ) -> None:
        entry = build_history_entry(
            definition,
            env_pairs,
            response,
            source_request_path,
        )
        self.state.prepend_history_entry(entry)
        append_history_entry(self._history_file_path, entry)

    def _append_request_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ensure_parent_dir(self._log_file_path)
        with self._log_file_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")

    def _copy_text(self, text: str) -> bool:
        self.copy_to_clipboard(text)

        system = platform.system()
        try:
            if system == "Darwin" and shutil.which("pbcopy"):
                result = subprocess.run(
                    ["pbcopy"],
                    input=text,
                    text=True,
                    check=False,
                )
                return result.returncode == 0
            if system == "Linux":
                if shutil.which("wl-copy"):
                    result = subprocess.run(
                        ["wl-copy"],
                        input=text,
                        text=True,
                        check=False,
                    )
                    return result.returncode == 0
                if shutil.which("xclip"):
                    result = subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text,
                        text=True,
                        check=False,
                    )
                    return result.returncode == 0
                if shutil.which("xsel"):
                    result = subprocess.run(
                        ["xsel", "--clipboard", "--input"],
                        input=text,
                        text=True,
                        check=False,
                    )
                    return result.returncode == 0
            if system == "Windows" and shutil.which("clip"):
                result = subprocess.run(
                    ["clip"],
                    input=text,
                    text=True,
                    check=False,
                )
                return result.returncode == 0
        except OSError:
            return False

        return True

    def _reset_command_completion(self) -> None:
        self._command_completion_anchor = ""
        self._command_completion_index = -1

    def _reset_edit_path_completion(self) -> None:
        self._edit_path_completion_anchor = ""
        self._edit_path_completion_index = -1

    def _binary_path_edit_active(self) -> bool:
        request = self.state.get_active_request()
        return (
            request is not None
            and request.body_type == "binary"
            and self.state.mode == "HOME_BODY_EDIT"
        )

    def _normalize_pasted_inline_text(self, pasted: str) -> str:
        return pasted.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "")

    def _paste_text(self) -> str | None:
        system = platform.system()
        try:
            if system == "Darwin" and shutil.which("pbpaste"):
                result = subprocess.run(
                    ["pbpaste"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return result.stdout if result.returncode == 0 else None
            if system == "Linux":
                if shutil.which("wl-paste"):
                    result = subprocess.run(
                        ["wl-paste", "-n"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return result.stdout if result.returncode == 0 else None
                if shutil.which("xclip"):
                    result = subprocess.run(
                        ["xclip", "-o", "-selection", "clipboard"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return result.stdout if result.returncode == 0 else None
                if shutil.which("xsel"):
                    result = subprocess.run(
                        ["xsel", "--clipboard", "--output"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return result.stdout if result.returncode == 0 else None
            if system == "Windows":
                powershell = shutil.which("powershell") or shutil.which("pwsh")
                if powershell is not None:
                    result = subprocess.run(
                        [powershell, "-NoProfile", "-Command", "Get-Clipboard"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return result.stdout if result.returncode == 0 else None
        except OSError:
            return None

        return None

    def _response_copy_keys(self) -> tuple[str, ...]:
        system = platform.system()
        if system == "Darwin":
            return ("ctrl+c",)
        if system == "Windows":
            return ("ctrl+shift+c", "ctrl+insert")
        return ("ctrl+shift+c",)

    def _register_text_area_languages(self) -> None:
        try:
            javascript_language = get_language("javascript")
        except Exception:
            return
        if javascript_language is None:
            return
        for editor_id in ("#body-editor", "#response-viewer"):
            editor = self.query_one(editor_id, TextArea)
            editor.register_language(
                self.GRAPHQL_TEXTAREA_LANGUAGE,
                javascript_language,
                self.GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY,
            )

    def _set_text_area_language(
        self,
        editor: TextArea,
        language: str | None,
    ) -> None:
        try:
            editor.language = language
        except LanguageDoesNotExist:
            editor.language = None

    def _response_copy_hint(self) -> str:
        system = platform.system()
        if system == "Darwin":
            return "Ctrl+C"
        if system == "Windows":
            return "Ctrl+Shift+C/Ctrl+Insert"
        return "Ctrl+Shift+C"

    def _body_editor_header_text(self) -> str:
        request = self.state.get_active_request()
        request_name = request.name if request is not None else "Request"
        if request is not None and request.body_type == "binary":
            return f"Binary File Path  [{request_name}]"
        if request is not None and request.body_type == "graphql":
            return f"GraphQL Editor  [{request_name}]"
        return f"Body Editor  [{request_name}]"

    def _body_editor_footer_text(self) -> str:
        request = self.state.get_active_request()
        if request is not None and request.body_type == "binary":
            return "Enter or paste a file path. Ctrl+S saves, Esc cancels."
        if request is not None and request.body_type == "graphql":
            return "Edit the GraphQL document. Ctrl+S saves, Esc cancels."
        return "Paste and edit freely. Ctrl+S saves, Esc cancels."

    def _open_body_text_editor(self, origin_mode: str | None = None) -> None:
        request = self.state.get_active_request()
        if request is None:
            self.state.message = "No requests to edit."
            self._refresh_screen()
            return
        self.state.enter_home_body_text_editor_mode(origin_mode=origin_mode)
        editor = self.query_one("#body-editor", TextArea)
        self._set_text_area_language(
            editor,
            text_area_syntax_language(request_body_syntax_language(request)),
        )
        editor.load_text(request.body_text)
        editor.move_cursor((0, 0))
        self._refresh_screen()

    def _close_body_text_editor(self, save: bool) -> None:
        editor = self.query_one("#body-editor", TextArea)
        if save:
            request = self.state.get_active_request()
            validation_error = (
                validate_raw_body(request, editor.text) if request is not None else None
            )
            if validation_error is not None:
                self.state.message = validation_error
                self._refresh_screen()
                return
            updated_field = self.state.save_raw_body_text(editor.text)
            if updated_field is not None:
                self._persist_requests()
        else:
            self.state.leave_home_body_text_editor_mode()
        self.set_focus(None)
        self._refresh_screen()
        self.call_after_refresh(self._refresh_screen)

    def _open_response_viewer(self, origin_mode: str | None = None) -> None:
        request = self.state.get_active_request()
        if request is None or request.last_response is None:
            self.state.message = "No response to view."
            self._refresh_screen()
            return
        if not self.state.enter_home_response_view_mode(origin_mode or self.state.mode):
            self._refresh_screen()
            return
        editor = self.query_one("#response-viewer", TextArea)
        body_text = format_response_body(request.last_response.body_text)
        self._set_text_area_language(
            editor,
            text_area_syntax_language(detect_text_syntax_language(body_text)),
        )
        editor.load_text(body_text or request.last_response.body_text or "")
        editor.move_cursor((0, 0))
        self._refresh_screen()

    def _open_history_response_viewer(self, origin_mode: str | None = None) -> None:
        entry = self.state.get_selected_history_entry()
        if entry is None:
            self.state.message = "No history entry selected."
            self._refresh_screen()
            return
        if not self.state.enter_history_response_view_mode(origin_mode or self.state.mode):
            self._refresh_screen()
            return
        editor = self.query_one("#response-viewer", TextArea)
        if self.state.selected_history_detail_block == "request":
            if self.state.selected_history_request_tab == "headers":
                self._set_text_area_language(editor, None)
                content = "\n".join(
                    f"{key}: {value}" for key, value in entry.request_headers
                ) or "-"
            else:
                body_text = format_response_body(entry.request_body)
                self._set_text_area_language(
                    editor,
                    text_area_syntax_language(detect_text_syntax_language(body_text)),
                )
                content = body_text or entry.request_body or ""
        elif self.state.selected_history_response_tab == "headers":
            self._set_text_area_language(editor, None)
            content = "\n".join(
                f"{key}: {value}" for key, value in entry.response_headers
            ) or "-"
        else:
            body_text = format_response_body(entry.response_body)
            self._set_text_area_language(
                editor,
                text_area_syntax_language(detect_text_syntax_language(body_text)),
            )
            content = body_text or entry.response_body or ""
        editor.load_text(content)
        editor.move_cursor((0, 0))
        self._refresh_screen()

    def _close_response_viewer(self) -> None:
        if self.state.mode == "HISTORY_RESPONSE_TEXTAREA":
            self.state.leave_history_response_view_mode()
        else:
            self.state.leave_home_response_view_mode()
        self.set_focus(None)
        self._refresh_screen()
        self.call_after_refresh(self._refresh_screen)
