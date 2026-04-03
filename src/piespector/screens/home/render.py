from __future__ import annotations

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from textual.css.query import NoMatches
from textual.widgets import ContentSwitcher, DataTable, Input, Select, Static, Tab, TabbedContent, Tabs, Tree

from piespector.domain.editor import (
    AUTH_TYPE_OPTIONS,
    BODY_KEY_VALUE_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    HOME_EDITOR_TAB_REQUEST,
    RAW_SUBTYPE_OPTIONS,
    REQUEST_EDITOR_TABS,
    RESPONSE_TAB_BODY,
    RESPONSE_TAB_HEADERS,
    RESPONSE_TABS,
)
from piespector.domain.http import HTTP_METHODS
from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_NORMAL,
    REQUEST_RESPONSE_SHORTCUT_MODES,
)
from piespector.domain.requests import RequestDefinition
from piespector.request_builder import preview_auto_headers, preview_request_url
from piespector.screens.home import messages
from piespector.screens.home.layout import (
    home_request_list_visible_rows,
    home_response_visible_rows,
    home_sidebar_width,
    home_top_bar_height,
    response_scroll_step,
)
from piespector.screens.home.selection import (
    home_highlighted_panels,
    home_selection,
    request_panel_selected,
)
from piespector.screens.home.request.method_selection import method_color
from piespector.screens.home.request.request_auth import (
    auth_option_select_context,
    render_auth_secret,
    render_request_auth_editor,
)
from piespector.screens.home.request.request_body import (
    body_context_label,
    refresh_request_body_table,
    render_request_body_preview,
)
from piespector.screens.home.request.request_editor import render_home_editor as render_home_editor_panel
from piespector.screens.home.request.request_metadata import (
    render_request_overview_fields,
    request_label,
)
from piespector.screens.home.request.header_editor import refresh_request_headers_table
from piespector.screens.home.request.query_editor import refresh_request_params_table
from piespector.screens.home.request.dropdown import sync_select_widget
from piespector.screens.home.request.url_bar import render_request_url_preview
from piespector.screens.home.request.url_bar import render_top_url_bar
from piespector.screens.home.response_panel import (
    render_request_response,
    render_response_summary,
    render_response_tabs,
)
from piespector.screens.home.sidebar import render_home_sidebar as render_home_sidebar_panel
from piespector.state import PiespectorState
from piespector.ui.rendering_helpers import (
    render_response_body,
    render_response_headers,
    response_body_lines,
    response_header_row_count,
)
from piespector.ui.selection import FOCUS_FRAME_CLASS, effective_mode, set_selected

home_editor_subtitle = messages.home_editor_subtitle
response_caption = messages.response_caption


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
    method_select=None,
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

    if method_select is not None:
        set_selected(method_select, selection.method_selected)


# ================================================================
#  Sidebar Tree refresh
# ================================================================

def refresh_home_sidebar(
    state: PiespectorState,
    tree: Tree,
    subtitle: Static,
    container,
    title: Static,
    visible_rows: int,
) -> None:
    items = state.get_sidebar_nodes()
    _rebuild_tree(tree, state, items)
    _ensure_tree_cursor(tree, state, len(items))

    start = state.request_scroll_offset
    end = min(start + visible_rows, len(items))
    caption = messages.home_sidebar_caption(state, start, end, len(items))
    subtitle.update(caption)

    del container, title
    selected = home_selection(state).panel == "sidebar"
    if selected and tree.can_focus and not tree.has_focus:
        tree.focus()


def _rebuild_tree(tree: Tree, state: PiespectorState, items: list) -> None:
    signature = (
        tuple(
            (
                item.node_id,
                item.kind,
                item.label,
                item.request_id,
                item.request_index,
                item.method,
                item.depth,
            )
            for item in items
        ),
        tuple(sorted(state.collapsed_collection_ids)),
        tuple(sorted(state.collapsed_folder_ids)),
    )

    if getattr(tree, "_piespector_signature", None) == signature:
        return

    tree.clear()
    tree.root.expand()
    parent_stack: list[tuple[object, int]] = [(tree.root, -1)]

    for index, item in enumerate(items):
        while len(parent_stack) > 1 and parent_stack[-1][1] >= item.depth:
            parent_stack.pop()
        parent_node = parent_stack[-1][0]

        if item.kind == "request":
            label = Text()
            label.append(f"{item.method:7s}", style=method_color(item.method))
            label.append(item.label)
            node = parent_node.add_leaf(label, data=index)
        elif item.kind == "collection":
            marker = "[+]" if item.node_id in state.collapsed_collection_ids else "[-]"
            label = Text(f"{marker} {item.label}")
            node = parent_node.add(
                label,
                data=index,
                expand=item.node_id not in state.collapsed_collection_ids,
            )
            parent_stack.append((node, item.depth))
        else:
            marker = "[+]" if item.node_id in state.collapsed_folder_ids else "[-]"
            label = Text(f"{marker} {item.label}")
            node = parent_node.add(
                label,
                data=index,
                expand=item.node_id not in state.collapsed_folder_ids,
            )
            parent_stack.append((node, item.depth))

    tree._piespector_signature = signature


