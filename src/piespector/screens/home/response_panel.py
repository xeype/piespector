from __future__ import annotations

from http import HTTPStatus

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from piespector.domain.editor import (
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
    RESPONSE_TABS,
)
from piespector.formatting import format_bytes
from piespector.screens.home import messages
from piespector.screens.home.jump_titles import render_panel_title
from piespector.screens.home.layout import home_response_panel_body_height, home_response_visible_rows
from piespector.screens.home.selection import home_selection
from piespector.ui.rendering_helpers import (
    render_response_body,
    render_response_headers,
    response_body_lines,
    response_header_row_count,
)
from piespector.state import PiespectorState
from piespector.domain.requests import RequestDefinition


def response_status_style(status_code: int | None) -> str:
    if status_code is None:
        return "white"
    if 200 <= status_code < 300:
        return "#00ff00"
    if 300 <= status_code < 400:
        return "#00ffff"
    if 400 <= status_code < 500:
        return "#ffff00"
    if 500 <= status_code < 600:
        return "#ff0000"
    return "white"


def response_status_label(status_code: int | None) -> str:
    if status_code is None:
        return "-"
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        phrase = ""
    return f"{status_code} {phrase}".strip()


def render_response_summary_line(status_code: int | None, elapsed_ms: float | None, body_length: int) -> Text:
    summary = Text()
    summary.append(response_status_label(status_code), style=response_status_style(status_code))
    summary.append("   ")
    summary.append(f"{elapsed_ms or 0:.1f} ms")
    summary.append("   ")
    summary.append(format_bytes(body_length))
    return summary


def render_response_summary(response) -> Text:
    return render_response_summary_line(
        response.status_code,
        response.elapsed_ms,
        response.body_length,
    )


def render_response_header(response_tabs: Text, response) -> RenderableType:
    summary = render_response_summary(response)
    return Columns(
        (
            response_tabs,
            Align.right(summary),
        ),
        expand=True,
        equal=False,
    )


def render_response_tabs(state: PiespectorState) -> Text:
    response_tabs = Text()
    for index, (tab_id, label) in enumerate(RESPONSE_TABS):
        if index:
            response_tabs.append(" ")
        if state.selected_home_response_tab == tab_id:
            response_tabs.append(f"[{label}]")
        else:
            response_tabs.append(label)
    return response_tabs


def render_request_response(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
    shortcuts_enabled: bool,
) -> RenderableType:
    response_tabs = render_response_tabs(state)
    panel_selected = home_selection(state).panel == "response"
    title = render_panel_title("Response", selected=panel_selected)
    body_height = home_response_panel_body_height(viewport_height)

    if (
        request is not None
        and state.pending_request_id is not None
        and request.request_id == state.pending_request_id
    ):
        return Panel(
            Align.left(
                Group(
                    response_tabs,
                    Text(messages.HOME_SENDING_REQUEST),
                ),
                vertical="top",
                height=body_height,
            ),
            title=title,
            title_align="right",
            subtitle=messages.HOME_REQUEST_IN_PROGRESS,
            subtitle_align="left",
        )

    if request is None or request.last_response is None:
        return Panel(
            Align.left(
                Group(
                    response_tabs,
                    Text(messages.HOME_NO_RESPONSE),
                ),
                vertical="top",
                height=body_height,
            ),
            title=title,
            title_align="right",
        )

    response = request.last_response
    header = render_response_header(response_tabs, response)

    visible_rows = home_response_visible_rows(viewport_height)
    if state.selected_home_response_tab == RESPONSE_TAB_HEADERS:
        lines = list(range(response_header_row_count(response.response_headers)))
    else:
        lines = response_body_lines(response.body_text, viewport_width)
    state.clamp_response_scroll_offset(len(lines), visible_rows)
    start = state.response_scroll_offset
    end = min(start + visible_rows, len(lines))
    if state.selected_home_response_tab == RESPONSE_TAB_HEADERS:
        content = render_response_headers(response.response_headers, start, end)
    else:
        content = render_response_body(response.body_text, viewport_width, start, end)
        return Panel(
            Align.left(
                Group(header, content),
                vertical="top",
                height=body_height,
            ),
        title=title,
        title_align="right",
        subtitle=messages.response_caption(
            start,
            end,
            len(lines),
            shortcuts_enabled,
            state.selected_home_response_tab,
            panel_selected,
            "Rows" if state.selected_home_response_tab == RESPONSE_TAB_HEADERS else "Lines",
            response.error,
        ),
        subtitle_align="left",
    )
