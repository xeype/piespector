from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import HOME_SIDEBAR_LABEL
from piespector.screens.home import messages
from piespector.screens.home.jump_titles import render_panel_title
from piespector.screens.home.selection import home_selection
from piespector.screens.home.request.method_selection import method_color
from piespector.state import PiespectorState
from piespector.ui.selection import selected_element_style


def render_home_sidebar(
    state: PiespectorState,
    visible_rows: int,
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
        style = selected_element_style(
            state,
            selected=index == state.selected_sidebar_index,
        )
        if item.kind == "request":
            kind_cell = Text(item.method, style=method_color(item.method))
            name_cell = Text(item.label)
        elif item.kind == "collection":
            kind_cell = Text("COLL")
            marker = "[+]" if item.node_id in state.collapsed_collection_ids else "[-]"
            name_cell = Text.assemble(
                (f"{marker} "),
                (item.label),
            )
        else:
            kind_cell = Text("DIR")
            marker = "[+]" if item.node_id in state.collapsed_folder_ids else "[-]"
            name_cell = Text.assemble(
                (f"{marker} "),
                (item.label),
            )
        tree_prefix = _sidebar_tree_prefix(items, index)
        name_with_tree = Text(tree_prefix)
        name_with_tree.append_text(name_cell)
        table.add_row(
            kind_cell,
            name_with_tree,
            style=style,
        )

    filler_rows = max(visible_rows - len(visible_items), 0)
    for _ in range(filler_rows):
        table.add_row("", "")

    caption = messages.home_sidebar_caption(state, start, end, len(items))
    selected = home_selection(state).panel == "sidebar"
    title = render_panel_title(HOME_SIDEBAR_LABEL, selected=selected)
    return Panel(
        table,
        title=title,
        title_align="right",
        subtitle=caption,
        subtitle_align="left",
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
