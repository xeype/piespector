from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from piespector.domain.history import HistoryEntry, history_entry_matches
from piespector.domain.requests import (
    RequestAuth,
    RequestBody,
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
from piespector.ui.session_state import (
    ENV_SCREEN_FIELD_NAMES,
    HISTORY_SCREEN_FIELD_NAMES,
    HOME_SCREEN_FIELD_NAMES,
    SESSION_ROOT_FIELD_NAMES,
    UISessionState,
)


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
        session_root_kwargs = {
            name: kwargs.pop(name)
            for name in list(kwargs)
            if name in SESSION_ROOT_FIELD_NAMES
        }
        home_kwargs = {
            name: kwargs.pop(name)
            for name in list(kwargs)
            if name in HOME_SCREEN_FIELD_NAMES
        }
        env_kwargs = {
            name: kwargs.pop(name)
            for name in list(kwargs)
            if name in ENV_SCREEN_FIELD_NAMES
        }
        history_kwargs = {
            name: kwargs.pop(name)
            for name in list(kwargs)
            if name in HISTORY_SCREEN_FIELD_NAMES
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

        session_override_kwargs = (
            session_root_kwargs | home_kwargs | env_kwargs | history_kwargs
        )
        if session is not None and session_override_kwargs:
            conflicting = ", ".join(sorted(session_override_kwargs))
            raise TypeError(
                f"Cannot pass both session and session fields: {conflicting}"
            )

        self.session = session or UISessionState(**session_root_kwargs)
        for field_name, value in home_kwargs.items():
            setattr(self.session.home, field_name, value)
        for field_name, value in env_kwargs.items():
            setattr(self.session.env, field_name, value)
        for field_name, value in history_kwargs.items():
            setattr(self.session.history, field_name, value)
        self._app = None
        self._mutation_subscribers: dict[str, list[Callable[..., None]]] = {}

    def attach_app(self, app) -> None:
        self._app = app

    def subscribe(self, topic: str, callback: Callable[..., None]) -> None:
        self._mutation_subscribers.setdefault(topic, []).append(callback)

    def _notify(self, topic: str, *args) -> None:
        for callback in tuple(self._mutation_subscribers.get(topic, ())):
            callback(*args)

    def notify_requests_mutated(self) -> None:
        self._notify("requests")

    def notify_env_mutated(self) -> None:
        self._notify("env")

    def notify_history_entry_appended(self, entry: HistoryEntry) -> None:
        self._notify("history_entry_appended", entry)

    def _screen_owner(self, group_name: str):
        app = getattr(self, "_app", None)
        if app is None:
            return None
        if group_name == "home":
            return getattr(app, "_home_screen", None)
        if group_name == "env":
            return getattr(app, "_env_screen", None)
        if group_name == "history":
            return getattr(app, "_history_screen", None)
        return None

def _session_field_property(field_name: str) -> property:
    def getter(self: PiespectorState):
        return getattr(self.session, field_name)

    def setter(self: PiespectorState, value) -> None:
        setattr(self.session, field_name, value)

    return property(getter, setter)


def _screen_state_field_property(group_name: str, field_name: str) -> property:
    def getter(self: PiespectorState):
        owner = self._screen_owner(group_name)
        if owner is not None and hasattr(owner, field_name):
            return getattr(owner, field_name)
        return getattr(getattr(self.session, group_name), field_name)

    def setter(self: PiespectorState, value) -> None:
        setattr(getattr(self.session, group_name), field_name, value)
        owner = self._screen_owner(group_name)
        if owner is not None and hasattr(owner, field_name):
            setattr(owner, field_name, value)

    return property(getter, setter)


for _session_field_name in SESSION_ROOT_FIELD_NAMES:
    setattr(PiespectorState, _session_field_name, _session_field_property(_session_field_name))
for _home_field_name in HOME_SCREEN_FIELD_NAMES:
    setattr(PiespectorState, _home_field_name, _screen_state_field_property("home", _home_field_name))
for _env_field_name in ENV_SCREEN_FIELD_NAMES:
    setattr(PiespectorState, _env_field_name, _screen_state_field_property("env", _env_field_name))
for _history_field_name in HISTORY_SCREEN_FIELD_NAMES:
    setattr(
        PiespectorState,
        _history_field_name,
        _screen_state_field_property("history", _history_field_name),
    )

del _session_field_name
del _home_field_name
del _env_field_name
del _history_field_name
