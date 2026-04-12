from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Tree

from piespector.domain.workspace import SidebarNode
from piespector.screens.home import messages
from piespector.screens.home.request.method_selection import method_color
from piespector.screens.home.selection import home_selection
from piespector.widget.tree import (
    PiespectorTree,
    move_cursor as tree_move_cursor,
    rebuild as rebuild_tree,
)

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class CollectionsSidebar(Widget):
    selected_sidebar_index = reactive(0)

    class SelectionChanged(Message):
        def __init__(self, sidebar: CollectionsSidebar, index: int) -> None:
            super().__init__()
            self.sidebar = sidebar
            self.index = index

        @property
        def control(self) -> CollectionsSidebar:
            return self.sidebar

    class RequestOpened(Message):
        def __init__(
            self,
            sidebar: CollectionsSidebar,
            index: int,
            request_id: str,
        ) -> None:
            super().__init__()
            self.sidebar = sidebar
            self.index = index
            self.request_id = request_id

        @property
        def control(self) -> CollectionsSidebar:
            return self.sidebar

    class ExpansionChanged(Message):
        def __init__(
            self,
            sidebar: CollectionsSidebar,
            index: int,
            expanded: bool,
        ) -> None:
            super().__init__()
            self.sidebar = sidebar
            self.index = index
            self.expanded = expanded

        @property
        def control(self) -> CollectionsSidebar:
            return self.sidebar

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._items: list[SidebarNode] = []

    def compose(self) -> ComposeResult:
        yield Static("Collections", classes="panel-title", id="sidebar-title")
        yield PiespectorTree("Collections", id="sidebar-tree")
        yield Static("", classes="panel-subtitle", id="sidebar-subtitle")

    def on_mount(self) -> None:
        tree = self.query_one("#sidebar-tree", PiespectorTree)
        tree.show_root = False
        tree.focus()
        self.border_title = "Collections"

    def refresh_from_state(self, state: PiespectorState, visible_rows: int) -> None:
        self._items = state.get_sidebar_nodes()
        self.selected_sidebar_index = self._clamp_index(state.selected_sidebar_index)
        self._rebuild_tree(state)
        self._sync_cursor()
        self._refresh_subtitle(state, visible_rows)
        self._sync_focus(state)

    def sync_cursor(self, selected_index: int) -> None:
        self.selected_sidebar_index = self._clamp_index(selected_index)
        self._sync_cursor()

    def _clamp_index(self, index: int) -> int:
        if not self._items:
            return 0
        return max(0, min(index, len(self._items) - 1))

    def _sidebar_tree(self) -> PiespectorTree:
        return self.query_one("#sidebar-tree", PiespectorTree)

    def _refresh_subtitle(self, state: PiespectorState, visible_rows: int) -> None:
        start = state.request_scroll_offset
        end = min(start + visible_rows, len(self._items))
        caption = messages.home_sidebar_caption(state, start, end, len(self._items))
        self.query_one("#sidebar-subtitle", Static).update(caption)

    def _sync_focus(self, state: PiespectorState) -> None:
        tree = self._sidebar_tree()
        selected = home_selection(state).panel == "sidebar"
        if selected and tree.can_focus and not tree.has_focus:
            tree.focus()
        elif not selected and tree.has_focus:
            tree.blur()

    def _rebuild_tree(self, state: PiespectorState) -> None:
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
                for item in self._items
            ),
            tuple(sorted(state.collapsed_collection_ids)),
            tuple(sorted(state.collapsed_folder_ids)),
        )

        def build(tree: PiespectorTree) -> None:
            parent_stack: list[tuple[object, int]] = [(tree.root, -1)]
            for index, item in enumerate(self._items):
                while len(parent_stack) > 1 and parent_stack[-1][1] >= item.depth:
                    parent_stack.pop()
                parent_node = parent_stack[-1][0]

                if item.kind == "request":
                    label = Text()
                    label.append(f"{item.method:7s}", style=method_color(item.method))
                    label.append(item.label)
                    parent_node.add_leaf(label, data=index)
                    continue

                collapsed_ids = (
                    state.collapsed_collection_ids
                    if item.kind == "collection"
                    else state.collapsed_folder_ids
                )
                marker = "[+]" if item.node_id in collapsed_ids else "[-]"
                label = Text(f"{marker} {item.label}")
                node = parent_node.add(
                    label,
                    data=index,
                    expand=item.node_id not in collapsed_ids,
                )
                parent_stack.append((node, item.depth))

        rebuild_tree(self._sidebar_tree(), signature, build)

    def _sync_cursor(self) -> None:
        if not self._items:
            return
        tree = self._sidebar_tree()
        if tree.cursor_line == self.selected_sidebar_index:
            return
        tree_move_cursor(tree, self.selected_sidebar_index)

    def _sync_selection_from_tree_event(
        self,
        event: Tree.NodeHighlighted | Tree.NodeSelected | Tree.NodeExpanded | Tree.NodeCollapsed,
    ) -> int | None:
        index = event.node.data
        if not isinstance(index, int):
            return None
        tree = event.control
        if isinstance(tree, PiespectorTree) and tree.sync_state.ignore_highlight_index == index:
            tree.sync_state.ignore_highlight_index = None
            return None
        self.selected_sidebar_index = self._clamp_index(index)
        return self.selected_sidebar_index

    @on(Tree.NodeHighlighted, "#sidebar-tree")
    def _on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        index = self._sync_selection_from_tree_event(event)
        if index is None:
            return
        event.stop()
        self.post_message(self.SelectionChanged(self, index))

    @on(Tree.NodeSelected, "#sidebar-tree")
    def _on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        index = self._sync_selection_from_tree_event(event)
        if index is None:
            return
        event.stop()
        item = self._items[index]
        if item.request_id is None:
            return
        self.post_message(self.RequestOpened(self, index, item.request_id))

    @on(Tree.NodeExpanded, "#sidebar-tree")
    def _on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        index = self._sync_selection_from_tree_event(event)
        if index is None:
            return
        event.stop()
        self.post_message(self.ExpansionChanged(self, index, True))

    @on(Tree.NodeCollapsed, "#sidebar-tree")
    def _on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        index = self._sync_selection_from_tree_event(event)
        if index is None:
            return
        event.stop()
        self.post_message(self.ExpansionChanged(self, index, False))
