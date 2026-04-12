from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import ContentSwitcher, Static, Tab, Tabs

from piespector.domain.editor import (
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
    RESPONSE_TABS,
)
from piespector.domain.modes import REQUEST_RESPONSE_SHORTCUT_MODES
from piespector.domain.requests import RequestDefinition
from piespector.formatting import format_bytes
from piespector.screens.home import messages
from piespector.screens.home.jump_titles import render_panel_title
from piespector.screens.home.layout import home_response_panel_body_height, home_response_visible_rows
from piespector.screens.home.selection import home_selection
from piespector.state import PiespectorState
from piespector.ui.rendering_helpers import (
    render_response_body,
    render_response_headers,
    response_body_lines,
    response_header_row_count,
)

if TYPE_CHECKING:
    from piespector.domain.requests import ResponseSummary


def _response_content_id(tab_id: str) -> str:
    if tab_id == RESPONSE_TAB_HEADERS:
        return "response-headers-content"
    return "response-body-content"


def _response_lines(
    response: ResponseSummary,
    tab_id: str,
    viewport_width: int | None,
) -> tuple[list[int], str]:
    if tab_id == RESPONSE_TAB_HEADERS:
        return (list(range(response_header_row_count(response.response_headers))), "Rows")
    return (response_body_lines(response.body_text, viewport_width), "Lines")


def _render_response_content(
    response: ResponseSummary,
    tab_id: str,
    viewport_width: int | None,
    start: int,
    end: int,
) -> RenderableType:
    if tab_id == RESPONSE_TAB_HEADERS:
        return render_response_headers(response.response_headers, start, end)
    return render_response_body(response.body_text, viewport_width, start, end)


