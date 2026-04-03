from __future__ import annotations

from dataclasses import dataclass

from piespector.domain.editor import TAB_HOME
from piespector.domain.history import HistoryEntry
from piespector.state import PiespectorState


@dataclass(frozen=True)
class SearchTarget:
    display: str
    kind: str
    node_id: str
    query_terms: tuple[str, ...]
    request_id: str | None = None


@dataclass(frozen=True)
class MoveDestination:
    display: str
    kind: str
    node_id: str
    collection_id: str
    folder_id: str | None
    query_terms: tuple[str, ...]


def search_completion(state: PiespectorState, raw_buffer: str) -> str | None:
    buffer = raw_buffer.strip()
    candidates = search_matches(state, buffer)
    if not candidates:
        return None
    return candidates[0].display


def search_matches(state: PiespectorState, raw_buffer: str) -> list[SearchTarget]:
    return _matching_targets(state, raw_buffer)


def search_targets(state: PiespectorState) -> list[SearchTarget]:
    return _search_targets(state)


def move_destination_matches(
    state: PiespectorState,
    raw_buffer: str,
    *,
    source_kind: str | None = None,
    source_id: str | None = None,
) -> list[MoveDestination]:
    buffer = raw_buffer.strip().lower()
    destinations = _move_destinations(
        state,
        source_kind=source_kind,
        source_id=source_id,
    )
    if not buffer:
        return destinations
    return [
        destination
        for destination in destinations
        if any(buffer in term.lower() for term in destination.query_terms)
    ]


def resolve_move_destination(
    state: PiespectorState,
    raw_buffer: str,
    *,
    source_kind: str | None = None,
    source_id: str | None = None,
) -> MoveDestination | None:
    buffer = raw_buffer.strip().lower()
    if not buffer:
        return None

    destinations = _move_destinations(
        state,
        source_kind=source_kind,
        source_id=source_id,
    )
    exact_display = [
        destination
        for destination in destinations
        if destination.display.lower() == buffer
    ]
    if exact_display:
        return exact_display[0]

    exact_term = [
        destination
        for destination in destinations
        if any(term.lower() == buffer for term in destination.query_terms)
    ]
    if exact_term:
        return exact_term[0]

    matches = move_destination_matches(
        state,
        raw_buffer,
        source_kind=source_kind,
        source_id=source_id,
    )
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_search_target(
    state: PiespectorState,
    raw_buffer: str,
) -> SearchTarget | None:
    buffer = raw_buffer.strip().lower()
    if not buffer:
        return None

    targets = _search_targets(state)
    exact_display = [target for target in targets if target.display.lower() == buffer]
    if exact_display:
        return exact_display[0]

    exact_term = [
        target
        for target in targets
        if any(term.lower() == buffer for term in target.query_terms)
    ]
    if exact_term:
        return exact_term[0]

    matches = search_matches(state, raw_buffer)
    if len(matches) == 1:
        return matches[0]
    return None


def activate_search_target(state: PiespectorState, target: SearchTarget) -> bool:
    state.current_tab = TAB_HOME
    state.ensure_request_workspace()

    if target.kind == "collection":
        state.collapsed_collection_ids.discard(target.node_id)
        state._set_selected_sidebar_node("collection", target.node_id)
        state.active_request_id = None
        state.preview_request_id = None
        state.message = f"Opened collection {target.display}."
        return True

    if target.kind == "folder":
        folder = state.get_folder_by_id(target.node_id)
        if folder is None:
            return False
        if folder.collection_id:
            state.collapsed_collection_ids.discard(folder.collection_id)
        for ancestor in state.folder_chain(folder.folder_id):
            state.collapsed_folder_ids.discard(ancestor.folder_id)
        state._set_selected_sidebar_node("folder", target.node_id)
        state.active_request_id = None
        state.preview_request_id = None
        state.message = f"Opened folder {folder.name}."
        return True

    request = state.get_request_by_id(target.request_id or target.node_id)
    if request is None:
        return False
    state._expand_request_ancestors(request)
    state._set_selected_sidebar_by_request_id(request.request_id)
    state.open_selected_request(pin=True)
    state.message = f"Opened request {request.name}."
    return True


