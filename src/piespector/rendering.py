from __future__ import annotations

import json
import platform
import textwrap
from pygments.style import Style as PygmentsStyle
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Text as PygmentsText
from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from piespector.http_client import preview_auto_headers, preview_request_url, resolve_placeholders
from piespector.commands import (
    command_completion,
    command_completion_matches,
    filesystem_path_completions,
    help_commands,
)
from piespector.formatting import format_bytes
from piespector.search import search_completion, search_matches
from piespector.search import (
    history_search_completion,
    history_search_display,
    history_search_matches,
)
from piespector.state import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS,
    AUTH_TYPE_OPTIONS,
    BODY_TEXT_EDITOR_TYPES,
    BODY_TYPE_OPTIONS,
    HTTP_METHODS,
    HistoryEntry,
    PiespectorState,
    RAW_SUBTYPE_OPTIONS,
    REQUEST_EDITOR_TABS,
    RequestDefinition,
    RequestKeyValue,
    parse_headers_text,
    parse_query_text,
)
from piespector.placeholders import placeholder_match


class _PiespectorMonokaiStyle(PygmentsStyle):
    background_color = "#272822"
    default_style = ""
    styles = {
        PygmentsText: "#f8f8f2",
        Comment: "#75715e",
        Keyword: "#f92672",
        Operator: "#f8f8f2",
        Punctuation: "#f8f8f2",
        Name: "#f8f8f2",
        Name.Variable: "#f8f8f2",
        Name.Other: "#f8f8f2",
        Name.Attribute: "#a6e22e",
        Name.Function: "#a6e22e",
        Name.Class: "#a6e22e",
        Name.Tag: "#f92672",
        Number: "#ae81ff",
        String: "#e6db74",
    }


SYNTAX_THEME = _PiespectorMonokaiStyle


class _PiespectorGraphQLStyle(_PiespectorMonokaiStyle):
    styles = {
        **_PiespectorMonokaiStyle.styles,
        Name: "#a6e22e",
        Name.Function: "#66d9ef",
    }


GRAPHQL_SYNTAX_THEME = _PiespectorGraphQLStyle


def _display_mode(mode: str) -> str:
    if mode.endswith("_SELECT"):
        return "SELECT"
    if mode.endswith("_EDIT"):
        return "EDIT"
    return mode


def _response_copy_hint_items() -> list[tuple[str, str]]:
    system = platform.system()
    if system == "Darwin":
        return [("ctrl+c", "copy"), ("esc", "back")]
    if system == "Windows":
        return [
            ("ctrl+shift+c", "copy"),
            ("ctrl+insert", "copy"),
            ("esc", "back"),
        ]
    return [("ctrl+shift+c", "copy"), ("esc", "back")]


def _request_response_shortcuts_enabled(mode: str) -> bool:
    return mode in {
        "HOME_SECTION_SELECT",
        "HOME_REQUEST_SELECT",
        "HOME_REQUEST_METHOD_EDIT",
        "HOME_AUTH_SELECT",
        "HOME_AUTH_TYPE_EDIT",
        "HOME_AUTH_LOCATION_EDIT",
        "HOME_PARAMS_SELECT",
        "HOME_HEADERS_SELECT",
        "HOME_BODY_SELECT",
        "HOME_BODY_TYPE_EDIT",
        "HOME_BODY_RAW_TYPE_EDIT",
        "HOME_RESPONSE_SELECT",
    }


def _request_label(request: RequestDefinition | None) -> str:
    if request is None:
        return "No request"
    return request.name or "Unnamed request"


def _key_value_row_label(
    items: list[RequestKeyValue],
    index: int,
    add_label: str,
) -> str:
    if index >= len(items):
        return add_label
    item = items[index]
    key = item.key.strip() or "(empty key)"
    return f"Row {index + 1}: {key}"


def _body_context_label(state: PiespectorState) -> str:
    request = state.get_active_request()
    request_label = _request_label(request)
    if request is None:
        return "Body"

    if state.mode == "HOME_BODY_TYPE_EDIT":
        return f"{request_label} / Body / {state.body_type_label(request.body_type)}"

    if request.body_type == "raw":
        return f"{request_label} / Body / Raw / {state.raw_subtype_label(request.raw_subtype)}"

    if request.body_type == "graphql":
        return f"{request_label} / Body / GraphQL"

    if request.body_type == "binary":
        return f"{request_label} / Body / Binary"

    if request.body_type in {"form-data", "x-www-form-urlencoded"}:
        if state.mode == "HOME_BODY_EDIT":
            return f"{request_label} / Body / {state.body_type_label(request.body_type)}"
        return f"{request_label} / Body / {state.body_type_label(request.body_type)}"

    return f"{request_label} / Body / {state.body_type_label(request.body_type)}"


def request_body_syntax_language(request: RequestDefinition | None) -> str | None:
    if request is None:
        return None
    if request.body_type == "graphql":
        return "graphql"
    if request.body_type != "raw":
        return None
    if request.raw_subtype == "text":
        return None
    return request.raw_subtype


def text_area_syntax_language(language: str | None) -> str | None:
    if language == "graphql":
        return "piespector-graphql"
    return language


def syntax_theme_for_language(language: str | None) -> type[PygmentsStyle]:
    if language == "graphql":
        return GRAPHQL_SYNTAX_THEME
    return SYNTAX_THEME


def preview_syntax_language(language: str | None) -> str | None:
    if language == "xml":
        return "html"
    return language


def detect_text_syntax_language(body_text: str) -> str | None:
    stripped = body_text.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    if stripped[0] in "[{":
        return "json"
    if lowered.startswith(("query ", "mutation ", "subscription ", "fragment ")):
        return "graphql"
    if lowered.startswith(("function ", "const ", "let ", "var ", "import ", "export ", "class ")):
        return "javascript"
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        return "html"
    if lowered.startswith("<?xml"):
        return "xml"
    if stripped.startswith("<"):
        if any(marker in lowered for marker in ("<head", "<body", "<div", "<span", "<script", "<style")):
            return "html"
        return "xml"
    return None


def _mode_and_context(state: PiespectorState) -> tuple[str, str]:
    if state.current_tab == "help":
        if state.mode == "COMMAND":
            return ("COMMAND", "Help")
        return ("NORMAL", "Help")

    if state.current_tab == "env":
        env_label = state.active_env_label()
        item = state.get_selected_env_item()
        env_key = item[0] if item is not None else "No values"
        _field_name, field_label = state.selected_env_field()
        if state.mode == "ENV_EDIT":
            if state.env_creating_new:
                return ("EDIT", f"Env / {env_label} / New / Key")
            return ("EDIT", f"Env / {env_label} / {env_key} / {field_label}")
        if state.mode == "ENV_SELECT":
            return ("SELECT", f"Env / {env_label} / {env_key} / {field_label}")
        if state.mode == "COMMAND":
            return ("COMMAND", f"Env / {env_label}")
        return ("NORMAL", f"Env / {env_label}")

    if state.current_tab == "history":
        entry = state.get_selected_history_entry()
        history_label = (
            entry.source_request_name.strip()
            or entry.source_request_path.strip()
            or "History"
        ) if entry is not None else "History"
        if state.mode == "SEARCH":
            return ("SEARCH", "History")
        if state.mode == "COMMAND":
            return ("COMMAND", "History")
        if state.mode == "HISTORY_RESPONSE_SELECT":
            return ("SELECT", f"History / {history_label} / Response")
        if state.mode == "HISTORY_RESPONSE_TEXTAREA":
            return ("EDIT", f"History / {history_label} / Viewer")
        return ("NORMAL", f"History / {history_label}")

    request = state.get_active_request()
    request_label = _request_label(request)

    if state.mode == "CONFIRM":
        node = state.get_selected_sidebar_node()
        if node is not None:
            return ("CONFIRM", f"Delete / {node.label}")
        return ("CONFIRM", "Delete")
    if state.mode == "SEARCH":
        return ("SEARCH", "Collections")
    if state.mode == "COMMAND":
        return ("COMMAND", f"{state.current_tab.title()} / {request_label}")
    if state.mode == "HOME_SECTION_SELECT":
        current_section = state.home_editor_tab.replace("-", " ").title()
        return ("SELECT", f"{request_label} / {current_section}")
    if state.mode in {"HOME_REQUEST_EDIT", "HOME_REQUEST_METHOD_EDIT"}:
        return ("EDIT", f"{request_label} / Request")
    if state.mode == "HOME_REQUEST_SELECT":
        return ("SELECT", f"{request_label} / Request")
    if state.mode == "HOME_AUTH_EDIT":
        return ("EDIT", f"{request_label} / Auth")
    if state.mode in {"HOME_AUTH_SELECT", "HOME_AUTH_TYPE_EDIT", "HOME_AUTH_LOCATION_EDIT"}:
        return ("SELECT", f"{request_label} / Auth")
    if state.mode == "HOME_PARAMS_EDIT":
        return ("EDIT", f"{request_label} / Params")
    if state.mode == "HOME_PARAMS_SELECT":
        return ("SELECT", f"{request_label} / Params")
    if state.mode == "HOME_HEADERS_EDIT":
        return ("EDIT", f"{request_label} / Headers")
    if state.mode == "HOME_HEADERS_SELECT":
        return ("SELECT", f"{request_label} / Headers")
    if state.mode == "HOME_RESPONSE_SELECT":
        return ("SELECT", f"{request_label} / Response")
    if state.mode in {
        "HOME_BODY_EDIT",
        "HOME_BODY_TYPE_EDIT",
        "HOME_BODY_RAW_TYPE_EDIT",
        "HOME_BODY_TEXTAREA",
    }:
        return ("EDIT", _body_context_label(state))
    if state.mode == "HOME_BODY_SELECT":
        return ("SELECT", _body_context_label(state))
    return ("NORMAL", "Collections")


