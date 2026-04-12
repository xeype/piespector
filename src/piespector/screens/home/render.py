from __future__ import annotations

from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Select, Static, TabbedContent

from piespector.domain.editor import (
    BODY_KEY_VALUE_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_OPTIONS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    RAW_SUBTYPE_OPTIONS,
    REQUEST_EDITOR_TABS,
)
from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_NORMAL,
    REQUEST_RESPONSE_SHORTCUT_MODES,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages
from piespector.screens.home.layout import (
    home_request_list_visible_rows,
    home_top_bar_height,
)
from piespector.screens.home.selection import (
    home_highlighted_panels,
    home_selection,
    request_panel_selected,
)
from piespector.screens.home.request.auth_pane import RequestAuthPane
from piespector.screens.home.request.headers_pane import RequestHeadersPane
from piespector.screens.home.request.request_body import (
    RequestBodyTable,
    body_context_label,
    refresh_request_body_table,
    render_request_body_preview,
)
from piespector.screens.home.request.params_pane import RequestParamsPane
from piespector.screens.home.request.request_editor import render_home_editor as render_home_editor_panel
from piespector.screens.home.request.overview_pane import RequestOverviewPane
from piespector.screens.home.request.request_options import render_request_options_editor
from piespector.screens.home.request.url_bar import render_top_url_bar
from piespector.screens.home.response_panel import render_request_response
from piespector.screens.home.sidebar import render_home_sidebar as render_home_sidebar_panel
from piespector.state import PiespectorState
from piespector.ui.selection import FOCUS_FRAME_CLASS, effective_mode, set_selected
from piespector.widget.select import option_list, sync

def request_response_shortcuts_enabled(mode: str) -> bool:
    return mode in REQUEST_RESPONSE_SHORTCUT_MODES


def body_preview_is_selected(
    request: RequestDefinition | None,
    state: PiespectorState,
    *,
    panel_selected: bool,
) -> bool:
    if request is None or not panel_selected or state.home_editor_tab != HOME_EDITOR_TAB_BODY:
        return False

    mode = effective_mode(state)
    if mode != MODE_HOME_BODY_SELECT:
        return False
    if request.body_type == "raw":
        return state.selected_body_index == 2
    if request.body_type in BODY_KEY_VALUE_TYPES | {"none"}:
        return False
    return state.selected_body_index == 1


def body_preview_dimensions(
    body_preview: Static,
    request: RequestDefinition,
    body_type_select: Select,
    body_raw_type_select: Select,
) -> tuple[int | None, int | None]:
    parent = body_preview.parent
    app = getattr(body_preview, "app", None)
    request_tabs = None
    if app is not None and app.screen is not None:
        try:
            request_tabs = app.screen.query_one("#request-tabs", TabbedContent)
        except NoMatches:
            request_tabs = None
    layout_key = "raw" if request.body_type == "raw" else "single"
    cached_sizes = getattr(body_preview, "_piespector_preview_sizes", {})
    if not isinstance(cached_sizes, dict):
        cached_sizes = {}

    preview_width = next(
        (
            value
            for value in (
                body_preview.region.width,
                body_preview.size.width,
                parent.region.width if parent is not None else 0,
                parent.size.width if parent is not None else 0,
                request_tabs.region.width if request_tabs is not None else 0,
                request_tabs.size.width if request_tabs is not None else 0,
            )
            if value > 0
        ),
        None,
    )

    container_height = next(
        (
            value
            for value in (
                parent.region.height if parent is not None else 0,
                parent.size.height if parent is not None else 0,
                max(request_tabs.region.height - 2, 0) if request_tabs is not None else 0,
                max(request_tabs.size.height - 2, 0) if request_tabs is not None else 0,
            )
            if value > 0
        ),
        None,
    )
    if container_height is None:
        preview_height = next(
            (
                value
                for value in (
                    body_preview.region.height,
                    body_preview.size.height,
                )
                if value > 0
            ),
            None,
        )
        if preview_width is None or preview_height is None:
            return cached_sizes.get(layout_key, (preview_width, preview_height))
        cached_sizes[layout_key] = (preview_width, preview_height)
        body_preview._piespector_preview_sizes = cached_sizes
        return (preview_width, preview_height)

    occupied_height = 0
    if body_type_select.display:
        occupied_height += 1
    if body_raw_type_select.display:
        occupied_height += 1

    preview_height = max(container_height - occupied_height, 3)
    if preview_width is None:
        return cached_sizes.get(layout_key, (preview_width, preview_height))

    cached_sizes[layout_key] = (preview_width, preview_height)
    body_preview._piespector_preview_sizes = cached_sizes
    return (preview_width, preview_height)


