from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult, ScreenStackError
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Input, Select, Static, TabbedContent, TabPane, Tabs, Tree

from piespector.commands import CommandOutcome, DeleteConfirmationRequest
from piespector.domain.editor import (
    HOME_SIDEBAR_JUMP_KEY,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    REQUEST_EDITOR_JUMP_BINDINGS,
    RESPONSE_TAB_BODY,
    RESPONSE_JUMP_BINDINGS,
    TAB_HOME,
    TAB_LABELS,
    TOP_BAR_METHOD_JUMP_KEY,
    TOP_BAR_URL_JUMP_KEY,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_NORMAL,
)
from piespector.screens.home import messages
from piespector.screens.home.collections_sidebar import CollectionsSidebar
from piespector.screens.home.layout import home_top_bar_height
from piespector.screens.home.selection import home_highlighted_panels, home_selection
from piespector.screens.home.response_panel import ResponsePanel
from piespector.screens.home.url_bar import UrlBar
from piespector.screens.home.request.auth_pane import RequestAuthPane
from piespector.screens.home.request.body_pane import RequestBodyPane
from piespector.screens.home.request.headers_pane import RequestHeadersPane
from piespector.screens.home.request.options_pane import RequestOptionsPane
from piespector.screens.home.request.params_pane import RequestParamsPane
from piespector.screens.base import PiespectorScreen
from piespector.screens.home.request.overview_pane import RequestOverviewPane
from piespector.ui.body_editor_modal import BodyEditorModal
from piespector.ui.confirm_modal import ConfirmModal
from piespector.ui.jump_overlay import JumpOverlay
from piespector.ui.jumper import JumpTarget, Jumper
from piespector.ui.selection import FOCUS_FRAME_CLASS
from piespector.interactions.keys import (
    KEY_VIM_DOWN,
    KEY_VIM_LEFT,
    KEY_VIM_RIGHT,
    KEY_VIM_UP,
)