def _home_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 34
    return max(min(viewport_width // 4, 36), 28)


def _home_request_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 3, 6)


def _home_response_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 10
    return max(viewport_height - 22, 6)


def render_viewport(
    state: PiespectorState,
    viewport_height: int | None = None,
    viewport_width: int | None = None,
) -> RenderableType:
    if state.current_tab == "home":
        return _render_home_viewport(state, viewport_height, viewport_width)

    if state.current_tab == "env":
        return _render_env_viewport(state, viewport_height)

    if state.current_tab == "history":
        return _render_history_viewport(state, viewport_height, viewport_width)

    if state.current_tab == "help":
        return _render_help_viewport(state)

    return Text()


def _render_help_viewport(state: PiespectorState) -> RenderableType:
    source_tab = state.help_source_tab
    source_mode = state.help_source_mode
    context_label = {
        "home": "Home",
        "env": "Env",
        "history": "History",
    }.get(source_tab, "Help")

    intro = Text()
    intro.append("Context ", style="bold #abb2bf")
    intro.append(context_label, style="#98c379")
    if source_mode != "NORMAL":
        intro.append("  Opened from ", style="#7f848e")
        intro.append(source_mode.replace("_", " ").title(), style="#d7dae0")
    intro.append("  ", style="")
    intro.append("Esc", style="bold #1f2329 on #98c379")
    intro.append(" returns to the previous tab.", style="#7f848e")

    commands = Text()
    commands.append("Page Commands\n", style="bold #d7dae0")
    command_mode = _help_command_context_mode(source_tab, source_mode)
    for label in help_commands(state, source_tab, command_mode):
        commands.append(f"  {label}\n", style="#d7dae0")

    navigation = Text()
    navigation.append("Keys\n", style="bold #d7dae0")
    for line in _help_key_lines(source_tab, source_mode):
        navigation.append(f"  {line}\n", style="#d7dae0")

    imports = Text()
    imports.append("Import / Export\n", style="bold #d7dae0")
    imports.append("  Home: export PATH writes collections, import PATH adds collections as new copies\n", style="#d7dae0")
    imports.append("  Env: export PATH writes env data, import PATH creates new env set(s)\n", style="#d7dae0")
    imports.append("  Tab completes import/export paths in command mode\n", style="#d7dae0")

    return Panel(
        Group(intro, Text(""), commands, Text(""), navigation, Text(""), imports),
        title="Help",
        subtitle=f"{context_label} reference",
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _append_help_command_section(
    text: Text,
    title: str,
    commands: list[str],
) -> None:
    text.append(f"  {title}\n", style="bold #abb2bf")
    for command in commands:
        text.append(f"    {command}\n", style="#d7dae0")


def _help_command_context_mode(source_tab: str, source_mode: str) -> str:
    if source_tab != "home":
        return "NORMAL"
    if source_mode == "HOME_SECTION_SELECT":
        return source_mode
    if source_mode.startswith("HOME_"):
        return source_mode
    return "NORMAL"


def _help_key_lines(source_tab: str, source_mode: str) -> list[str]:
    if source_tab == "home":
        if source_mode == "NORMAL":
            return [
                "Normal: j/k sidebar, h/l opened, e open request editor or toggle folders/collections, s search, : command, Esc collapse",
                "PageUp/PageDown scroll the sidebar list.",
            ]
        if source_mode == "HOME_SECTION_SELECT":
            return [
                "Sections: h/l sections, e or Enter open, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_REQUEST_SELECT":
            return [
                "Request rows: j/k fields, e or Enter edit, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_REQUEST_EDIT":
            return [
                "Request edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
            ]
        if source_mode == "HOME_REQUEST_METHOD_EDIT":
            return [
                "Method edit: h/l or j/k cycle methods, Enter save, Esc cancel",
            ]
        if source_mode == "HOME_AUTH_SELECT":
            return [
                "Auth rows: j/k rows, e or Enter edit, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_AUTH_EDIT":
            return [
                "Auth edit: Enter save, Esc cancel, Tab path completion for file-path fields, ctrl+c copy, ctrl+v paste",
            ]
        if source_mode == "HOME_AUTH_TYPE_EDIT":
            return [
                "Auth type: h/l or j/k cycle auth type, e or Enter open rows, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_AUTH_LOCATION_EDIT":
            return [
                "Auth option: h/l or j/k cycle value, e or Enter close, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_PARAMS_SELECT":
            return [
                "Params: j/k rows, h/l fields, e or Enter edit, a add, d delete, space toggle, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_PARAMS_EDIT":
            return [
                "Param edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
            ]
        if source_mode == "HOME_HEADERS_SELECT":
            return [
                "Headers: j/k rows, h/l fields, e or Enter edit, a add, d delete, space toggle explicit or auto headers, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_HEADERS_EDIT":
            return [
                "Header edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
            ]
        if source_mode == "HOME_BODY_SELECT":
            return [
                "Body: j/k rows, e or Enter open or edit, a add for form bodies, d delete, space toggle, s send, v response, ctrl+u/d response scroll, Esc back",
            ]
        if source_mode == "HOME_BODY_TYPE_EDIT":
            return [
                "Body type: h/l cycle body types, e or Enter open the active type, Esc back",
            ]
        if source_mode == "HOME_BODY_RAW_TYPE_EDIT":
            return [
                "Raw subtype: h/l cycle subtypes, e or Enter open the editor, Esc back",
            ]
        if source_mode == "HOME_BODY_EDIT":
            return [
                "Body edit: Enter save, Esc cancel, Tab placeholder or path completion, ctrl+c copy, ctrl+v paste",
            ]
        if source_mode == "HOME_RESPONSE_SELECT":
            return [
                "Response: h/l body or headers, e or Enter open the body viewer, ctrl+u/d scroll, Esc back",
            ]
        if source_mode == "HOME_RESPONSE_TEXTAREA":
            return [
                "Response viewer: copy selection or full body with the shown shortcut, Esc closes",
            ]
        return [
            "Normal: j/k sidebar, h/l opened, e open request editor or toggle folders/collections, s search, : command, Esc collapse",
        ]

    if source_tab == "env":
        if source_mode == "ENV_SELECT":
            return [
                "Env rows: h/l or j/k key-value fields, e or Enter edit, a add, d delete, Esc back",
                "Import creates new env sets instead of merging into the selected one.",
            ]
        if source_mode == "ENV_EDIT":
            return [
                "Env edit: Enter save, Esc cancel, Tab placeholder completion, ctrl+c copy, ctrl+v paste",
            ]
        return [
            "Env: h/l env sets, j/k rows, e or Enter open key-value fields, a add, : command",
            "Import creates new env sets instead of merging into the selected one.",
        ]

    if source_tab == "history":
        if source_mode == "HISTORY_RESPONSE_SELECT":
            return [
                "Detail mode: j/k request-response blocks, h/l body-headers tabs, ctrl+u/d scroll the selected block, e opens the viewer, Esc back",
            ]
        if source_mode == "HISTORY_RESPONSE_TEXTAREA":
            return [
                "Response viewer: copy selection or full body with the shown shortcut, Esc closes",
            ]
        return [
            "History: j/k entries, s filter, e or Enter detail mode, : command",
        ]

    return ["Esc returns to the previous tab."]


def _history_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 6, 6)


def _history_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 42
    return max(min(viewport_width // 3, 52), 38)


def _render_history_viewport(
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if not state.history_entries:
        empty = Text()
        empty.append("No history yet.\n", style="bold #d7dae0")
        empty.append("Send a request, then open ", style="#7f848e")
        empty.append(":history", style="bold #98c379")
        empty.append(" to inspect the snapshot.", style="#7f848e")
        return Panel(
            Align.left(empty),
            title="History",
            border_style="#4b5263",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    visible_rows = _history_list_visible_rows(viewport_height)
    state.clamp_history_scroll_offset(visible_rows)
    selected_entry = state.get_selected_history_entry()
    detail_width = None
    if viewport_width is not None:
        detail_width = max(viewport_width - _history_sidebar_width(viewport_width) - 6, 48)

    layout = Table.grid(expand=True)
    layout.add_column(width=_history_sidebar_width(viewport_width))
    layout.add_column(ratio=1)
    layout.add_row(
        _render_history_sidebar(state, visible_rows),
        _render_history_detail(state, selected_entry, viewport_height, detail_width),
    )
    return layout


def _render_home_viewport(
    state: PiespectorState, viewport_height: int | None, viewport_width: int | None
) -> RenderableType:
    if not state.get_sidebar_nodes():
        empty = Text()
        empty.append("No collections or requests yet.\n", style="bold #d7dae0")
        empty.append("Use ", style="#7f848e")
        empty.append(":new collection NAME", style="bold #98c379")
        empty.append(" or ", style="#7f848e")
        empty.append(":new", style="bold #98c379")
        empty.append(" to create one.", style="#7f848e")
        return Panel(
            Align.left(empty),
            title="Home",
            border_style="#4b5263",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    state.ensure_request_workspace()
    visible_rows = _home_request_list_visible_rows(viewport_height)
    state.clamp_request_scroll_offset(visible_rows)

    sidebar = _render_home_sidebar(state, visible_rows, viewport_height)
    active_request = state.get_active_request()
    right_width = None
    if viewport_width is not None:
        right_width = max(viewport_width - _home_sidebar_width(viewport_width) - 6, 48)

    workspace = Group(
        _render_home_request_tabs(state),
        _render_home_editor(active_request, state, right_width),
        _render_request_response(active_request, state, viewport_height, right_width),
    )

    layout = Table.grid(expand=True)
    layout.add_column(width=_home_sidebar_width(viewport_width))
    layout.add_column(ratio=1)
    layout.add_row(sidebar, workspace)
    return layout


def _render_home_sidebar(
    state: PiespectorState,
    visible_rows: int,
    viewport_height: int | None,
) -> RenderableType:
    items = state.get_sidebar_nodes()
    start = state.request_scroll_offset
    end = min(start + visible_rows, len(items))
    visible_items = items[start:end]

    table = Table(
        expand=True,
        box=None,
        show_header=False,
        padding=(0, 0),
    )
    table.add_column("Kind", width=7)
    table.add_column("Name", ratio=1, no_wrap=True)

    for index, item in enumerate(visible_items, start=start):
        style = None
        kind_style_override = None
        name_style_override = None
        if index == state.selected_sidebar_index:
            style = "bold #1f2329 on #98c379"
            kind_style_override = "bold #1f2329"
            name_style_override = "bold #1f2329"
        if item.kind == "request":
            kind_cell = Text(
                item.method,
                style=kind_style_override or _method_style(item.method),
            )
            name_style = "bold #d7dae0"
            label = item.label
        elif item.kind == "collection":
            if style is None:
                style = "on #3a3120"
            kind_cell = Text("COLL", style=kind_style_override or "bold #e5c07b")
            name_style = "bold #f0cc8f"
            marker = "[+]" if item.node_id in state.collapsed_collection_ids else "[-]"
            label = f"{marker} {item.label}"
        else:
            if style is None:
                style = "on #24323b"
            kind_cell = Text("DIR", style=kind_style_override or "bold #61afef")
            name_style = "bold #8fb8de"
            marker = "[+]" if item.node_id in state.collapsed_folder_ids else "[-]"
            label = f"{marker} {item.label}"
        tree_prefix = _sidebar_tree_prefix(items, index)
        table.add_row(
            kind_cell,
            Text.assemble(
                (tree_prefix, "#5c6370"),
                (label, name_style_override or name_style),
            ),
            style=style,
        )

    filler_rows = max(visible_rows - len(visible_items), 0)
    for _ in range(filler_rows):
        table.add_row("", "")

    caption = _home_sidebar_caption(state, start, end, len(items))
    return Panel(
        table,
        title="Collections",
        subtitle=caption,
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _sidebar_tree_prefix(items: list, index: int) -> str:
    node = items[index]
    if node.depth <= 0:
        return ""

    parts: list[str] = []
    for ancestor_depth in range(1, node.depth):
        parts.append("│ " if _sidebar_has_future_sibling(items, index, ancestor_depth) else "  ")

    branch = "└ " if _sidebar_is_last_sibling(items, index) else "├ "
    parts.append(branch)
    return "".join(parts)


def _sidebar_has_future_sibling(items: list, index: int, depth: int) -> bool:
    for later in items[index + 1 :]:
        if later.depth < depth:
            return False
        if later.depth == depth:
            return True
    return False


def _sidebar_is_last_sibling(items: list, index: int) -> bool:
    depth = items[index].depth
    for later in items[index + 1 :]:
        if later.depth < depth:
            return True
        if later.depth == depth:
            return False
    return True


def _home_sidebar_caption(state: PiespectorState, start: int, end: int, total: int) -> str:
    parts = [f"Rows {start + 1}-{end} of {total}"]
    if total > end or start > 0:
        parts.append("PageUp/PageDown")
    parts.append("j/k browse")
    parts.append("h/l opened")
    parts.append(":new")
    parts.append(":new collection NAME")
    parts.append(":new folder NAME")
    parts.append(":del")
    if state.mode.startswith("HOME_") and state.mode != "NORMAL":
        parts.append("edit mode")
    return "  |  ".join(parts)


def _render_home_request_tabs(state: PiespectorState) -> RenderableType:
    tabs = Text()
    open_requests = state.get_open_requests()
    for index, request in enumerate(open_requests):
        if index:
            tabs.append(" ")

        is_active = request.request_id == state.active_request_id
        in_progress = request.request_id == state.pending_request_id
        spinner = f"{_request_loader_frame(state)} " if in_progress else ""
        segment = f" {spinner}{request.method} {request.name} "
        tabs.append(
            segment,
            style=(
                "bold #1f2329 on #61afef"
                if is_active
                else "bold #1f2329 on #e5c07b"
                if in_progress
                else "bold #d7dae0 on #3a3f4b"
            ),
        )

    return Panel(
        tabs or Text("No opened request.", style="#7f848e"),
        title="Opened Requests",
        subtitle="h/l opened",
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _request_loader_frame(state: PiespectorState) -> str:
    frames = ("|", "/", "-", "\\")
    return frames[state.pending_request_spinner_tick % len(frames)]


def _render_home_editor(
    request: RequestDefinition | None, state: PiespectorState, viewport_width: int | None
) -> RenderableType:
    if request is None:
        return Panel(
            Text("No active request.", style="#7f848e"),
            title="Request",
            border_style="#4b5263",
        )

    method_line = Text()
    method_line.append(
        f" {request.method} ",
        style=f"bold #1f2329 on {_method_color(request.method)}",
    )
    method_line.append("  ")
    request_url_preview = _render_request_url_preview(request, state)
    method_line.append(
        request_url_preview or "No URL set",
        style=(
            Style(color="#61afef", meta={"@click": "app.copy_active_request_url"})
            if request_url_preview
            else "#7f848e"
        ),
    )

    subtabs = _render_home_editor_tabs(state)
    content = _render_home_editor_content(request, state, viewport_width)
    return Panel(
        Group(method_line, subtabs, content),
        title=request.name,
        subtitle=_home_editor_subtitle(state),
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _render_home_editor_tabs(state: PiespectorState) -> Text:
    tabs = Text()
    for index, (tab_id, label) in enumerate(REQUEST_EDITOR_TABS):
        if index:
            tabs.append(" ")
        is_active = tab_id == state.home_editor_tab
        is_selected = state.mode == "HOME_SECTION_SELECT" and is_active
        tabs.append(
            f" {label} ",
            style=(
                "bold #1f2329 on #e5c07b"
                if is_selected
                else "bold #1f2329 on #61afef"
                if is_active
                else "bold #abb2bf on #343944"
            ),
        )
    return tabs


def _home_editor_subtitle(state: PiespectorState) -> str:
    if state.mode == "HOME_SECTION_SELECT":
        return "h/l sections   e open"
    if state.mode == "HOME_REQUEST_SELECT":
        return "j/k fields   e edit"
    if state.mode == "HOME_AUTH_SELECT":
        return "j/k rows   e edit"
    if state.mode == "HOME_AUTH_TYPE_EDIT":
        return "h/l type   e open"
    if state.mode == "HOME_AUTH_LOCATION_EDIT":
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            return "h/l client auth   e open"
        return "h/l location   e open"
    if state.mode in {"HOME_PARAMS_SELECT", "HOME_HEADERS_SELECT"}:
        return "j/k rows   space toggle   e edit   a add   d delete"
    if state.mode == "HOME_BODY_SELECT":
        request = state.get_active_request()
        if request is not None and request.body_type in {"form-data", "x-www-form-urlencoded"}:
            return "j/k rows   space toggle   e edit   a add   d delete"
        return "e edit"
    if state.mode == "HOME_BODY_TYPE_EDIT":
        return "h/l type   e open"
    if state.mode == "HOME_BODY_RAW_TYPE_EDIT":
        return "h/l raw   e open"
    if state.mode == "HOME_REQUEST_METHOD_EDIT":
        return "h/l method"
    return ""


def _render_home_editor_content(
    request: RequestDefinition, state: PiespectorState, viewport_width: int | None
) -> RenderableType:
    if state.home_editor_tab == "request":
        return _render_request_overview_fields(request, state)
    if state.home_editor_tab == "params":
        return _render_request_params_table(request, state)
    if state.home_editor_tab == "auth":
        return _render_request_auth_editor(request, state)
    if state.home_editor_tab == "headers":
        return _render_request_headers_table(request, state)
    return _render_request_body_editor(request, state, viewport_width)


def _render_auth_secret(value: str) -> str:
    if not value:
        return "-"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(len(value) - 4, 4)}{value[-4:]}"


def _render_request_auth_editor(
    request: RequestDefinition, state: PiespectorState
) -> RenderableType:
    selector = Text()
    for index, (value, label) in enumerate(AUTH_TYPE_OPTIONS):
        if index:
            selector.append(" ")
        is_active = request.auth_type == value
        is_selected = state.mode == "HOME_AUTH_TYPE_EDIT" and is_active
        style = "bold #1f2329 on #61afef" if is_active else "bold #abb2bf on #343944"
        if is_selected:
            style = "bold #1f2329 on #e5c07b"
        selector.append(f" {label} ", style=style)

    fields = state.auth_fields(request)
    if not fields:
        empty = Text()
        empty.append("No authorization configured.", style="bold #d7dae0")
        return Group(
            selector,
            Panel(empty, border_style="#3f4550", box=box.SIMPLE_HEAVY),
        )

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        border_style="#3f4550",
        padding=(0, 1),
    )
    table.add_column("Field", width=12, style="bold #abb2bf")
    table.add_column("Value", ratio=1, style="#d7dae0")

    for index, (field_name, label) in enumerate(fields, start=1):
        current_value: RenderableType
        if field_name == "auth_api_key_location":
            current_value = Text()
            for option_index, (value, option_label) in enumerate(AUTH_API_KEY_LOCATION_OPTIONS):
                if option_index:
                    current_value.append(" ")
                is_active = request.auth_api_key_location == value
                is_selected = state.mode == "HOME_AUTH_LOCATION_EDIT" and is_active
                style = "bold #1f2329 on #61afef" if is_active else "bold #abb2bf on #343944"
                if is_selected:
                    style = "bold #1f2329 on #e5c07b"
                current_value.append(f" {option_label} ", style=style)
        elif field_name == "auth_oauth_client_authentication":
            current_value = Text()
            for option_index, (value, option_label) in enumerate(
                AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS
            ):
                if option_index:
                    current_value.append(" ")
                is_active = request.auth_oauth_client_authentication == value
                is_selected = state.mode == "HOME_AUTH_LOCATION_EDIT" and is_active
                style = "bold #1f2329 on #61afef" if is_active else "bold #abb2bf on #343944"
                if is_selected:
                    style = "bold #1f2329 on #e5c07b"
                current_value.append(f" {option_label} ", style=style)
        else:
            raw_value = str(getattr(request, field_name) or "")
            if field_name in {
                "auth_basic_password",
                "auth_bearer_token",
                "auth_api_key_value",
                "auth_cookie_value",
                "auth_custom_header_value",
                "auth_oauth_client_secret",
            }:
                display_value = _render_auth_secret(raw_value)
            else:
                display_value = raw_value or "-"
            current_value = Text(display_value, style="#d7dae0")

        row_style = None
        if state.mode == "HOME_AUTH_LOCATION_EDIT" and field_name in {
            "auth_api_key_location",
            "auth_oauth_client_authentication",
        }:
            row_style = "bold #1f2329 on #e5c07b"
        elif state.mode in {"HOME_AUTH_SELECT", "HOME_AUTH_EDIT", "HOME_AUTH_LOCATION_EDIT"} and index == state.selected_auth_index:
            row_style = "bold #1f2329 on #98c379"
        table.add_row(label, current_value, style=row_style)

    footer = Text()
    if request.auth_type == "api-key" and request.auth_api_key_location == "query":
        footer.append("API key will be appended to the request URL as a query parameter.", style="#7f848e")
    elif request.auth_type == "cookie":
        footer.append("Cookie auth is sent as a Cookie header.", style="#7f848e")
    elif request.auth_type == "custom-header":
        footer.append("Custom header auth is inferred at send time. Explicit headers override it.", style="#7f848e")
    elif request.auth_type == "oauth2-client-credentials":
        client_auth_label = state.auth_oauth_client_authentication_label(
            request.auth_oauth_client_authentication
        ).lower()
        footer.append(
            "OAuth 2.0 client credentials fetches a bearer token from the token URL "
            f"at send time using {client_auth_label}.",
            style="#7f848e",
        )
    else:
        footer.append(
            "Auth headers are inferred at send time. Explicit headers override inferred auth.",
            style="#7f848e",
        )
    return Group(selector, table, footer)


def _render_request_overview_fields(
    request: RequestDefinition, state: PiespectorState
) -> RenderableType:
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        border_style="#3f4550",
        padding=(0, 1),
    )
    table.add_column("Field", width=12, style="bold #abb2bf")
    table.add_column("Value", ratio=1, style="#d7dae0")

    for index, (field_name, label) in enumerate(state.current_request_fields()):
        if field_name == "method":
            value = _render_method_selector_value(request, state)
        else:
            value = str(getattr(request, field_name) or "-").replace("\n", "\\n")
        row_style = None
        if state.mode in {"HOME_REQUEST_SELECT", "HOME_REQUEST_EDIT", "HOME_REQUEST_METHOD_EDIT"} and index == state.selected_request_field_index:
            row_style = "bold #1f2329 on #e5c07b"
        table.add_row(label, value, style=row_style)

    return table


def _render_method_selector_value(
    request: RequestDefinition,
    state: PiespectorState,
) -> Text:
    selected = (
        state.edit_buffer.upper()
        if state.mode == "HOME_REQUEST_METHOD_EDIT" and state.selected_request_field()[0] == "method"
        else request.method.upper()
    )
    text = Text()
    for index, method in enumerate(HTTP_METHODS):
        if index:
            text.append(" ")
        style = (
            f"bold #1f2329 on {_method_color(method)}"
            if method == selected
            else "bold #abb2bf on #343944"
        )
        text.append(f" {method} ", style=style)
    return text


def _render_request_params_table(
    request: RequestDefinition, state: PiespectorState
) -> RenderableType:
    params = request.query_items

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #abb2bf",
        border_style="#3f4550",
        row_styles=["on #2c313a", "on #262b33"],
        padding=(0, 1),
    )
    key_header = Text("Key", style="bold #e5c07b")
    value_header = Text("Value", style="bold #d7dae0")
    if state.mode in {"HOME_PARAMS_SELECT", "HOME_PARAMS_EDIT"}:
        if state.selected_param_field_index == 0:
            key_header = Text("Key", style="bold #1f2329 on #61afef")
        else:
            value_header = Text("Value", style="bold #1f2329 on #61afef")
    table.add_column("#", width=4, justify="right", style="bold #7f848e")
    table.add_column("On", width=6, justify="center", style="bold #abb2bf")
    table.add_column(key_header, ratio=2, style="bold #e5c07b")
    table.add_column(value_header, ratio=3, style="#d7dae0")

    for index, item in enumerate(params):
        row_style = None
        if state.mode in {"HOME_PARAMS_SELECT", "HOME_PARAMS_EDIT"} and index == state.selected_param_index:
            row_style = "bold #1f2329 on #98c379"
        key_style = "bold #e5c07b" if item.enabled else "#7f848e"
        value_style = "#d7dae0" if item.enabled else "#7f848e"
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]", style="bold #d7dae0"),
            Text(item.key, style=key_style),
            Text(item.value or "-", style=value_style),
            style=row_style,
        )

    footer = Text()
    footer.append("Composed URL: ", style="bold #7f848e")
    footer.append(_render_request_url_preview(request, state) or "-", style="#61afef")
    return Group(table, footer)


def _render_request_headers_table(
    request: RequestDefinition, state: PiespectorState
) -> RenderableType:
    headers = request.header_items
    auto_headers = preview_auto_headers(request, state.env_pairs)
    state.clamp_selected_header_index(len(headers) + len(auto_headers))

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #abb2bf",
        border_style="#3f4550",
        row_styles=["on #2c313a", "on #262b33"],
        padding=(0, 1),
    )
    key_header = Text("Key", style="bold #e5c07b")
    value_header = Text("Value", style="bold #d7dae0")
    if state.mode in {"HOME_HEADERS_SELECT", "HOME_HEADERS_EDIT"}:
        if state.selected_header_field_index == 0:
            key_header = Text("Key", style="bold #1f2329 on #61afef")
        else:
            value_header = Text("Value", style="bold #1f2329 on #61afef")
    table.add_column("#", width=4, justify="right", style="bold #7f848e")
    table.add_column("On", width=6, justify="center", style="bold #abb2bf")
    table.add_column(key_header, ratio=2, style="bold #e5c07b")
    table.add_column(value_header, ratio=3, style="#d7dae0")

    for index, item in enumerate(headers):
        row_style = None
        if state.mode in {"HOME_HEADERS_SELECT", "HOME_HEADERS_EDIT"} and index == state.selected_header_index:
            row_style = "bold #1f2329 on #98c379"
        key_style = "bold #e5c07b" if item.enabled else "#7f848e"
        value_style = "#d7dae0" if item.enabled else "#7f848e"
        table.add_row(
            str(index + 1),
            Text("[x]" if item.enabled else "[ ]", style="bold #d7dae0"),
            Text(item.key, style=key_style),
            Text(item.value or "-", style=value_style),
            style=row_style,
        )

    for auto_index, (key, value, enabled) in enumerate(auto_headers, start=len(headers)):
        row_style = None
        if state.mode in {"HOME_HEADERS_SELECT", "HOME_HEADERS_EDIT"} and auto_index == state.selected_header_index:
            row_style = "bold #1f2329 on #b8a25c"
        table.add_row(
            "auto",
            Text("[x]" if enabled else "[ ]", style="bold #e5c07b"),
            Text(key, style="bold #d6ba6d"),
            Text(value or "-", style="#c8b26a"),
            style=row_style or "#9aa1ab on #2a2924",
        )

    footer = Text()
    footer.append(
        "Headers sent with the request. Explicit headers override inferred defaults.",
        style="#7f848e",
    )
    return Group(table, footer)


def _render_request_body_editor(
    request: RequestDefinition, state: PiespectorState, viewport_width: int | None
) -> RenderableType:
    selector = Text()
    for index, (value, label) in enumerate(BODY_TYPE_OPTIONS):
        if index:
            selector.append(" ")
        is_active = request.body_type == value
        is_selected = (
            state.mode == "HOME_BODY_TYPE_EDIT"
            and state.selected_body_index == 0
            and is_active
        )
        style = "bold #1f2329 on #61afef" if is_active else "bold #abb2bf on #343944"
        if is_selected:
            style = "bold #1f2329 on #e5c07b"
        selector.append(f" {label} ", style=style)
    if request.body_type == "none":
        empty = Text()
        empty.append("No request body.", style="bold #d7dae0")
        return Group(selector, Panel(empty, border_style="#3f4550", box=box.SIMPLE_HEAVY))

    if request.body_type in {"form-data", "x-www-form-urlencoded"}:
        return Group(selector, _render_body_key_value_table(request, state))

    return Group(selector, _render_body_text_editor(request, state, viewport_width))


def _render_body_key_value_table(
    request: RequestDefinition, state: PiespectorState
) -> RenderableType:
    items = state.get_active_request_body_items()
    add_label = (
        "Add field"
        if request.body_type == "form-data"
        else "Add parameter"
    )
    footer_label = (
        "space toggles, a adds a field, d deletes it."
        if request.body_type == "form-data"
        else "space toggles, a adds a parameter, d deletes it."
    )

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #abb2bf",
        border_style="#3f4550",
        row_styles=["on #2c313a", "on #262b33"],
        padding=(0, 1),
    )
    table.add_column("#", width=4, justify="right", style="bold #7f848e")
    table.add_column("On", width=6, justify="center", style="bold #abb2bf")
    table.add_column("Key", ratio=2, style="bold #e5c07b")
    table.add_column("Value", ratio=3, style="#d7dae0")

    for index, item in enumerate(items, start=1):
        row_style = None
        if state.mode in {"HOME_BODY_SELECT", "HOME_BODY_EDIT"} and state.selected_body_index == index:
            row_style = "bold #1f2329 on #98c379"
        key_style = "bold #e5c07b" if item.enabled else "#7f848e"
        value_style = "#d7dae0" if item.enabled else "#7f848e"
        table.add_row(
            str(index),
            Text("[x]" if item.enabled else "[ ]", style="bold #d7dae0"),
            Text(item.key, style=key_style),
            Text(item.value or "-", style=value_style),
            style=row_style,
        )

    add_style = None
    if state.mode in {"HOME_BODY_SELECT", "HOME_BODY_EDIT"} and state.selected_body_index == len(items) + 1:
        add_style = "bold #1f2329 on #e5c07b"
    table.add_row("+", "", add_label, "", style=add_style)

    return table


def _render_body_text_editor(
    request: RequestDefinition,
    state: PiespectorState,
    viewport_width: int | None,
) -> RenderableType:
    subtype_selector: RenderableType = Text()
    if request.body_type == "raw":
        subtype_selector = Text()
        for index, (value, label) in enumerate(RAW_SUBTYPE_OPTIONS):
            if index:
                subtype_selector.append(" ")
            is_active = request.raw_subtype == value
            is_selected = state.mode == "HOME_BODY_RAW_TYPE_EDIT" and is_active
            style = "bold #1f2329 on #61afef" if is_active else "bold #abb2bf on #343944"
            if is_selected:
                style = "bold #1f2329 on #e5c07b"
            subtype_selector.append(f" {label} ", style=style)
    value = request.body_text
    preview = value or ""
    line_limit = 8
    preview_lines = preview.splitlines() or [preview]
    visible_preview = "\n".join(preview_lines[:line_limit])
    if len(preview_lines) > line_limit:
        visible_preview += "\n..."

    border_style = "#e5c07b" if (
        state.mode in {"HOME_BODY_SELECT", "HOME_BODY_EDIT"}
        and state.selected_body_index == 1
    ) else "#3f4550"

    renderable: RenderableType
    stripped = value.strip()
    language = request_body_syntax_language(request)
    preview_language = preview_syntax_language(language)
    if language is not None and stripped:
        renderable = Syntax(
            visible_preview,
            preview_language or language,
            theme=syntax_theme_for_language(language),
            line_numbers=False,
            word_wrap=True,
            code_width=max((viewport_width or 100) - 10, 24),
            indent_guides=True,
        )
    else:
        empty_label = "No binary file path." if request.body_type == "binary" else "No body."
        renderable = Text(visible_preview or empty_label, style="#d7dae0")

    if request.body_type == "graphql":
        title = "GraphQL"
    elif request.body_type == "binary":
        title = "Binary File"
    else:
        title = f"Raw {request.raw_subtype.upper()}"

    return Group(
        subtype_selector,
        Panel(
            renderable,
            title=title,
            border_style=border_style,
            box=box.SIMPLE_HEAVY,
        ),
    )


def _render_request_text_field(
    value: str,
    state: PiespectorState,
    label: str,
    empty_text: str,
    viewport_width: int | None,
) -> RenderableType:
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        border_style="#3f4550",
        padding=(0, 1),
    )
    table.add_column("Field", width=12, style="bold #abb2bf")
    table.add_column("Value", ratio=1, style="#d7dae0")

    preview = value or "-"
    wrapped_preview = _wrap_text_block(preview if value else empty_text, viewport_width, 3)
    row_style = None
    if state.mode in {"HOME_REQUEST_SELECT", "HOME_REQUEST_EDIT"} and state.selected_request_field_index == 0:
        row_style = "bold #1f2329 on #e5c07b"
    table.add_row(label, wrapped_preview, style=row_style)
    return table


def _method_color(method: str) -> str:
    palette = {
        "GET": "#98c379",
        "POST": "#e5c07b",
        "PUT": "#61afef",
        "PATCH": "#c678dd",
        "DELETE": "#e06c75",
    }
    return palette.get(method.upper(), "#abb2bf")


def _method_style(method: str) -> str:
    return f"bold {_method_color(method)}"


def _render_request_url_preview(
    request: RequestDefinition, state: PiespectorState
) -> str:
    return preview_request_url(request, state.env_pairs)


def _format_response_body(body_text: str) -> str:
    stripped = body_text.strip()
    if not stripped:
        return ""

    if stripped[0] in "[{":
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return body_text
        return json.dumps(payload, indent=2, ensure_ascii=False)

    return body_text


def format_response_body(body_text: str) -> str:
    return _format_response_body(body_text)


def _looks_like_json(body_text: str) -> bool:
    stripped = body_text.strip()
    return bool(stripped) and stripped[0] in "[{"


def _response_body_lines(body_text: str, viewport_width: int | None) -> list[str]:
    formatted = _format_response_body(body_text)
    if not formatted:
        return ["-"]

    wrap_width = max((viewport_width or 100) - 8, 32)
    lines: list[str] = []
    for raw_line in formatted.splitlines():
        wrapped = textwrap.wrap(
            raw_line,
            width=wrap_width,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines or ["-"]


def _response_header_row_count(headers: list[tuple[str, str]]) -> int:
    return max(len(headers), 1)


def _render_response_body(
    body_text: str,
    viewport_width: int | None,
    start: int,
    end: int,
) -> RenderableType:
    formatted = _format_response_body(body_text)
    if not formatted:
        return Text("-", style="#d7dae0")

    language = detect_text_syntax_language(formatted)
    if language is not None:
        return Syntax(
            formatted,
            preview_syntax_language(language) or language,
            theme=syntax_theme_for_language(language),
            line_numbers=False,
            line_range=(start + 1, end),
            word_wrap=True,
            code_width=max((viewport_width or 100) - 8, 24),
            indent_guides=True,
        )

    return Text("\n".join(_response_body_lines(body_text, viewport_width)[start:end]), style="#d7dae0")


def _render_response_headers(
    headers: list[tuple[str, str]],
    start: int,
    end: int,
) -> RenderableType:
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #abb2bf",
        border_style="#4b5263",
        row_styles=["on #2c313a", "on #262b33"],
        padding=(0, 1),
    )
    table.add_column("Header", width=22, style="bold #e5c07b", no_wrap=True)
    table.add_column("Value", ratio=1, style="#d7dae0")

    visible_headers = headers[start:end]
    if not visible_headers:
        table.add_row("-", "-")
        return table

    for key, value in visible_headers:
        table.add_row(key, value or "-")
    return table


def _response_caption(
    start: int,
    end: int,
    total: int,
    shortcuts_enabled: bool,
    response_tab: str = "body",
    response_selected: bool = False,
    unit_label: str = "Lines",
) -> str:
    parts = [response_tab.title(), f"{unit_label} {start + 1}-{end} of {total}"]
    if response_selected:
        parts.append("h/l tabs")
        if response_tab == "body":
            parts.append("e viewer")
    if shortcuts_enabled and (total > end or start > 0):
        parts.append("ctrl+u up")
        parts.append("ctrl+d down")
    return "  |  ".join(parts)


def response_scroll_step(viewport_height: int | None) -> int:
    return max(_home_response_visible_rows(viewport_height) // 2, 1)


def _render_request_response(
    request: RequestDefinition | None,
    state: PiespectorState,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if (
        request is not None
        and state.pending_request_id is not None
        and request.request_id == state.pending_request_id
    ):
        return Panel(
            Text("Sending request...", style="#e5c07b"),
            title="Response",
            subtitle="Request in progress",
            subtitle_align="left",
            border_style="#4b5263",
            box=box.ROUNDED,
        )

    if request is None or request.last_response is None:
        return Panel(
            Text("No response yet. Use :send.", style="#7f848e"),
            title="Response",
            border_style="#4b5263",
            box=box.ROUNDED,
        )

    response = request.last_response
    summary = Text()
    if response.error:
        summary.append(f"Error: {response.error}\n", style="bold #e06c75")
    summary.append("Status ", style="bold #abb2bf")
    summary.append(str(response.status_code or "-"), style="#98c379")
    summary.append("   Time ", style="bold #abb2bf")
    summary.append(f"{response.elapsed_ms or 0:.1f} ms", style="#e5c07b")
    summary.append("   Size ", style="bold #abb2bf")
    summary.append(format_bytes(response.body_length), style="#61afef")

    visible_rows = _home_response_visible_rows(viewport_height)
    response_tabs = Text()
    response_tabs.append(
        " Body ",
        style=(
            "bold #1f2329 on #98c379"
            if state.selected_home_response_tab == "body"
            else "bold #d7dae0 on #3a3f4b"
        ),
    )
    response_tabs.append(" ", style="")
    response_tabs.append(
        " Headers ",
        style=(
            "bold #1f2329 on #98c379"
            if state.selected_home_response_tab == "headers"
            else "bold #d7dae0 on #3a3f4b"
        ),
    )

    if state.selected_home_response_tab == "headers":
        lines = list(range(_response_header_row_count(response.response_headers)))
    else:
        lines = _response_body_lines(response.body_text, viewport_width)
    state.clamp_response_scroll_offset(len(lines), visible_rows)
    start = state.response_scroll_offset
    end = min(start + visible_rows, len(lines))
    if state.selected_home_response_tab == "headers":
        content = _render_response_headers(response.response_headers, start, end)
    else:
        content = _render_response_body(response.body_text, viewport_width, start, end)
    return Panel(
        Group(summary, response_tabs, content),
        title="Response",
        subtitle=_response_caption(
            start,
            end,
            len(lines),
            _request_response_shortcuts_enabled(state.mode),
            state.selected_home_response_tab,
            state.mode == "HOME_RESPONSE_SELECT",
            "Rows" if state.selected_home_response_tab == "headers" else "Lines",
        ),
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _wrap_text_block(text: str, viewport_width: int | None, max_lines: int) -> str:
    wrap_width = max((viewport_width or 100) - 20, 28)
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        wrapped = textwrap.wrap(
            raw_line,
            width=wrap_width,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[:max_lines]) + "\n…"


def _render_history_sidebar(
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
        when_style = "#7f848e"
        meta_style = "#abb2bf"
        name_style = "#d7dae0"
        if index == state.selected_history_index:
            row_style = "bold #1f2329 on #98c379"
            when_style = "bold #1f2329"
            meta_style = "bold #1f2329"
            name_style = "bold #1f2329"

        status = str(entry.status_code) if entry.status_code is not None else "ERR"
        meta = f"{entry.method} {status}"
        name = entry.source_request_name.strip() or entry.source_request_path.strip() or entry.url or "(unnamed)"
        table.add_row(
            Text(_history_time_label(entry.created_at), style=when_style),
            Text(meta, style=meta_style),
            Text(name, style=name_style),
            style=row_style,
        )

    return Panel(
        table
        if entries
        else Text("No matching history entries.", style="#7f848e"),
        title="History",
        subtitle=_history_sidebar_caption(
            start,
            end,
            len(entries),
            len(state.history_entries),
            state.history_filter_query,
        ),
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _render_history_detail(
    state: PiespectorState,
    entry: HistoryEntry | None,
    viewport_height: int | None,
    viewport_width: int | None,
) -> RenderableType:
    if entry is None:
        if state.history_entries and state.history_filter_query:
            empty = Text()
            empty.append("No matching history entries.\n", style="bold #d7dae0")
            empty.append("Press ", style="#7f848e")
            empty.append("s", style="bold #98c379")
            empty.append(" and submit an empty query to clear the filter.", style="#7f848e")
            body: RenderableType = empty
        else:
            body = Text("No history entry selected.", style="#7f848e")
        return Panel(
            body,
            title="Details",
            border_style="#4b5263",
            box=box.ROUNDED,
        )

    summary = Text()
    summary.append("When ", style="bold #abb2bf")
    summary.append(entry.created_at or "-", style="#d7dae0")
    summary.append("\nRequest ", style="bold #abb2bf")
    summary.append(entry.source_request_path or entry.source_request_name or "-", style="#98c379")
    summary.append("\nAuth ", style="bold #abb2bf")
    auth_summary, auth_style = _history_auth_summary(entry)
    summary.append(auth_summary, style=auth_style)
    summary.append("\nURL ", style="bold #abb2bf")
    summary.append(entry.url or "-", style="#61afef")
    summary.append("\nStatus ", style="bold #abb2bf")
    summary.append(str(entry.status_code or "-"), style="#98c379" if entry.status_code else "#e06c75")
    summary.append("   Time ", style="bold #abb2bf")
    summary.append(f"{entry.elapsed_ms or 0:.1f} ms", style="#e5c07b")
    summary.append("   Size ", style="bold #abb2bf")
    summary.append(format_bytes(entry.response_size), style="#61afef")
    if entry.error:
        summary.append("\nError ", style="bold #abb2bf")
        summary.append(entry.error, style="#e06c75")

    request_tabs = Text()
    request_tabs.append(
        "Request ",
        style=(
            "bold #98c379"
            if state.selected_history_detail_block == "request"
            else "bold #d7dae0"
        ),
    )
    request_tabs.append(
        " Body ",
        style=(
            "bold #1f2329 on #98c379"
            if (
                state.selected_history_detail_block == "request"
                and state.selected_history_request_tab == "body"
            )
            else "bold #d7dae0 on #3a3f4b"
        ),
    )
    request_tabs.append(" ", style="")
    request_tabs.append(
        " Headers ",
        style=(
            "bold #1f2329 on #98c379"
            if (
                state.selected_history_detail_block == "request"
                and state.selected_history_request_tab == "headers"
            )
            else "bold #d7dae0 on #3a3f4b"
        ),
    )

    request_content: RenderableType
    request_visible_rows = max(_home_response_visible_rows(viewport_height) - 2, 4)
    if state.selected_history_request_tab == "headers":
        request_lines = list(range(_response_header_row_count(entry.request_headers)))
        state.clamp_history_request_scroll_offset(
            len(request_lines),
            request_visible_rows,
        )
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content = _render_response_headers(
            entry.request_headers,
            request_start,
            request_end,
        )
    else:
        request_lines = _response_body_lines(entry.request_body, viewport_width)
        state.clamp_history_request_scroll_offset(
            len(request_lines),
            request_visible_rows,
        )
        request_start = state.history_request_scroll_offset
        request_end = min(request_start + request_visible_rows, len(request_lines))
        request_content = _render_response_body(
            entry.request_body,
            viewport_width,
            request_start,
            request_end,
        )

    response_tabs = Text()
    response_tabs.append(
        "Response ",
        style=(
            "bold #98c379"
            if state.selected_history_detail_block == "response"
            else "bold #d7dae0"
        ),
    )
    response_tabs.append(
        " Body ",
        style=(
            "bold #1f2329 on #98c379"
            if (
                state.selected_history_detail_block == "response"
                and state.selected_history_response_tab == "body"
            )
            else "bold #d7dae0 on #3a3f4b"
        ),
    )
    response_tabs.append(" ", style="")
    response_tabs.append(
        " Headers ",
        style=(
            "bold #1f2329 on #98c379"
            if (
                state.selected_history_detail_block == "response"
                and state.selected_history_response_tab == "headers"
            )
            else "bold #d7dae0 on #3a3f4b"
        ),
    )

    response_content: RenderableType
    response_visible_rows = max(_home_response_visible_rows(viewport_height) - 2, 4)
    if state.selected_history_response_tab == "headers":
        response_lines = list(range(_response_header_row_count(entry.response_headers)))
        state.clamp_history_response_scroll_offset(
            len(response_lines),
            response_visible_rows,
        )
        start = state.history_response_scroll_offset
        end = min(start + response_visible_rows, len(response_lines))
        response_content = _render_response_headers(
            entry.response_headers,
            start,
            end,
        )
    else:
        response_lines = _response_body_lines(entry.response_body, viewport_width)
        state.clamp_history_response_scroll_offset(
            len(response_lines),
            response_visible_rows,
        )
        start = state.history_response_scroll_offset
        end = min(start + response_visible_rows, len(response_lines))
        response_content = _render_response_body(
            entry.response_body,
            viewport_width,
            start,
            end,
        )

    return Panel(
        Group(summary, request_tabs, request_content, response_tabs, response_content),
        title="Details",
        subtitle=(
            _history_detail_caption(
                state,
                request_start,
                request_end,
                len(request_lines),
                start,
                end,
                len(response_lines),
            )
            if state.mode == "HISTORY_RESPONSE_SELECT"
            else "e enters response"
        ),
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _history_auth_summary(entry: HistoryEntry) -> tuple[str, str]:
    if entry.auth_type == "basic":
        return ("Basic Auth via Authorization header", "#e5c07b")
    if entry.auth_type == "bearer":
        return ("Bearer Token via Authorization header", "#e5c07b")
    if entry.auth_type == "api-key":
        if entry.auth_location == "query":
            name = entry.auth_name or "query key"
            return (f"API Key via query param {name}", "#e5c07b")
        name = entry.auth_name or "header"
        return (f"API Key via header {name}", "#e5c07b")
    if entry.auth_type == "cookie":
        name = entry.auth_name or "cookie"
        return (f"Cookie Auth via Cookie header ({name})", "#e5c07b")
    if entry.auth_type == "custom-header":
        name = entry.auth_name or "custom header"
        return (f"Custom Header via {name}", "#e5c07b")
    if entry.auth_type == "oauth2-client-credentials":
        return ("OAuth 2.0 Client Credentials via Authorization header", "#e5c07b")
    return ("No Auth", "#7f848e")


def _history_headers_block(headers: list[tuple[str, str]]) -> str:
    if not headers:
        return "-"
    lines = [f"{key}: {value}" for key, value in headers[:12]]
    if len(headers) > 12:
        lines.append(f"… (+{len(headers) - 12} more)")
    return "\n".join(lines)


def _history_time_label(created_at: str) -> str:
    if not created_at:
        return "-"
    if len(created_at) >= 19:
        return created_at[:19].replace("T", " ")
    return created_at.replace("T", " ")


def _history_sidebar_caption(
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


def _history_detail_caption(
    state: PiespectorState,
    request_start: int,
    request_end: int,
    request_total: int,
    response_start: int,
    response_end: int,
    response_total: int,
) -> str:
    if state.selected_history_detail_block == "request":
        block = "Request"
        tab = state.selected_history_request_tab.title()
        start = request_start
        end = request_end
        total = request_total
        unit = "Rows" if state.selected_history_request_tab == "headers" else "Lines"
    else:
        block = "Response"
        tab = state.selected_history_response_tab.title()
        start = response_start
        end = response_end
        total = response_total
        unit = "Rows" if state.selected_history_response_tab == "headers" else "Lines"
    return (
        f"{block} / {tab}  |  {unit} {start + 1}-{end} of {total}  |  j/k blocks  |  h/l tabs  |  ctrl+u up  |  ctrl+d down  |  e viewer  |  Esc back"
    )


def _env_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 20
    return max(viewport_height - 6, 1)


def _render_env_viewport(
    state: PiespectorState, viewport_height: int | None
) -> RenderableType:
    selector = Text()
    for index, env_name in enumerate(state.env_names):
        if index:
            selector.append(" ")
        is_active = env_name == state.selected_env_name
        selector.append(
            f" {env_name} ",
            style=(
                "bold #1f2329 on #61afef"
                if is_active
                else "bold #abb2bf on #343944"
            ),
        )

    items = state.get_env_items()
    if not items:
        empty = Text()
        empty.append("No registered values.\n", style="bold #d7dae0")
        empty.append("Use ", style="#7f848e")
        empty.append(":set KEY=value", style="bold #98c379")
        empty.append(" to add one.", style="#7f848e")
        return Panel(
            Group(selector, Align.left(empty)),
            title="Env",
            border_style="#4b5263",
            box=box.ROUNDED,
            padding=(1, 2),
            subtitle=_env_caption(state, 0, 0, 0),
            subtitle_align="left",
        )

    visible_rows = _env_visible_rows(viewport_height)
    state.clamp_env_scroll_offset(visible_rows)
    start = state.env_scroll_offset
    end = min(start + visible_rows, len(items))
    visible_items = items[start:end]

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #abb2bf",
        border_style="#3f4550",
        row_styles=["on #2c313a", "on #262b33"],
        padding=(0, 1),
    )
    key_header = Text("Key", style="bold #e5c07b")
    value_header = Text("Value", style="bold #d7dae0")
    if state.mode in {"ENV_SELECT", "ENV_EDIT"}:
        if state.selected_env_field_index == 0:
            key_header = Text("Key", style="bold #1f2329 on #61afef")
        else:
            value_header = Text("Value", style="bold #1f2329 on #61afef")
    table.add_column("#", width=4, justify="right", style="bold #7f848e")
    table.add_column(key_header, ratio=2, style="bold #e5c07b")
    table.add_column(value_header, ratio=3, style="#d7dae0")

    for index, (key, value) in enumerate(visible_items, start=start):
        row_style = None
        if state.current_tab == "env" and index == state.selected_env_index:
            row_style = "bold #1f2329 on #98c379"
        table.add_row(str(index + 1), key, value, style=row_style)

    return Panel(
        Group(selector, table),
        title="Env",
        subtitle=_env_caption(state, start, end, len(items)),
        subtitle_align="left",
        border_style="#4b5263",
        box=box.ROUNDED,
    )


def _env_caption(state: PiespectorState, start: int, end: int, total: int) -> str:
    parts = [f"Env {state.active_env_label()}"]
    if total > 0:
        parts.append(f"Rows {start + 1}-{end} of {total}")
    if state.mode == "NORMAL":
        parts.append("h/l envs")
        parts.append("j/k rows")
    if state.mode == "ENV_SELECT":
        parts.append("h/l fields")
    if state.mode == "ENV_EDIT":
        parts.append("enter save")
    parts.append("a add")
    parts.append(":new NAME")
    parts.append(":rename NAME")
    parts.append(":del")
    parts.append(":set KEY=value")
    parts.append(":edit")
    parts.append(":del KEY")
    return "  |  ".join(parts)


def _hint_items(state: PiespectorState) -> list[tuple[str, str]]:
    if state.mode == "CONFIRM":
        return [("y", "confirm"), ("n", "cancel"), ("esc", "cancel")]

    if state.mode == "COMMAND":
        return [("enter", "run"), ("esc", "cancel")]

    if state.mode == "SEARCH":
        return [
            ("tab", "complete"),
            ("enter", "filter" if state.current_tab == "history" else "open"),
            ("esc", "cancel"),
        ]

    if state.mode == "HOME_SECTION_SELECT":
        return [
            ("h/l", "sections"),
            ("e", "open"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HOME_REQUEST_SELECT":
        return [
            ("j/k", "fields"),
            ("e", "edit"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HOME_AUTH_SELECT":
        return [
            ("j/k", "rows"),
            ("e", "edit"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HOME_PARAMS_SELECT":
        return [
            ("j/k", "rows"),
            ("h/l", "fields"),
            ("space", "toggle"),
            ("e", "edit"),
            ("a", "add"),
            ("d", "delete"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HOME_HEADERS_SELECT":
        return [
            ("j/k", "rows"),
            ("h/l", "fields"),
            ("space", "toggle"),
            ("e", "edit"),
            ("a", "add"),
            ("d", "delete"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HOME_BODY_SELECT":
        hints = [
            ("j/k", "rows"),
            ("space", "toggle"),
            ("e", "edit"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
            (":", "command"),
        ]
        request = state.get_active_request()
        if request is not None and request.body_type in {"form-data", "x-www-form-urlencoded"}:
            hints.insert(3, ("a", "add"))
            hints.insert(4, ("d", "delete"))
        else:
            hints = [item for item in hints if item[0] != "space"]
        return hints

    if state.mode == "HOME_BODY_TYPE_EDIT":
        return [
            ("h/l", "type"),
            ("e", "open"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode == "HOME_BODY_RAW_TYPE_EDIT":
        return [
            ("h/l", "raw"),
            ("e", "open"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode == "HOME_BODY_TEXTAREA":
        return [("ctrl+s", "save"), ("esc", "cancel")]

    if state.mode == "HOME_RESPONSE_TEXTAREA":
        return _response_copy_hint_items()

    if state.mode == "HISTORY_RESPONSE_TEXTAREA":
        return _response_copy_hint_items()

    if state.mode == "HOME_REQUEST_METHOD_EDIT":
        return [
            ("h/l", "method"),
            ("enter", "save"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "cancel"),
        ]

    if state.mode == "HOME_AUTH_TYPE_EDIT":
        return [
            ("h/l", "type"),
            ("e", "open"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode == "HOME_AUTH_LOCATION_EDIT":
        field = state.selected_auth_field()
        label = "client auth" if field is not None and field[0] == "auth_oauth_client_authentication" else "location"
        return [
            ("h/l", label),
            ("e", "open"),
            ("s", "send"),
            ("v", "response"),
            ("ctrl+u/d", "response"),
            ("esc", "back"),
        ]

    if state.mode == "HOME_RESPONSE_SELECT":
        return [
            ("h/l", "tabs"),
            ("e", "viewer"),
            ("ctrl+u/d", "scroll"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode in {"HOME_REQUEST_EDIT", "HOME_AUTH_EDIT", "HOME_PARAMS_EDIT", "HOME_HEADERS_EDIT", "HOME_BODY_EDIT", "ENV_EDIT"}:
        return [("enter", "save"), ("ctrl+c/v", "copy/paste"), ("esc", "cancel")]

    if state.mode == "ENV_SELECT":
        return [
            ("h/l", "fields"),
            ("e", "edit"),
            ("a", "add"),
            ("d", "delete"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.mode == "HISTORY_RESPONSE_SELECT":
        return [
            ("j/k", "blocks"),
            ("h/l", "tabs"),
            ("e", "viewer"),
            ("ctrl+u/d", "scroll"),
            ("esc", "back"),
            (":", "command"),
        ]

    if state.current_tab == "home":
        return [
            ("j/k", "sidebar"),
            ("h/l", "opened"),
            ("s", "search"),
            ("e", "open/edit"),
            ("esc", "collapse"),
            (":", "command"),
        ]

    if state.current_tab == "env":
        return [
            ("h/l", "envs"),
            ("j/k", "rows"),
            ("a", "add"),
            ("e", "edit"),
            (":", "command"),
        ]

    if state.current_tab == "history":
        return [
            ("j/k", "entries"),
            ("s", "search"),
            ("e", "response"),
            (":", "command"),
        ]

    if state.current_tab == "help":
        return [
            ("esc", "back"),
            (":", "command"),
        ]

    return []


def render_status_line(state: PiespectorState) -> Text:
    text = Text()
    mode_label, context_label = _mode_and_context(state)
    text.append(f" {mode_label} ", style="bold #1f2329 on #61afef")
    text.append(" | ", style="bold #abb2bf on #3a3f4b")
    text.append(f" {context_label} ", style="bold #d7dae0 on #3a3f4b")
    for index, (key, label) in enumerate(_hint_items(state)):
        text.append("  ", style="")
        text.append(f" {key} ", style="bold #1f2329 on #98c379")
        text.append(f" {label} ", style="bold #d7dae0 on #3a3f4b")
    if state.current_tab == "home":
        text.append("  ", style="")
        text.append(" env ", style="bold #1f2329 on #e5c07b")
        text.append(
            f" {state.active_env_label()} ",
            style="bold #d7dae0 on #3a3f4b",
        )
    return text


def _append_edit_buffer_preview(text: Text, state: PiespectorState) -> None:
    cursor_index = max(0, min(state.edit_cursor_index, len(state.edit_buffer)))
    before = state.edit_buffer[:cursor_index]
    after = state.edit_buffer[cursor_index:]
    text.append(before, style="bold #d7dae0")
    text.append("|", style="bold #61afef")
    text.append(after, style="bold #d7dae0")
    match = placeholder_match(
        state.edit_buffer,
        cursor_index,
        sorted(state.env_pairs),
    )
    if match is not None and match.suggestion != match.prefix:
        text.append(f"  env: {match.suggestion}", style="#7f848e")


def _append_completion_hint(text: Text, current_value: str, matches: list[str]) -> None:
    if not matches:
        return
    first = matches[0]
    if first != current_value and first.startswith(current_value):
        suffix = first[len(current_value) :]
        if suffix:
            text.append(suffix, style="#7f848e")
    else:
        previews = matches[:3]
        text.append("  ", style="")
        text.append("  |  ".join(previews), style="#7f848e")
        if len(matches) > 3:
            text.append(f"  (+{len(matches) - 3} more)", style="#5c6370")
        return
    if len(matches) > 1:
        text.append(f"  (+{len(matches) - 1} more)", style="#5c6370")


def _append_path_completion_hint(text: Text, current_value: str) -> None:
    _append_completion_hint(text, current_value, filesystem_path_completions(current_value))


def render_command_line(state: PiespectorState) -> Text:
    text = Text()
    if state.mode == "CONFIRM":
        text.append(state.confirm_prompt, style="bold #e5c07b")
    elif state.mode == "COMMAND":
        text.append(f":{state.command_buffer}", style="bold #d7dae0")
        _append_completion_hint(
            text,
            state.command_buffer,
            command_completion_matches(state, state.command_buffer),
        )
    elif state.mode == "SEARCH":
        text.append(f"Search {state.command_buffer}", style="bold #d7dae0")
        completion = (
            history_search_completion(state, state.command_buffer)
            if state.current_tab == "history"
            else search_completion(state, state.command_buffer)
        )
        if (
            completion is not None
            and completion != state.command_buffer
            and completion.lower().startswith(state.command_buffer.lower())
        ):
            suffix = completion[len(state.command_buffer) :]
            if suffix:
                text.append(suffix, style="#7f848e")
        else:
            matches = (
                history_search_matches(state, state.command_buffer)
                if state.current_tab == "history"
                else search_matches(state, state.command_buffer)
            )
            if matches:
                previews = [
                    history_search_display(match)
                    if state.current_tab == "history"
                    else match.display
                    for match in matches[:3]
                ]
                text.append("  ", style="")
                text.append("  |  ".join(previews), style="#7f848e")
                if len(matches) > 3:
                    text.append(f"  (+{len(matches) - 3} more)", style="#5c6370")
    elif state.mode == "HOME_REQUEST_EDIT":
        _field_name, label = state.selected_request_field()
        text.append(f"Edit {label}=", style="bold #d7dae0")
        _append_edit_buffer_preview(text, state)
    elif state.mode == "HOME_REQUEST_METHOD_EDIT":
        text.append(f"Method {state.edit_buffer or 'GET'}  h/l change, Enter save", style="bold #d7dae0")
    elif state.mode == "HOME_AUTH_EDIT":
        field = state.selected_auth_field()
        label = field[1] if field is not None else "Auth"
        text.append(f"Edit {label}=", style="bold #d7dae0")
        _append_edit_buffer_preview(text, state)
    elif state.mode == "HOME_AUTH_TYPE_EDIT":
        text.append("Auth type: h/l change, e open", style="bold #d7dae0")
    elif state.mode == "HOME_AUTH_LOCATION_EDIT":
        field = state.selected_auth_field()
        if field is not None and field[0] == "auth_oauth_client_authentication":
            text.append("OAuth client auth: h/l change, e open", style="bold #d7dae0")
        else:
            text.append("API key location: h/l change, e open", style="bold #d7dae0")
    elif state.mode == "HOME_PARAMS_EDIT":
        if state.params_creating_new:
            text.append("New key=", style="bold #d7dae0")
        else:
            item = state.get_active_request_params()
            selected_key = (
                item[state.selected_param_index].key
                if item and state.selected_param_index < len(item)
                else ""
            )
            field_name, _field_label = state.selected_param_field()
            if field_name == "key":
                text.append("Edit key=", style="bold #d7dae0")
            else:
                text.append(f"Edit {selected_key}=", style="bold #d7dae0")
        _append_edit_buffer_preview(text, state)
    elif state.mode == "HOME_HEADERS_EDIT":
        if state.headers_creating_new:
            text.append("New key=", style="bold #d7dae0")
        else:
            item = state.get_active_request_headers()
            selected_key = (
                item[state.selected_header_index].key
                if item and state.selected_header_index < len(item)
                else ""
            )
            field_name, _field_label = state.selected_header_field()
            if field_name == "key":
                text.append("Edit key=", style="bold #d7dae0")
            else:
                text.append(f"Edit {selected_key}=", style="bold #d7dae0")
        _append_edit_buffer_preview(text, state)
    elif state.mode == "HOME_BODY_TYPE_EDIT":
        text.append("Body type: h/l change, e open", style="bold #d7dae0")
    elif state.mode == "HOME_BODY_RAW_TYPE_EDIT":
        text.append("Raw type: h/l change, e open", style="bold #d7dae0")
    elif state.mode == "HOME_BODY_TEXTAREA":
        if state.message:
            text.append(state.message, style="bold #e06c75")
        else:
            text.append("Raw body editor", style="bold #d7dae0")
    elif state.mode == "HOME_BODY_EDIT":
        request = state.get_active_request()
        text.append(
            "Path " if request is not None and request.body_type == "binary" else "Body ",
            style="bold #d7dae0",
        )
        _append_edit_buffer_preview(text, state)
        if request is not None and request.body_type == "binary":
            _append_path_completion_hint(text, state.edit_buffer)
    elif state.mode == "ENV_EDIT":
        if state.env_creating_new:
            text.append("New key=", style="bold #d7dae0")
        else:
            item = state.get_selected_env_item()
            key = item[0] if item is not None else ""
            field_name, field_label = state.selected_env_field()
            if field_name == "key":
                text.append("Edit key=", style="bold #d7dae0")
            else:
                text.append(f"Edit {key}=", style="bold #d7dae0")
        _append_edit_buffer_preview(text, state)
    elif state.message:
        text.append(state.message, style="bold #d7dae0")
    return text
