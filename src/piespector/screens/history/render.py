from __future__ import annotations

from rich.console import Group, RenderableType
from rich.rule import Rule
from rich.text import Text

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_REQUEST,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
)
from piespector.domain.history import HistoryEntry
from piespector.domain.modes import MODE_HISTORY_RESPONSE_SELECT
from piespector.formatting import format_bytes
from piespector.state import PiespectorState
from piespector.ui import rendering_helpers
from piespector.ui.selection import selected_element_style


def history_time_label(created_at: str) -> str:
    if not created_at:
        return "-"
    if len(created_at) >= 19:
        return created_at[:19].replace("T", " ")
    return created_at.replace("T", " ")


def history_entry_name(entry: HistoryEntry) -> str:
    return (
        entry.source_request_name.strip()
        or entry.source_request_path.strip()
        or entry.url
        or "(unnamed)"
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


def history_sidebar_subtitle(
    all_total: int,
    visible_total: int,
    filter_query: str,
) -> str:
    if all_total == 0:
        return ""
    if filter_query:
        return f"{visible_total} of {all_total}  |  filter: {filter_query}"
    return f"{all_total} entries"


def history_block_total(
    tab_id: str,
    headers: list[tuple[str, str]],
    body_text: str,
    viewport_width: int | None,
) -> int:
    if tab_id == RESPONSE_TAB_HEADERS:
        return rendering_helpers.response_header_row_count(headers)
    return len(rendering_helpers.response_body_lines(body_text, viewport_width))


def render_history_block(
    tab_id: str,
    headers: list[tuple[str, str]],
    body_text: str,
    viewport_width: int | None,
    start: int,
    end: int,
) -> RenderableType:
    if tab_id == RESPONSE_TAB_HEADERS:
        return rendering_helpers.render_response_headers(headers, start, end)
    return rendering_helpers.render_response_body(body_text, viewport_width, start, end)


def history_detail_subtitle(
    state: PiespectorState,
    *,
    request_start: int,
    request_end: int,
    request_total: int,
    response_start: int,
    response_end: int,
    response_total: int,
) -> str:
    if state.mode != MODE_HISTORY_RESPONSE_SELECT:
        return ""

    if state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
        tab = state.selected_history_request_tab.title()
        unit = "Rows" if state.selected_history_request_tab == RESPONSE_TAB_HEADERS else "Lines"
        start, end, total = request_start, request_end, request_total
        return f"Request / {tab}  |  {unit} {start + 1}-{end} of {total}"

    tab = state.selected_history_response_tab.title()
    unit = "Rows" if state.selected_history_response_tab == RESPONSE_TAB_HEADERS else "Lines"
    start, end, total = response_start, response_end, response_total
    return f"Response / {tab}  |  {unit} {start + 1}-{end} of {total}"


def render_history_detail_content(
    state: PiespectorState,
    entry: HistoryEntry | None,
    *,
    request_start: int,
    request_end: int,
    response_start: int,
    response_end: int,
    viewport_width: int | None,
) -> RenderableType:
    if entry is None:
        if not state.history_entries:
            empty = Text()
            empty.append("No history yet.\n\n", style="dim")
            empty.append(
                "Send a request from the Home tab — each response is saved here automatically.\n"
            )
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

    request_content = render_history_block(
        state.selected_history_request_tab,
        entry.request_headers,
        entry.request_body,
        viewport_width,
        request_start,
        request_end,
    )
    response_content = render_history_block(
        state.selected_history_response_tab,
        entry.response_headers,
        entry.response_body,
        viewport_width,
        response_start,
        response_end,
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
