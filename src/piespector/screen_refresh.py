from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ScreenStackError
from textual.widgets import (
    ContentSwitcher,
    DataTable,
    Input,
    Select,
    Static,
    TabbedContent,
    Tabs,
    Tree,
)

from piespector.domain.editor import (
    HOME_SIDEBAR_LABEL,
    TAB_ENV,
    TAB_HISTORY,
    TAB_HOME,
    TAB_ORDER,
)
from piespector.domain.modes import MODE_COMMAND
from piespector.screens.base import PiespectorScreen
from piespector.screens.env import render as env_render
from piespector.screens.history import render as history_render
from piespector.screens.home.layout import home_top_bar_height
from piespector.screens.home.render import (
    refresh_home_request_content,
    refresh_home_response,
    refresh_home_sidebar,
    refresh_home_url_bar,
    sync_home_focus_highlights,
)
from piespector.ui.command_line_content import build_command_line_text
from piespector.ui.footer import PiespectorFooter
from piespector.ui.status_content import status_bar_content

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class ScreenRefreshCoordinator:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def install_bindings(self) -> None:
        bindings = {
            "_current_base_screen": self.current_base_screen,
            "_env_visible_rows": self.env_visible_rows,
            "_has_live_screen": self.has_live_screen,
            "_history_detail_scroll_step": self.history_detail_scroll_step,
            "_history_visible_rows": self.history_visible_rows,
            "_home_request_list_visible_rows": self.home_request_list_visible_rows,
            "_home_response_scroll_step": self.home_response_scroll_step,
            "_home_response_visible_rows": self.home_response_visible_rows,
            "_query_current": self.query_current,
            "_refresh_command_line": self.refresh_command_line,
            "_refresh_env_screen": self.refresh_env_screen,
            "_refresh_history_screen": self.refresh_history_screen,
            "_refresh_home_jump_cues": self.refresh_home_jump_cues,
            "_refresh_home_request_panel": self.refresh_home_request_panel,
            "_refresh_home_response_panel": self.refresh_home_response_panel,
            "_refresh_home_screen": self.refresh_home_screen,
            "_refresh_home_sidebar_panel": self.refresh_home_sidebar_panel,
            "_refresh_home_url_bar_panel": self.refresh_home_url_bar_panel,
            "_refresh_jump_state": self.refresh_jump_state,
            "_refresh_overlay_editors": self.refresh_overlay_editors,
            "_refresh_screen": self.refresh,
            "_refresh_status_line": self.refresh_status_line,
            "_refresh_viewport": self.refresh_viewport,
            "_screen_for_tab": self.screen_for_tab,
            "_screen_widgets_ready": self.screen_widgets_ready,
            "_switch_screen_visibility": self.switch_screen_visibility,
            "_sync_home_sidebar_cursor": self.sync_home_sidebar_cursor,
        }
        for name, method in bindings.items():
            setattr(self.app, name, method)

    def sync_home_sidebar_cursor(self) -> None:
        if self.state.current_tab != TAB_HOME or not self.app._has_live_screen():
            return
        try:
            tree = self.app._query_current("#sidebar-tree", Tree)
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

    def switch_screen_visibility(self) -> None:
        if not self.app._screens_installed:
            return
        current_screen = self.app._current_base_screen()
        if current_screen is None:
            return
        if self.app.screen.is_modal:
            return

        target_tab = self.state.current_tab if self.state.current_tab in TAB_ORDER else TAB_HOME
        if current_screen is not self.app._screen_for_tab(target_tab):
            self.app.switch_screen(target_tab)

    def screen_for_tab(self, tab_id: str) -> PiespectorScreen:
        if tab_id == TAB_ENV:
            return self.app._env_screen
        if tab_id == TAB_HISTORY:
            return self.app._history_screen
        return self.app._home_screen

    def current_base_screen(self) -> PiespectorScreen | None:
        for screen in reversed(self.app.screen_stack):
            if isinstance(screen, PiespectorScreen):
                return screen
        return None

    def query_current(self, selector, expect_type=None):
        current_screen = self.app._current_base_screen()
        if current_screen is None:
            raise ScreenStackError("No active application screen.")
        return current_screen.query_one(selector, expect_type)

    def refresh(self) -> None:
        if not self.app._screens_installed:
            return
        self.app._switch_screen_visibility()
        if not self.app._screen_widgets_ready():
            self.app.call_after_refresh(self.app._refresh_screen)
            return
        self.app.overlay_controller.refresh()
        self.app._refresh_viewport()
        self.app._refresh_status_line()
        self.app._refresh_command_line()

    def screen_widgets_ready(self) -> bool:
        try:
            self.app._query_current("#workspace")
            self.app._query_current("#status-line")
            self.app._query_current("#command-line")
            self.app._query_current("#command-line-content", Static)
            self.app._query_current("#command-input", Input)
        except Exception:
            return False
        return True

    def refresh_viewport(self) -> None:
        if self.state.current_tab == TAB_HOME:
            self.state.ensure_request_workspace()
            visible_rows = self.app._home_request_list_visible_rows()
            self.state.ensure_request_selection_visible(visible_rows)
            self.app._refresh_home_screen()
        elif self.state.current_tab == TAB_ENV:
            visible_rows = self.app._env_visible_rows()
            self.state.ensure_env_selection_visible(visible_rows)
            self.app._refresh_env_screen()
        elif self.state.current_tab == TAB_HISTORY:
            visible_rows = self.app._history_visible_rows()
            self.state.ensure_history_selection_visible(visible_rows)
            self.app._refresh_history_screen()

    def refresh_home_screen(self) -> None:
        self.app._refresh_home_sidebar_panel()
        self.app._refresh_home_url_bar_panel()
        self.app._refresh_home_request_panel()
        self.app._refresh_home_response_panel()
        self.app._refresh_home_jump_cues()

    def refresh_home_jump_cues(self) -> None:
        if not self.app._has_live_screen():
            return

        url_bar_container = self.app._query_current("#url-bar-container")
        sidebar_container = self.app._query_current("#sidebar-container")
        request_panel = self.app._query_current("#request-panel")
        response_panel = self.app._query_current("#response-panel")
        method_select = self.app._query_current("#method-select", Select)
        url_bar_subtitle = self.app._query_current("#url-bar-subtitle", Static)
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

    def has_live_screen(self) -> bool:
        return self.app._current_base_screen() is not None

    def refresh_home_sidebar_panel(self) -> None:
        if not self.app._has_live_screen():
            self.app._refresh_viewport()
            return
        tree = self.app._query_current("#sidebar-tree", Tree)
        sidebar_subtitle = self.app._query_current("#sidebar-subtitle", Static)
        sidebar_container = self.app._query_current("#sidebar-container")
        sidebar_title = self.app._query_current("#sidebar-title", Static)
        visible_rows = self.app._home_request_list_visible_rows()
        refresh_home_sidebar(
            self.state,
            tree,
            sidebar_subtitle,
            sidebar_container,
            sidebar_title,
            visible_rows,
        )

    def refresh_home_url_bar_panel(self) -> None:
        if not self.app._has_live_screen():
            self.app._refresh_screen()
            return
        method_select = self.app._query_current("#method-select", Select)
        url_display = self.app._query_current("#url-display", Static)
        url_input = self.app._query_current("#url-input", Input)
        open_tabs = self.app._query_current("#open-request-tabs", Tabs)
        refresh_home_url_bar(self.state, method_select, url_display, url_input, open_tabs)

    def refresh_home_request_panel(self) -> None:
        if not self.app._has_live_screen():
            self.app._refresh_screen()
            return
        request_panel = self.app._query_current("#request-panel")
        request_title = self.app._query_current("#request-title", Static)
        request_subtitle = self.app._query_current("#request-subtitle", Static)
        request_tabs = self.app._query_current("#request-tabs", TabbedContent)
        refresh_home_request_content(
            self.state,
            request_tabs,
            request_panel,
            request_title,
            request_subtitle,
        )

    def refresh_home_response_panel(self) -> None:
        if not self.app._has_live_screen():
            self.app._refresh_viewport()
            return
        response_note = self.app._query_current("#response-note", Static)
        response_summary = self.app._query_current("#response-summary", Static)
        response_panel = self.app._query_current("#response-panel")
        response_title = self.app._query_current("#response-title", Static)
        response_subtitle = self.app._query_current("#response-subtitle", Static)
        response_tabs = self.app._query_current("#response-tabs", Tabs)
        response_content = self.app._query_current("#response-content", ContentSwitcher)
        response_body_content = self.app._query_current("#response-body-content", Static)
        response_content_height = (
            response_content.size.height or response_body_content.size.height or None
        )
        response_width = (
            response_content.size.width
            or response_body_content.size.width
            or self.app._query_current("#home-main").size.width
        )
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

    def refresh_jump_state(self) -> None:
        if not self.app._has_live_screen():
            self.app._refresh_screen()
            return
        self.app.overlay_controller.refresh()
        self.app._refresh_viewport()
        self.app._refresh_status_line()
        self.app._refresh_command_line()

    def refresh_env_screen(self) -> None:
        try:
            env_input = self.app._query_current("#env-field-input", Input)
        except Exception:
            env_input = None
        env_render.refresh_env_widgets(
            self.state,
            self.app._query_current("#env-select", Select),
            self.app._query_current("#env-table", DataTable),
            env_input,
        )

    def refresh_history_screen(self) -> None:
        history_render.refresh_history_widgets(
            self.state,
            self.app._query_current("#history-list", DataTable),
            self.app._query_current("#history-detail", Static),
        )

    def refresh_overlay_editors(self) -> None:
        self.app.overlay_controller.refresh()

    def refresh_status_line(self) -> None:
        footer = self.app._query_current("#status-line", PiespectorFooter)
        footer.set_status_content(status_bar_content(self.state))

    def refresh_command_line(self) -> None:
        command_prompt = self.app._query_current("#command-prompt", Static)
        command_content = self.app._query_current("#command-line-content", Static)
        command_input = self.app._query_current("#command-input", Input)

        if self.state.mode == MODE_COMMAND:
            command_prompt.display = True
            command_content.display = False
            command_input.display = True
            self.app._sync_command_input(command_input)
            return

        command_prompt.display = False
        command_input.display = False
        command_input._piespector_focus_token = None
        if command_input.value:
            command_input.value = ""
        command_content.display = True
        command_content.update(build_command_line_text(self.state))

    def env_visible_rows(self) -> int:
        try:
            env_table = self.app._query_current("#env-table", DataTable)
            return max(env_table.size.height - 2, 1)
        except Exception:
            return 20

    def history_visible_rows(self) -> int:
        try:
            history_list = self.app._query_current("#history-list", DataTable)
            return max(history_list.size.height - 2, 6)
        except Exception:
            return 14

    def home_request_list_visible_rows(self) -> int:
        try:
            tree = self.app._query_current("#sidebar-tree", Tree)
            return max(tree.size.height - 2, 6)
        except Exception:
            return 14

    def home_response_visible_rows(self) -> int:
        try:
            response_content = self.app._query_current("#response-body-content", Static)
            return max(response_content.size.height, 1)
        except Exception:
            return 8

    def home_response_scroll_step(self) -> int:
        return max(self.app._home_response_visible_rows() // 2, 1)

    def history_detail_scroll_step(self) -> int:
        try:
            history_detail = self.app._query_current("#history-detail", Static)
            return max(history_detail.size.height // 4, 1)
        except Exception:
            return 4