def _ensure_tree_cursor(tree: Tree, state: PiespectorState, item_count: int) -> None:
    if not item_count:
        return

    cursor_line = tree.cursor_line
    if 0 <= cursor_line < item_count:
        return

    selected_index = max(0, min(state.selected_sidebar_index, item_count - 1))
    tree.cursor_line = selected_index
    tree.scroll_to_line(selected_index, animate=False)


# ================================================================
#  URL bar refresh
# ================================================================

def refresh_home_url_bar(
    state: PiespectorState,
    method_select: Select,
    url_display: Static,
    url_input: Input,
    open_tabs: Tabs,
) -> None:
    active_request = state.get_active_request()
    open_requests = state.get_open_requests()

    open_tabs_signature = _open_request_tabs_signature(state)
    if getattr(open_tabs, "_piespector_signature", None) != open_tabs_signature:
        _refresh_open_request_tabs(state, open_tabs)
        open_tabs._piespector_signature = open_tabs_signature
    open_tabs.display = bool(open_requests)

    if active_request is None:
        method_select.display = False
        method_select.can_focus = False
        _sync_input_widget(url_input, "", display=False)
        url_display.display = True
        url_display.update(Text("No opened request."))
        url_display._piespector_signature = ("no-opened-request",)
        return

    method_select.can_focus = state.mode == MODE_HOME_REQUEST_METHOD_EDIT

    sync_select_widget(
        method_select,
        tuple((method, Text(method, style=method_color(method))) for method in HTTP_METHODS),
        active_request.method.upper(),
        auto_open_token=(
            ("method-select", active_request.request_id, state.mode)
            if state.mode == MODE_HOME_REQUEST_METHOD_EDIT
            else None
        ),
    )
    method_select.display = True
    try:
        method_select.query_one("#label").styles.color = method_color(active_request.method)
    except NoMatches:
        pass

    mode = effective_mode(state)
    if mode == MODE_HOME_URL_EDIT:
        url_display.display = False
        _sync_input_widget(
            url_input,
            active_request.url or "",
            display=True,
            placeholder="Request URL",
            focus_token=("url", active_request.request_id, state.mode),
        )
        return

    _sync_input_widget(url_input, "", display=False)
    url_display.display = True
    url_display_signature = _url_line_signature(state, active_request)
    if getattr(url_display, "_piespector_signature", None) == url_display_signature:
        return

    line = Text()
    url_preview = render_request_url_preview(active_request, state)
    line.append(
        url_preview or "No URL set",
        style=(
            Style(meta={"@click": "app.copy_active_request_url"})
            if url_preview
            else None
        ),
    )

    url_display.update(line)
    url_display._piespector_signature = url_display_signature


def _open_request_tabs_signature(state: PiespectorState) -> tuple[tuple[str, str, str, str], ...] | tuple[tuple[str, str, str, str], ...]:
    spinner_frames = ("|", "/", "-", "\\")
    spinner_frame = spinner_frames[state.pending_request_spinner_tick % len(spinner_frames)]
    return tuple(
        (
            request.request_id,
            request.method,
            request.name,
            spinner_frame if request.request_id == state.pending_request_id else "",
        )
        for request in state.get_open_requests()
    ) + ((state.active_request_id or "", "", "", ""),)


def _url_line_signature(
    state: PiespectorState,
    active_request: RequestDefinition | None,
) -> tuple[object, ...]:
    if active_request is None:
        return ("no-opened-request",)

    mode = effective_mode(state)
    url_preview = render_request_url_preview(active_request, state)

    if mode in {MODE_HOME_REQUEST_METHOD_EDIT, MODE_HOME_REQUEST_METHOD_SELECT}:
        return (
            "method-select",
            active_request.request_id,
            active_request.method,
            url_preview,
        )

    return (
        "url-preview",
        active_request.request_id,
        active_request.method,
        url_preview,
    )


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
        return
    table.blur()


