from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from piespector.domain.modes import (
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_URL_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.http_client import preview_request_url
from piespector.screens.home.request.method_selection import (
    method_color,
    render_method_selector_value,
)
from piespector.state import PiespectorState
from piespector.ui.selection import effective_mode, selected_element_style


def render_request_url_preview(
    request: RequestDefinition,
    state: PiespectorState,
) -> str:
    return preview_request_url(request, state.env_pairs)


def render_request_url_bar(
    request: RequestDefinition,
    state: PiespectorState,
) -> Text:
    method_line = Text()
    method_line.append(f" {request.method} ", style=method_color(request.method))
    method_line.append("  ")
    request_url_preview = render_request_url_preview(request, state)
    method_line.append(
        request_url_preview or "No URL set",
        style=Style(meta={"@click": "app.copy_active_request_url"}) if request_url_preview else None,
    )
    return method_line


def render_top_url_bar(
    state: PiespectorState,
    viewport_width: int | None = None,
) -> RenderableType:
    mode = effective_mode(state)
    active_request = state.get_active_request()
    if active_request is None:
        url_line = Text("No opened request.")
    elif mode == MODE_HOME_REQUEST_METHOD_EDIT:
        url_line = render_method_and_url_line(
            active_request,
            state,
            method_selected=True,
            show_method_caret=True,
        )
    elif mode == MODE_HOME_REQUEST_METHOD_SELECT:
        url_line = render_method_and_url_line(
            active_request,
            state,
            method_selected=True,
            show_method_caret=True,
        )
    elif mode == MODE_HOME_URL_EDIT:
        url_line = _render_url_line(active_request, state)
    else:
        url_line = _render_url_line(active_request, state)

    content = Text()
    content.append_text(_render_open_request_tabs(state, viewport_width))
    content.append("\n")
    content.append_text(url_line)

    return Panel(
        content,
        padding=(0, 1),
    )


def _render_open_request_tabs(
    state: PiespectorState,
    viewport_width: int | None,
) -> Text:
    open_requests = state.get_open_requests()
    if not open_requests:
        return Text("No opened requests.")

    segments: list[Text] = []
    active_index = 0
    for index, req in enumerate(open_requests):
        is_active = req.request_id == state.active_request_id
        in_progress = req.request_id == state.pending_request_id
        if is_active:
            active_index = index
        spinner_frames = ("|", "/", "-", "\\")
        spinner = (
            f"{spinner_frames[state.pending_request_spinner_tick % len(spinner_frames)]} "
            if in_progress
            else ""
        )
        segment = Text()
        segment.append(
            f" {spinner}",
            style=selected_element_style(state, selected=is_active),
        )
        segment.append(
            req.method,
            style=selected_element_style(
                state,
                selected=is_active,
                foreground=method_color(req.method),
            )
            or method_color(req.method),
        )
        segment.append(
            f" {req.name} ",
            style=selected_element_style(state, selected=is_active),
        )
        segments.append(segment)

    left = 0
    right = len(segments) - 1
    if viewport_width is not None:
        max_width = max(viewport_width - 8, 24)
        left, right = _visible_tab_window(segments, active_index, max_width)

    line = Text()
    rendered_segments: list[Text] = []
    if left > 0:
        rendered_segments.append(Text("…"))
    rendered_segments.extend(segment.copy() for segment in segments[left : right + 1])
    if right < len(segments) - 1:
        rendered_segments.append(Text("…"))

    for index, segment in enumerate(rendered_segments):
        if index:
            line.append(" ")
        line.append_text(segment)
    return line


def _visible_tab_window(
    segments: list[Text],
    active_index: int,
    max_width: int,
) -> tuple[int, int]:
    widths = [segment.cell_len for segment in segments]
    left = active_index
    right = active_index
    prefer_right = True

    while True:
        expanded = False
        if prefer_right and right + 1 < len(segments):
            candidate_right = right + 1
            if _tab_window_width(widths, left, candidate_right) <= max_width:
                right = candidate_right
                expanded = True
        if not expanded and left > 0:
            candidate_left = left - 1
            if _tab_window_width(widths, candidate_left, right) <= max_width:
                left = candidate_left
                expanded = True
        if not expanded and right + 1 < len(segments):
            candidate_right = right + 1
            if _tab_window_width(widths, left, candidate_right) <= max_width:
                right = candidate_right
                expanded = True
        if not expanded and left > 0:
            candidate_left = left - 1
            if _tab_window_width(widths, candidate_left, right) <= max_width:
                left = candidate_left
                expanded = True
        if not expanded:
            break
        prefer_right = not prefer_right

    return left, right


def _tab_window_width(widths: list[int], left: int, right: int) -> int:
    visible_count = right - left + 1
    ellipsis_count = int(left > 0) + int(right < len(widths) - 1)
    segment_count = visible_count + ellipsis_count
    return (
        sum(widths[left : right + 1])
        + ellipsis_count
        + max(segment_count - 1, 0)
    )


def _render_url_line(request: RequestDefinition, state: PiespectorState) -> Text:
    return render_method_and_url_line(request, state)


def render_method_and_url_line(
    request: RequestDefinition,
    state: PiespectorState,
    *,
    method_selected: bool = False,
    show_method_caret: bool = False,
) -> Text:
    line = Text()
    if method_selected:
        line.append_text(
            render_method_selector_value(
                request,
                state,
                selected=True,
                show_caret=show_method_caret,
            )
        )
    else:
        line.append(f" {request.method} ", style=method_color(request.method))
    line.append("  ")
    url_preview = render_request_url_preview(request, state)
    line.append(
        url_preview or "No URL set",
        style=Style(meta={"@click": "app.copy_active_request_url"}) if url_preview else None,
    )
    return line


def _render_url_edit_line(request: RequestDefinition, state: PiespectorState) -> Text:
    return render_method_and_url_line(request, state)