def sync_home_focus_highlights(
    state: PiespectorState,
    url_bar_container,
    sidebar_container,
    request_panel,
    response_panel,
) -> None:
    selection = home_selection(state)
    highlighted_panels = home_highlighted_panels(state)
    highlighted_widgets = (
        (
            url_bar_container,
            "topbar" in highlighted_panels,
        ),
        (sidebar_container, "sidebar" in highlighted_panels),
        (request_panel, "request" in highlighted_panels),
        (response_panel, "response" in highlighted_panels),
    )
    for widget, selected in highlighted_widgets:
        widget.set_class(selected, FOCUS_FRAME_CLASS)

    request_panel.set_class(selection.request_tab_select, "piespector-tab-select")
    response_panel.set_class(selection.panel == "response", "piespector-tab-select")


def _sync_input_widget(
    input_widget: Input,
    value: str,
    *,
    display: bool,
    placeholder: str = "",
    focus_token: object | None = None,
) -> None:
    input_widget.display = display
    input_widget.placeholder = placeholder

    if not display:
        if input_widget.has_focus:
            input_widget.blur()
        input_widget._piespector_focus_token = None
        return

    if focus_token is None:
        if input_widget.value != value:
            input_widget.value = value
        return

    if getattr(input_widget, "_piespector_focus_token", None) == focus_token:
        return

    input_widget._piespector_focus_token = focus_token
    input_widget.value = value
    input_widget.cursor_position = len(value)
    input_widget.focus()


def _deactivate_table_widget(table: DataTable) -> None:
    if not table.has_focus:
        return
    app = table.app
    if app is not None:
        app.set_focus(None)
    else:
        table.blur()


# ================================================================
#  Request panel refresh
# ================================================================

