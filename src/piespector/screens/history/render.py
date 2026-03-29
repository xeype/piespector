from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_REQUEST,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
)
from piespector.domain.history import HistoryEntry
from piespector.domain.modes import MODE_HISTORY_RESPONSE_SELECT
from piespector.formatting import format_bytes
from piespector.screens.home.render import home_response_visible_rows
from piespector.state import PiespectorState
from piespector.ui import rich_styles as ui_styles
from piespector.ui import rendering_helpers


def history_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 6, 6)


def history_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 42
    return max(min(viewport_width // 3, 52), 38)


def render_history_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if not state.history_entries:
        empty = Text()
        empty.append("No history yet.\n", style=ui_styles.primary_style(bold=True))
        empty.append("Send a request, then open ", style=ui_styles.TEXT_MUTED)
        empty.append(":history", style=ui_styles.success_style(bold=True))
        empty.append(" to inspect the snapshot.", style=ui_styles.TEXT_MUTED)
        return Panel(
            Align.left(empty),
            title="History",
            border_style=ui_styles.BORDER,
            box=box.ROUNDED,
            padding=(1, 2),
        )

    visible_rows = history_list_visible_rows(viewport_height)
    state.clamp_history_scroll_offset(visible_rows)
    selected_entry = state.get_selected_history_entry()
    detail_width = None
    if viewport_width is not None:
        detail_width = max(
            viewport_width - history_sidebar_width(viewport_width) - 6,
            48,
        )

    layout = Table.grid(expand=True)
    layout.add_column(width=history_sidebar_width(viewport_width))
    layout.add_column(ratio=1)
    layout.add_row(
        render_history_sidebar(state, visible_rows),
        render_history_detail(state, selected_entry, viewport_height, detail_width),
    )
    return layout


def render_history_sidebar(
    state: PiespectorState,
    visible_rows: int,
) -> RenderableType:
    entries = state.visible_history_entries()
    start = state.history_scroll_offset
    end = min(start + visible_rows, len(entries))

    table = Table(
        expand=True,
        box=None,
        show_header=False,
        padding=(0, 0),
    )
    table.add_column("When", width=19, no_wrap=True)
    table.add_column("Meta", width=12, no_wrap=True)
    table.add_column("Name", ratio=1, no_wrap=True)

    for index, entry in enumerate(entries[start:end], start=start):
        row_style = None
        when_style = ui_styles.TEXT_MUTED
        meta_style = ui_styles.TEXT_SECONDARY
        name_style = ui_styles.TEXT_PRIMARY
        if index == state.selected_history_index:
            row_style = ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
            when_style = ui_styles.text_style(ui_styles.TEXT_INVERSE, bold=True)
            meta_style = ui_styles.text_style(ui_styles.TEXT_INVERSE, bold=True)
            name_style = ui_styles.text_style(ui_styles.TEXT_INVERSE, bold=True)

        status = str(entry.status_code) if entry.status_code is not None else "ERR"
        meta = f"{entry.method} {status}"
        name = (
            entry.source_request_name.strip()
            or entry.source_request_path.strip()
            or entry.url
            or "(unnamed)"
        )
        table.add_row(
            Text(history_time_label(entry.created_at), style=when_style),
            Text(meta, style=meta_style),
            Text(name, style=name_style),
            style=row_style,
        )

    return Panel(
        table if entries else Text("No matching history entries.", style=ui_styles.TEXT_MUTED),
        title="History",
        subtitle=history_sidebar_caption(
            start,
            end,
            len(entries),
            len(state.history_entries),
            state.history_filter_query,
        ),
        subtitle_align="left",
        border_style=ui_styles.BORDER,
        box=box.ROUNDED,
    )


def render_history_detail(
    state: PiespectorState,
    entry: HistoryEntry | None,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if entry is None:
        if state.history_entries and state.history_filter_query:
            empty = Text()
            empty.append("No matching history entries.\n", style=ui_styles.primary_style(bold=True))
            empty.append("Press ", style=ui_styles.TEXT_MUTED)
            empty.append("s", style=ui_styles.success_style(bold=True))
            empty.append(
                " and submit an empty query to clear the filter.",
                style=ui_styles.TEXT_MUTED,
            )
            body: RenderableType = empty
        else:
            body = Text("No history entry selected.", style=ui_styles.TEXT_MUTED)
        return Panel(
            body,
            title="Details",
            border_style=ui_styles.BORDER,
            box=box.ROUNDED,
        )

    summary = Text()
    summary.append("When ", style=ui_styles.secondary_style(bold=True))
    summary.append(entry.created_at or "-", style=ui_styles.TEXT_PRIMARY)
    summary.append("\nRequest ", style=ui_styles.secondary_style(bold=True))
    summary.append(
        entry.source_request_path or entry.source_request_name or "-",
        style=ui_styles.TEXT_SUCCESS,
    )
    summary.append("\nAuth ", style=ui_styles.secondary_style(bold=True))
    auth_summary, auth_style = history_auth_summary(entry)
    summary.append(auth_summary, style=auth_style)
    summary.append("\nURL ", style=ui_styles.secondary_style(bold=True))
    summary.append(entry.url or "-", style=ui_styles.TEXT_URL)
    summary.append("\nStatus ", style=ui_styles.secondary_style(bold=True))
    summary.append(
        str(entry.status_code or "-"),
        style=ui_styles.TEXT_SUCCESS if entry.status_code else ui_styles.TEXT_DANGER,
    )
    summary.append("   Time ", style=ui_styles.secondary_style(bold=True))
    summary.append(f"{entry.elapsed_ms or 0:.1f} ms", style=ui_styles.TEXT_WARNING)
    summary.append("   Size ", style=ui_styles.secondary_style(bold=True))
    summary.append(format_bytes(entry.response_size), style=ui_styles.TEXT_URL)
    if entry.error:
        summary.append("\nError ", style=ui_styles.secondary_style(bold=True))
        summary.append(entry.error, style=ui_styles.TEXT_DANGER)

    request_tabs = Text()
    request_tabs.append(
        "Request ",
        style=(
            ui_styles.success_style(bold=True)
            if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST
            else ui_styles.primary_style(bold=True)
        ),
    )
    request_tabs.append(
        " Body ",
        style=(
            ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
            if (
                state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_request_tab == RESPONSE_TAB_BODY
            )
            else ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE)
        ),
    )
    request_tabs.append(" ", style="")
    request_tabs.append(
        " Headers ",
        style=(
            ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
            if (
                state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_request_tab == RESPONSE_TAB_HEADERS
            )
            else ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE)
        ),
    )

    request_visible_rows = max(home_response_visible_rows(viewport_height) - 2, 4)
    if state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
        request_lines = list(
            range(rendering_helpers.response_header_row_count(entry.request_headers))
        )
        state.clamp_history_request_scroll_offset(
            len(request_lines),
            request_visible_rows,
        )
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content: RenderableType = rendering_helpers.render_response_headers(
            entry.request_headers,
            request_start,
            request_end,
        )
    else:
        request_lines = rendering_helpers.response_body_lines(
            entry.request_body,
            viewport_width,
        )
        state.clamp_history_request_scroll_offset(
            len(request_lines),
            request_visible_rows,
        )
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content = rendering_helpers.render_response_body(
            entry.request_body,
            viewport_width,
            request_start,
            request_end,
        )

    response_tabs = Text()
    response_tabs.append(
        "Response ",
        style=(
            ui_styles.success_style(bold=True)
            if state.selected_history_detail_block != HISTORY_DETAIL_BLOCK_REQUEST
            else ui_styles.primary_style(bold=True)
        ),
    )
    response_tabs.append(
        " Body ",
        style=(
            ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
            if (
                state.selected_history_detail_block != HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_response_tab == RESPONSE_TAB_BODY
            )
            else ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE)
        ),
    )
    response_tabs.append(" ", style="")
    response_tabs.append(
        " Headers ",
        style=(
            ui_styles.pill_style(ui_styles.TEXT_SUCCESS)
            if (
                state.selected_history_detail_block != HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_response_tab == RESPONSE_TAB_HEADERS
            )
            else ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE)
        ),
    )

    response_visible_rows = max(home_response_visible_rows(viewport_height) - 2, 4)
    if state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
        response_lines = list(
            range(rendering_helpers.response_header_row_count(entry.response_headers))
        )
        state.clamp_history_response_scroll_offset(
            len(response_lines),
            response_visible_rows,
        )
        response_start = state.history_response_scroll_offset
        response_end = min(response_start + response_visible_rows, len(response_lines))
        response_content: RenderableType = rendering_helpers.render_response_headers(
            entry.response_headers,
            response_start,
            response_end,
        )
    else:
        response_lines = rendering_helpers.response_body_lines(
            entry.response_body,
            viewport_width,
        )
        state.clamp_history_response_scroll_offset(
            len(response_lines),
            response_visible_rows,
        )
        response_start = state.history_response_scroll_offset
        response_end = min(response_start + response_visible_rows, len(response_lines))
        response_content = rendering_helpers.render_response_body(
            entry.response_body,
            viewport_width,
            response_start,
            response_end,
        )

    return Panel(
        Group(summary, request_tabs, request_content, response_tabs, response_content),
        title="Details",
        subtitle=(
            history_detail_caption(
                state,
                request_start,
                request_end,
                len(request_lines),
                response_start,
                response_end,
                len(response_lines),
            )
            if state.mode == MODE_HISTORY_RESPONSE_SELECT
            else "e enters response"
        ),
        subtitle_align="left",
        border_style=ui_styles.BORDER,
        box=box.ROUNDED,
    )


