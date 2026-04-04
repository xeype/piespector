from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher, DataTable, Input, Select, Static, Tab, TabbedContent, TabPane, Tabs, Tree

from piespector.domain.editor import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_TYPE_OPTIONS,
    BODY_KEY_VALUE_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    RAW_SUBTYPE_OPTIONS,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
)
from piespector.domain.http import HTTP_METHODS
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_URL_EDIT,
)
from piespector.commands import filesystem_path_completions
from piespector.placeholders import apply_placeholder_completion
from piespector.screens.home import messages
from piespector.screens.base import PiespectorScreen
from piespector.screens.home.request.header_editor import RequestHeadersTable
from piespector.screens.home.request.query_editor import RequestParamsTable
from piespector.screens.home.request.request_body import RequestBodyTable
from piespector.ui.input import PiespectorInput
from piespector.ui.select import PiespectorSelect


class SidebarTree(Tree, inherit_bindings=False):
    BINDINGS = []


class HomeScreen(PiespectorScreen):
    @staticmethod
    def _response_content_id(tab_id: str) -> str:
        if tab_id == RESPONSE_TAB_HEADERS:
            return "response-headers-content"
        return "response-body-content"

    def compose_workspace(self) -> ComposeResult:
        with Vertical(id="home-screen"):
            with Vertical(id="url-bar-container"):
                yield Tabs(id="open-request-tabs")
                yield Static("", classes="panel-subtitle", id="url-bar-subtitle")
                with Horizontal(id="url-line"):
                    yield PiespectorSelect(
                        [(method, method) for method in HTTP_METHODS],
                        id="method-select",
                        allow_blank=False,
                        value="GET",
                        compact=True,
                    )
                    yield Static("", id="url-display")
                    yield PiespectorInput(
                        "",
                        id="url-input",
                        compact=True,
                        select_on_focus=False,
                    )
            with Horizontal(id="home-workspace"):
                with Vertical(id="sidebar-container"):
                    yield Static("Collections", classes="panel-title", id="sidebar-title")
                    yield SidebarTree("Collections", id="sidebar-tree")
                    yield Static("", classes="panel-subtitle", id="sidebar-subtitle")
                with Vertical(id="home-main"):
                    with Vertical(id="request-panel"):
                        yield Static("Request", classes="panel-title", id="request-title")
                        with TabbedContent(id="request-tabs", initial=HOME_EDITOR_TAB_REQUEST):
                            with TabPane("Request", id=HOME_EDITOR_TAB_REQUEST):
                                yield Static("", id="request-overview-content")
                                yield PiespectorInput(
                                    "",
                                    id="request-overview-input",
                                    compact=True,
                                    select_on_focus=False,
                                )
                            with TabPane("Auth", id=HOME_EDITOR_TAB_AUTH):
                                yield PiespectorSelect(
                                    [(label, value) for value, label in AUTH_TYPE_OPTIONS],
                                    id="auth-type-select",
                                    allow_blank=False,
                                    value=AUTH_TYPE_OPTIONS[0][0],
                                    compact=True,
                                )
                                yield Static("", id="auth-option-label")
                                yield PiespectorSelect(
                                    [(label, value) for value, label in AUTH_API_KEY_LOCATION_OPTIONS],
                                    id="auth-option-select",
                                    allow_blank=False,
                                    value=AUTH_API_KEY_LOCATION_OPTIONS[0][0],
                                    compact=True,
                                )
                                yield Static("", id="request-auth-content")
                                yield PiespectorInput(
                                    "",
                                    id="auth-field-input",
                                    compact=True,
                                    select_on_focus=False,
                                )
                            with TabPane("Params", id=HOME_EDITOR_TAB_PARAMS):
                                yield RequestParamsTable(
                                    id="request-params-table",
                                    cursor_type="row",
                                    zebra_stripes=True,
                                )
                                yield PiespectorInput(
                                    "",
                                    id="request-params-input",
                                    compact=True,
                                    select_on_focus=False,
                                )
                            with TabPane("Headers", id=HOME_EDITOR_TAB_HEADERS):
                                yield Static("", id="request-content-note")
                                yield RequestHeadersTable(
                                    id="request-headers-table",
                                    cursor_type="row",
                                    zebra_stripes=True,
                                )
                                yield PiespectorInput(
                                    "",
                                    id="request-headers-input",
                                    compact=True,
                                    select_on_focus=False,
                                )
                            with TabPane("Body", id=HOME_EDITOR_TAB_BODY):
                                yield PiespectorSelect(
                                    [(label, value) for value, label in BODY_TYPE_OPTIONS],
                                    id="body-type-select",
                                    allow_blank=False,
                                    value=BODY_TYPE_OPTIONS[0][0],
                                    compact=True,
                                )
                                yield PiespectorSelect(
                                    [(label, value) for value, label in RAW_SUBTYPE_OPTIONS],
                                    id="body-raw-type-select",
                                    allow_blank=False,
                                    value=RAW_SUBTYPE_OPTIONS[1][0],
                                    compact=True,
                                )
                                yield RequestBodyTable(
                                    id="request-body-table",
                                    cursor_type="row",
                                    zebra_stripes=True,
                                )
                                yield PiespectorInput(
                                    "",
                                    id="request-body-input",
                                    compact=True,
                                    select_on_focus=False,
                                )
                                yield Static("", id="request-body-preview")
                            with TabPane("Options", id=HOME_EDITOR_TAB_OPTIONS):
                                yield Static("", id="request-options-content")
                        yield Static("", classes="panel-subtitle", id="request-subtitle")
                    with Vertical(id="response-panel"):
                        yield Static("Response", classes="panel-title", id="response-title")
                        yield Static("", id="response-note")
                        with Horizontal(id="response-header-row"):
                            yield Tabs(
                                Tab("Body", id=RESPONSE_TAB_BODY),
                                Tab("Headers", id=RESPONSE_TAB_HEADERS),
                                id="response-tabs",
                                active=RESPONSE_TAB_BODY,
                            )
                            yield Static("", id="response-summary")
                        with ContentSwitcher(id="response-content", initial=RESPONSE_TAB_BODY):
                            yield Static("", id="response-body-content")
                            yield Static("", id="response-headers-content")
                        yield Static("", classes="panel-subtitle", id="response-subtitle")

    def on_mount(self) -> None:
        super().on_mount()
        self._tab_activation_ready = False
        tree = self.query_one("#sidebar-tree", Tree)
        tree.show_root = False
        tree.focus()
        self.disable_focus("open-request-tabs")
        for widget_id in (
            "request-content-note",
            "auth-option-label",
            "auth-option-select",
            "auth-field-input",
            "body-raw-type-select",
            "request-body-table",
            "request-body-input",
            "request-body-preview",
            "url-bar-subtitle",
            "url-input",
            "request-overview-input",
            "request-params-input",
            "request-headers-input",
            "response-note",
        ):
            self.query_one(f"#{widget_id}").display = False
        request_tabs = self.query_one("#request-tabs", TabbedContent)
        response_tabs = self.query_one("#response-tabs", Tabs)
        response_content = self.query_one("#response-content", ContentSwitcher)
        request_tabs.active = self.app.state.home_editor_tab
        response_tabs.active = self.app.state.selected_home_response_tab
        response_content.current = self._response_content_id(self.app.state.selected_home_response_tab)
        for select_id in (
            "method-select",
            "auth-type-select",
            "auth-option-select",
            "body-type-select",
            "body-raw-type-select",
        ):
            select = self.query_one(f"#{select_id}", Select)
            select._piespector_ignored_change_value = select.value
        self._tab_activation_ready = True
        self.query_one("#sidebar-container").border_title = "Collections"
        self.query_one("#request-panel").border_title = "Request"
        self.query_one("#response-panel").border_title = "Response"

    def _sync_sidebar_selection(self, node: Tree.NodeHighlighted | Tree.NodeSelected | Tree.NodeExpanded | Tree.NodeCollapsed) -> bool:
        app = self.app
        if app is None or node.control.id != "sidebar-tree":
            return False
        index = node.node.data
        if not isinstance(index, int):
            return False
        if getattr(node.control, "_piespector_ignore_highlight_index", None) == index:
            node.control._piespector_ignore_highlight_index = None
            return False
        app.state.sync_sidebar_selection(index)
        return True

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if self._sync_sidebar_selection(event):
            self.app._refresh_screen()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if not self._sync_sidebar_selection(event):
            return
        if self.app.state.get_selected_request() is None:
            return
        self.app.state.open_selected_request(pin=True)
        self.app._refresh_screen()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        if not self._sync_sidebar_selection(event):
            return
        self.app.state.set_selected_sidebar_node_expanded(True)
        self.app._refresh_screen()

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        if not self._sync_sidebar_selection(event):
            return
        self.app.state.set_selected_sidebar_node_expanded(False)
        self.app._refresh_screen()

    def _sync_request_table_row(self, table: DataTable, cursor_row: int) -> bool:
        app = self.app
        if app is None or cursor_row < 0:
            return False

        if table.id == "request-params-table":
            if app.state.selected_param_index == cursor_row:
                return False
            app.state.selected_param_index = cursor_row
            return True

        if table.id == "request-headers-table":
            if app.state.selected_header_index == cursor_row:
                return False
            app.state.selected_header_index = cursor_row
            return True

        if table.id == "request-body-table":
            request = app.state.get_active_request()
            if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
                return False
            selected_index = cursor_row + 1
            if app.state.selected_body_index == selected_index:
                return False
            app.state.selected_body_index = selected_index
            return True

        return False

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        app = self.app
        if (
            app is not None
            and event.control.id == "request-body-table"
            and (
                app.state.mode != MODE_HOME_BODY_SELECT
                or app.state.selected_body_index <= 0
            )
        ):
            return
        self._sync_request_table_row(event.control, event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self.app
        if app is None:
            return

        self._sync_request_table_row(event.control, event.cursor_row)

        if event.control.id == "request-params-table":
            request = app.state.get_active_request()
            params = request.query_items if request is not None else []
            if event.cursor_row >= len(params):
                app.state.enter_home_params_edit_mode(creating=True)
            else:
                app.state.enter_home_params_edit_mode()
        elif event.control.id == "request-headers-table":
            request = app.state.get_active_request()
            if request is None:
                return
            from piespector.request_builder import preview_auto_headers
            auto_headers = preview_auto_headers(request, app.state.env_pairs)
            total = len(request.header_items) + len(auto_headers)
            if event.cursor_row >= total:
                app.state.enter_home_headers_edit_mode(creating=True)
            elif app.state.selected_header_index >= len(request.header_items):
                app.state.message = messages.HOME_AUTO_HEADER_EDIT
            else:
                app.state.enter_home_headers_edit_mode()
        elif event.control.id == "request-body-table":
            request = app.state.get_active_request()
            if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
                return
            app.state.enter_home_body_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
        else:
            return

        app._refresh_screen()

    def on_select_changed(self, event: Select.Changed) -> None:
        app = self.app
        if app is None or getattr(event.select, "_piespector_syncing", False):
            return
        if getattr(event.select, "_piespector_suppress_changes", False):
            return

        value = event.value
        if value == Select.NULL:
            return
        ignored_value = getattr(event.select, "_piespector_ignored_change_value", None)
        if ignored_value == value:
            event.select._piespector_ignored_change_value = None
            return

        if event.select.id == "method-select" and app.state.mode == MODE_HOME_REQUEST_METHOD_EDIT:
            app.state.save_home_method_selection(str(value))
        elif event.select.id == "auth-type-select" and app.state.mode == MODE_HOME_AUTH_TYPE_EDIT:
            app.state.save_home_auth_type_selection(str(value))
        elif event.select.id == "auth-option-select" and app.state.mode == MODE_HOME_AUTH_LOCATION_EDIT:
            app.state.save_home_auth_option_selection(str(value))
        elif event.select.id == "body-type-select" and app.state.mode == MODE_HOME_BODY_TYPE_EDIT:
            app.state.save_home_body_type_selection(str(value))
        elif event.select.id == "body-raw-type-select" and app.state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
            app.state.save_home_body_raw_type_selection(str(value))
        else:
            return

        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        app = self.app
        if app is None or not getattr(self, "_tab_activation_ready", False):
            return

        tab_id = event.control.active
        if not tab_id:
            return

        if event.control.id == "request-tabs":
            if tab_id == app.state.home_editor_tab:
                return
            app.state.set_home_editor_tab(tab_id)
            app._refresh_screen()
            return

        if event.control.id == "response-tabs":
            if tab_id == app.state.selected_home_response_tab:
                return
            app.state.selected_home_response_tab = tab_id
            app.state.response_scroll_offset = 0
            app._refresh_screen()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        app = self.app
        if app is None or not getattr(self, "_tab_activation_ready", False):
            return
        if event.control.id != "response-tabs":
            return

        tab_id = event.tab.id
        if not tab_id or tab_id == app.state.selected_home_response_tab:
            return

        app.state.selected_home_response_tab = tab_id
        app.state.response_scroll_offset = 0
        app._refresh_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app = self.app
        if app is None:
            return

        if event.input.id == "url-input" and app.state.mode == MODE_HOME_URL_EDIT:
            app.state.save_home_url_edit(event.value)
        elif (
            event.input.id == "request-overview-input"
            and app.state.mode == MODE_HOME_REQUEST_EDIT
        ):
            app.state.save_selected_request_field(event.value)
        elif (
            event.input.id == "request-params-input"
            and app.state.mode == MODE_HOME_PARAMS_EDIT
        ):
            app.state.save_selected_param_field(event.value)
        elif (
            event.input.id == "request-headers-input"
            and app.state.mode == MODE_HOME_HEADERS_EDIT
        ):
            app.state.save_selected_header_field(event.value)
        elif (
            event.input.id == "auth-field-input"
            and app.state.mode == MODE_HOME_AUTH_EDIT
        ):
            app.state.save_selected_auth_field(event.value)
        elif (
            event.input.id == "request-body-input"
            and app.state.mode == MODE_HOME_BODY_EDIT
        ):
            app.state.save_body_selection(event.value)
        else:
            return

        app.set_focus(None)
        app._refresh_screen()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if app is None or event.key != "tab":
            return

        focused = app.focused
        if not isinstance(focused, Input):
            return
        if focused.id not in {
            "url-input",
            "request-overview-input",
            "request-params-input",
            "request-headers-input",
            "request-body-input",
        }:
            return

        if focused.id == "request-body-input" and app.state.mode == MODE_HOME_BODY_EDIT:
            current = focused.value
            anchor = app._edit_path_completion_anchor or current
            matches = filesystem_path_completions(anchor)
            if matches:
                if app._edit_path_completion_anchor != anchor:
                    app._edit_path_completion_anchor = anchor
                    app._edit_path_completion_index = 0
                else:
                    app._edit_path_completion_index = (
                        app._edit_path_completion_index + 1
                    ) % len(matches)
                completed = matches[app._edit_path_completion_index]
                focused.value = completed
                focused.cursor_position = len(completed)
            event.stop()
            return

        if focused.id == "url-input" and app.state.mode == MODE_HOME_URL_EDIT:
            completed = apply_placeholder_completion(
                focused.value,
                focused.cursor_position,
                sorted(app.state.env_pairs),
            )
            if completed is not None:
                value, cursor_position = completed
                focused.value = value
                focused.cursor_position = cursor_position

        event.stop()
