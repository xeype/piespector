from __future__ import annotations

from copy import deepcopy
from urllib import parse
from uuid import uuid4

from piespector.domain.editor import BODY_TEXT_EDITOR_TYPES, HOME_EDITOR_TAB_REQUEST, TAB_HOME
from piespector.domain.modes import MODE_HOME_SECTION_SELECT, MODE_NORMAL
from piespector.domain.requests import RequestDefinition, RequestKeyValue, parse_headers_text, parse_query_text
from piespector.domain.workspace import CollectionDefinition, FolderDefinition, SidebarNode


class WorkspaceStateMixin:
    def get_request_items(self) -> list[RequestDefinition]:
        return self.requests

    def _append_collection(self, collection: CollectionDefinition) -> None:
        self.collections.append(collection)
        self._collections_by_id[collection.collection_id] = collection

    def _extend_collections(self, collections: list[CollectionDefinition]) -> None:
        self.collections.extend(collections)
        for collection in collections:
            self._collections_by_id[collection.collection_id] = collection

    def _append_folder(self, folder: FolderDefinition) -> None:
        self.folders.append(folder)
        self._folders_by_id[folder.folder_id] = folder

    def _extend_folders(self, folders: list[FolderDefinition]) -> None:
        self.folders.extend(folders)
        for folder in folders:
            self._folders_by_id[folder.folder_id] = folder

    def _append_request(self, request: RequestDefinition) -> None:
        self.requests.append(request)
        self._requests_by_id[request.request_id] = request

    def _extend_requests(self, requests: list[RequestDefinition]) -> None:
        self.requests.extend(requests)
        for request in requests:
            self._requests_by_id[request.request_id] = request

    def _pop_request(self, index: int) -> RequestDefinition:
        request = self.requests.pop(index)
        self._requests_by_id.pop(request.request_id, None)
        return request

    def get_collection_by_id(self, collection_id: str | None) -> CollectionDefinition | None:
        if collection_id is None:
            return None
        return self._collections_by_id.get(collection_id)

    def get_folder_by_id(self, folder_id: str | None) -> FolderDefinition | None:
        if folder_id is None:
            return None
        return self._folders_by_id.get(folder_id)

    def folder_chain(self, folder_id: str | None) -> list[FolderDefinition]:
        chain: list[FolderDefinition] = []
        current_id = folder_id
        seen: set[str] = set()
        while current_id is not None and current_id not in seen:
            folder = self.get_folder_by_id(current_id)
            if folder is None:
                break
            chain.append(folder)
            seen.add(current_id)
            current_id = folder.parent_folder_id
        chain.reverse()
        return chain

    def current_request_container(self) -> tuple[str | None, str | None]:
        node = self.get_selected_sidebar_node()
        if node is not None:
            if node.kind == "collection":
                if node.node_id in self.collapsed_collection_ids:
                    return (None, None)
                return (node.node_id, None)
            if node.kind == "folder":
                folder = self.get_folder_by_id(node.node_id)
                if folder is not None and node.node_id not in self.collapsed_folder_ids:
                    return (folder.collection_id, folder.folder_id)
            if node.kind == "request":
                request = self.get_selected_request()
                if request is not None:
                    return (request.collection_id, request.folder_id)
        return (None, None)

    def get_request_by_id(self, request_id: str | None) -> RequestDefinition | None:
        if request_id is None:
            return None
        return self._requests_by_id.get(request_id)

    def get_sidebar_nodes(self) -> list[SidebarNode]:
        nodes: list[SidebarNode] = []

        for request_index, request in enumerate(self.requests):
            if request.collection_id is None:
                nodes.append(
                    SidebarNode(
                        kind="request",
                        node_id=request.request_id,
                        label=request.name,
                        depth=0,
                        request_id=request.request_id,
                        request_index=request_index,
                        method=request.method,
                    )
                )

        for collection in self.collections:
            nodes.append(
                SidebarNode(
                    kind="collection",
                    node_id=collection.collection_id,
                    label=collection.name,
                    depth=0,
                )
            )
            if collection.collection_id not in self.collapsed_collection_ids:
                nodes.extend(
                    self._sidebar_request_nodes_for_container(
                        collection.collection_id,
                        None,
                        depth=1,
                    )
                )
                nodes.extend(
                    self._sidebar_folder_nodes(
                        collection.collection_id,
                        None,
                        depth=1,
                    )
                )

        return nodes

    def _sidebar_request_nodes_for_container(
        self,
        collection_id: str,
        folder_id: str | None,
        *,
        depth: int,
    ) -> list[SidebarNode]:
        nodes: list[SidebarNode] = []
        for request_index, request in enumerate(self.requests):
            if request.collection_id != collection_id or request.folder_id != folder_id:
                continue
            nodes.append(
                SidebarNode(
                    kind="request",
                    node_id=request.request_id,
                    label=request.name,
                    depth=depth,
                    request_id=request.request_id,
                    request_index=request_index,
                    method=request.method,
                )
            )
        return nodes

    def _sidebar_folder_nodes(
        self,
        collection_id: str,
        parent_folder_id: str | None,
        *,
        depth: int,
    ) -> list[SidebarNode]:
        nodes: list[SidebarNode] = []
        for folder in self.folders:
            if (
                folder.collection_id != collection_id
                or folder.parent_folder_id != parent_folder_id
            ):
                continue
            nodes.append(
                SidebarNode(
                    kind="folder",
                    node_id=folder.folder_id,
                    label=folder.name,
                    depth=depth,
                )
            )
            if folder.folder_id not in self.collapsed_folder_ids:
                nodes.extend(
                    self._sidebar_request_nodes_for_container(
                        collection_id,
                        folder.folder_id,
                        depth=depth + 1,
                    )
                )
                nodes.extend(
                    self._sidebar_folder_nodes(
                        collection_id,
                        folder.folder_id,
                        depth=depth + 1,
                    )
                )
        return nodes

    def clamp_selected_sidebar_index(self) -> None:
        nodes = self.get_sidebar_nodes()
        if not nodes:
            self.selected_sidebar_index = 0
            return
        self.selected_sidebar_index = max(
            0, min(self.selected_sidebar_index, len(nodes) - 1)
        )

    def get_selected_sidebar_node(self) -> SidebarNode | None:
        nodes = self.get_sidebar_nodes()
        if not nodes:
            return None
        self.clamp_selected_sidebar_index()
        return nodes[self.selected_sidebar_index]

    def _set_selected_sidebar_by_request_id(self, request_id: str) -> None:
        for index, node in enumerate(self.get_sidebar_nodes()):
            if node.kind == "request" and node.request_id == request_id:
                self.selected_sidebar_index = index
                return

    def _set_selected_sidebar_node(self, kind: str, node_id: str) -> None:
        for index, node in enumerate(self.get_sidebar_nodes()):
            if node.kind == kind and node.node_id == node_id:
                self.selected_sidebar_index = index
                return

    def _selected_collection_id(self) -> str | None:
        node = self.get_selected_sidebar_node()
        if node is None:
            return None
        if node.kind == "collection":
            return node.node_id
        if node.kind == "folder":
            folder = self.get_folder_by_id(node.node_id)
            return folder.collection_id if folder is not None else None
        request = self.get_selected_request()
        return request.collection_id if request is not None else None

    def _selected_folder_id(self) -> str | None:
        node = self.get_selected_sidebar_node()
        if node is None:
            return None
        if node.kind == "folder":
            return node.node_id
        if node.kind != "request":
            return None
        request = self.get_selected_request()
        return request.folder_id if request is not None else None

    def _folder_navigation_ids(
        self,
        collection_id: str,
        parent_folder_id: str | None = None,
    ) -> list[str]:
        folder_ids: list[str] = []
        for folder in self.folders:
            if (
                folder.collection_id != collection_id
                or folder.parent_folder_id != parent_folder_id
            ):
                continue
            folder_ids.append(folder.folder_id)
            folder_ids.extend(
                self._folder_navigation_ids(collection_id, folder.folder_id)
            )
        return folder_ids

    def _expand_folder_ancestors(self, folder_id: str) -> None:
        folder = self.get_folder_by_id(folder_id)
        if folder is None:
            return
        self.collapsed_collection_ids.discard(folder.collection_id)
        for ancestor in self.folder_chain(folder.parent_folder_id):
            self.collapsed_folder_ids.discard(ancestor.folder_id)

    def _expand_request_ancestors(self, request: RequestDefinition) -> None:
        if request.collection_id is not None:
            self.collapsed_collection_ids.discard(request.collection_id)
        for folder in self.folder_chain(request.folder_id):
            self.collapsed_folder_ids.discard(folder.folder_id)

    def toggle_selected_sidebar_node(self) -> bool:
        node = self.get_selected_sidebar_node()
        if node is None:
            return False
        if node.kind == "collection":
            if node.node_id in self.collapsed_collection_ids:
                self.collapsed_collection_ids.discard(node.node_id)
            else:
                self.collapsed_collection_ids.add(node.node_id)
            self.clamp_selected_sidebar_index()
            self.active_request_id = None
            self.preview_request_id = None
            self.notify_requests_mutated()
            return True
        if node.kind == "folder":
            if node.node_id in self.collapsed_folder_ids:
                self.collapsed_folder_ids.discard(node.node_id)
            else:
                self.collapsed_folder_ids.add(node.node_id)
            self.clamp_selected_sidebar_index()
            self.active_request_id = None
            self.preview_request_id = None
            self.notify_requests_mutated()
            return True
        return False

    def collapse_selected_context(self) -> bool:
        node = self.get_selected_sidebar_node()
        if node is None:
            return False
        if node.kind == "collection":
            if node.node_id not in self.collapsed_collection_ids:
                self.collapsed_collection_ids.add(node.node_id)
                self.active_request_id = None
                self.preview_request_id = None
                self.notify_requests_mutated()
                return True
            return False
        if node.kind == "folder":
            if node.node_id not in self.collapsed_folder_ids:
                self.collapsed_folder_ids.add(node.node_id)
                self.active_request_id = None
                self.preview_request_id = None
                self.notify_requests_mutated()
                return True
            return False
        request = self.get_selected_request()
        if request is None:
            return False
        chain = self.folder_chain(request.folder_id)
        if chain:
            folder = chain[-1]
            self.collapsed_folder_ids.add(folder.folder_id)
            self._set_selected_sidebar_node("folder", folder.folder_id)
            self.active_request_id = None
            self.preview_request_id = None
            self.notify_requests_mutated()
            return True
        if request.collection_id is not None:
            self.collapsed_collection_ids.add(request.collection_id)
            self._set_selected_sidebar_node("collection", request.collection_id)
            self.active_request_id = None
            self.preview_request_id = None
            self.notify_requests_mutated()
            return True
        return False

    def _sync_request_from_selected_sidebar(self) -> None:
        node = self.get_selected_sidebar_node()
        if node is None or node.kind != "request" or node.request_id is None:
            self.preview_request_id = None
            self.active_request_id = None
            return
        if node.request_index is not None:
            self.selected_request_index = node.request_index
        request = self.get_request_by_id(node.request_id)
        if request is not None:
            self._expand_request_ancestors(request)
        self.open_selected_request()

    def sync_sidebar_selection(self, index: int) -> None:
        nodes = self.get_sidebar_nodes()
        if not nodes:
            self.selected_sidebar_index = 0
            self.preview_request_id = None
            self.active_request_id = None
            return
        self.selected_sidebar_index = max(0, min(index, len(nodes) - 1))
        self._sync_request_from_selected_sidebar()

    def set_selected_sidebar_node_expanded(self, expanded: bool) -> bool:
        node = self.get_selected_sidebar_node()
        if node is None:
            return False

        if node.kind == "collection":
            was_collapsed = node.node_id in self.collapsed_collection_ids
            if expanded:
                self.collapsed_collection_ids.discard(node.node_id)
            else:
                self.collapsed_collection_ids.add(node.node_id)
            changed = was_collapsed == expanded
        elif node.kind == "folder":
            was_collapsed = node.node_id in self.collapsed_folder_ids
            if expanded:
                self.collapsed_folder_ids.discard(node.node_id)
            else:
                self.collapsed_folder_ids.add(node.node_id)
            changed = was_collapsed == expanded
        else:
            return False

        if changed:
            self.active_request_id = None
            self.preview_request_id = None
            self.clamp_selected_sidebar_index()
            self.notify_requests_mutated()
        return changed

    def ensure_request_workspace(self) -> None:
        nodes = self.get_sidebar_nodes()
        if not nodes:
            self.selected_request_index = 0
            self.selected_sidebar_index = 0
            self.request_scroll_offset = 0
            self.response_scroll_offset = 0
            self.active_request_id = None
            self.preview_request_id = None
            self.open_request_ids = []
            self.request_workspace_initialized = True
            return

        self.clamp_selected_sidebar_index()
        self.clamp_selected_request_index()
        existing_ids = {request.request_id for request in self.requests}
        should_sync_selection = False
        self.open_request_ids = [
            request_id for request_id in self.open_request_ids if request_id in existing_ids
        ]
        if self.active_request_id not in existing_ids:
            self.active_request_id = None
        if self.preview_request_id not in existing_ids:
            self.preview_request_id = None

        selected_node = self.get_selected_sidebar_node()
        if (
            not self.request_workspace_initialized
            and (selected_node is None or selected_node.request_id is None)
        ):
            for index, node in enumerate(self.get_sidebar_nodes()):
                if node.request_id is not None:
                    self.selected_sidebar_index = index
                    selected_node = node
                    break
        if self.active_request_id is None:
            if self.preview_request_id is not None:
                self.active_request_id = self.preview_request_id
                should_sync_selection = True
            elif selected_node is not None and selected_node.request_id is not None:
                if not self.request_workspace_initialized:
                    self.preview_request_id = selected_node.request_id
                self.active_request_id = selected_node.request_id
                should_sync_selection = True
        if should_sync_selection and self.active_request_id is not None:
            self.sync_selected_request_to_active()
        self._clamp_selected_request_field_index()
        self.request_workspace_initialized = True

    def clamp_selected_request_index(self) -> None:
        if not self.requests:
            self.selected_request_index = 0
            return
        self.selected_request_index = max(
            0, min(self.selected_request_index, len(self.requests) - 1)
        )

    def clamp_request_scroll_offset(self, visible_rows: int) -> None:
        max_offset = max(len(self.get_sidebar_nodes()) - max(visible_rows, 1), 0)
        self.request_scroll_offset = max(0, min(self.request_scroll_offset, max_offset))

    def open_selected_request(self, *, pin: bool = False) -> None:
        request = self.get_selected_request()
        if request is None:
            self.active_request_id = None
            return
        self._expand_request_ancestors(request)
        self.preview_request_id = None if pin else request.request_id
        self.active_request_id = request.request_id
        self.request_workspace_initialized = True
        if pin and request.request_id not in self.open_request_ids:
            self.open_request_ids.append(request.request_id)
        self.response_scroll_offset = 0

    def select_request(self, step: int) -> None:
        nodes = self.get_sidebar_nodes()
        if not nodes:
            self.selected_sidebar_index = 0
            return
        self.selected_sidebar_index = (self.selected_sidebar_index + step) % len(nodes)
        self._sync_request_from_selected_sidebar()

    def select_collection(self, step: int) -> bool:
        if step == 0 or not self.collections:
            return False

        collection_ids = [collection.collection_id for collection in self.collections]
        current_collection_id = self._selected_collection_id()
        if current_collection_id in collection_ids:
            target_index = (
                collection_ids.index(current_collection_id) + step
            ) % len(collection_ids)
        else:
            target_index = 0 if step > 0 else len(collection_ids) - 1

        self._set_selected_sidebar_node("collection", collection_ids[target_index])
        self._sync_request_from_selected_sidebar()
        return True

    def select_folder(self, step: int) -> bool:
        if step == 0:
            return False

        collection_id = self._selected_collection_id()
        if collection_id is None:
            return False

        folder_ids = self._folder_navigation_ids(collection_id)
        if not folder_ids:
            return False

        current_folder_id = self._selected_folder_id()
        if current_folder_id in folder_ids:
            target_index = (folder_ids.index(current_folder_id) + step) % len(folder_ids)
        else:
            target_index = 0 if step > 0 else len(folder_ids) - 1

        target_folder_id = folder_ids[target_index]
        self._expand_folder_ancestors(target_folder_id)
        self._set_selected_sidebar_node("folder", target_folder_id)
        self._sync_request_from_selected_sidebar()
        return True

    def activate_request_by_index(self, index: int, *, pin: bool = False) -> None:
        if not self.requests:
            self.active_request_id = None
            self.selected_request_index = 0
            return
        self.selected_request_index = max(0, min(index, len(self.requests) - 1))
        self._set_selected_sidebar_by_request_id(self.requests[self.selected_request_index].request_id)
        self.open_selected_request(pin=pin)

    def sync_selected_request_to_active(self) -> None:
        if self.active_request_id is None:
            return
        for index, request in enumerate(self.requests):
            if request.request_id == self.active_request_id:
                self.selected_request_index = index
                self._set_selected_sidebar_by_request_id(request.request_id)
                return

    def cycle_open_request(self, step: int) -> None:
        self.ensure_request_workspace()
        if (
            self.preview_request_id is not None
            and self.preview_request_id not in self.open_request_ids
        ):
            if self.active_request_id == self.preview_request_id:
                if self.open_request_ids:
                    self.active_request_id = (
                        self.open_request_ids[-1] if step < 0 else self.open_request_ids[0]
                    )
                else:
                    self.active_request_id = None
            self.preview_request_id = None

        open_request_ids = [request.request_id for request in self.get_open_requests()]
        if not open_request_ids:
            return
        if self.active_request_id not in open_request_ids:
            self.active_request_id = open_request_ids[-1] if step < 0 else open_request_ids[0]
        current_index = open_request_ids.index(self.active_request_id)
        self.active_request_id = open_request_ids[
            (current_index + step) % len(open_request_ids)
        ]
        self.response_scroll_offset = 0
        self.sync_selected_request_to_active()

    def get_selected_request(self) -> RequestDefinition | None:
        node = self.get_selected_sidebar_node()
        if node is None or node.kind != "request":
            return None
        if node.request_id is None:
            return None
        return self.get_request_by_id(node.request_id)

    def get_active_request(self) -> RequestDefinition | None:
        self.ensure_request_workspace()
        if self.active_request_id is None:
            return None
        return self.get_request_by_id(self.active_request_id)

    def get_open_requests(self) -> list[RequestDefinition]:
        self.ensure_request_workspace()
        open_requests: list[RequestDefinition] = []
        for request_id in self.open_request_ids:
            request = self.get_request_by_id(request_id)
            if request is not None:
                open_requests.append(request)
        if (
            self.preview_request_id is not None
            and self.preview_request_id not in self.open_request_ids
        ):
            request = self.get_request_by_id(self.preview_request_id)
            if request is not None:
                open_requests.append(request)
        return open_requests

    def pin_active_request(self) -> RequestDefinition | None:
        self.ensure_request_workspace()
        request = self.get_active_request()
        if request is None:
            return None
        if request.request_id not in self.open_request_ids:
            self.open_request_ids.append(request.request_id)
        if self.preview_request_id == request.request_id:
            self.preview_request_id = None
        self.active_request_id = request.request_id
        self.request_workspace_initialized = True
        return request

    def close_active_request(self) -> RequestDefinition | None:
        self.ensure_request_workspace()
        request = self.get_active_request()
        if request is None:
            return None

        open_request_ids = [item.request_id for item in self.get_open_requests()]
        if request.request_id not in open_request_ids:
            return None

        current_index = open_request_ids.index(request.request_id)
        self.open_request_ids = [
            request_id
            for request_id in self.open_request_ids
            if request_id != request.request_id
        ]
        if self.preview_request_id == request.request_id:
            self.preview_request_id = None
        if request.transient:
            self.requests = [
                item for item in self.requests if item.request_id != request.request_id
            ]
        remaining_ids = [
            request_id for request_id in open_request_ids if request_id != request.request_id
        ]
        if remaining_ids:
            next_index = min(current_index, len(remaining_ids) - 1)
            self.active_request_id = remaining_ids[next_index]
            self.sync_selected_request_to_active()
        else:
            self.active_request_id = None
            self.clamp_selected_sidebar_index()
            self.clamp_selected_request_index()
        self.response_scroll_offset = 0
        self.mode = MODE_NORMAL
        self.message = f"Closed {request.name}."
        return request

    def ensure_request_selection_visible(self, visible_rows: int) -> None:
        self.clamp_selected_sidebar_index()
        if self.selected_sidebar_index < self.request_scroll_offset:
            self.request_scroll_offset = self.selected_sidebar_index
        elif self.selected_sidebar_index >= self.request_scroll_offset + visible_rows:
            self.request_scroll_offset = self.selected_sidebar_index - visible_rows + 1
        self.clamp_request_scroll_offset(visible_rows)

    def scroll_request_window(self, step: int, visible_rows: int) -> None:
        self.request_scroll_offset += step
        self.clamp_request_scroll_offset(visible_rows)

    def create_request(
        self,
        *,
        collection_id: str | None = None,
        folder_id: str | None = None,
    ) -> RequestDefinition:
        if collection_id is None and folder_id is None:
            collection_id, folder_id = self.current_request_container()
        request = RequestDefinition(
            name=f"Request {len(self.requests) + 1}",
            collection_id=collection_id,
            folder_id=folder_id,
        )
        self._append_request(request)
        self._expand_request_ancestors(request)
        self.current_tab = TAB_HOME
        self.home_editor_tab = HOME_EDITOR_TAB_REQUEST
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        self.mode = MODE_HOME_SECTION_SELECT
        self.message = ""
        self.notify_requests_mutated()
        return request

    def replay_selected_history_entry(self) -> RequestDefinition | None:
        entry = self.get_selected_history_entry()
        if entry is None:
            self.message = "No history entry selected."
            return None

        redacted_marker = "<redacted>"
        redacted_omitted = False
        auth_api_key_value = ""
        auth_cookie_value = ""
        auth_custom_header_value = ""
        header_items: list[RequestKeyValue] = []

        for key, value in entry.request_headers:
            normalized_key = key.strip()
            if not normalized_key:
                continue
            if value == redacted_marker:
                redacted_omitted = True
                continue
            if entry.auth_type in {"basic", "bearer"} and normalized_key.lower() == "authorization":
                continue
            if (
                entry.auth_type == "api-key"
                and entry.auth_location == "header"
                and entry.auth_name
                and normalized_key.lower() == entry.auth_name.lower()
            ):
                auth_api_key_value = value
                continue
            if entry.auth_type == "custom-header" and entry.auth_name:
                if normalized_key.lower() == entry.auth_name.lower():
                    auth_custom_header_value = value
                    continue
            if entry.auth_type == "cookie" and normalized_key.lower() == "cookie":
                if entry.auth_name and value != redacted_marker:
                    for cookie_key, cookie_value in parse_headers_text(value.replace(";", "\n")):
                        if cookie_key == entry.auth_name:
                            auth_cookie_value = cookie_value
                            break
                continue
            header_items.append(
                RequestKeyValue(key=normalized_key, value=value, enabled=True)
            )

        url_parts = parse.urlsplit(entry.url)
        base_url = parse.urlunsplit(
            (url_parts.scheme, url_parts.netloc, url_parts.path, "", url_parts.fragment)
        )
        query_items: list[RequestKeyValue] = []
        for key, value in parse.parse_qsl(url_parts.query, keep_blank_values=True):
            if (
                entry.auth_type == "api-key"
                and entry.auth_location == "query"
                and entry.auth_name
                and key == entry.auth_name
            ):
                if not auth_api_key_value:
                    auth_api_key_value = value
                continue
            query_items.append(RequestKeyValue(key=key, value=value, enabled=True))

        body_text = ""
        body_form_items: list[RequestKeyValue] = []
        body_urlencoded_items: list[RequestKeyValue] = []
        if entry.request_body_type in BODY_TEXT_EDITOR_TYPES:
            body_text = entry.request_body
        elif entry.request_body_type == "form-data":
            body_form_items = [
                RequestKeyValue(key=key, value=value, enabled=True)
                for key, value in parse_query_text(entry.request_body.replace("\n", "&"))
            ]
        elif entry.request_body_type == "x-www-form-urlencoded":
            body_urlencoded_items = [
                RequestKeyValue(key=key, value=value, enabled=True)
                for key, value in parse.parse_qsl(
                    entry.request_body,
                    keep_blank_values=True,
                )
            ]

        request_name = entry.source_request_name.strip() or "History Replay"
        replay = RequestDefinition(
            name=f"Replay {request_name}",
            method=entry.method.upper() or "GET",
            url=base_url,
            query_items=query_items,
            header_items=header_items,
            auth_type=(
                entry.auth_type
                if entry.auth_type in {"basic", "bearer", "api-key", "cookie", "custom-header"}
                else "none"
            ),
            auth_api_key_name=entry.auth_name or "X-API-Key",
            auth_api_key_value=auth_api_key_value,
            auth_api_key_location=entry.auth_location if entry.auth_location in {"header", "query"} else "header",
            auth_cookie_name=entry.auth_name or "session",
            auth_cookie_value=auth_cookie_value,
            auth_custom_header_name=entry.auth_name or "X-Auth-Token",
            auth_custom_header_value=auth_custom_header_value,
            transient=True,
            body_type=(
                entry.request_body_type
                if entry.request_body_type in {
                    "none",
                    "raw",
                    "form-data",
                    "x-www-form-urlencoded",
                    "graphql",
                    "binary",
                }
                else "none"
            ),
            body_text=body_text,
            body_form_items=body_form_items,
            body_urlencoded_items=body_urlencoded_items,
        )
        self._append_request(replay)
        self.current_tab = TAB_HOME
        self.home_editor_tab = HOME_EDITOR_TAB_REQUEST
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        self.mode = MODE_HOME_SECTION_SELECT
        self.message = (
            "Replayed history into a temporary request. Redacted secrets were omitted."
            if redacted_omitted
            else "Replayed history into a temporary request."
        )
        self.notify_requests_mutated()
        return replay

    def create_collection(self, name: str) -> CollectionDefinition:
        collection = CollectionDefinition(name=name)
        self._append_collection(collection)
        self.current_tab = TAB_HOME
        self.collapsed_collection_ids.add(collection.collection_id)
        self._set_selected_sidebar_node("collection", collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Created collection {name}."
        self.notify_requests_mutated()
        return collection

    def create_folder(self, name: str) -> FolderDefinition | None:
        collection_id, parent_folder_id = self.current_request_container()
        if collection_id is None:
            self.message = "Open a collection or folder first."
            return None
        folder = FolderDefinition(
            name=name,
            collection_id=collection_id,
            parent_folder_id=parent_folder_id,
        )
        self._append_folder(folder)
        self.current_tab = TAB_HOME
        self.collapsed_collection_ids.discard(collection_id)
        if parent_folder_id is not None:
            self.collapsed_folder_ids.discard(parent_folder_id)
        self.collapsed_folder_ids.add(folder.folder_id)
        self._set_selected_sidebar_node("folder", folder.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Created folder {name}."
        self.notify_requests_mutated()
        return folder

    def move_request_to(
        self,
        request_id: str,
        collection_id: str,
        folder_id: str | None,
    ) -> bool:
        request = self.get_request_by_id(request_id)
        if request is None:
            self.message = "Request not found."
            return False
        if request.collection_id == collection_id and request.folder_id == folder_id:
            self.message = "Request is already there."
            return False
        request.collection_id = collection_id
        request.folder_id = folder_id
        self._expand_request_ancestors(request)
        self._set_selected_sidebar_by_request_id(request.request_id)
        self.active_request_id = request.request_id
        if request.request_id in self.open_request_ids:
            self.preview_request_id = None
        self.message = f"Moved request {request.name}."
        self.notify_requests_mutated()
        return True

    def rename_request(self, request_id: str, name: str) -> bool:
        request = self.get_request_by_id(request_id)
        new_name = name.strip()
        if request is None:
            self.message = "Request not found."
            return False
        if not new_name:
            self.message = "Name cannot be empty."
            return False
        request.name = new_name
        self._set_selected_sidebar_by_request_id(request.request_id)
        if self.active_request_id == request.request_id:
            self.preview_request_id = None
        self.current_tab = TAB_HOME
        self.mode = MODE_NORMAL
        self.message = f"Renamed request {new_name}."
        self.notify_requests_mutated()
        return True

    def rename_collection(self, collection_id: str, name: str) -> bool:
        collection = self.get_collection_by_id(collection_id)
        new_name = name.strip()
        if collection is None:
            self.message = "Collection not found."
            return False
        if not new_name:
            self.message = "Name cannot be empty."
            return False
        collection.name = new_name
        self.current_tab = TAB_HOME
        self._set_selected_sidebar_node("collection", collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Renamed collection {new_name}."
        self.notify_requests_mutated()
        return True

    def rename_folder(self, folder_id: str, name: str) -> bool:
        folder = self.get_folder_by_id(folder_id)
        new_name = name.strip()
        if folder is None:
            self.message = "Folder not found."
            return False
        if not new_name:
            self.message = "Name cannot be empty."
            return False
        folder.name = new_name
        self.current_tab = TAB_HOME
        self._set_selected_sidebar_node("folder", folder.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Renamed folder {new_name}."
        self.notify_requests_mutated()
        return True

    def copy_request_to(
        self,
        request_id: str,
        collection_id: str,
        folder_id: str | None,
    ) -> RequestDefinition | None:
        request = self.get_request_by_id(request_id)
        if request is None:
            self.message = "Request not found."
            return None

        copied = deepcopy(request)
        copied.request_id = uuid4().hex
        copied.name = (
            f"{request.name} Copy"
            if request.name.strip()
            else "Request Copy"
        )
        copied.collection_id = collection_id
        copied.folder_id = folder_id
        self._append_request(copied)
        self.current_tab = TAB_HOME
        self.home_editor_tab = HOME_EDITOR_TAB_REQUEST
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        request_label = request.name.strip() or "request"
        self.message = f"Copied request {request_label}."
        self.notify_requests_mutated()
        return copied

    def _copy_folder_subtree(
        self,
        folders: list[FolderDefinition],
        requests: list[RequestDefinition],
        *,
        collection_id: str,
        parent_folder_overrides: dict[str, str | None] | None = None,
        renamed_folder_ids: set[str] | None = None,
    ) -> tuple[list[FolderDefinition], list[RequestDefinition]]:
        folder_id_map: dict[str, str] = {}
        copied_folders: list[FolderDefinition] = []
        overrides = parent_folder_overrides or {}
        renamed_ids = renamed_folder_ids or set()

        for original in folders:
            new_folder_id = uuid4().hex
            folder_id_map[original.folder_id] = new_folder_id
            copied_folders.append(
                FolderDefinition(
                    folder_id=new_folder_id,
                    name=(
                        f"{original.name} Copy"
                        if original.folder_id in renamed_ids
                        else original.name
                    ),
                    collection_id=collection_id,
                    parent_folder_id=(
                        overrides[original.folder_id]
                        if original.folder_id in overrides
                        else folder_id_map.get(original.parent_folder_id)
                    ),
                )
            )

        copied_requests: list[RequestDefinition] = []
        for request in requests:
            copied = deepcopy(request)
            copied.request_id = uuid4().hex
            copied.collection_id = collection_id
            copied.folder_id = folder_id_map.get(request.folder_id)
            copied_requests.append(copied)

        return copied_folders, copied_requests

    def copy_folder_to(
        self,
        folder_id: str,
        collection_id: str,
        parent_folder_id: str | None,
    ) -> FolderDefinition | None:
        folder = self.get_folder_by_id(folder_id)
        if folder is None:
            self.message = "Folder not found."
            return None

        subtree = self._folder_subtree(folder.folder_id)
        subtree_ids = {item.folder_id for item in subtree}
        copied_folders, copied_requests = self._copy_folder_subtree(
            subtree,
            [
                request
                for request in self.requests
                if request.folder_id in subtree_ids
            ],
            collection_id=collection_id,
            parent_folder_overrides={folder.folder_id: parent_folder_id},
            renamed_folder_ids={folder.folder_id},
        )

        self._extend_folders(copied_folders)
        self._extend_requests(copied_requests)
        copied_root = copied_folders[0]
        self.current_tab = TAB_HOME
        self.collapsed_collection_ids.discard(collection_id)
        if parent_folder_id is not None:
            for ancestor in self.folder_chain(parent_folder_id):
                self.collapsed_folder_ids.discard(ancestor.folder_id)
        self.collapsed_folder_ids.add(copied_root.folder_id)
        self._set_selected_sidebar_node("folder", copied_root.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Copied folder {folder.name}."
        self.notify_requests_mutated()
        return copied_root

    def copy_collection(self, collection_id: str) -> CollectionDefinition | None:
        collection = self.get_collection_by_id(collection_id)
        if collection is None:
            self.message = "Collection not found."
            return None

        copied_collection = CollectionDefinition(name=f"{collection.name} Copy")
        self._append_collection(copied_collection)

        source_folders = [
            folder
            for folder in self.folders
            if folder.collection_id == collection.collection_id
        ]
        ordered_folders = sorted(
            source_folders,
            key=lambda item: len(self.folder_chain(item.folder_id)),
        )
        copied_folders, copied_requests = self._copy_folder_subtree(
            ordered_folders,
            [
                request
                for request in self.requests
                if request.collection_id == collection.collection_id
            ],
            collection_id=copied_collection.collection_id,
        )

        self._extend_folders(copied_folders)
        self._extend_requests(copied_requests)
        self.current_tab = TAB_HOME
        self.collapsed_collection_ids.add(copied_collection.collection_id)
        self._set_selected_sidebar_node("collection", copied_collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = f"Copied collection {collection.name}."
        self.notify_requests_mutated()
        return copied_collection

    def import_collections(
        self,
        collections: list[CollectionDefinition],
        folders: list[FolderDefinition],
        requests: list[RequestDefinition],
    ) -> int:
        if not collections:
            self.message = "No collections found in import file."
            return 0

        collection_id_map: dict[str, str] = {}
        imported_collections: list[CollectionDefinition] = []
        used_collection_names = {collection.name.strip().lower() for collection in self.collections}
        for original in collections:
            new_collection_id = uuid4().hex
            collection_id_map[original.collection_id] = new_collection_id
            collection_name = self._unique_collection_name(original.name, used_collection_names)
            imported_collections.append(
                CollectionDefinition(
                    collection_id=new_collection_id,
                    name=collection_name,
                )
            )

        source_folders = [
            folder
            for folder in folders
            if folder.collection_id in collection_id_map
        ]
        ordered_folders = sorted(
            source_folders,
            key=lambda item: len(self._folder_chain_from_items(source_folders, item.folder_id)),
        )
        folder_id_map: dict[str, str] = {}
        imported_folders: list[FolderDefinition] = []
        for original in ordered_folders:
            new_folder_id = uuid4().hex
            folder_id_map[original.folder_id] = new_folder_id
            imported_folders.append(
                FolderDefinition(
                    folder_id=new_folder_id,
                    name=original.name,
                    collection_id=collection_id_map[original.collection_id],
                    parent_folder_id=folder_id_map.get(original.parent_folder_id),
                )
            )

        imported_requests: list[RequestDefinition] = []
        for original in requests:
            if original.collection_id not in collection_id_map:
                continue
            copied = deepcopy(original)
            copied.request_id = uuid4().hex
            copied.collection_id = collection_id_map[original.collection_id]
            copied.folder_id = folder_id_map.get(original.folder_id)
            copied.transient = False
            imported_requests.append(copied)

        self._extend_collections(imported_collections)
        self._extend_folders(imported_folders)
        self._extend_requests(imported_requests)
        first_collection = imported_collections[0]
        self.current_tab = TAB_HOME
        self.collapsed_collection_ids.discard(first_collection.collection_id)
        self._set_selected_sidebar_node("collection", first_collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = MODE_NORMAL
        self.message = (
            f"Imported {len(imported_collections)} collection."
            if len(imported_collections) == 1
            else f"Imported {len(imported_collections)} collections."
        )
        self.notify_requests_mutated()
        return len(imported_collections)

    def move_folder_to(
        self,
        folder_id: str,
        collection_id: str,
        parent_folder_id: str | None,
    ) -> bool:
        folder = self.get_folder_by_id(folder_id)
        if folder is None:
            self.message = "Folder not found."
            return False

        subtree_ids = self._descendant_folder_ids(folder.folder_id)
        if parent_folder_id == folder.folder_id or parent_folder_id in subtree_ids:
            self.message = "Cannot move a folder into itself or its descendants."
            return False
        if folder.collection_id == collection_id and folder.parent_folder_id == parent_folder_id:
            self.message = "Folder is already there."
            return False

        subtree_ids.add(folder.folder_id)
        folder.collection_id = collection_id
        folder.parent_folder_id = parent_folder_id

        for item in self.folders:
            if item.folder_id in subtree_ids:
                item.collection_id = collection_id

        for request in self.requests:
            if request.folder_id in subtree_ids:
                request.collection_id = collection_id

        self.collapsed_collection_ids.discard(collection_id)
        for ancestor in self.folder_chain(parent_folder_id):
            self.collapsed_folder_ids.discard(ancestor.folder_id)
        self._set_selected_sidebar_node("folder", folder.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.message = f"Moved folder {folder.name}."
        self.notify_requests_mutated()
        return True

    def _folder_chain_from_items(
        self,
        folders: list[FolderDefinition],
        folder_id: str | None,
    ) -> list[FolderDefinition]:
        by_id = {folder.folder_id: folder for folder in folders}
        chain: list[FolderDefinition] = []
        current_id = folder_id
        seen: set[str] = set()
        while current_id is not None and current_id not in seen:
            folder = by_id.get(current_id)
            if folder is None:
                break
            chain.append(folder)
            seen.add(current_id)
            current_id = folder.parent_folder_id
        chain.reverse()
        return chain

    def _unique_collection_name(
        self,
        base_name: str,
        used_names: set[str],
    ) -> str:
        candidate = base_name.strip() or "Imported Collection"
        normalized = candidate.lower()
        if normalized not in used_names:
            used_names.add(normalized)
            return candidate

        suffix = " Import"
        numbered = 1
        while True:
            proposed = (
                f"{candidate}{suffix}"
                if numbered == 1
                else f"{candidate}{suffix} {numbered}"
            )
            normalized = proposed.lower()
            if normalized not in used_names:
                used_names.add(normalized)
                return proposed
            numbered += 1

    def delete_selected_request(self) -> RequestDefinition | None:
        request = self.get_selected_request()
        if request is None:
            return None

        deleted = self._pop_request(self.selected_request_index)
        self.open_request_ids = [
            request_id
            for request_id in self.open_request_ids
            if request_id != deleted.request_id
        ]
        if self.preview_request_id == deleted.request_id:
            self.preview_request_id = None
        if self.active_request_id == deleted.request_id:
            self.active_request_id = None

        if not self.get_sidebar_nodes():
            self.selected_sidebar_index = 0
            self.selected_request_index = 0
            self.request_scroll_offset = 0
            self.response_scroll_offset = 0
        else:
            self.clamp_selected_sidebar_index()
            self.clamp_selected_request_index()
            self._sync_request_from_selected_sidebar()

        self.mode = MODE_NORMAL
        self.message = f"Deleted {deleted.name}."
        self.notify_requests_mutated()
        return deleted

    def delete_selected_collection(self) -> CollectionDefinition | None:
        node = self.get_selected_sidebar_node()
        if node is None or node.kind != "collection":
            return None
        collection = self.get_collection_by_id(node.node_id)
        if collection is None:
            return None
        folder_ids = {
            folder.folder_id
            for folder in self.folders
            if folder.collection_id == collection.collection_id
        }
        request_ids = {
            request.request_id
            for request in self.requests
            if request.collection_id == collection.collection_id
        }
        self.collections = [
            item for item in self.collections if item.collection_id != collection.collection_id
        ]
        self.folders = [
            folder for folder in self.folders if folder.collection_id != collection.collection_id
        ]
        self.requests = [
            request for request in self.requests if request.collection_id != collection.collection_id
        ]
        self.open_request_ids = [
            request_id for request_id in self.open_request_ids if request_id not in request_ids
        ]
        self.collapsed_collection_ids.discard(collection.collection_id)
        self.collapsed_folder_ids -= folder_ids
        if self.active_request_id in request_ids:
            self.active_request_id = None
        if self.preview_request_id in request_ids:
            self.preview_request_id = None
        self.clamp_selected_sidebar_index()
        self.mode = MODE_NORMAL
        self.message = f"Deleted collection {collection.name}."
        self.notify_requests_mutated()
        return collection

    def delete_selected_folder(self) -> FolderDefinition | None:
        node = self.get_selected_sidebar_node()
        if node is None or node.kind != "folder":
            return None
        folder = self.get_folder_by_id(node.node_id)
        if folder is None:
            return None
        descendant_ids = self._descendant_folder_ids(folder.folder_id)
        descendant_ids.add(folder.folder_id)
        request_ids = {
            request.request_id
            for request in self.requests
            if request.folder_id in descendant_ids
        }
        self.folders = [
            item for item in self.folders if item.folder_id not in descendant_ids
        ]
        self.requests = [
            request for request in self.requests if request.folder_id not in descendant_ids
        ]
        self.open_request_ids = [
            request_id for request_id in self.open_request_ids if request_id not in request_ids
        ]
        self.collapsed_folder_ids -= descendant_ids
        if self.active_request_id in request_ids:
            self.active_request_id = None
        if self.preview_request_id in request_ids:
            self.preview_request_id = None
        self.clamp_selected_sidebar_index()
        self.mode = MODE_NORMAL
        self.message = f"Deleted folder {folder.name}."
        self.notify_requests_mutated()
        return folder

    def _descendant_folder_ids(self, folder_id: str) -> set[str]:
        result: set[str] = set()
        for folder in self.folders:
            if folder.parent_folder_id != folder_id:
                continue
            result.add(folder.folder_id)
            result |= self._descendant_folder_ids(folder.folder_id)
        return result

    def _folder_subtree(self, folder_id: str) -> list[FolderDefinition]:
        folder = self.get_folder_by_id(folder_id)
        if folder is None:
            return []
        result = [folder]
        children = [
            item
            for item in self.folders
            if item.parent_folder_id == folder_id
        ]
        for child in children:
            result.extend(self._folder_subtree(child.folder_id))
        return result
