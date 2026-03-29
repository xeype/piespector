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
from textual import work
from textual.widgets import Static, TextArea

from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS
from piespector.domain.modes import COMMAND_BLOCKED_MODES, REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_EDIT,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_RESPONSE_TEXTAREA,
    MODE_NORMAL,
    MODE_SEARCH,
)
from piespector.formatting import format_bytes
from piespector.history import build_history_entry
from piespector.http_client import (
    perform_request,
    preview_request_url,
)
from piespector.rendering import (
    render_command_line,
    render_status_line,
    render_viewport,
)
from piespector.interactions.controller import InteractionController
from piespector.interactions.keys import response_copy_hint, response_copy_keys
from piespector.screens.env import render as env_render
from piespector.screens.env.controller import EnvController
from piespector.screens.history import render as history_render
from piespector.screens.history.controller import HistoryController
from piespector.screens.home.controller import HomeController
from piespector.search import request_path
from piespector.state import PiespectorState
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
from piespector.ui.overlays import OverlayController, build_overlay_widgets


class PiespectorApp(App[None]):
    """Minimal terminal UI skeleton with a Vim-like layout."""

    ENABLE_COMMAND_PALETTE = False
    REQUEST_TIMEOUT_SECONDS = 15.0
    theme = "atom-one-dark"
    CSS = APP_CSS
    BINDINGS = APP_BINDINGS
    REQUEST_RESPONSE_SHORTCUT_MODES = REQUEST_RESPONSE_SHORTCUT_MODES

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
        self.response_copy_keys = response_copy_keys()
        self.response_copy_hint = response_copy_hint()
        self._command_completion_anchor = ""
        self._command_completion_index = -1
        self._edit_path_completion_anchor = ""
        self._edit_path_completion_index = -1
        self.env_controller = EnvController(self)
        self.history_controller = HistoryController(self)
        self.home_controller = HomeController(self)
        self.interaction_controller = InteractionController(self)
        self.overlay_controller = OverlayController(self)

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="workspace"):
                yield Static("", id="viewport")
                for widget in build_overlay_widgets():
                    yield widget
            yield Static("", id="status-line")
            yield Static("", id="command-line")

    def on_mount(self) -> None:
        self.overlay_controller.register_text_area_languages()
        self._load_env_workspace()
        self._load_history()
        self._load_request_workspace()
        if self.state.requests and self.state.get_active_request() is None:
            self.state.open_selected_request()
        self.set_interval(0.12, self._tick_request_loader)
        self._refresh_screen()
        self.call_after_refresh(self._refresh_screen)

    def _load_env_workspace(self) -> None:
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

    def _load_history(self) -> None:
        history_source_path = self._history_file_path
        if (
            not self._history_file_path.exists()
            and self._legacy_history_file_path.exists()
        ):
            history_source_path = self._legacy_history_file_path
        self.state.history_entries = load_history_entries(history_source_path)
        if history_source_path != self._history_file_path:
            save_history_entries(self._history_file_path, self.state.history_entries)

    def _load_request_workspace(self) -> None:
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

    def on_resize(self) -> None:
        self._refresh_screen()

    def on_key(self, event: events.Key) -> None:
        if self.state.mode == MODE_CONFIRM:
            self.interaction_controller.handle_confirm_key(event)
            return

        if self.state.mode == MODE_COMMAND:
            self.interaction_controller.handle_command_key(event)
            return

        if self.state.mode == MODE_SEARCH:
            self.interaction_controller.handle_search_key(event)
            return

        if self.state.current_tab == TAB_HOME:
            if self.home_controller.handle_request_response_shortcuts(event):
                return
            if self.state.mode == MODE_NORMAL and self.home_controller.handle_home_view_key(event):
                return
            if self.state.mode == MODE_HOME_RESPONSE_TEXTAREA:
                return
            self.home_controller.dispatch_key(self.state.mode, event)
            return

        if self.state.current_tab == TAB_ENV:
            if self.state.mode == MODE_NORMAL and self.env_controller.handle_env_view_key(event):
                return
            if self.state.mode == MODE_ENV_SELECT:
                self.env_controller.handle_env_select_key(event)
                return
            if self.state.mode == MODE_ENV_EDIT:
                self.env_controller.handle_env_edit_key(event)
                return

        if self.state.current_tab == TAB_HISTORY:
            if self.state.mode == MODE_NORMAL and self.history_controller.handle_history_view_key(event):
                return
            if self.state.mode == MODE_HISTORY_RESPONSE_SELECT:
                self.history_controller.handle_history_response_select_key(event)
                return

        if self.state.current_tab == TAB_HELP:
            if (
                self.state.mode == MODE_NORMAL
                and self.interaction_controller.handle_help_view_key(event)
            ):
                return

    def _handle_inline_edit_key(self, event: events.Key) -> bool:
        return self.interaction_controller.handle_inline_edit_key(event)

    def _autocomplete_body_editor_placeholder(self) -> bool:
        return self.overlay_controller.autocomplete_body_editor_placeholder()

    def _postprocess_body_editor_brace(self) -> None:
        self.overlay_controller.postprocess_body_editor_brace()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.state.mode in COMMAND_BLOCKED_MODES and action == "enter_command_mode":
            return False

        if self.state.mode != MODE_NORMAL and action in {
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
        self.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        self._refresh_screen()

    def action_show_env(self) -> None:
        self.state.switch_tab(TAB_ENV, TAB_LABELS[TAB_ENV])
        self._refresh_screen()

    def action_show_history(self) -> None:
        self.state.switch_tab(TAB_HISTORY, TAB_LABELS[TAB_HISTORY])
        self._refresh_screen()

    def action_previous_tab(self) -> None:
        self.state.cycle_tab(-1)
        self._refresh_screen()

    def action_next_tab(self) -> None:
        self.state.cycle_tab(1)
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
        self.overlay_controller.refresh()
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
        if self.state.current_tab == TAB_HOME:
            self.state.ensure_request_workspace()
            visible_rows = self._home_request_list_visible_rows()
            self.state.ensure_request_selection_visible(visible_rows)
        if self.state.current_tab == TAB_ENV:
            visible_rows = self._env_visible_rows()
            self.state.ensure_env_selection_visible(visible_rows)
        if self.state.current_tab == TAB_HISTORY:
            visible_rows = self._history_visible_rows()
            self.state.ensure_history_selection_visible(visible_rows)
        viewport.update(render_viewport(self.state, viewport.size.height, viewport.size.width))

    def _refresh_overlay_editors(self) -> None:
        self.overlay_controller.refresh()

    def _refresh_status_line(self) -> None:
        self.query_one("#status-line", Static).update(render_status_line(self.state))

    def _refresh_command_line(self) -> None:
        self.query_one("#command-line", Static).update(render_command_line(self.state))

    def _env_visible_rows(self) -> int:
        viewport = self.query_one("#viewport", Static)
        return env_render.env_visible_rows(viewport.size.height)

    def _history_visible_rows(self) -> int:
        viewport = self.query_one("#viewport", Static)
        return history_render.history_list_visible_rows(viewport.size.height)

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

    def action_copy_active_request_url(self) -> None:
        request = self.state.get_active_request()
        if request is None:
            self.state.message = "No active request."
            self._refresh_command_line()
            return

        resolved_url = preview_request_url(request, self.state.env_pairs).strip()
        if not resolved_url:
            self.state.message = "No URL to copy."
            self._refresh_command_line()
            return

        copied = self._copy_text(resolved_url)
        self.state.message = "Copied resolved URL." if copied else "Copy failed."
        self._refresh_command_line()

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
            and self.state.mode == MODE_HOME_BODY_EDIT
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

    def _register_text_area_languages(self) -> None:
        self.overlay_controller.register_text_area_languages()

    def _set_text_area_language(
        self,
        editor: TextArea,
        language: str | None,
    ) -> None:
        self.overlay_controller.set_text_area_language(editor, language)

    def _body_editor_header_text(self) -> str:
        return self.overlay_controller.body_editor_header_text()

    def _body_editor_footer_text(self) -> str:
        return self.overlay_controller.body_editor_footer_text()

    def _open_body_text_editor(self, origin_mode: str | None = None) -> None:
        self.overlay_controller.open_body_text_editor(origin_mode=origin_mode)

    def _close_body_text_editor(self, save: bool) -> None:
        self.overlay_controller.close_body_text_editor(save)

    def _open_response_viewer(self, origin_mode: str | None = None) -> None:
        self.overlay_controller.open_response_viewer(origin_mode=origin_mode)

    def _open_history_response_viewer(self, origin_mode: str | None = None) -> None:
        self.overlay_controller.open_history_response_viewer(origin_mode=origin_mode)

    def _close_response_viewer(self) -> None:
        self.overlay_controller.close_response_viewer()
