from __future__ import annotations

from pathlib import Path
import platform
import shutil
import subprocess

from textual import events
from textual.app import App, ScreenStackError, SystemCommand
from textual.command import CommandPalette
from textual.css.query import NoMatches
from textual import work
from textual.suggester import SuggestFromList
from textual.widgets import (
    ContentSwitcher,
    DataTable,
    Input,
    Select,
    Static,
    TabbedContent,
    Tabs,
    TextArea,
    Tree,
)

from piespector.commands import command_context_mode, help_commands
from piespector.domain.editor import (
    HOME_SIDEBAR_JUMP_KEY,
    HOME_SIDEBAR_LABEL,
    REQUEST_EDITOR_JUMP_BINDINGS,
    RESPONSE_JUMP_BINDINGS,
    TAB_ENV,
    TAB_HISTORY,
    TAB_HOME,
    TAB_LABELS,
    TAB_ORDER,
    TOP_BAR_METHOD_JUMP_KEY,
    TOP_BAR_URL_JUMP_KEY,
)
from piespector.domain.modes import COMMAND_BLOCKED_MODES, REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_HOME_URL_EDIT,
    MODE_NORMAL,
)
from piespector.http_client import (
    preview_request_url,
)
from piespector.interactions.controller import EventRouter, InteractionController
from piespector.interactions.keys import response_copy_hint, response_copy_keys
from piespector.persistence import PersistenceManager
from piespector.request_executor import RequestExecutor
from piespector.screens.base import PiespectorScreen
from piespector.screens.env import render as env_render
from piespector.screens.env.controller import EnvController
from piespector.screens.env.screen import EnvScreen
from piespector.screens.history import render as history_render
from piespector.screens.history.controller import HistoryController
from piespector.screens.history.screen import HistoryScreen
from piespector.screens.home.controller import HomeController
from piespector.screens.home.layout import home_top_bar_height
from piespector.screens.home.render import (
    refresh_home_sidebar,
    refresh_home_request_content,
    refresh_home_response,
    refresh_home_url_bar,
    sync_home_focus_highlights,
)
from piespector.screens.home.screen import HomeScreen
from piespector.state import PiespectorState
from piespector.storage import (
    app_data_dir,
    env_workspace_path,
    history_file_path,
    load_env_workspace,
    load_history_entries,
    load_request_workspace,
    requests_file_path,
)
from piespector.ui import APP_BINDINGS, APP_CSS
from piespector.ui.command_line_content import build_command_line_text
from piespector.ui.command_palette import (
    PiespectorPalette,
    PiespectorCommandProvider,
    PiespectorSearchProvider,
    PiespectorThemeProvider,
)
from piespector.ui.footer import PiespectorFooter
from piespector.ui.help_panel import PiespectorHelpPanel
from piespector.ui.jump_overlay import JumpOverlay
from piespector.ui.jumper import JumpTarget, Jumper
from piespector.ui.overlays import OverlayController
from piespector.ui.status_content import status_bar_content

