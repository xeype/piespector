from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    REQUEST_EDITOR_TABS,
)
from piespector.domain.modes import MODE_HOME_SECTION_SELECT
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages, styles
from piespector.screens.home.request.request_auth import render_request_auth_editor
from piespector.screens.home.request.request_body import render_request_body_editor
from piespector.screens.home.request.request_metadata import render_request_overview_fields
from piespector.screens.home.request.query_editor import render_request_params_table
from piespector.screens.home.request.header_editor import render_request_headers_table
from piespector.screens.home.request.url_bar import render_request_url_bar
from piespector.state import PiespectorState


def render_home_editor_tabs(state: PiespectorState) -> Text:
    tabs = Text()
    for index, (tab_id, label) in enumerate(REQUEST_EDITOR_TABS):
        if index:
            tabs.append(" ")
        is_active = tab_id == state.home_editor_tab
        is_selected = state.mode == MODE_HOME_SECTION_SELECT and is_active
        tabs.append(
            f" {label} ",
            style=(
                styles.pill_style(styles.TEXT_WARNING)
                if is_selected
                else styles.pill_style(styles.TEXT_URL)
                if is_active
                else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
            ),
        )
    return tabs


def render_home_editor_content(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    if state.home_editor_tab == HOME_EDITOR_TAB_REQUEST:
        return render_request_overview_fields(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
        return render_request_params_table(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
        return render_request_auth_editor(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
        return render_request_headers_table(request, state)
    return render_request_body_editor(request, state, viewport_width)


def render_home_editor(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    if request is None:
        return Panel(
            Text(messages.HOME_NO_ACTIVE_REQUEST, style=styles.TEXT_MUTED),
            title="Request",
            border_style=styles.BORDER,
        )

    subtabs = render_home_editor_tabs(state)
    content = render_home_editor_content(request, state, viewport_width)
    return Panel(
        Group(render_request_url_bar(request, state), subtabs, content),
        title=request.name,
        subtitle=messages.home_editor_subtitle(state),
        subtitle_align="left",
        border_style=styles.BORDER,
        box=box.ROUNDED,
    )
