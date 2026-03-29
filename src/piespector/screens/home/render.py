from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.modes import REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages, styles
from piespector.screens.home.layout import (
    home_request_list_visible_rows,
    home_response_visible_rows,
    home_sidebar_width,
    response_scroll_step,
)
from piespector.screens.home.request.method_selection import render_method_selector_value
from piespector.screens.home.request.request_auth import (
    render_auth_secret,
    render_request_auth_editor,
)
from piespector.screens.home.request.request_body import (
    body_context_label,
    render_body_key_value_table,
    render_body_text_editor,
    render_request_body_editor,
)
from piespector.screens.home.request.request_editor import (
    render_home_editor,
    render_home_editor_content,
    render_home_editor_tabs,
)
from piespector.screens.home.request.request_metadata import (
    render_request_overview_fields,
    request_label,
)
from piespector.screens.home.request.header_editor import render_request_headers_table
from piespector.screens.home.request.query_editor import render_request_params_table
from piespector.screens.home.request.url_bar import render_request_url_preview
from piespector.screens.home.response_panel import render_request_response
from piespector.screens.home.sidebar import render_home_sidebar
from piespector.state import PiespectorState

method_color = styles.method_color
method_style = styles.method_style
home_editor_subtitle = messages.home_editor_subtitle
response_caption = messages.response_caption


def request_response_shortcuts_enabled(mode: str) -> bool:
    return mode in REQUEST_RESPONSE_SHORTCUT_MODES


def render_home_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if not state.get_sidebar_nodes():
        empty = Text()
        empty.append(f"{messages.HOME_EMPTY_MESSAGE}\n", style=f"bold {styles.TEXT_PRIMARY}")
        empty.append("Use ", style=styles.TEXT_MUTED)
        empty.append(messages.HOME_EMPTY_CREATE_COLLECTION, style=f"bold {styles.TEXT_SUCCESS}")
        empty.append(" or ", style=styles.TEXT_MUTED)
        empty.append(messages.HOME_EMPTY_CREATE_REQUEST, style=f"bold {styles.TEXT_SUCCESS}")
        empty.append(" to create one.", style=styles.TEXT_MUTED)
        return Panel(
            Align.left(empty),
            title="Home",
            border_style=styles.BORDER,
            box=box.ROUNDED,
            padding=(1, 2),
        )

    state.ensure_request_workspace()
    visible_rows = home_request_list_visible_rows(viewport_height)
    state.clamp_request_scroll_offset(visible_rows)

    sidebar = render_home_sidebar(state, visible_rows)
    active_request = state.get_active_request()
    right_width = None
    if viewport_width is not None:
        right_width = max(viewport_width - home_sidebar_width(viewport_width) - 6, 48)

    workspace = Group(
        render_home_request_tabs(state),
        render_home_editor(active_request, state, right_width),
        render_request_response(
            active_request,
            state,
            viewport_height,
            right_width,
            request_response_shortcuts_enabled(state.mode),
        ),
    )

    layout = Table.grid(expand=True)
    layout.add_column(width=home_sidebar_width(viewport_width))
    layout.add_column(ratio=1)
    layout.add_row(sidebar, workspace)
    return layout


def render_home_request_tabs(state: PiespectorState) -> RenderableType:
    tabs = Text()
    open_requests = state.get_open_requests()
    for index, request in enumerate(open_requests):
        if index:
            tabs.append(" ")

        is_active = request.request_id == state.active_request_id
        in_progress = request.request_id == state.pending_request_id
        spinner = f"{request_loader_frame(state)} " if in_progress else ""
        segment = f" {spinner}{request.method} {request.name} "
        tabs.append(
            segment,
            style=(
                styles.pill_style(styles.TEXT_URL)
                if is_active
                else styles.pill_style(styles.TEXT_WARNING)
                if in_progress
                else styles.pill_style(styles.TAB_INACTIVE, foreground=styles.TEXT_PRIMARY)
            ),
        )

    return Panel(
        tabs or Text("No opened request.", style=styles.TEXT_MUTED),
        title="Opened Requests",
        subtitle="h/l opened",
        subtitle_align="left",
        border_style=styles.BORDER,
        box=box.ROUNDED,
    )


def request_loader_frame(state: PiespectorState) -> str:
    frames = ("|", "/", "-", "\\")
    return frames[state.pending_request_spinner_tick % len(frames)]
