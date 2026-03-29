from __future__ import annotations

from dataclasses import dataclass, field

from piespector.domain.history import HistoryEntry, history_entry_matches
from piespector.domain.requests import (
    RequestDefinition,
    RequestKeyValue,
    ResponseSummary,
    format_headers_text,
    format_query_text,
    parse_headers_text,
    parse_query_text,
)
from piespector.domain.workspace import CollectionDefinition, FolderDefinition
from piespector.state_core import CoreStateMixin
from piespector.state_env import EnvStateMixin
from piespector.state_history import HistoryStateMixin
from piespector.state_home import HomeStateMixin
from piespector.state_workspace import WorkspaceStateMixin
from piespector.ui.session_state import SESSION_FIELD_NAMES, UISessionState


@dataclass(init=False)
class PiespectorState(
    CoreStateMixin,
    HistoryStateMixin,
    EnvStateMixin,
    WorkspaceStateMixin,
    HomeStateMixin,
):
    collections: list[CollectionDefinition] = field(default_factory=list)
    folders: list[FolderDefinition] = field(default_factory=list)
    collapsed_collection_ids: set[str] = field(default_factory=set)
    collapsed_folder_ids: set[str] = field(default_factory=set)
    requests: list[RequestDefinition] = field(default_factory=list)
    env_names: list[str] = field(default_factory=lambda: ["Default"])
    env_sets: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"Default": {}}
    )
    selected_env_name: str = "Default"
    history_entries: list[HistoryEntry] = field(default_factory=list)
    session: UISessionState = field(default_factory=UISessionState, repr=False)

    def __init__(self, **kwargs) -> None:
        session = kwargs.pop("session", None)
        session_kwargs = {
            name: kwargs.pop(name)
            for name in list(kwargs)
            if name in SESSION_FIELD_NAMES
        }

        self.collections = kwargs.pop("collections", [])
        self.folders = kwargs.pop("folders", [])
        self.collapsed_collection_ids = kwargs.pop("collapsed_collection_ids", set())
        self.collapsed_folder_ids = kwargs.pop("collapsed_folder_ids", set())
        self.requests = kwargs.pop("requests", [])
        self.env_names = kwargs.pop("env_names", ["Default"])
        self.env_sets = kwargs.pop("env_sets", {"Default": {}})
        self.selected_env_name = kwargs.pop("selected_env_name", "Default")
        self.history_entries = kwargs.pop("history_entries", [])

        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected state argument(s): {unexpected}")

        if session is not None and session_kwargs:
            conflicting = ", ".join(sorted(session_kwargs))
            raise TypeError(
                f"Cannot pass both session and session fields: {conflicting}"
            )

        self.session = session or UISessionState(**session_kwargs)


def _session_field_property(field_name: str) -> property:
    def getter(self: PiespectorState):
        return getattr(self.session, field_name)

    def setter(self: PiespectorState, value) -> None:
        setattr(self.session, field_name, value)

    return property(getter, setter)


for _session_field_name in SESSION_FIELD_NAMES:
    setattr(PiespectorState, _session_field_name, _session_field_property(_session_field_name))

del _session_field_name