def history_auth_summary(entry: HistoryEntry) -> tuple[str, str]:
    if entry.auth_type == "basic":
        return ("Basic Auth via Authorization header", ui_styles.TEXT_WARNING)
    if entry.auth_type == "bearer":
        return ("Bearer Token via Authorization header", ui_styles.TEXT_WARNING)
    if entry.auth_type == "api-key":
        if entry.auth_location == "query":
            name = entry.auth_name or "query key"
            return (f"API Key via query param {name}", ui_styles.TEXT_WARNING)
        name = entry.auth_name or "header"
        return (f"API Key via header {name}", ui_styles.TEXT_WARNING)
    if entry.auth_type == "cookie":
        name = entry.auth_name or "cookie"
        return (f"Cookie Auth via Cookie header ({name})", ui_styles.TEXT_WARNING)
    if entry.auth_type == "custom-header":
        name = entry.auth_name or "custom header"
        return (f"Custom Header via {name}", ui_styles.TEXT_WARNING)
    if entry.auth_type == "oauth2-client-credentials":
        return ("OAuth 2.0 Client Credentials via Authorization header", ui_styles.TEXT_WARNING)
    return ("No Auth", ui_styles.TEXT_MUTED)


def history_time_label(created_at: str) -> str:
    if not created_at:
        return "-"
    if len(created_at) >= 19:
        return created_at[:19].replace("T", " ")
    return created_at.replace("T", " ")


