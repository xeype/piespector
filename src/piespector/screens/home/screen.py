from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, TabbedContent, TabPane

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
)
from piespector.domain.modes import MODE_HOME_AUTH_EDIT
from piespector.screens.home.collections_sidebar import CollectionsSidebar
from piespector.screens.home.response_panel import ResponsePanel
from piespector.screens.home.url_bar import UrlBar
from piespector.screens.home.request.auth_pane import RequestAuthPane
from piespector.screens.home.request.body_pane import RequestBodyPane
from piespector.screens.home.request.headers_pane import RequestHeadersPane
from piespector.screens.home.request.params_pane import RequestParamsPane
from piespector.screens.base import PiespectorScreen
from piespector.screens.home.request.overview_pane import RequestOverviewPane
from piespector.ui.body_editor_modal import BodyEditorModal


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
                                yield RequestHeadersPane(id="request-headers-pane")
                            with TabPane("Body", id=HOME_EDITOR_TAB_BODY):
                                yield RequestBodyPane(id="request-body-pane")
                            with TabPane("Options", id=HOME_EDITOR_TAB_OPTIONS):
                                yield Static("", id="request-options-content")
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

        headers_pane = self.query_one("#request-headers-pane", RequestHeadersPane)
        if headers_pane.handle_input_key(event):
            return

        body_pane = self.query_one("#request-body-pane", RequestBodyPane)
        if body_pane.handle_input_key(event):
            return

        focused = app.focused
        if not isinstance(focused, Input):
            return
        if focused.id != "request-overview-input":
            return

        if event.key == "tab":
            event.stop()
            return
