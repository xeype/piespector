from __future__ import annotations

from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from textual.widgets import Static, TabbedContent

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
)
from piespector.domain.modes import REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages
from piespector.screens.home.layout import home_request_list_visible_rows
from piespector.screens.home.selection import (
    home_highlighted_panels,
    home_selection,
)
from piespector.screens.home.request.auth_pane import RequestAuthPane
from piespector.screens.home.request.body_pane import RequestBodyPane
from piespector.screens.home.request.headers_pane import RequestHeadersPane
from piespector.screens.home.request.options_pane import RequestOptionsPane
from piespector.screens.home.request.params_pane import RequestParamsPane
from piespector.screens.home.request.request_editor import render_home_editor as render_home_editor_panel
from piespector.screens.home.request.overview_pane import RequestOverviewPane
from piespector.screens.home.request.url_bar import render_top_url_bar
from piespector.screens.home.response_panel import render_request_response
from piespector.screens.home.sidebar import render_home_sidebar as render_home_sidebar_panel
from piespector.state import PiespectorState
from piespector.ui.selection import FOCUS_FRAME_CLASS


def request_response_shortcuts_enabled(mode: str) -> bool:
    return mode in REQUEST_RESPONSE_SHORTCUT_MODES


def sync_home_focus_highlights(
    state: PiespectorState,
    url_bar_container,
    sidebar_container,
    request_panel,
    response_panel,
) -> None:
    selection = home_selection(state)
    highlighted_panels = home_highlighted_panels(state)
    highlighted_widgets = (
        (
            url_bar_container,
            "topbar" in highlighted_panels,
        ),
        (sidebar_container, "sidebar" in highlighted_panels),
        (request_panel, "request" in highlighted_panels),
        (response_panel, "response" in highlighted_panels),
    )
    for widget, selected in highlighted_widgets:
        widget.set_class(selected, FOCUS_FRAME_CLASS)

    request_panel.set_class(selection.request_tab_select, "piespector-tab-select")
    response_panel.set_class(selection.panel == "response", "piespector-tab-select")


# ================================================================
#  Request panel refresh
# ================================================================

def refresh_home_request_content(
    state: PiespectorState,
    tabs: TabbedContent,
    panel,
    title: Static,
    subtitle: Static,
) -> None:
    active_request = state.get_active_request()
    del panel, title

    # Update active tab
    if tabs.query(f"TabPane#{state.home_editor_tab}"):
        tabs.active = state.home_editor_tab

    overview_pane = tabs.query_one("#request-overview-pane", RequestOverviewPane)
    auth_pane = tabs.query_one("#request-auth-pane", RequestAuthPane)
    params_pane = tabs.query_one("#request-params-pane", RequestParamsPane)
    headers_pane = tabs.query_one("#request-headers-pane", RequestHeadersPane)
    body_pane = tabs.query_one("#request-body-pane", RequestBodyPane)
    options_pane = tabs.query_one("#request-options-pane", RequestOptionsPane)

    overview_pane.refresh_from_state(state)
    auth_pane.refresh_from_state(state)
    body_pane.refresh_from_state(state)

    if active_request is None:
        options_pane.refresh_from_state(state)
        params_pane.refresh_from_state(state)
        headers_pane.refresh_from_state(state)
        subtitle.update("")
        return

    subtitle.update(messages.home_editor_subtitle(state))

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

# ================================================================
#  Legacy rendering - kept for backward compatibility (tests, etc.)
# ================================================================

def render_home_editor(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    return render_home_editor_panel(request, state, viewport_height, viewport_width)


def render_home_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    """Legacy rendering function for tests. Returns Rich renderable."""
    if not state.get_sidebar_nodes():
        empty = Text()
        empty.append(f"{messages.HOME_EMPTY_MESSAGE}\n")
        empty.append("Open the Command Palette with Ctrl+P, then run ")
        empty.append(messages.HOME_EMPTY_CREATE_COLLECTION)
        empty.append(" or ")
        empty.append(messages.HOME_EMPTY_CREATE_REQUEST)
        empty.append(" to create one.")
        return Panel(
            Align.left(empty),
            title="Home",
            padding=(1, 2),
        )

    visible_rows = home_request_list_visible_rows(viewport_height)
    state.ensure_request_selection_visible(visible_rows)
    active_request = state.get_active_request()
    shortcuts_enabled = request_response_shortcuts_enabled(state.mode)

    sidebar = render_home_sidebar_panel(state, visible_rows)
    request_panel = render_home_editor_panel(
        active_request,
        state,
        viewport_height,
        viewport_width,
    )
    if active_request is None:
        right_column = request_panel
    else:
        response_panel = render_request_response(
            active_request,
            state,
            viewport_height,
            viewport_width,
            shortcuts_enabled,
        )
        right_column = Group(request_panel, response_panel)
    body = Columns(
        (sidebar, right_column),
        expand=True,
        equal=False,
    )
    return Group(
        render_top_url_bar(state, viewport_width),
        body,
    )


def request_loader_frame(state: PiespectorState) -> str:
    frames = ("|", "/", "-", "\\")
    return frames[state.pending_request_spinner_tick % len(frames)]
