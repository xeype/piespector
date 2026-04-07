from __future__ import annotations

from textual import events

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
)
from piespector.domain.modes import MODE_HOME_SECTION_SELECT, MODE_NORMAL
from piespector.interactions.keys import (
    DOWN_KEYS,
    KEY_CLOSE,
    KEY_EDIT,
    KEY_ESCAPE,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_SEND,
    OPEN_KEYS,
    TAB_NEXT_KEYS,
    TAB_PREVIOUS_KEYS,
    UP_KEYS,
)
from piespector.screens.home import messages
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler


class HomeNavigationController(HomeControllerBase):
    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {
            MODE_HOME_SECTION_SELECT: self.handle_home_section_select_key,
        }

    def browse_sidebar(self, step: int) -> None:
        tree = self.sidebar_tree()
        if tree is None:
            self.state.select_request(step)
            self.app._refresh_home_sidebar_panel()
            return
        if not tree.has_focus:
            tree.focus()
        if step < 0:
            tree.action_cursor_up()
        elif step > 0:
            tree.action_cursor_down()

    def cycle_open_request(self, step: int) -> None:
        self.state.cycle_open_request(step)
        self.app._refresh_viewport()

    def jump_folder(self, step: int) -> None:
        if self.state.select_folder(step):
            self.app._refresh_viewport()
            self.app._sync_home_sidebar_cursor()

    def jump_collection(self, step: int) -> None:
        if self.state.select_collection(step):
            self.app._refresh_viewport()
            self.app._sync_home_sidebar_cursor()

    def handle_home_view_key(self, event: events.Key) -> bool:
        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()
            return True

        if event.key == KEY_CLOSE:
            closed = self.state.close_active_request()
            if closed is None:
                self.state.message = "No opened request selected."
                self.app._refresh_screen()
            else:
                self.app._refresh_viewport()
            event.stop()
            return True

        if event.key == KEY_ESCAPE:
            tree = self.sidebar_tree()
            if tree is None:
                if self.state.collapse_selected_context():
                    self.app._refresh_home_sidebar_panel()
                    event.stop()
                    return True
            else:
                if not tree.has_focus:
                    tree.focus()
                cursor_node = tree.cursor_node
                if cursor_node is None:
                    return False
                if cursor_node.allow_expand and cursor_node.is_expanded:
                    tree.action_toggle_node()
                    event.stop()
                    return True
                parent = cursor_node.parent
                if (
                    parent is not None
                    and not parent.is_root
                    and parent.allow_expand
                    and parent.is_expanded
                ):
                    tree.action_cursor_parent()
                    tree.action_toggle_node()
                    event.stop()
                    return True
            return False

        if event.key == KEY_PAGE_DOWN:
            tree = self.sidebar_tree()
            if tree is None:
                visible_rows = self.app._home_request_list_visible_rows()
                self.state.scroll_request_window(visible_rows, visible_rows)
                self.app._refresh_home_sidebar_panel()
            else:
                if not tree.has_focus:
                    tree.focus()
                tree.action_page_down()
            event.stop()
            return True

        if event.key == KEY_PAGE_UP:
            tree = self.sidebar_tree()
            if tree is None:
                visible_rows = self.app._home_request_list_visible_rows()
                self.state.scroll_request_window(-visible_rows, visible_rows)
                self.app._refresh_home_sidebar_panel()
            else:
                if not tree.has_focus:
                    tree.focus()
                tree.action_page_up()
            event.stop()
            return True

        if event.key == KEY_EDIT:
            tree = self.sidebar_tree()
            if tree is None:
                selected_request = self.state.get_selected_request()
                if selected_request is not None:
                    self.state.open_selected_request(pin=True)
                    self.app._refresh_viewport()
                    event.stop()
                    return True
                if self.state.toggle_selected_sidebar_node():
                    self.app._refresh_home_sidebar_panel()
                    event.stop()
                    return True
                self.state.message = messages.HOME_SELECT_REQUEST_FIRST
                self.app._refresh_screen()
            else:
                if not tree.has_focus:
                    tree.focus()
                    tree.action_confirm()
                # if tree already has focus, widget binding (e → confirm) handles it
            event.stop()
            return True

        return False

    def enter_current_home_value_select_mode(self) -> None:
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request(pin=True)
        if self.state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
            self.state.enter_home_params_select_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
            self.state.enter_home_headers_select_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
            self.state.enter_home_auth_select_mode()
        elif self.state.home_editor_tab == HOME_EDITOR_TAB_BODY:
            self.state.enter_home_body_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)
        else:
            self.state.enter_home_request_select_mode()

    def handle_home_section_select_key(self, event: events.Key) -> None:
        if event.key == KEY_ESCAPE:
            self.state.mode = MODE_NORMAL
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS or event.key in DOWN_KEYS:
            self.enter_current_home_value_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in TAB_PREVIOUS_KEYS:
            self.state.cycle_home_editor_tab(-1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in TAB_NEXT_KEYS:
            self.state.cycle_home_editor_tab(1)
            self.app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            self.enter_current_home_value_select_mode()
            self.app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            self.app._send_selected_request()
            event.stop()