def history_sidebar_caption(
    start: int,
    end: int,
    visible_total: int,
    all_total: int,
    filter_query: str,
) -> str:
    if all_total <= 0:
        return "No entries"
    if visible_total <= 0:
        if filter_query:
            return f"0 of {all_total}  |  filter {filter_query}"
        return "No entries"
    parts = [f"Entries {start + 1}-{end} of {visible_total}"]
    if filter_query:
        parts.append(f"filtered from {all_total}")
        parts.append(f"filter {filter_query}")
    return "  |  ".join(parts)


def history_detail_caption(
    state: PiespectorState,
    request_start: int,
    request_end: int,
    request_total: int,
    response_start: int,
    response_end: int,
    response_total: int,
) -> str:
    if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
        block = "Request"
        tab = state.selected_history_request_tab.title()
        start = request_start
        end = request_end
        total = request_total
        unit = "Rows" if state.selected_history_request_tab == RESPONSE_TAB_HEADERS else "Lines"
    else:
        block = "Response"
        tab = state.selected_history_response_tab.title()
        start = response_start
        end = response_end
        total = response_total
        unit = "Rows" if state.selected_history_response_tab == RESPONSE_TAB_HEADERS else "Lines"
    return (
        f"{block} / {tab}  |  {unit} {start + 1}-{end} of {total}  |  j/k blocks  |  h/l tabs  |  ctrl+u up  |  ctrl+d down  |  e viewer  |  Esc back"
    )