def _matching_targets(state: PiespectorState, raw_buffer: str) -> list[SearchTarget]:
    buffer = raw_buffer.strip().lower()
    if not buffer:
        return _search_targets(state)
    return [
        target
        for target in _search_targets(state)
        if any(buffer in term.lower() for term in target.query_terms)
    ]


def _search_targets(state: PiespectorState) -> list[SearchTarget]:
    targets: list[SearchTarget] = []

    for collection in sorted(state.collections, key=lambda item: item.name.lower()):
        display = collection.name
        targets.append(
            SearchTarget(
                display=display,
                kind="collection",
                node_id=collection.collection_id,
                query_terms=(collection.name, display),
            )
        )

    for folder in sorted(state.folders, key=lambda item: folder_path(state, item).lower()):
        path = folder_path(state, folder)
        display = path
        targets.append(
            SearchTarget(
                display=display,
                kind="folder",
                node_id=folder.folder_id,
                query_terms=(folder.name, path, display),
            )
        )

    for request in sorted(state.requests, key=lambda item: request_path(state, item).lower()):
        path = request_path(state, request)
        display = path
        targets.append(
            SearchTarget(
                display=display,
                kind="request",
                node_id=request.request_id,
                request_id=request.request_id,
                query_terms=(request.name, path, display),
            )
        )

    return targets


def folder_path(state: PiespectorState, folder) -> str:
    parts: list[str] = []
    collection = state.get_collection_by_id(folder.collection_id)
    if collection is not None:
        parts.append(collection.name)
    parts.extend(item.name for item in state.folder_chain(folder.folder_id))
    return " / ".join(part for part in parts if part)


def request_path(state: PiespectorState, request) -> str:
    parts: list[str] = []
    collection = state.get_collection_by_id(request.collection_id)
    if collection is not None:
        parts.append(collection.name)
    parts.extend(folder.name for folder in state.folder_chain(request.folder_id))
    parts.append(request.name)
    return " / ".join(part for part in parts if part)


def history_search_matches(state: PiespectorState, raw_buffer: str) -> list[HistoryEntry]:
    return state.visible_history_entries(raw_buffer)


def history_search_display(entry: HistoryEntry) -> str:
    status = str(entry.status_code) if entry.status_code is not None else "ERR"
    name = (
        entry.source_request_name.strip()
        or entry.source_request_path.strip()
        or entry.url.strip()
        or "(unnamed)"
    )
    return f"{entry.method} {status} {name}"


def history_search_completion(state: PiespectorState, raw_buffer: str) -> str | None:
    buffer = raw_buffer.strip()
    if not buffer:
        return None
    matches = history_search_matches(state, buffer)
    if not matches:
        return None
    display = history_search_display(matches[0])
    if display.lower().startswith(buffer.lower()):
        return display
    return None


def _move_destinations(
    state: PiespectorState,
    *,
    source_kind: str | None = None,
    source_id: str | None = None,
) -> list[MoveDestination]:
    destinations: list[MoveDestination] = []
    blocked_folder_ids: set[str] = set()
    if source_kind == "folder" and source_id is not None:
        blocked_folder_ids = state._descendant_folder_ids(source_id)
        blocked_folder_ids.add(source_id)

    for collection in sorted(state.collections, key=lambda item: item.name.lower()):
        destinations.append(
            MoveDestination(
                display=collection.name,
                kind="collection",
                node_id=collection.collection_id,
                collection_id=collection.collection_id,
                folder_id=None,
                query_terms=(collection.name,),
            )
        )

    for folder in sorted(state.folders, key=lambda item: folder_path(state, item).lower()):
        if folder.folder_id in blocked_folder_ids:
            continue
        path = folder_path(state, folder)
        destinations.append(
            MoveDestination(
                display=path,
                kind="folder",
                node_id=folder.folder_id,
                collection_id=folder.collection_id,
                folder_id=folder.folder_id,
                query_terms=(folder.name, path),
            )
        )

    return destinations
