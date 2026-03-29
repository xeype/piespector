from __future__ import annotations

from rich import box
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.screens.home import messages, styles
from piespector.state import PiespectorState


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
        style = None
        kind_style_override = None
        name_style_override = None
        if index == state.selected_sidebar_index:
            style = styles.pill_style(styles.TEXT_SUCCESS)
            kind_style_override = f"bold {styles.TEXT_INVERSE}"
            name_style_override = f"bold {styles.TEXT_INVERSE}"
        if item.kind == "request":
            kind_cell = Text(
                item.method,
                style=kind_style_override or styles.method_style(item.method),
            )
            name_style = f"bold {styles.TEXT_PRIMARY}"
            label = item.label
        elif item.kind == "collection":
            if style is None:
                style = styles.ROW_COLLECTION
            kind_cell = Text("COLL", style=kind_style_override or f"bold {styles.TEXT_WARNING}")
            name_style = f"bold {styles.TEXT_COLLECTION}"
            marker = "[+]" if item.node_id in state.collapsed_collection_ids else "[-]"
            label = f"{marker} {item.label}"
        else:
            if style is None:
                style = styles.ROW_FOLDER
            kind_cell = Text("DIR", style=kind_style_override or f"bold {styles.TEXT_URL}")
            name_style = f"bold {styles.TEXT_FOLDER}"
            marker = "[+]" if item.node_id in state.collapsed_folder_ids else "[-]"
            label = f"{marker} {item.label}"
        tree_prefix = _sidebar_tree_prefix(items, index)
        table.add_row(
            kind_cell,
            Text.assemble(
                (tree_prefix, styles.TEXT_TREE_GUIDE),
                (label, name_style_override or name_style),
            ),
            style=style,
        )

    filler_rows = max(visible_rows - len(visible_items), 0)
    for _ in range(filler_rows):
        table.add_row("", "")

    caption = messages.home_sidebar_caption(state, start, end, len(items))
    return Panel(
        table,
        title="Collections",
        subtitle=caption,
        subtitle_align="left",
        border_style=styles.BORDER,
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