def _refresh_open_request_tabs(state: PiespectorState, tabs: Tabs) -> None:
    try:
        tabs_list = tabs.query_one("#tabs-list")
    except NoMatches:
        return

    open_requests = state.get_open_requests()
    existing_tabs = {
        tab.id: tab
        for tab in tabs.query("#tabs-list > Tab")
        if tab.id is not None
    }
    desired_ids = {
        f"open-req-{request.request_id}"
        for request in open_requests
    }

    for tab_id, tab in existing_tabs.items():
        if tab_id not in desired_ids:
            tab.remove()

    for req in open_requests:
        in_progress = req.request_id == state.pending_request_id
        spinner_frames = ("|", "/", "-", "\\")
        spinner = (
            f"{spinner_frames[state.pending_request_spinner_tick % len(spinner_frames)]} "
            if in_progress
            else ""
        )
        tab_id = f"open-req-{req.request_id}"
        label = Text()
        if spinner:
            label.append(spinner)
        label.append(req.method, style=method_color(req.method))
        label.append(f" {req.name}")
        existing = existing_tabs.get(tab_id)
        if existing is not None:
            existing.update(label)
        else:
            tabs_list.mount(Tab(label, id=tab_id))

    if state.active_request_id:
        active_tab_id = f"open-req-{state.active_request_id}"
        if tabs.query(f"#tabs-list > #{active_tab_id}"):
            tabs.active = active_tab_id
        return

    _clear_open_request_tabs_selection(tabs)


