from __future__ import annotations

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from textual.widgets import DataTable, Static

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_REQUEST,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
)
from piespector.domain.history import HistoryEntry
from piespector.domain.modes import MODE_HISTORY_RESPONSE_SELECT, MODE_NORMAL
from piespector.formatting import format_bytes
from piespector.screens.home.layout import home_response_visible_rows
from piespector.screens.home.request.method_selection import method_color
from piespector.state import PiespectorState
from piespector.ui import rendering_helpers
from piespector.ui.selection import FOCUS_FRAME_CLASS, selected_element_style


def history_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 6, 6)


def history_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 42
    return max(min(viewport_width // 3, 52), 38)


# ================================================================
#  Widget-based refresh
# ================================================================

def refresh_history_widgets(
    state: PiespectorState,
    history_list: DataTable,
    history_detail: Static,
    history_sidebar_container=None,
    history_detail_container=None,
    history_sidebar_subtitle: Static | None = None,
    request_visible_rows: int = 8,
    response_visible_rows: int = 8,
) -> None:
    entries = state.visible_history_entries()

    # Signature-gated list rebuild — skip full clear+re-add when only cursor moved
    data_signature = tuple((e.history_id, e.status_code) for e in entries)
    if getattr(history_list, "_piespector_signature", None) != data_signature:
        history_list._piespector_signature = data_signature
        history_list.clear()
        for entry in entries:
            status = str(entry.status_code) if entry.status_code is not None else "ERR"
            meta = Text()
            meta.append(entry.method, style=method_color(entry.method))
            meta.append(f" {status}")
            name = (
                entry.source_request_name.strip()
                or entry.source_request_path.strip()
                or entry.url
                or "(unnamed)"
            )
            history_list.add_row(history_time_label(entry.created_at), meta, name)

    if entries and state.selected_history_index < len(entries):
        history_list.move_cursor(row=state.selected_history_index)

    # Sidebar subtitle
    if history_sidebar_subtitle is not None:
        history_sidebar_subtitle.update(_history_sidebar_subtitle(state))

    # Detail panel
    selected_entry = state.get_selected_history_entry()
    detail_content = _render_history_detail_content(
        state, selected_entry, request_visible_rows, response_visible_rows,
    )
    history_detail.update(detail_content)

    if history_sidebar_container is not None:
        history_sidebar_container.set_class(state.mode == MODE_NORMAL, FOCUS_FRAME_CLASS)
    if history_detail_container is not None:
        history_detail_container.set_class(state.mode == MODE_HISTORY_RESPONSE_SELECT, FOCUS_FRAME_CLASS)
        if selected_entry is not None:
            history_detail_container.border_subtitle = _detail_border_subtitle(
                state, selected_entry, request_visible_rows, response_visible_rows,
            )
        else:
            history_detail_container.border_subtitle = ""


def _history_sidebar_subtitle(state: PiespectorState) -> str:
    all_total = len(state.history_entries)
    if all_total == 0:
        return ""
    visible_total = len(state.visible_history_entries())
    if state.history_filter_query:
        return f"{visible_total} of {all_total}  |  filter: {state.history_filter_query}"
    return f"{all_total} entries"


def _detail_border_subtitle(
    state: PiespectorState,
    entry: HistoryEntry,
    request_visible_rows: int,
    response_visible_rows: int,
) -> str:
    if state.mode != MODE_HISTORY_RESPONSE_SELECT:
        return ""

    if state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
        request_total = rendering_helpers.response_header_row_count(entry.request_headers)
    else:
        request_total = len(rendering_helpers.response_body_lines(entry.request_body, None))

    if state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
        response_total = rendering_helpers.response_header_row_count(entry.response_headers)
    else:
        response_total = len(rendering_helpers.response_body_lines(entry.response_body, None))

    req_start = state.history_request_scroll_offset
    req_end = min(req_start + request_visible_rows, request_total)
    resp_start = state.history_response_scroll_offset
    resp_end = min(resp_start + response_visible_rows, response_total)

    if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
        tab = state.selected_history_request_tab.title()
        unit = "Rows" if state.selected_history_request_tab == RESPONSE_TAB_HEADERS else "Lines"
        start, end, total = req_start, req_end, request_total
        return f"Request / {tab}  |  {unit} {start + 1}-{end} of {total}"
    else:
        tab = state.selected_history_response_tab.title()
        unit = "Rows" if state.selected_history_response_tab == RESPONSE_TAB_HEADERS else "Lines"
        start, end, total = resp_start, resp_end, response_total
        return f"Response / {tab}  |  {unit} {start + 1}-{end} of {total}"


def _render_history_detail_content(
    state: PiespectorState,
    entry: HistoryEntry | None,
    request_visible_rows: int = 8,
    response_visible_rows: int = 8,
) -> RenderableType:
    if entry is None:
        if not state.history_entries:
            empty = Text()
            empty.append("No history yet.\n\n", style="dim")
            empty.append("Send a request from the Home tab — each response is saved here automatically.\n")
            empty.append("Use ")
            empty.append("/", style="bold")
            empty.append(" to search the workspace  |  ")
            empty.append("r", style="bold")
            empty.append(" to replay  |  ")
            empty.append("e", style="bold")
            empty.append(" to inspect")
            return empty
        if state.history_filter_query:
            empty = Text()
            empty.append("No entries match ")
            empty.append(f'"{state.history_filter_query}"', style="bold")
            empty.append(".\nUse the command palette to clear the filter.")
            return empty
        return Text("No history entry selected.")

    summary = Text()
    summary.append("When     ", style="dim")
    summary.append(entry.created_at or "-")
    summary.append("\nRequest  ", style="dim")
    summary.append(entry.source_request_path or entry.source_request_name or "-")
    summary.append("\nURL      ", style="dim")
    summary.append(entry.url or "-")
    summary.append("\nAuth     ", style="dim")
    summary.append(history_auth_summary(entry))
    if entry.request_body_type and entry.request_body_type != "none":
        summary.append("\nBody     ", style="dim")
        summary.append(entry.request_body_type)
    summary.append("\nStatus   ", style="dim")
    status_code = entry.status_code
    if status_code is not None:
        if status_code < 300:
            status_style = "green"
        elif status_code < 400:
            status_style = "yellow"
        else:
            status_style = "red"
        summary.append(str(status_code), style=status_style)
    else:
        summary.append("-")
    summary.append("   Time  ", style="dim")
    summary.append(f"{entry.elapsed_ms or 0:.1f} ms")
    summary.append("   Size  ", style="dim")
    summary.append(format_bytes(entry.response_size))
    if entry.error:
        summary.append("\nError    ", style="dim")
        summary.append(entry.error, style="red")

    # Request tabs
    request_tabs = Text()
    request_tabs.append("Request  ", style="dim")
    request_tabs.append(
        " Body ",
        style=selected_element_style(
            state,
            selected=(
                state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_request_tab == RESPONSE_TAB_BODY
            ),
        ),
    )
    request_tabs.append(" ")
    request_tabs.append(
        " Headers ",
        style=selected_element_style(
            state,
            selected=(
                state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_request_tab == RESPONSE_TAB_HEADERS
            ),
        ),
    )

    # Request content
    if state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
        request_lines = list(
            range(rendering_helpers.response_header_row_count(entry.request_headers))
        )
        state.clamp_history_request_scroll_offset(len(request_lines), request_visible_rows)
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content: RenderableType = rendering_helpers.render_response_headers(
            entry.request_headers, request_start, request_end,
        )
    else:
        request_lines = rendering_helpers.response_body_lines(entry.request_body, None)
        state.clamp_history_request_scroll_offset(len(request_lines), request_visible_rows)
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content = rendering_helpers.render_response_body(
            entry.request_body, None, request_start, request_end,
        )

    # Response tabs
    response_tabs = Text()
    response_tabs.append("Response ", style="dim")
    response_tabs.append(
        " Body ",
        style=selected_element_style(
            state,
            selected=(
                state.selected_history_detail_block != HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_response_tab == RESPONSE_TAB_BODY
            ),
        ),
    )
    response_tabs.append(" ")
    response_tabs.append(
        " Headers ",
        style=selected_element_style(
            state,
            selected=(
                state.selected_history_detail_block != HISTORY_DETAIL_BLOCK_REQUEST
                and state.selected_history_response_tab == RESPONSE_TAB_HEADERS
            ),
        ),
    )

    # Response content
    if state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
        response_lines = list(
            range(rendering_helpers.response_header_row_count(entry.response_headers))
        )
        state.clamp_history_response_scroll_offset(len(response_lines), response_visible_rows)
        response_start = state.history_response_scroll_offset
        response_end = min(response_start + response_visible_rows, len(response_lines))
        response_content: RenderableType = rendering_helpers.render_response_headers(
            entry.response_headers, response_start, response_end,
        )
    else:
        response_lines = rendering_helpers.response_body_lines(entry.response_body, None)
        state.clamp_history_response_scroll_offset(len(response_lines), response_visible_rows)
        response_start = state.history_response_scroll_offset
        response_end = min(response_start + response_visible_rows, len(response_lines))
        response_content = rendering_helpers.render_response_body(
            entry.response_body, None, response_start, response_end,
        )

    return Group(
        summary,
        Rule(style="dim"),
        request_tabs,
        request_content,
        Rule(style="dim"),
        response_tabs,
        response_content,
    )


# ================================================================
#  Legacy Rich rendering (kept for test compatibility)
# ================================================================

def render_history_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if not state.history_entries:
        empty = Text()
        empty.append("No history yet.\n")
        empty.append("Send a request, then open the Command Palette with Ctrl+P and run ")
        empty.append("history")
        empty.append(" to inspect the snapshot.")
        return Panel(
            Align.left(empty),
            title="History",
            padding=(1, 2),
        )

    visible_rows = history_list_visible_rows(viewport_height)
    state.ensure_history_selection_visible(visible_rows)
    sidebar = render_history_sidebar(state, visible_rows)
    detail = render_history_detail(
        state,
        state.get_selected_history_entry(),
        viewport_height,
        viewport_width,
    )
    return Columns((sidebar, detail), expand=True, equal=False)


def render_history_sidebar(
    state: PiespectorState,
    visible_rows: int,
) -> RenderableType:
    entries = state.visible_history_entries()
    state.clamp_history_scroll_offset(visible_rows)
    start = state.history_scroll_offset
    end = min(start + visible_rows, len(entries))
    visible_entries = entries[start:end]

    table = Table(
        expand=True,
        box=None,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("When", width=20)
    table.add_column("Meta", width=10)
    table.add_column("Name", ratio=1, no_wrap=True)

    for index, entry in enumerate(visible_entries, start=start):
        status = str(entry.status_code) if entry.status_code is not None else "ERR"
        meta = Text()
        meta.append(entry.method, style=method_color(entry.method))
        meta.append(f" {status}")
        name = (
            entry.source_request_name.strip()
            or entry.source_request_path.strip()
            or entry.url
            or "(unnamed)"
        )
        row_style = selected_element_style(
            state,
            selected=index == state.selected_history_index,
        )
        table.add_row(
            history_time_label(entry.created_at),
            meta,
            name,
            style=row_style,
        )

    return Panel(
        table,
        title="History",
        subtitle=history_sidebar_caption(
            start,
            end,
            len(entries),
            len(state.history_entries),
            state.history_filter_query,
        ),
        subtitle_align="left",
    )


def render_history_detail(
    state: PiespectorState,
    entry: HistoryEntry | None,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    return Panel(
        _render_history_detail_content(state, entry),
        title="Detail",
    )


def history_auth_summary(entry: HistoryEntry) -> str:
    if entry.auth_type == "basic":
        return "Basic Auth via Authorization header"
    if entry.auth_type == "bearer":
        return "Bearer Token via Authorization header"
    if entry.auth_type == "api-key":
        if entry.auth_location == "query":
            name = entry.auth_name or "query key"
            return f"API Key via query param {name}"
        name = entry.auth_name or "header"
        return f"API Key via header {name}"
    if entry.auth_type == "cookie":
        name = entry.auth_name or "cookie"
        return f"Cookie Auth via Cookie header ({name})"
    if entry.auth_type == "custom-header":
        name = entry.auth_name or "custom header"
        return f"Custom Header via {name}"
    if entry.auth_type == "oauth2-client-credentials":
        return "OAuth 2.0 Client Credentials via Authorization header"
    return "No Auth"


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
