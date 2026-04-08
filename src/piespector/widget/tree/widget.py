from __future__ import annotations

from rich.style import Style
from textual.binding import Binding
from textual.widgets import Tree
from textual.widgets._tree import TreeNode

from .state import TreeSyncState


class PiespectorTree(Tree, inherit_bindings=False):
    """Tree widget with vim-friendly defaults and typed sync state.

    Differences from Textual's ``Tree``:

    - Arrow keys, Enter, and Shift+arrow variants are stripped
      (``inherit_bindings=False``); the app controller drives those via
      programmatic action calls so they never conflict with normal-mode
      navigation.
    - ``j`` / ``k`` / ``e`` are bound directly on the widget so that when
      the tree already owns focus the keys are handled here without bubbling
      to the controller first — consistent with :class:`PiespectorSelect`.
    - Cursor highlight is suppressed when the widget is unfocused, so the
      selection ring only appears when the tree actually owns keyboard focus.
    - All sync bookkeeping lives in ``.sync_state`` (:class:`TreeSyncState`)
      instead of scattered monkey-patched attributes.
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Browse Down", show=False),
        Binding("k", "cursor_up", "Browse Up", show=False),
        Binding("e", "confirm", "Confirm", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sync_state = TreeSyncState()

    def action_confirm(self) -> None:
        """Toggle expandable nodes; select leaf nodes."""
        if self.cursor_line < 0:
            return
        try:
            line = self._tree_lines[self.cursor_line]
        except IndexError:
            return
        node = line.path[-1]
        if node.allow_expand:
            self.action_toggle_node()
        else:
            self.action_select_cursor()

    def render_label(self, node: TreeNode, base_style: Style, style: Style) -> object:
        if not self.has_focus:
            style = Style.null()
        return super().render_label(node, base_style, style)