def _clear_open_request_tabs_selection(tabs: Tabs) -> None:
    tabs.active = ""


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

    overview_content = tabs.query_one("#request-overview-content", Static)
    overview_input = tabs.query_one("#request-overview-input", Input)
    auth_type_select = tabs.query_one("#auth-type-select", Select)
    auth_option_label = tabs.query_one("#auth-option-label", Static)
    auth_option_select = tabs.query_one("#auth-option-select", Select)
    auth_content = tabs.query_one("#request-auth-content", Static)
    auth_field_input = tabs.query_one("#auth-field-input", Input)
    note = tabs.query_one("#request-content-note", Static)
    body_type_select = tabs.query_one("#body-type-select", Select)
    body_raw_type_select = tabs.query_one("#body-raw-type-select", Select)
    params_table = tabs.query_one("#request-params-table", DataTable)
    params_input = tabs.query_one("#request-params-input", Input)
    headers_table = tabs.query_one("#request-headers-table", DataTable)
    headers_input = tabs.query_one("#request-headers-input", Input)
    body_table = tabs.query_one("#request-body-table", DataTable)
    body_input = tabs.query_one("#request-body-input", Input)
    body_preview = tabs.query_one("#request-body-preview", Static)

    mode = effective_mode(state)
    selection = home_selection(state)

    set_selected(auth_type_select, selection.auth_type_selected)
    set_selected(body_type_select, selection.body_type_selected)
    set_selected(body_raw_type_select, selection.body_raw_type_selected)
    set_selected(auth_option_select, selection.auth_option_selected)
    set_selected(body_preview, False)

    if active_request is None:
        empty = Text(messages.HOME_NO_ACTIVE_REQUEST)
        overview_content.update(empty)
        _sync_input_widget(overview_input, "", display=False)
        _sync_input_widget(auth_field_input, "", display=False)
        auth_content.update(empty)
        body_preview.update(empty)
        note.update("")
        auth_type_select.display = False
        auth_option_label.display = False
        auth_option_select.display = False
        body_type_select.display = False
        body_raw_type_select.display = False
        _sync_input_widget(params_input, "", display=False)
        params_table.clear(columns=True)
        params_table.add_columns("Request")
        params_table.add_row("No active request.")
        params_table.cursor_type = "none"
        _sync_input_widget(headers_input, "", display=False)
        headers_table.clear(columns=True)
        headers_table.add_columns("Request")
        headers_table.add_row("No active request.")
        headers_table.cursor_type = "none"
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
    auth_type_select.display = state.home_editor_tab == HOME_EDITOR_TAB_AUTH
    body_type_select.display = state.home_editor_tab == HOME_EDITOR_TAB_BODY
    auth_option_label.display = False
    auth_option_select.display = False
    body_raw_type_select.display = False
    note.display = False
    body_table.display = False
    body_preview.display = False
    _sync_input_widget(overview_input, "", display=False)
    _sync_input_widget(auth_field_input, "", display=False)
    _sync_input_widget(params_input, "", display=False)
    _sync_input_widget(headers_input, "", display=False)
    _sync_input_widget(body_input, "", display=False)

    if state.home_editor_tab == HOME_EDITOR_TAB_REQUEST:
        overview_content.update(render_request_overview_fields(active_request, state))
        field_name, field_label = state.selected_request_field()
        _sync_input_widget(
            overview_input,
            str(getattr(active_request, field_name) or ""),
            display=state.mode == MODE_HOME_REQUEST_EDIT,
            placeholder=field_label,
            focus_token=(
                ("request", active_request.request_id, state.selected_request_field_index)
                if state.mode == MODE_HOME_REQUEST_EDIT
                else None
            ),
        )
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_AUTH:
        sync_select_widget(
            auth_type_select,
            AUTH_TYPE_OPTIONS,
            active_request.auth_type,
            auto_open_token=(
                ("auth-type", active_request.request_id, state.mode)
                if state.mode == MODE_HOME_AUTH_TYPE_EDIT
                else None
            ),
        )
        option_context = auth_option_select_context(active_request, state)
        if option_context is not None:
            label, options, current_value = option_context
            auth_option_label.update(label)
            auth_option_label.display = True
            sync_select_widget(
                auth_option_select,
                options,
                current_value,
                display=True,
                auto_open_token=(
                    (
                        "auth-option",
                        active_request.request_id,
                        state.selected_auth_index,
                        state.mode,
                    )
                    if state.mode == MODE_HOME_AUTH_LOCATION_EDIT
                    else None
                ),
            )
        auth_content.update(
            render_request_auth_editor(
                active_request,
                state,
                include_type_selector=False,
            )
        )
        auth_field = state.selected_auth_field()
        if auth_field is not None and state.mode == MODE_HOME_AUTH_EDIT:
            field_name, field_label = auth_field
            auth_initial = str(getattr(active_request, field_name) or "")
            _sync_input_widget(
                auth_field_input,
                auth_initial,
                display=True,
                placeholder=f"Auth {field_label.lower()}",
                focus_token=(
                    "auth-field",
                    active_request.request_id,
                    state.selected_auth_index,
                    field_name,
                ),
            )
        else:
            _sync_input_widget(auth_field_input, "", display=False)
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_PARAMS:
        refresh_request_params_table(params_table, active_request, state)
        field_name, field_label = state.selected_param_field()
        if state.params_creating_new:
            param_value = ""
        elif active_request.query_items and state.selected_param_index < len(active_request.query_items):
            item = active_request.query_items[state.selected_param_index]
            param_value = item.key if field_name == "key" else item.value
        else:
            param_value = ""
        _sync_input_widget(
            params_input,
            param_value,
            display=state.mode == MODE_HOME_PARAMS_EDIT,
            placeholder=f"Param {field_label.lower()}",
            focus_token=(
                (
                    "params",
                    active_request.request_id,
                    state.params_creating_new,
                    state.selected_param_index,
                    state.selected_param_field_index,
                )
                if state.mode == MODE_HOME_PARAMS_EDIT
                else None
            ),
        )
        params_table_selected = panel_selected and state.mode == MODE_HOME_PARAMS_SELECT
        if params_table_selected and params_table.can_focus and not params_table.has_focus:
            params_table.focus()
        elif not params_table_selected:
            _deactivate_table_widget(params_table)
        return

    if state.home_editor_tab == HOME_EDITOR_TAB_HEADERS:
        note.update(Text(messages.HOME_HEADERS_FOOTER))
        note.display = True
        refresh_request_headers_table(headers_table, active_request, state)
        field_name, field_label = state.selected_header_field()
        if state.headers_creating_new:
            header_value = ""
        elif active_request.header_items and state.selected_header_index < len(active_request.header_items):
            item = active_request.header_items[state.selected_header_index]
            header_value = item.key if field_name == "key" else item.value
        else:
            header_value = ""
        _sync_input_widget(
            headers_input,
            header_value,
            display=state.mode == MODE_HOME_HEADERS_EDIT,
            placeholder=f"Header {field_label.lower()}",
            focus_token=(
                (
                    "headers",
                    active_request.request_id,
                    state.headers_creating_new,
                    state.selected_header_index,
                    state.selected_header_field_index,
                )
                if state.mode == MODE_HOME_HEADERS_EDIT
                else None
            ),
        )
        headers_table_selected = panel_selected and state.mode == MODE_HOME_HEADERS_SELECT
        if headers_table_selected and headers_table.can_focus and not headers_table.has_focus:
            headers_table.focus()
        elif not headers_table_selected:
            _deactivate_table_widget(headers_table)
        return

    sync_select_widget(
        body_type_select,
        BODY_TYPE_OPTIONS,
        active_request.body_type,
        auto_open_token=(
            ("body-type", active_request.request_id, state.mode)
            if state.mode == MODE_HOME_BODY_TYPE_EDIT
            else None
        ),
    )
    if active_request.body_type == "raw":
        sync_select_widget(
            body_raw_type_select,
            RAW_SUBTYPE_OPTIONS,
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
        item_index = state.selected_body_index - 1
        if state.mode == MODE_HOME_BODY_EDIT:
            if item_index < 0 or item_index >= len(items):
                body_initial = ""
            else:
                item = items[item_index]
                body_initial = f"{item.key}={item.value}" if item.value else item.key
            _sync_input_widget(
                body_input,
                body_initial,
                display=True,
                placeholder="KEY=value",
                focus_token=(
                    "body-field",
                    active_request.request_id,
                    state.selected_body_index,
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
#  Response panel refresh
# ================================================================

def refresh_home_response(
    state: PiespectorState,
    note: Static,
    summary: Static,
    tabs: Tabs,
    content_switcher: ContentSwitcher,
    panel,
    title: Static,
    subtitle: Static,
    viewport_height: int | None,
    viewport_width: int | None,
) -> None:
    def _response_content_id(tab_id: str) -> str:
        if tab_id == RESPONSE_TAB_HEADERS:
            return "response-headers-content"
        return "response-body-content"

    active_request = state.get_active_request()
    mode = effective_mode(state)
    panel_selected = home_selection(state).panel == "response"
    del panel, title

    # Update tabs
    if tabs.query(f"#tabs-list > #{state.selected_home_response_tab}"):
        tabs.active = state.selected_home_response_tab
    content_id = _response_content_id(state.selected_home_response_tab)
    if content_switcher.query(f"#{content_id}"):
        content_switcher.current = content_id

    body_content = content_switcher.query_one("#response-body-content", Static)
    headers_content = content_switcher.query_one("#response-headers-content", Static)

    shortcuts_enabled = request_response_shortcuts_enabled(state.mode)

    # Handle pending request
    if (
        active_request is not None
        and state.pending_request_id is not None
        and active_request.request_id == state.pending_request_id
    ):
        note.display = False
        note.update("")
        summary.update(Text(messages.HOME_SENDING_REQUEST))
        body_content.update("")
        headers_content.update("")
        subtitle.update(messages.HOME_REQUEST_IN_PROGRESS)
        return

    # Handle no response
    if active_request is None or active_request.last_response is None:
        note.display = False
        note.update("")
        summary.update("")
        empty = Text(messages.HOME_NO_RESPONSE)
        body_content.update(empty)
        headers_content.update(empty)
        subtitle.update("")
        return

    # Render response summary
    response = active_request.last_response
    note.display = False
    note.update("")
    summary.update(render_response_summary(response))

    # Render response content
    visible_rows = max(viewport_height, 1) if viewport_height is not None else home_response_visible_rows(None)
    if state.selected_home_response_tab == RESPONSE_TAB_HEADERS:
        lines = list(range(response_header_row_count(response.response_headers)))
    else:
        lines = response_body_lines(response.body_text, viewport_width)
    state.clamp_response_scroll_offset(len(lines), visible_rows)
    start = state.response_scroll_offset
    end = min(start + visible_rows, len(lines))

    if state.selected_home_response_tab == RESPONSE_TAB_HEADERS:
        rendered = render_response_headers(response.response_headers, start, end)
        headers_content.update(rendered)
    else:
        rendered = render_response_body(response.body_text, viewport_width, start, end)
        body_content.update(rendered)

    subtitle.update(messages.response_caption(
        start,
        end,
        len(lines),
        shortcuts_enabled,
        state.selected_home_response_tab,
        panel_selected,
        "Rows" if state.selected_home_response_tab == RESPONSE_TAB_HEADERS else "Lines",
        response.error,
    ))


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
