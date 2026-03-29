from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from piespector.domain.editor import RESPONSE_TAB_BODY, RESPONSE_TAB_HEADERS
from piespector.domain.modes import MODE_HOME_RESPONSE_SELECT
from piespector.formatting import format_bytes
from piespector.screens.home import messages, styles
from piespector.screens.home.layout import home_response_visible_rows
from piespector.ui.rendering_helpers import (
    render_response_body,
    render_response_headers,
    response_body_lines,
    response_header_row_count,
)
from piespector.state import PiespectorState
from piespector.domain.requests import RequestDefinition


def render_request_response(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
    shortcuts_enabled: bool,
) -> RenderableType:
    if (
        request is not None
        and state.pending_request_id is not None
        and request.request_id == state.pending_request_id
    ):
        return Panel(
            Text(messages.HOME_SENDING_REQUEST, style=styles.TEXT_WARNING),
            title="Response",
            subtitle=messages.HOME_REQUEST_IN_PROGRESS,
            subtitle_align="left",
            border_style=styles.BORDER,
            box=box.ROUNDED,
        )

    if request is None or request.last_response is None:
        return Panel(
            Text(messages.HOME_NO_RESPONSE, style=styles.TEXT_MUTED),
            title="Response",
            border_style=styles.BORDER,
            box=box.ROUNDED,
        )

    response = request.last_response
    summary = Text()
    if response.error:
        summary.append(f"Error: {response.error}\n", style=f"bold {styles.TEXT_DANGER}")
    summary.append("Status ", style=f"bold {styles.TEXT_SECONDARY}")
    summary.append(str(response.status_code or "-"), style=styles.TEXT_SUCCESS)
    summary.append("   Time ", style=f"bold {styles.TEXT_SECONDARY}")
    summary.append(f"{response.elapsed_ms or 0:.1f} ms", style=styles.TEXT_WARNING)
    summary.append("   Size ", style=f"bold {styles.TEXT_SECONDARY}")
    summary.append(format_bytes(response.body_length), style=styles.TEXT_URL)

    visible_rows = home_response_visible_rows(viewport_height)
    response_tabs = Text()
    response_tabs.append(
        " Body ",
        style=(
            styles.pill_style(styles.TEXT_SUCCESS)
            if state.selected_home_response_tab == RESPONSE_TAB_BODY
            else styles.pill_style(styles.TAB_INACTIVE, foreground=styles.TEXT_PRIMARY)
        ),
    )
    response_tabs.append(" ", style="")
    response_tabs.append(
        " Headers ",
        style=(
            styles.pill_style(styles.TEXT_SUCCESS)
            if state.selected_home_response_tab == RESPONSE_TAB_HEADERS
            else styles.pill_style(styles.TAB_INACTIVE, foreground=styles.TEXT_PRIMARY)
        ),
    )

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
        Group(summary, response_tabs, content),
        title="Response",
        subtitle=messages.response_caption(
            start,
            end,
            len(lines),
            shortcuts_enabled,
            state.selected_home_response_tab,
            state.mode == MODE_HOME_RESPONSE_SELECT,
            "Rows" if state.selected_home_response_tab == RESPONSE_TAB_HEADERS else "Lines",
        ),
        subtitle_align="left",
        border_style=styles.BORDER,
        box=box.ROUNDED,
    )
