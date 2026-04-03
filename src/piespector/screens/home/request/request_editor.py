from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from piespector.domain.editor import (
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    REQUEST_EDITOR_TABS,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages
from piespector.screens.home.jump_titles import render_panel_title
from piespector.screens.home.layout import home_request_panel_body_height
from piespector.screens.home.selection import request_panel_selected
from piespector.screens.home.request.request_auth import render_request_auth_editor
from piespector.screens.home.request.request_body import render_request_body_editor
from piespector.screens.home.request.request_metadata import render_request_overview_fields
from piespector.screens.home.request.query_editor import render_request_params_fallback
from piespector.screens.home.request.header_editor import render_request_headers_fallback
from piespector.state import PiespectorState


def render_home_editor_tabs(state: PiespectorState) -> RenderableType:
    tabs = Text()
    for index, (tab_id, label) in enumerate(REQUEST_EDITOR_TABS):
        if index:
            tabs.append(" ")
        if tab_id == state.home_editor_tab:
            tabs.append(f"[{label}]")
        else:
            tabs.append(label)
    return tabs


def render_home_editor_content(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    if state.home_editor_tab == HOME_EDITOR_TAB_REQUEST:
        return render_request_overview_fields(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
        return render_request_params_fallback(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
        return render_request_auth_editor(request, state)
    if state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
        return render_request_headers_fallback(request, state)
    return render_request_body_editor(request, state, viewport_width)


def render_home_editor(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    panel_selected = request_panel_selected(state)
    title = render_panel_title("Request", selected=panel_selected)
    body_height = home_request_panel_body_height(viewport_height)

    if request is None:
        return Panel(
            Align.left(
                Text(messages.HOME_NO_ACTIVE_REQUEST),
                vertical="top",
                height=body_height,
            ),
            title=title,
            title_align="right",
        )

    subtabs = render_home_editor_tabs(state)
    content = render_home_editor_content(request, state, viewport_width)
    return Panel(
        Align.left(
            Group(subtabs, content),
            vertical="top",
            height=body_height,
        ),
        title=title,
        title_align="right",
        subtitle=messages.home_editor_subtitle(state),
        subtitle_align="left",
    )