class ResponsePanel(Vertical):
    active_tab = reactive(RESPONSE_TAB_BODY)
    response_scroll_offset = reactive(0)

    class TabChanged(Message):
        def __init__(self, response_panel: ResponsePanel, tab_id: str) -> None:
            super().__init__()
            self.response_panel = response_panel
            self.tab_id = tab_id

        @property
        def control(self) -> ResponsePanel:
            return self.response_panel

    class ViewerRequested(Message):
        def __init__(
            self,
            response_panel: ResponsePanel,
            *,
            origin_mode: str | None = None,
        ) -> None:
            super().__init__()
            self.response_panel = response_panel
            self.origin_mode = origin_mode

        @property
        def control(self) -> ResponsePanel:
            return self.response_panel

    def compose(self) -> ComposeResult:
        note = Static("", id="response-note")
        note.display = False

        yield Static("Response", classes="panel-title", id="response-title")
        yield note
        with Horizontal(id="response-header-row"):
            yield Tabs(
                Tab("Body", id=RESPONSE_TAB_BODY),
                Tab("Headers", id=RESPONSE_TAB_HEADERS),
                id="response-tabs",
                active=RESPONSE_TAB_BODY,
            )
            yield Static("", id="response-summary")
        with ContentSwitcher(
            id="response-content",
            initial=_response_content_id(RESPONSE_TAB_BODY),
        ):
            yield Static("", id="response-body-content")
            yield Static("", id="response-headers-content")
        yield Static("", classes="panel-subtitle", id="response-subtitle")

    def on_mount(self) -> None:
        self.border_title = "Response"

    def watch_active_tab(self, active_tab: str) -> None:
        if not self.is_mounted:
            return

        tabs = self.query_one("#response-tabs", Tabs)
        if tabs.active != active_tab and tabs.query(f"#tabs-list > #{active_tab}"):
            tabs.active = active_tab

        content_switcher = self.query_one("#response-content", ContentSwitcher)
        content_id = _response_content_id(active_tab)
        if content_switcher.current != content_id and content_switcher.query(f"#{content_id}"):
            content_switcher.current = content_id

    def visible_rows(self) -> int:
        if not self.is_mounted:
            return home_response_visible_rows(None)

        content_switcher = self.query_one("#response-content", ContentSwitcher)
        body_content = self.query_one("#response-body-content", Static)
        viewport_height = content_switcher.size.height or body_content.size.height
        if viewport_height:
            return max(viewport_height, 1)
        return home_response_visible_rows(None)

    def scroll_step(self) -> int:
        return max(self.visible_rows() // 2, 1)

    def request_viewer(self, *, origin_mode: str | None = None) -> None:
        self.post_message(self.ViewerRequested(self, origin_mode=origin_mode))

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        self.active_tab = state.selected_home_response_tab

        note = self.query_one("#response-note", Static)
        summary = self.query_one("#response-summary", Static)
        subtitle = self.query_one("#response-subtitle", Static)
        body_content = self.query_one("#response-body-content", Static)
        headers_content = self.query_one("#response-headers-content", Static)

        note.display = False
        note.update("")

        active_request = state.get_active_request()
        if (
            active_request is not None
            and state.pending_request_id is not None
            and active_request.request_id == state.pending_request_id
        ):
            summary.update(Text(messages.HOME_SENDING_REQUEST))
            body_content.update("")
            headers_content.update("")
            subtitle.update(messages.HOME_REQUEST_IN_PROGRESS)
            self.response_scroll_offset = 0
            return

        if active_request is None or active_request.last_response is None:
            empty = Text(messages.HOME_NO_RESPONSE)
            summary.update("")
            body_content.update(empty)
            headers_content.update(empty)
            subtitle.update("")
            self.response_scroll_offset = state.response_scroll_offset
            return

        response = active_request.last_response
        summary.update(render_response_summary(response))

        viewport_width = self._viewport_width()
        lines, unit_label = _response_lines(response, self.active_tab, viewport_width)
        visible_rows = self.visible_rows()
        state.clamp_response_scroll_offset(len(lines), visible_rows)
        self.response_scroll_offset = state.response_scroll_offset
        start = self.response_scroll_offset
        end = min(start + visible_rows, len(lines))

        rendered = _render_response_content(
            response,
            self.active_tab,
            viewport_width,
            start,
            end,
        )
        if self.active_tab == RESPONSE_TAB_HEADERS:
            headers_content.update(rendered)
        else:
            body_content.update(rendered)

        subtitle.update(
            messages.response_caption(
                start,
                end,
                len(lines),
                state.mode in REQUEST_RESPONSE_SHORTCUT_MODES,
                self.active_tab,
                home_selection(state).panel == "response",
                unit_label,
                response.error,
            )
        )

    def _viewport_width(self) -> int | None:
        content_switcher = self.query_one("#response-content", ContentSwitcher)
        body_content = self.query_one("#response-body-content", Static)
        return content_switcher.size.width or body_content.size.width or self.size.width or None

    @on(Tabs.TabActivated, "#response-tabs")
    def _on_response_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id
        if not tab_id:
            return

        self.active_tab = tab_id
        event.stop()
        self.post_message(self.TabChanged(self, tab_id))


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


def render_response_summary_line(
    status_code: int | None,
    elapsed_ms: float | None,
    body_length: int,
) -> Text:
    summary = Text()
    summary.append(response_status_label(status_code), style=response_status_style(status_code))
    summary.append("   ")
    summary.append(f"{elapsed_ms or 0:.1f} ms")
    summary.append("   ")
    summary.append(format_bytes(body_length))
    return summary


def render_response_summary(response: ResponseSummary) -> Text:
    return render_response_summary_line(
        response.status_code,
        response.elapsed_ms,
        response.body_length,
    )


def render_response_header(response_tabs: Text, response: ResponseSummary) -> RenderableType:
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

    lines, unit_label = _response_lines(
        response,
        state.selected_home_response_tab,
        viewport_width,
    )
    visible_rows = home_response_visible_rows(viewport_height)
    state.clamp_response_scroll_offset(len(lines), visible_rows)
    start = state.response_scroll_offset
    end = min(start + visible_rows, len(lines))
    content = _render_response_content(
        response,
        state.selected_home_response_tab,
        viewport_width,
        start,
        end,
    )
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
            unit_label,
            response.error,
        ),
        subtitle_align="left",
    )
