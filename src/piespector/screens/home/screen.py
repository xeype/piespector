from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Static, TabbedContent, TabPane

from piespector.domain.editor import (
    BODY_KEY_VALUE_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    RAW_SUBTYPE_OPTIONS,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
)
from piespector.commands import filesystem_path_completions
from piespector.placeholders import placeholder_match
from piespector.screens.home import messages
from piespector.screens.home.collections_sidebar import CollectionsSidebar
from piespector.screens.home.response_panel import ResponsePanel
from piespector.screens.home.url_bar import UrlBar
from piespector.screens.home.request.auth_pane import RequestAuthPane
from piespector.screens.home.request.params_pane import RequestParamsPane
from piespector.screens.base import PiespectorScreen
from piespector.screens.home.request.overview_pane import RequestOverviewPane
from piespector.screens.home.request.header_editor import RequestHeadersTable
from piespector.screens.home.request.request_body import RequestBodyTable
from piespector.ui.body_editor_modal import BodyEditorModal
from piespector.ui.input import PiespectorInput
from piespector.widget.select import PiespectorSelect, SelectionChanged, option_list


class HomeScreen(PiespectorScreen):
    def compose_workspace(self) -> ComposeResult:
        with Vertical(id="home-screen"):
            yield UrlBar(id="url-bar-container")
            with Horizontal(id="home-workspace"):
                yield CollectionsSidebar(id="sidebar-container")
                with Vertical(id="home-main"):
                    with Vertical(id="request-panel"):
                        yield Static("Request", classes="panel-title", id="request-title")
                        with TabbedContent(id="request-tabs", initial=HOME_EDITOR_TAB_REQUEST):
                            with TabPane("Request", id=HOME_EDITOR_TAB_REQUEST):
                                yield RequestOverviewPane(id="request-overview-pane")
                            with TabPane("Auth", id=HOME_EDITOR_TAB_AUTH):
                                yield RequestAuthPane(id="request-auth-pane")
                            with TabPane("Params", id=HOME_EDITOR_TAB_PARAMS):
                                yield RequestParamsPane(id="request-params-pane")
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
                                    option_list(*BODY_TYPE_OPTIONS),
                                    id="body-type-select",
                                    allow_blank=False,
                                    value=BODY_TYPE_OPTIONS[0][0],
                                    compact=True,
                                )
                                yield PiespectorSelect(
                                    option_list(*RAW_SUBTYPE_OPTIONS),
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
                    yield ResponsePanel(id="response-panel")
        yield Static("", id="headers-input-hint", classes="hidden")

    def on_mount(self) -> None:
        super().on_mount()
        self._tab_activation_ready = False
        for widget_id in (
            "request-content-note",
            "body-raw-type-select",
            "request-body-table",
            "request-body-input",
            "request-body-preview",
            "request-headers-input",
        ):
            self.query_one(f"#{widget_id}").display = False
        request_tabs = self.query_one("#request-tabs", TabbedContent)
        request_tabs.active = self.app.state.home_editor_tab
        self._tab_activation_ready = True
        self.query_one("#sidebar-container").border_title = "Collections"
        self.query_one("#request-panel").border_title = "Request"

    def open_body_text_editor(self, origin_mode: str | None = None) -> None:
        app = self.app
        if app is None:
            return
        if not app.state.prepare_home_body_text_editor(origin_mode=origin_mode):
            app._refresh_screen()
            return
        app._refresh_screen()
        if app.screen.is_modal and isinstance(app.screen, BodyEditorModal):
            return
        request = app.state.get_active_request()
        if request is None:
            return
        app.push_screen(
            BodyEditorModal(request),
            self._handle_body_text_editor_closed,
        )

    def _handle_body_text_editor_closed(self, _result: None) -> None:
        app = self.app
        if app is None:
            return
        app.set_focus(None)
        app._refresh_screen()
        app.call_after_refresh(app._clear_home_jump_focus)

    @on(CollectionsSidebar.SelectionChanged)
    def _on_sidebar_selection_changed(self, event: CollectionsSidebar.SelectionChanged) -> None:
        app = self.app
        if app is None:
            return
        app.state.sync_sidebar_selection(event.index)
        app._refresh_screen()

    @on(CollectionsSidebar.RequestOpened)
    def _on_sidebar_request_opened(self, event: CollectionsSidebar.RequestOpened) -> None:
        app = self.app
        if app is None:
            return
        app.state.sync_sidebar_selection(event.index)
        if app.state.get_selected_request() is None:
            return
        app.state.open_selected_request(pin=True)
        app._refresh_screen()

    @on(CollectionsSidebar.ExpansionChanged)
    def _on_sidebar_expansion_changed(self, event: CollectionsSidebar.ExpansionChanged) -> None:
        app = self.app
        if app is None:
            return
        app.state.sync_sidebar_selection(event.index)
        app.state.set_selected_sidebar_node_expanded(event.expanded)
        app._refresh_screen()

    def _sync_request_table_row(self, table: DataTable, cursor_row: int) -> bool:
        app = self.app
        if app is None or cursor_row < 0:
            return False

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

        if event.control.id == "request-headers-table":
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

    @on(UrlBar.OpenRequestActivated)
    def _on_open_request_activated(self, event: UrlBar.OpenRequestActivated) -> None:
        app = self.app
        if app is None or app.state.active_request_id == event.request_id:
            return
        app.state.active_request_id = event.request_id
        app.state.response_scroll_offset = 0
        app.state.sync_selected_request_to_active()
        app._refresh_screen()

    @on(UrlBar.MethodChanged)
    def _on_method_changed(self, event: UrlBar.MethodChanged) -> None:
        app = self.app
        if app is None:
            return
        app.state.save_home_method_selection(event.method)
        app.set_focus(None)
        app._refresh_screen()

    @on(UrlBar.UrlSaved)
    def _on_url_saved(self, event: UrlBar.UrlSaved) -> None:
        app = self.app
        if app is None:
            return
        app.state.save_home_url_edit(event.value)
        app.set_focus(None)
        app._refresh_screen()

    @on(SelectionChanged, "#body-type-select")
    def _on_body_type_selected(self, event: SelectionChanged) -> None:
        if self.app.state.mode != MODE_HOME_BODY_TYPE_EDIT:
            return
        self.app.state.save_home_body_type_selection(event.value)
        self.app.set_focus(None)
        self.app._refresh_screen()

    @on(SelectionChanged, "#body-raw-type-select")
    def _on_body_raw_type_selected(self, event: SelectionChanged) -> None:
        if self.app.state.mode != MODE_HOME_BODY_RAW_TYPE_EDIT:
            return
        self.app.state.save_home_body_raw_type_selection(event.value)
        self.app.set_focus(None)
        self.app._refresh_screen()

    @on(RequestOverviewPane.FieldSaved)
    def _on_request_overview_field_saved(
        self,
        event: RequestOverviewPane.FieldSaved,
    ) -> None:
        app = self.app
        if app is None:
            return

        app.state.save_selected_request_field(event.value)
        app.set_focus(None)
        app._refresh_screen()

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

    @on(ResponsePanel.TabChanged)
    def _on_response_tab_changed(self, event: ResponsePanel.TabChanged) -> None:
        app = self.app
        if app is None or event.tab_id == app.state.selected_home_response_tab:
            return

        app.state.selected_home_response_tab = event.tab_id
        app.state.response_scroll_offset = 0
        app._refresh_screen()

    @on(ResponsePanel.ViewerRequested)
    def _on_response_viewer_requested(self, event: ResponsePanel.ViewerRequested) -> None:
        app = self.app
        if app is None:
            return

        app._open_response_viewer(origin_mode=event.origin_mode)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app = self.app
        if app is None:
            return

        if (
            event.input.id == "request-headers-input"
            and app.state.mode == MODE_HOME_HEADERS_EDIT
        ):
            app.state.save_selected_header_field(event.value)
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

    def on_input_changed(self, event: Input.Changed) -> None:
        app = self.app
        if app is None:
            return
        text = event.value
        cursor = event.input.cursor_position
        if event.input.id == "request-headers-input" and app.state.mode == MODE_HOME_HEADERS_EDIT:
            if cursor >= 2 and text[cursor - 2 : cursor] == "{{" and text[cursor : cursor + 2] != "}}":
                event.input.value = text[:cursor] + "}}" + text[cursor:]
                event.input.cursor_position = cursor
            app.call_after_refresh(app._refresh_request_input_hints_only)

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if app is None:
            return

        if (
            event.key == "tab"
            and app.state.home_editor_tab == HOME_EDITOR_TAB_AUTH
            and app.state.mode == MODE_HOME_AUTH_EDIT
        ):
            auth_pane = self.query_one("#request-auth-pane", RequestAuthPane)
            if auth_pane.handle_input_key(event):
                return

        params_pane = self.query_one("#request-params-pane", RequestParamsPane)
        if params_pane.handle_input_key(event):
            return

        focused = app.focused
        if not isinstance(focused, Input):
            return
        if focused.id not in {
            "request-overview-input",
            "request-headers-input",
            "request-body-input",
        }:
            return

        if event.key == "tab":
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

            input_mode_map = {
                "request-headers-input": MODE_HOME_HEADERS_EDIT,
            }
            if focused.id in input_mode_map and app.state.mode == input_mode_map[focused.id]:
                env_keys = sorted(app.state.env_pairs)
                match = placeholder_match(focused.value, focused.cursor_position, env_keys)
                if match is not None:
                    anchor = app._input_env_completion_anchor
                    stored = app._input_env_completion_matches
                    if anchor and match.prefix in stored:
                        matches = stored
                        new_idx = (app._input_env_completion_index + 1) % len(matches)
                    else:
                        anchor = match.prefix
                        matches = [k for k in env_keys if k.startswith(anchor)]
                        new_idx = 0
                    if matches:
                        app._input_env_completion_anchor = anchor
                        app._input_env_completion_matches = matches
                        app._input_env_completion_index = new_idx
                        suggestion = matches[new_idx]
                        before = focused.value[: match.start]
                        after = focused.value[match.end :]
                        completed = f"{before}{{{{{suggestion}}}}}{after}"
                        new_cursor = len(before) + 2 + len(suggestion)
                        focused.value = completed
                        focused.cursor_position = new_cursor
                        app.call_after_refresh(app._refresh_request_input_hints_only)
            event.stop()
            return