class HomeScreen(PiespectorScreen):
    BINDINGS = PiespectorScreen.BINDINGS + [
        Binding(KEY_VIM_UP, "home_browse_up", "Browse Up", show=False),
        Binding(KEY_VIM_DOWN, "home_browse_down", "Browse Down", show=False),
        Binding("K", "home_previous_folder", "Previous Folder", show=False),
        Binding("J", "home_next_folder", "Next Folder", show=False),
        Binding("ctrl+k", "home_previous_collection", "Previous Collection", show=False),
        Binding("ctrl+j", "home_next_collection", "Next Collection", show=False),
        Binding(KEY_VIM_LEFT, "home_previous_open_request", "Previous Pinned Request", show=False),
        Binding(KEY_VIM_RIGHT, "home_next_open_request", "Next Pinned Request", show=False),
    ]

    params_creating_new: reactive[bool] = reactive(False)
    headers_creating_new: reactive[bool] = reactive(False)
    body_creating_new: reactive[bool] = reactive(False)
    request_scroll_offset: reactive[int] = reactive(0)
    response_scroll_offset: reactive[int] = reactive(0)
    selected_home_response_tab: reactive[str] = reactive(RESPONSE_TAB_BODY)
    selected_request_field_index: reactive[int] = reactive(0)
    selected_auth_index: reactive[int] = reactive(0)
    selected_param_index: reactive[int] = reactive(0)
    selected_param_field_index: reactive[int] = reactive(0)
    selected_header_index: reactive[int] = reactive(0)
    selected_header_field_index: reactive[int] = reactive(0)
    selected_body_index: reactive[int] = reactive(0)
    selected_body_field_index: reactive[int] = reactive(0)
    selected_top_bar_field: reactive[str] = reactive("method")
    home_top_bar_return_mode: reactive[str] = reactive(MODE_NORMAL)
    home_top_bar_edit_return_mode: reactive[str] = reactive(MODE_NORMAL)
    home_auth_type_return_mode: reactive[str] = reactive(MODE_HOME_AUTH_SELECT)
    home_body_type_return_mode: reactive[str] = reactive(MODE_HOME_SECTION_SELECT)
    home_body_raw_type_return_mode: reactive[str] = reactive(MODE_HOME_BODY_TYPE_EDIT)
    home_body_content_return_mode: reactive[str] = reactive(MODE_HOME_BODY_SELECT)
    home_body_select_return_mode: reactive[str] = reactive(MODE_HOME_SECTION_SELECT)
    home_response_select_return_mode: reactive[str] = reactive(MODE_NORMAL)
    home_editor_tab: reactive[str] = reactive(HOME_EDITOR_TAB_REQUEST)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
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
            state = self._state
            return state is not None and state.mode == MODE_NORMAL
        return super().check_action(action, parameters)

    def _handle_command_outcome(self, outcome: CommandOutcome) -> None:
        if outcome.confirmation_request is not None:
            self._open_delete_confirmation(outcome.confirmation_request)
            return
        super()._handle_command_outcome(outcome)

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
                                yield RequestHeadersPane(id="request-headers-pane")
                            with TabPane("Body", id=HOME_EDITOR_TAB_BODY):
                                yield RequestBodyPane(id="request-body-pane")
                            with TabPane("Options", id=HOME_EDITOR_TAB_OPTIONS):
                                yield RequestOptionsPane(id="request-options-pane")
                        yield Static("", classes="panel-subtitle", id="request-subtitle")
                    yield ResponsePanel(id="response-panel")

    def on_mount(self) -> None:
        super().on_mount()
        self._tab_activation_ready = False
        request_tabs = self.query_one("#request-tabs", TabbedContent)
        request_tabs.active = self.app.state.home_editor_tab
        self._tab_activation_ready = True
        self.query_one("#sidebar-container").border_title = "Collections"
        self.query_one("#request-panel").border_title = "Request"

    def refresh_from_state(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        app.state.ensure_request_workspace()
        app.state.ensure_request_selection_visible(self.visible_request_rows())
        self.refresh_sidebar()
        self.refresh_url_bar()
        self.refresh_request_panel()
        self.refresh_response_panel()
        self.refresh_jump_cues()

    def refresh_sidebar(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        sidebar = self.query_one("#sidebar-container", CollectionsSidebar)
        sidebar.refresh_from_state(app.state, self.visible_request_rows())

    def refresh_url_bar(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        url_bar = self.query_one("#url-bar-container", UrlBar)
        url_bar.refresh_from_state(app.state)

    def refresh_request_panel(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        state = app.state
        request_subtitle = self.query_one("#request-subtitle", Static)
        request_tabs = self.query_one("#request-tabs", TabbedContent)
        active_request = state.get_active_request()

        if request_tabs.query(f"TabPane#{state.home_editor_tab}"):
            request_tabs.active = state.home_editor_tab

        overview_pane = self.query_one("#request-overview-pane", RequestOverviewPane)
        auth_pane = self.query_one("#request-auth-pane", RequestAuthPane)
        params_pane = self.query_one("#request-params-pane", RequestParamsPane)
        headers_pane = self.query_one("#request-headers-pane", RequestHeadersPane)
        body_pane = self.query_one("#request-body-pane", RequestBodyPane)
        options_pane = self.query_one("#request-options-pane", RequestOptionsPane)

        overview_pane.refresh_from_state(state)
        auth_pane.refresh_from_state(state)
        body_pane.refresh_from_state(state)

        if active_request is None:
            options_pane.refresh_from_state(state)
            params_pane.refresh_from_state(state)
            headers_pane.refresh_from_state(state)
            request_subtitle.update("")
            return

        request_subtitle.update(messages.home_editor_subtitle(state))

        if state.home_editor_tab == HOME_EDITOR_TAB_REQUEST:
            return

        if state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
            return

        if state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
            params_pane.refresh_from_state(state)
            return

        if state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
            headers_pane.refresh_from_state(state)
            return

        if state.home_editor_tab == HOME_EDITOR_TAB_OPTIONS:
            options_pane.refresh_from_state(state)
            return

    def refresh_response_panel(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        response_panel = self.query_one("#response-panel", ResponsePanel)
        response_panel.refresh_from_state(app.state)

    def refresh_jump_cues(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        url_bar_container = self.query_one("#url-bar-container")
        sidebar_container = self.query_one("#sidebar-container")
        request_panel = self.query_one("#request-panel")
        response_panel = self.query_one("#response-panel")
        sidebar_container.styles.border_title_align = "right"
        request_panel.styles.border_title_align = "right"
        response_panel.styles.border_title_align = "right"
        sidebar_container.border_title = "Collections"
        request_panel.border_title = "Request"
        response_panel.border_title = "Response"
        url_bar_container.styles.height = home_top_bar_height()
        selection = home_selection(app.state)
        highlighted_panels = home_highlighted_panels(app.state)
        highlighted_widgets = (
            (url_bar_container, "topbar" in highlighted_panels),
            (sidebar_container, "sidebar" in highlighted_panels),
            (request_panel, "request" in highlighted_panels),
            (response_panel, "response" in highlighted_panels),
        )
        for widget, selected in highlighted_widgets:
            widget.set_class(selected, FOCUS_FRAME_CLASS)

        request_panel.set_class(selection.request_tab_select, "piespector-tab-select")
        response_panel.set_class(selection.panel == "response", "piespector-tab-select")

    def visible_request_rows(self) -> int:
        if not self.is_mounted:
            return 14
        try:
            tree = self.query_one("#sidebar-tree", Tree)
            return max(tree.size.height - 2, 6)
        except NoMatches:
            return 14

    def response_scroll_step(self) -> int:
        if not self.is_mounted:
            return 4
        try:
            response_panel = self.query_one("#response-panel", ResponsePanel)
        except NoMatches:
            return 4
        return response_panel.scroll_step()

    def sync_sidebar_cursor(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return
        try:
            sidebar = self.query_one("#sidebar-container", CollectionsSidebar)
        except NoMatches:
            return
        sidebar.sync_cursor(app.state.selected_sidebar_index)

    def live_select(self, selector: str) -> Select | None:
        if not self.is_mounted:
            return None
        try:
            return self.query_one(selector, Select)
        except NoMatches:
            return None

    def live_input(self, selector: str) -> Input | None:
        if not self.is_mounted:
            return None
        try:
            return self.query_one(selector, Input)
        except NoMatches:
            return None

    def sidebar_tree(self) -> Tree | None:
        if not self.is_mounted:
            return None
        try:
            return self.query_one("#sidebar-tree", Tree)
        except NoMatches:
            return None

    def open_jump_overlay(self) -> bool:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return False
        app._refresh_screen()
        if app.screen.is_modal:
            return False
        app.push_screen(
            self._build_jump_overlay(),
            self._handle_jump_overlay_result,
        )
        return True

    def clear_jump_focus(self) -> None:
        app = self._owner_app()
        if app is None or not self.is_mounted:
            return

        if app.state.mode == MODE_HOME_URL_EDIT:
            url_input = self.live_input("#url-input")
            if url_input is not None and url_input.display:
                app.set_focus(url_input)
                return

        if app.state.current_tab == "home" and home_selection(app.state).panel == "sidebar":
            tree = self.sidebar_tree()
            if tree is not None and tree.can_focus:
                app.set_focus(tree)
                return

        if home_selection(app.state).panel != "sidebar":
            app.set_focus(None)
        for widget_id in (
            "method-select",
            "auth-type-select",
            "auth-option-select",
            "body-type-select",
            "body-raw-type-select",
        ):
            select = self.live_select(f"#{widget_id}")
            if select is not None:
                select.blur()
        for widget_id in ("open-request-tabs", "request-tabs", "response-tabs"):
            try:
                self.query_one(f"#{widget_id}").blur()
            except NoMatches:
                pass

    def _build_jump_overlay(self) -> JumpOverlay:
        app = self._owner_app()
        assert app is not None
        active_request = app.state.get_active_request()
        tree = self.query_one("#sidebar-tree", Tree)
        method_select = self.query_one("#method-select", Select)
        url_display = self.query_one("#url-display", Static)
        url_input = self.query_one("#url-input", Input)
        request_tabs = self.query_one("#request-tabs", TabbedContent)
        response_tabs = self.query_one("#response-tabs", Tabs)

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
            for widget, (tab_id, jump_key) in zip(
                request_tab_widgets, REQUEST_EDITOR_JUMP_BINDINGS
            )
        )
        targets.extend(
            JumpTarget(jump_key, f"response:{tab_id}", widget)
            for widget, (tab_id, jump_key) in zip(
                response_tab_widgets, RESPONSE_JUMP_BINDINGS
            )
        )
        return JumpOverlay(Jumper(tuple(targets)))

    def _handle_jump_overlay_result(self, target: str | None) -> None:
        app = self._owner_app()
        if app is None:
            return
        app.state.leave_jump_mode()
        if target is not None:
            self.activate_jump_target(target)
        app._refresh_screen()
        app.call_after_refresh(self.clear_jump_focus)

    def activate_jump_target(self, target: str) -> bool:
        app = self._owner_app()
        if app is None:
            return False
        if target == "collections":
            self._open_collections_jump_target()
            return True
        if target.startswith("request:"):
            self._open_request_jump_target(target.split(":", 1)[1])
            return True
        if target.startswith("response:"):
            self._open_response_jump_target(target.split(":", 1)[1])
            return True
        if target.startswith("topbar:"):
            self._open_top_bar_jump_target(target.split(":", 1)[1])
            return True
        return False

    def _open_collections_jump_target(self) -> None:
        app = self._owner_app()
        assert app is not None
        app.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        app.state.mode = MODE_NORMAL
        app.state.message = ""

    def _open_request_jump_target(self, tab_id: str) -> None:
        app = self._owner_app()
        assert app is not None
        app.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        if app.state.get_active_request() is None and app.state.get_selected_request() is not None:
            app.state.open_selected_request(pin=True)
        app.state.set_home_editor_tab(tab_id)
        app.state.enter_home_section_select_mode()

    def _open_top_bar_jump_target(self, target: str) -> None:
        app = self._owner_app()
        assert app is not None
        app.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        if app.state.get_active_request() is None and app.state.get_selected_request() is not None:
            app.state.open_selected_request(pin=True)
        if target == "method":
            app.state.enter_home_method_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)
        elif target == "url":
            app.state.enter_home_url_edit_mode()

    def _open_response_jump_target(self, tab_id: str) -> None:
        app = self._owner_app()
        assert app is not None
        app.state.switch_tab(TAB_HOME, TAB_LABELS[TAB_HOME])
        if app.state.get_active_request() is None and app.state.get_selected_request() is not None:
            app.state.open_selected_request(pin=True)
        app.state.selected_home_response_tab = tab_id
        app.state.enter_home_response_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)

    def action_home_browse_up(self) -> None:
        self._browse_sidebar(-1)

    def action_home_browse_down(self) -> None:
        self._browse_sidebar(1)

    def action_home_previous_folder(self) -> None:
        self._jump_folder(-1)

    def action_home_next_folder(self) -> None:
        self._jump_folder(1)

    def action_home_previous_collection(self) -> None:
        self._jump_collection(-1)

    def action_home_next_collection(self) -> None:
        self._jump_collection(1)

    def action_home_previous_open_request(self) -> None:
        self._cycle_open_request(-1)

    def action_home_next_open_request(self) -> None:
        self._cycle_open_request(1)

    def _browse_sidebar(self, step: int) -> None:
        app = self._owner_app()
        if app is None:
            return
        tree = self.sidebar_tree()
        if tree is None:
            app.state.select_request(step)
            self.refresh_sidebar()
            return
        if not tree.has_focus:
            tree.focus()
        if step < 0:
            tree.action_cursor_up()
        elif step > 0:
            tree.action_cursor_down()

    def _cycle_open_request(self, step: int) -> None:
        app = self._owner_app()
        if app is None:
            return
        app.state.cycle_open_request(step)
        app._refresh_viewport()

    def _jump_folder(self, step: int) -> None:
        app = self._owner_app()
        if app is None:
            return
        if app.state.select_folder(step):
            app._refresh_viewport()
            self.sync_sidebar_cursor()

    def _jump_collection(self, step: int) -> None:
        app = self._owner_app()
        if app is None:
            return
        if app.state.select_collection(step):
            app._refresh_viewport()
            self.sync_sidebar_cursor()

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
        app.call_after_refresh(self.clear_jump_focus)

    def _open_delete_confirmation(self, request: DeleteConfirmationRequest) -> None:
        app = self.app
        if app is None:
            return
        app._refresh_screen()
        app.push_screen(
            ConfirmModal(request.prompt),
            lambda confirmed, request=request: self._handle_delete_confirmation_result(
                request,
                confirmed,
            ),
        )

    def _handle_delete_confirmation_result(
        self,
        request: DeleteConfirmationRequest,
        confirmed: bool | None,
    ) -> None:
        app = self.app
        if app is None:
            return
        if confirmed:
            self._apply_delete_confirmation(request)
        app.set_focus(None)
        app._refresh_screen()
        app.call_after_refresh(self.clear_jump_focus)

    def _apply_delete_confirmation(self, request: DeleteConfirmationRequest) -> None:
        app = self.app
        if app is None:
            return
        if request.action == "delete_collection":
            app.state._set_selected_sidebar_node("collection", request.target_id)
            node = app.state.get_selected_sidebar_node()
            if (
                node is not None
                and node.kind == "collection"
                and node.node_id == request.target_id
            ):
                app.state.delete_selected_collection()
            return
        if request.action == "delete_folder":
            app.state._set_selected_sidebar_node("folder", request.target_id)
            node = app.state.get_selected_sidebar_node()
            if (
                node is not None
                and node.kind == "folder"
                and node.node_id == request.target_id
            ):
                app.state.delete_selected_folder()

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

    def on_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return
        mode = app.state.mode

        if self.is_mounted:
            if (
                event.key == "tab"
                and app.state.home_editor_tab == HOME_EDITOR_TAB_AUTH
                and mode == MODE_HOME_AUTH_EDIT
            ):
                auth_pane = self.query_one("#request-auth-pane", RequestAuthPane)
                if auth_pane.handle_input_key(event):
                    return

            if mode == MODE_HOME_PARAMS_EDIT:
                params_pane = self.query_one("#request-params-pane", RequestParamsPane)
                if params_pane.handle_input_key(event):
                    return

            if mode == MODE_HOME_HEADERS_EDIT:
                headers_pane = self.query_one("#request-headers-pane", RequestHeadersPane)
                if headers_pane.handle_input_key(event):
                    return

            if mode == MODE_HOME_BODY_EDIT:
                body_pane = self.query_one("#request-body-pane", RequestBodyPane)
                if body_pane.handle_input_key(event):
                    return

        try:
            focused = app.focused
        except ScreenStackError:
            focused = None
        if isinstance(focused, Input) and focused.id == "request-overview-input" and event.key == "tab":
            event.stop()
            return

        if app.home_controller.handle_request_response_shortcuts(event):
            return

        if mode == MODE_NORMAL and app.home_controller.handle_home_view_key(event):
            return

        app.home_controller.dispatch_key(mode, event)