def refresh_home_request_content(
    state: PiespectorState,
    tabs: TabbedContent,
    panel,
    title: Static,
    subtitle: Static,
) -> None:
    active_request = state.get_active_request()
    panel_selected = request_panel_selected(state)
    del panel, title

    # Update active tab
    if tabs.query(f"TabPane#{state.home_editor_tab}"):
        tabs.active = state.home_editor_tab

    overview_pane = tabs.query_one("#request-overview-pane", RequestOverviewPane)
    auth_pane = tabs.query_one("#request-auth-pane", RequestAuthPane)
    params_pane = tabs.query_one("#request-params-pane", RequestParamsPane)
    headers_pane = tabs.query_one("#request-headers-pane", RequestHeadersPane)
    body_type_select = tabs.query_one("#body-type-select", Select)
    body_raw_type_select = tabs.query_one("#body-raw-type-select", Select)
    body_table = tabs.query_one("#request-body-table", RequestBodyTable)
    body_input = tabs.query_one("#request-body-input", Input)
    body_preview = tabs.query_one("#request-body-preview", Static)
    options_content = tabs.query_one("#request-options-content", Static)

    selection = home_selection(state)

    set_selected(body_type_select, selection.body_type_selected)
    set_selected(body_raw_type_select, selection.body_raw_type_selected)
    set_selected(body_preview, False)
    overview_pane.refresh_from_state(state)
    auth_pane.refresh_from_state(state)

    if active_request is None:
        empty = Text(messages.HOME_NO_ACTIVE_REQUEST)
        options_content.update(empty)
        body_preview.update(empty)
        body_type_select.display = False
        body_raw_type_select.display = False
        params_pane.refresh_from_state(state)
        headers_pane.refresh_from_state(state)
        body_table.clear(columns=True)
        body_table.add_columns("Request")
        body_table.add_row("No active request.")
        body_table.cursor_type = "none"
        body_table.display = False
        _sync_input_widget(body_input, "", display=False)
        body_preview.display = True
        subtitle.update("")
        return

    subtitle.update(messages.home_editor_subtitle(state))
    body_type_select.display = state.home_editor_tab == HOME_EDITOR_TAB_BODY
    body_raw_type_select.display = False
    body_table.display = False
    body_preview.display = False
    _sync_input_widget(body_input, "", display=False)

    if state.home_editor_tab == HOME_EDITOR_TAB_REQUEST:
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
        params_pane.refresh_from_state(state)
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
        headers_pane.refresh_from_state(state)
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_OPTIONS:
        options_content.update(render_request_options_editor(active_request, state))
        return

    sync(
        body_type_select,
        option_list(*BODY_TYPE_OPTIONS),
        active_request.body_type,
        auto_open_token=(
            ("body-type", active_request.request_id, state.mode)
            if state.mode == MODE_HOME_BODY_TYPE_EDIT
            else None
        ),
    )
    if active_request.body_type == "raw":
        sync(
            body_raw_type_select,
            option_list(*RAW_SUBTYPE_OPTIONS),
            active_request.raw_subtype,
            display=True,
            auto_open_token=(
                (
                    "body-raw-type",
                    active_request.request_id,
                    state.mode,
                )
                if state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT
                else None
            ),
        )
        body_raw_type_select.display = True
    if active_request.body_type in BODY_KEY_VALUE_TYPES:
        refresh_request_body_table(body_table, active_request, state)
        body_table.display = True
        body_preview.display = False
        items = state.get_active_request_body_items()
        field_name, field_label = state.selected_body_field()
        if state.mode == MODE_HOME_BODY_EDIT:
            item_index = state.selected_body_index - 1
            if state.body_creating_new:
                body_initial = ""
            elif 0 <= item_index < len(items):
                item = items[item_index]
                body_initial = item.key if field_name == "key" else item.value
            else:
                body_initial = ""
            _sync_input_widget(
                body_input,
                body_initial,
                display=True,
                placeholder=f"Body {field_label.lower()}",
                focus_token=(
                    (
                        "body-field",
                        active_request.request_id,
                        state.body_creating_new,
                        state.selected_body_index,
                        state.selected_body_field_index,
                    )
                ),
            )
        else:
            _sync_input_widget(body_input, "", display=False)
            body_table_selected = (
                panel_selected
                and state.mode == MODE_HOME_BODY_SELECT
                and state.selected_body_index > 0
            )
            if body_table_selected and body_table.can_focus and not body_table.has_focus:
                body_table.focus()
            elif not body_table_selected:
                _deactivate_table_widget(body_table)
        return

    preview_selected = body_preview_is_selected(
        active_request,
        state,
        panel_selected=panel_selected,
    )
    preview_width, preview_height = body_preview_dimensions(
        body_preview,
        active_request,
        body_type_select,
        body_raw_type_select,
    )
    body_preview.update(
        render_request_body_preview(
            active_request,
            state,
            preview_width,
            include_raw_selector=False,
            panel_height=preview_height,
            selected=preview_selected,
        )
    )
    if state.mode == MODE_HOME_BODY_EDIT and active_request.body_type == "binary":
        binary_initial = active_request.body_text or ""
        _sync_input_widget(
            body_input,
            binary_initial,
            display=True,
            placeholder="File path",
            focus_token=("body-binary", active_request.request_id),
        )
        body_preview.display = False
    else:
        _sync_input_widget(body_input, "", display=False)
        body_preview.display = True

# ================================================================
#  Legacy rendering - kept for backward compatibility (tests, etc.)
# ================================================================

def render_home_editor(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    return render_home_editor_panel(request, state, viewport_height, viewport_width)

def render_home_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    """Legacy rendering function for tests. Returns Rich renderable."""
    if not state.get_sidebar_nodes():
        empty = Text()
        empty.append(f"{messages.HOME_EMPTY_MESSAGE}\n")
        empty.append("Open the Command Palette with Ctrl+P, then run ")
        empty.append(messages.HOME_EMPTY_CREATE_COLLECTION)
        empty.append(" or ")
        empty.append(messages.HOME_EMPTY_CREATE_REQUEST)
        empty.append(" to create one.")
        return Panel(
            Align.left(empty),
            title="Home",
            padding=(1, 2),
        )

    visible_rows = home_request_list_visible_rows(viewport_height)
    state.ensure_request_selection_visible(visible_rows)
    active_request = state.get_active_request()
    shortcuts_enabled = request_response_shortcuts_enabled(state.mode)

    sidebar = render_home_sidebar_panel(state, visible_rows)
    request_panel = render_home_editor_panel(
        active_request,
        state,
        viewport_height,
        viewport_width,
    )
    if active_request is None:
        right_column = request_panel
    else:
        response_panel = render_request_response(
            active_request,
            state,
            viewport_height,
            viewport_width,
            shortcuts_enabled,
        )
        right_column = Group(request_panel, response_panel)
    body = Columns(
        (sidebar, right_column),
        expand=True,
        equal=False,
    )
    return Group(
        render_top_url_bar(state, viewport_width),
        body,
    )


def request_loader_frame(state: PiespectorState) -> str:
    frames = ("|", "/", "-", "\\")
    return frames[state.pending_request_spinner_tick % len(frames)]