class PiespectorApp(App[None]):
    """Terminal UI API client with Vim-like navigation."""

    ENABLE_COMMAND_PALETTE = True
    REQUEST_TIMEOUT_SECONDS = 15.0
    theme = "monokai"
    CSS = APP_CSS
    BINDINGS = APP_BINDINGS
    COMMANDS = App.COMMANDS | {PiespectorCommandProvider}
    REQUEST_RESPONSE_SHORTCUT_MODES = REQUEST_RESPONSE_SHORTCUT_MODES

    def __init__(self, *, persist_state: bool = False) -> None:
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
        self._edit_path_completion_anchor = ""
        self._edit_path_completion_index = -1
        self.state.attach_app(self)
        self.persistence_manager = PersistenceManager(self, enabled=persist_state)
        self.request_executor = RequestExecutor(self)
        self.env_controller = EnvController(self)
        self.history_controller = HistoryController(self)
        self.home_controller = HomeController(self)
        self.interaction_controller = InteractionController(self)
        self.event_router = EventRouter(self)
        self.overlay_controller = OverlayController(self)
        self._home_screen = HomeScreen()
        self._env_screen = EnvScreen()
        self._history_screen = HistoryScreen()
        self._screens_installed = False

    def on_mount(self) -> None:
        self.install_screen(self._home_screen, TAB_HOME)
        self.install_screen(self._env_screen, TAB_ENV)
        self.install_screen(self._history_screen, TAB_HISTORY)
        self._screens_installed = True
        initial_tab = self.state.current_tab if self.state.current_tab in TAB_ORDER else TAB_HOME
        self.push_screen(initial_tab)
        self._load_env_workspace()
        self._load_history()
        self._load_request_workspace()
        if self.state.requests and self.state.get_active_request() is None:
            self.state.open_selected_request()
        self.set_interval(0.12, self._tick_request_loader)
        self.call_after_refresh(self._refresh_screen)

    def apply_theme(self, theme_name: str) -> None:
        self.theme = theme_name
        if self._screens_installed:
            self.refresh_css(animate=False)
            self._refresh_screen()

    def search_themes(self) -> None:
        self.open_palette(
            providers=[PiespectorThemeProvider],
            placeholder="Search for themes…",
            palette_id="--theme-palette",
        )

    def get_system_commands(self, screen):
        for command in super().get_system_commands(screen):
            if command.title != "Keys":
                yield command
                continue
            yield SystemCommand(
                "Help",
                (
                    "Hide the help panel."
                    if screen.query(PiespectorHelpPanel)
                    else "Show help for the focused widget and a summary of available keys."
                ),
                command.callback,
                command.discover,
            )

    def action_show_help_panel(self) -> None:
        try:
            self.screen.query_one(PiespectorHelpPanel)
        except NoMatches:
            self.screen.mount(PiespectorHelpPanel())

    def action_hide_help_panel(self) -> None:
        self.screen.query(PiespectorHelpPanel).remove()

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
            self._persist_env_pairs()

    def _load_history(self) -> None:
        history_source_path = self._history_file_path
        if (
            not self._history_file_path.exists()
            and self._legacy_history_file_path.exists()
        ):
            history_source_path = self._legacy_history_file_path
        self.state.history_entries = load_history_entries(history_source_path)
        if history_source_path != self._history_file_path:
            self._persist_history_entries()

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
            self._persist_requests()

    def on_resize(self) -> None:
        self._refresh_screen()

    def on_key(self, event: events.Key) -> None:
        self.event_router.handle_key(event)

    def _autocomplete_body_editor_placeholder(self) -> bool:
        return self.overlay_controller.autocomplete_body_editor_placeholder()

    def _postprocess_body_editor_brace(self) -> None:
        self.overlay_controller.postprocess_body_editor_brace()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {
            "enter_command_mode",
            "command_palette",
            "search_workspace",
        } and self.state.mode in COMMAND_BLOCKED_MODES:
            return False

        if (
            action == "enter_jump_mode"
            and self.state.mode in COMMAND_BLOCKED_MODES
            and self.state.mode != MODE_HOME_URL_EDIT
        ):
            return False

        if action in {
            "home_browse_up",
            "home_browse_down",
            "home_previous_folder",
            "home_next_folder",
            "home_previous_collection",
            "home_next_collection",
            "home_previous_open_request",
            "home_next_open_request",
        }:
            return self.state.current_tab == TAB_HOME and self.state.mode == MODE_NORMAL

        if self.state.mode != MODE_NORMAL and action in {
            "show_home",
            "show_env",
            "show_history",
            "previous_tab",
            "next_tab",
        }:
            return False
        return True

    def action_enter_jump_mode(self) -> None:
        self.state.enter_jump_mode()
        if self.state.current_tab == TAB_HOME and self._has_live_screen():
            self._refresh_screen()
            self.push_screen(
                self._build_home_jump_overlay(),
                self._handle_jump_overlay_result,
            )
            return
        self._refresh_jump_state()

    def action_enter_command_mode(self) -> None:
        self.action_command_palette()

    def open_palette(
        self,
        *,
        placeholder: str,
        initial_value: str = "",
        providers=None,
        palette_id: str = "--command-palette",
    ) -> None:
        if not self.use_command_palette or CommandPalette.is_open(self):
            return
        self.push_screen(
            PiespectorPalette(
                providers=providers,
                placeholder=placeholder,
                id=palette_id,
                initial_value=initial_value,
            )
        )

    def open_command_palette(self, initial_value: str = "") -> None:
        self.open_palette(
            placeholder="Run a piespector command…",
            initial_value=initial_value,
            palette_id="--command-palette",
        )

    def action_command_palette(self) -> None:
        self.open_command_palette()

    def open_search_palette(self) -> None:
        self.open_palette(
            providers=[PiespectorSearchProvider],
            placeholder="Search collections, folders, and requests…",
            palette_id="--workspace-search",
        )

    def action_search_workspace(self) -> None:
        self.open_search_palette()

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

    def action_home_browse_up(self) -> None:
        self.home_controller.navigation.browse_sidebar(-1)

    def action_home_browse_down(self) -> None:
        self.home_controller.navigation.browse_sidebar(1)

    def action_home_previous_folder(self) -> None:
        self.home_controller.navigation.jump_folder(-1)

    def action_home_next_folder(self) -> None:
        self.home_controller.navigation.jump_folder(1)

    def action_home_previous_collection(self) -> None:
        self.home_controller.navigation.jump_collection(-1)

    def action_home_next_collection(self) -> None:
        self.home_controller.navigation.jump_collection(1)

    def action_home_previous_open_request(self) -> None:
        self.home_controller.navigation.cycle_open_request(-1)

    def action_home_next_open_request(self) -> None:
        self.home_controller.navigation.cycle_open_request(1)

    def _sync_home_sidebar_cursor(self) -> None:
        if self.state.current_tab != TAB_HOME or not self._has_live_screen():
            return
        try:
            tree = self._query_current("#sidebar-tree", Tree)
        except Exception:
            return
        item_count = len(self.state.get_sidebar_nodes())
        if item_count <= 0:
            return
        selected_index = max(0, min(self.state.selected_sidebar_index, item_count - 1))
        tree._piespector_ignore_highlight_index = selected_index
        try:
            tree.cursor_line = selected_index
            tree.scroll_to_line(selected_index, animate=False)
        except Exception:
            tree._piespector_ignore_highlight_index = None

    def _switch_screen_visibility(self) -> None:
        if not self._screens_installed:
            return
        current_screen = self._current_base_screen()
        if current_screen is None:
            return
        if self.screen.is_modal:
            return

        target_tab = self.state.current_tab if self.state.current_tab in TAB_ORDER else TAB_HOME
        if current_screen is not self._screen_for_tab(target_tab):
            self.switch_screen(target_tab)

    def _screen_for_tab(self, tab_id: str) -> PiespectorScreen:
        if tab_id == TAB_ENV:
            return self._env_screen
        if tab_id == TAB_HISTORY:
            return self._history_screen
        return self._home_screen

    def _current_base_screen(self) -> PiespectorScreen | None:
        for screen in reversed(self.screen_stack):
            if isinstance(screen, PiespectorScreen):
                return screen
        return None

    def _query_current(self, selector: str, expect_type=None):
        current_screen = self._current_base_screen()
        if current_screen is None:
            raise ScreenStackError("No active application screen.")
        return current_screen.query_one(selector, expect_type)

    def _send_selected_request(self) -> None:
        self.request_executor.send_selected_request()

    @work(thread=True, exclusive=True, group="request-send", exit_on_error=False)
    def _perform_request_in_worker(
        self,
        request_id: str,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
    ) -> None:
        self.request_executor.perform_request_in_worker(
            request_id,
            definition,
            env_pairs,
            source_request_path,
        )

    def _refresh_screen(self) -> None:
        if not self._screens_installed:
            return
        self._switch_screen_visibility()
        if not self._screen_widgets_ready():
            self.call_after_refresh(self._refresh_screen)
            return
        self.overlay_controller.refresh()
        self._refresh_viewport()
        self._refresh_status_line()
        self._refresh_command_line()

    def _screen_widgets_ready(self) -> bool:
        try:
            self._query_current("#workspace")
            self._query_current("#status-line")
            self._query_current("#command-line")
            self._query_current("#command-line-content", Static)
            self._query_current("#command-input", Input)
        except Exception:
            return False
        return True

    def _tick_request_loader(self) -> None:
        if self.state.pending_request_id is None:
            return
        self.state.pending_request_spinner_tick = (
            self.state.pending_request_spinner_tick + 1
        ) % 4
        self._refresh_viewport()

    def _refresh_viewport(self) -> None:
        if self.state.current_tab == TAB_HOME:
            self.state.ensure_request_workspace()
            visible_rows = self._home_request_list_visible_rows()
            self.state.ensure_request_selection_visible(visible_rows)
            self._refresh_home_screen()
        elif self.state.current_tab == TAB_ENV:
            visible_rows = self._env_visible_rows()
            self.state.ensure_env_selection_visible(visible_rows)
            self._refresh_env_screen()
        elif self.state.current_tab == TAB_HISTORY:
            visible_rows = self._history_visible_rows()
            self.state.ensure_history_selection_visible(visible_rows)
            self._refresh_history_screen()

    def _refresh_home_screen(self) -> None:
        self._refresh_home_sidebar_panel()
        self._refresh_home_url_bar_panel()
        self._refresh_home_request_panel()
        self._refresh_home_response_panel()
        self._refresh_home_jump_cues()

    def _refresh_home_jump_cues(self) -> None:
        if not self._has_live_screen():
            return

        url_bar_container = self._query_current("#url-bar-container")
        sidebar_container = self._query_current("#sidebar-container")
        request_panel = self._query_current("#request-panel")
        response_panel = self._query_current("#response-panel")
        method_select = self._query_current("#method-select", Select)
        url_bar_subtitle = self._query_current("#url-bar-subtitle", Static)
        sidebar_container.styles.border_title_align = "right"
        request_panel.styles.border_title_align = "right"
        response_panel.styles.border_title_align = "right"
        sidebar_container.border_title = HOME_SIDEBAR_LABEL
        request_panel.border_title = "Request"
        response_panel.border_title = "Response"
        url_bar_container.styles.height = home_top_bar_height()
        url_bar_subtitle.update("")
        url_bar_subtitle.display = False
        sync_home_focus_highlights(
            self.state,
            url_bar_container,
            sidebar_container,
            request_panel,
            response_panel,
            method_select,
        )

    def _build_home_jump_overlay(self) -> JumpOverlay:
        active_request = self.state.get_active_request()
        tree = self._query_current("#sidebar-tree", Tree)
        method_select = self._query_current("#method-select", Select)
        url_display = self._query_current("#url-display", Static)
        url_input = self._query_current("#url-input", Input)
        request_tabs = self._query_current("#request-tabs", TabbedContent)
        response_tabs = self._query_current("#response-tabs", Tabs)

        request_tab_widgets = sorted(
            request_tabs.query("ContentTab"),
            key=lambda widget: widget.region.x,
        )
        response_tab_widgets = sorted(
            response_tabs.query("Tab"),
            key=lambda widget: widget.region.x,
        )

        targets: list[JumpTarget] = [
            JumpTarget(HOME_SIDEBAR_JUMP_KEY, "collections", tree),
        ]
        if active_request is not None:
            targets.extend(
                [
                    JumpTarget(TOP_BAR_METHOD_JUMP_KEY, "topbar:method", method_select),
                    JumpTarget(
                        TOP_BAR_URL_JUMP_KEY,
                        "topbar:url",
                        url_input if url_input.display else url_display,
                    ),
                ]
            )
        targets.extend(
            JumpTarget(jump_key, f"request:{tab_id}", widget)
            for widget, (tab_id, jump_key) in zip(request_tab_widgets, REQUEST_EDITOR_JUMP_BINDINGS)
        )
        targets.extend(
            JumpTarget(jump_key, f"response:{tab_id}", widget)
            for widget, (tab_id, jump_key) in zip(response_tab_widgets, RESPONSE_JUMP_BINDINGS)
        )
        return JumpOverlay(Jumper(tuple(targets)))

    def _handle_jump_overlay_result(self, target: str | None) -> None:
        self.state.leave_jump_mode()
        if target is not None:
            self.interaction_controller.activate_jump_target(target)
        self._refresh_screen()
        self.call_after_refresh(self._clear_home_jump_focus)

    def _clear_home_jump_focus(self) -> None:
        if self.state.mode == MODE_HOME_URL_EDIT:
            try:
                url_input = self._query_current("#url-input", Input)
            except Exception:
                url_input = None
            if url_input is not None and url_input.display:
                self.set_focus(url_input)
                return

        self.set_focus(None)
        for widget_id in (
            "method-select",
            "auth-type-select",
            "auth-option-select",
            "body-type-select",
            "body-raw-type-select",
        ):
            try:
                self._query_current(f"#{widget_id}", Select).blur()
            except Exception:
                pass

    def _has_live_screen(self) -> bool:
        return self._current_base_screen() is not None

    def _refresh_home_sidebar_panel(self) -> None:
        if not self._has_live_screen():
            self._refresh_viewport()
            return
        tree = self._query_current("#sidebar-tree", Tree)
        sidebar_subtitle = self._query_current("#sidebar-subtitle", Static)
        sidebar_container = self._query_current("#sidebar-container")
        sidebar_title = self._query_current("#sidebar-title", Static)
        visible_rows = self._home_request_list_visible_rows()
        refresh_home_sidebar(
            self.state,
            tree,
            sidebar_subtitle,
            sidebar_container,
            sidebar_title,
            visible_rows,
        )

    def _refresh_home_url_bar_panel(self) -> None:
        if not self._has_live_screen():
            self._refresh_screen()
            return
        method_select = self._query_current("#method-select", Select)
        url_display = self._query_current("#url-display", Static)
        url_input = self._query_current("#url-input", Input)
        open_tabs = self._query_current("#open-request-tabs", Tabs)
        refresh_home_url_bar(self.state, method_select, url_display, url_input, open_tabs)

    def _refresh_home_request_panel(self) -> None:
        if not self._has_live_screen():
            self._refresh_screen()
            return
        request_panel = self._query_current("#request-panel")
        request_title = self._query_current("#request-title", Static)
        request_subtitle = self._query_current("#request-subtitle", Static)
        request_tabs = self._query_current("#request-tabs", TabbedContent)
        refresh_home_request_content(
            self.state,
            request_tabs,
            request_panel,
            request_title,
            request_subtitle,
        )

    def _refresh_home_response_panel(self) -> None:
        if not self._has_live_screen():
            self._refresh_viewport()
            return
        response_note = self._query_current("#response-note", Static)
        response_summary = self._query_current("#response-summary", Static)
        response_panel = self._query_current("#response-panel")
        response_title = self._query_current("#response-title", Static)
        response_subtitle = self._query_current("#response-subtitle", Static)
        response_tabs = self._query_current("#response-tabs", Tabs)
        response_content = self._query_current("#response-content", ContentSwitcher)
        response_body_content = self._query_current("#response-body-content", Static)
        response_content_height = response_content.size.height or response_body_content.size.height or None
        response_width = response_content.size.width or response_body_content.size.width or self._query_current("#home-main").size.width
        refresh_home_response(
            self.state,
            response_note,
            response_summary,
            response_tabs,
            response_content,
            response_panel,
            response_title,
            response_subtitle,
            response_content_height,
            response_width,
        )

    def _refresh_jump_state(self) -> None:
        if not self._has_live_screen():
            self._refresh_screen()
            return
        self.overlay_controller.refresh()
        self._refresh_viewport()
        self._refresh_status_line()
        self._refresh_command_line()

    def _refresh_env_screen(self) -> None:
        try:
            env_input = self._query_current("#env-field-input", Input)
        except Exception:
            env_input = None
        env_render.refresh_env_widgets(
            self.state,
            self._query_current("#env-select", Select),
            self._query_current("#env-table", DataTable),
            env_input,
        )

    def _refresh_history_screen(self) -> None:
        history_render.refresh_history_widgets(
            self.state,
            self._query_current("#history-list", DataTable),
            self._query_current("#history-detail", Static),
        )

    def _refresh_overlay_editors(self) -> None:
        self.overlay_controller.refresh()

    def _refresh_status_line(self) -> None:
        footer = self._query_current("#status-line", PiespectorFooter)
        footer.set_status_content(status_bar_content(self.state))

    def _refresh_command_line(self) -> None:
        command_prompt = self._query_current("#command-prompt", Static)
        command_content = self._query_current("#command-line-content", Static)
        command_input = self._query_current("#command-input", Input)

        if self.state.mode == MODE_COMMAND:
            command_prompt.display = True
            command_content.display = False
            command_input.display = True
            self._sync_command_input(command_input)
            return

        command_prompt.display = False
        command_input.display = False
        command_input._piespector_focus_token = None
        if command_input.value:
            command_input.value = ""
        command_content.display = True
        command_content.update(build_command_line_text(self.state))

    def _sync_command_input(self, command_input: Input) -> None:
        suggestions = self._command_suggestions()
        command_input.suggester = SuggestFromList(suggestions, case_sensitive=False)

        focus_token = (
            self.state.current_tab,
            self.state.command_context_mode,
        )
        if getattr(command_input, "_piespector_focus_token", None) == focus_token:
            return

        command_input._piespector_focus_token = focus_token
        command_input.value = ""
        command_input.focus()

    def _command_input_widget(self) -> Input | None:
        try:
            return self._query_current("#command-input", Input)
        except Exception:
            return None

    def _command_suggestions(self) -> list[str]:
        return help_commands(
            self.state,
            self.state.current_tab,
            command_context_mode(self.state),
        )

    def _env_visible_rows(self) -> int:
        try:
            env_table = self._query_current("#env-table", DataTable)
            return max(env_table.size.height - 2, 1)
        except Exception:
            return 20

    def _history_visible_rows(self) -> int:
        try:
            history_list = self._query_current("#history-list", DataTable)
            return max(history_list.size.height - 2, 6)
        except Exception:
            return 14

    def _home_request_list_visible_rows(self) -> int:
        try:
            tree = self._query_current("#sidebar-tree", Tree)
            return max(tree.size.height - 2, 6)
        except Exception:
            return 14

    def _home_response_visible_rows(self) -> int:
        try:
            response_content = self._query_current("#response-body-content", Static)
            return max(response_content.size.height, 1)
        except Exception:
            return 8

    def _home_response_scroll_step(self) -> int:
        return max(self._home_response_visible_rows() // 2, 1)

    def _history_detail_scroll_step(self) -> int:
        try:
            history_detail = self._query_current("#history-detail", Static)
            return max(history_detail.size.height // 4, 1)
        except Exception:
            return 4

    def _persist_env_pairs(self) -> None:
        self.persistence_manager.persist_env_workspace()

    def _persist_requests(self) -> None:
        self.persistence_manager.persist_request_workspace()

    def _persist_history_entries(self) -> None:
        self.persistence_manager.persist_history_entries()

    def _append_history_entry(self, entry) -> None:
        self.persistence_manager.append_history_entry(entry)

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

    def _reset_edit_path_completion(self) -> None:
        self._edit_path_completion_anchor = ""
        self._edit_path_completion_index = -1

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input" or self.state.mode != MODE_COMMAND:
            return
        event.stop()
        self.interaction_controller.run_command(event.value)

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
