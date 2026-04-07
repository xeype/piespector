from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .widget import PiespectorTree


def rebuild(
    tree: PiespectorTree,
    signature: Any,
    build_fn: Callable[[PiespectorTree], None],
) -> None:
    """Rebuild tree nodes if *signature* differs from the last known value.

    Clears the tree, expands the root, calls *build_fn* to populate nodes,
    and stores *signature* on ``tree.sync_state``.  A no-op when the
    signature is unchanged.
    """
    if tree.sync_state.signature == signature:
        return
    tree.sync_state.signature = signature
    tree.clear()
    tree.root.expand()
    build_fn(tree)


def move_cursor(tree: PiespectorTree, index: int) -> None:
    """Move the cursor to *index* and suppress the resulting highlight event.

    Sets ``tree.sync_state.ignore_highlight_index`` so the screen-level
    ``on_tree_node_highlighted`` handler skips the event that fires as a
    side-effect of the programmatic cursor move.
    """
    tree.sync_state.ignore_highlight_index = index
    tree.cursor_line = index
    tree.scroll_to_line(index, animate=False)
