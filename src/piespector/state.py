from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from piespector.domain.history import HistoryEntry, history_entry_matches
from piespector.domain.requests import (
    EnvVariable,
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
from piespector.domain.editor import HISTORY_DETAIL_BLOCK_RESPONSE, HOME_EDITOR_TAB_REQUEST, RESPONSE_TAB_BODY, TAB_HOME
from piespector.domain.modes import (
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
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
    env_sets: dict[str, list[EnvVariable]] = field(
        default_factory=lambda: {"Default": []}
    )
    selected_env_name: str = "Default"
    history_entries: list[HistoryEntry] = field(default_factory=list)
    _collections_by_id: dict[str, CollectionDefinition]
    _folders_by_id: dict[str, FolderDefinition]
    _requests_by_id: dict[str, RequestDefinition]

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name == "collections":
            super().__setattr__(
                "_collections_by_id",
                {item.collection_id: item for item in value},
            )
        elif name == "folders":
            super().__setattr__(
                "_folders_by_id",
                {item.folder_id: item for item in value},
            )
        elif name == "requests":
            super().__setattr__(
                "_requests_by_id",
                {item.request_id: item for item in value},
            )

    def __init__(self, **kwargs) -> None:
        self.collections = kwargs.pop("collections", [])
        self.folders = kwargs.pop("folders", [])
        self.collapsed_collection_ids = kwargs.pop("collapsed_collection_ids", set())
        self.collapsed_folder_ids = kwargs.pop("collapsed_folder_ids", set())
        self.requests = kwargs.pop("requests", [])
        self.env_names = kwargs.pop("env_names", ["Default"])
        self.env_sets = kwargs.pop("env_sets", {"Default": []})
        self.selected_env_name = kwargs.pop("selected_env_name", "Default")
        self.history_entries = kwargs.pop("history_entries", [])
        self.mode = kwargs.pop("mode", MODE_NORMAL)
        self.current_tab = kwargs.pop("current_tab", TAB_HOME)
        self.jump_return_mode = kwargs.pop("jump_return_mode", MODE_NORMAL)
        self.message = kwargs.pop("message", "")
        _open_request_ids = kwargs.pop("open_request_ids", None)
        self.open_request_ids = [] if _open_request_ids is None else _open_request_ids
        self.active_request_id = kwargs.pop("active_request_id", None)
        self.preview_request_id = kwargs.pop("preview_request_id", None)
        self.request_workspace_initialized = kwargs.pop("request_workspace_initialized", False)
        self.selected_sidebar_index = kwargs.pop("selected_sidebar_index", 0)
        self.selected_request_index = kwargs.pop("selected_request_index", 0)
        self.pending_request_id = kwargs.pop("pending_request_id", None)
        self.pending_request_spinner_tick = kwargs.pop("pending_request_spinner_tick", 0)
        _env_pairs = kwargs.pop("env_pairs", None)
        self.env_pairs = {} if _env_pairs is None else _env_pairs
        self.history_filter_query = kwargs.pop("history_filter_query", "")
        self.help_return_tab = kwargs.pop("help_return_tab", TAB_HOME)
        self.help_source_tab = kwargs.pop("help_source_tab", TAB_HOME)
        self.help_source_mode = kwargs.pop("help_source_mode", MODE_NORMAL)

        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected state argument(s): {unexpected}")

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

def _screen_only_field_property(group_name: str, field_name: str, default) -> property:
    """Property that reads/writes exclusively from/to the owning screen's reactive attr.

    When the screen is not yet available (app not attached or screen not created),
    reads return ``default`` and writes are no-ops.  This removes the session-state
    mirror that previously duplicated env/history UI fields into ``session.env`` /
    ``session.history``.
    """
    def getter(self: PiespectorState):
        owner = self._screen_owner(group_name)
        if owner is not None and hasattr(owner, field_name):
            return getattr(owner, field_name)
        return default

    def setter(self: PiespectorState, value) -> None:
        owner = self._screen_owner(group_name)
        if owner is not None and hasattr(owner, field_name):
            setattr(owner, field_name, value)

    return property(getter, setter)


# Home screen — select UI fields live exclusively on HomeScreen reactive attrs.
_HOME_SCREEN_ONLY_DEFAULTS: dict[str, object] = {
    "params_creating_new": False,
    "headers_creating_new": False,
    "body_creating_new": False,
    "request_scroll_offset": 0,
    "response_scroll_offset": 0,
    "selected_home_response_tab": RESPONSE_TAB_BODY,
    "selected_request_field_index": 0,
    "selected_auth_index": 0,
    "selected_param_index": 0,
    "selected_param_field_index": 0,
    "selected_header_index": 0,
    "selected_header_field_index": 0,
    "selected_body_index": 0,
    "selected_body_field_index": 0,
    "selected_top_bar_field": "method",
    "home_top_bar_return_mode": MODE_NORMAL,
    "home_top_bar_edit_return_mode": MODE_NORMAL,
    "home_auth_type_return_mode": MODE_HOME_AUTH_SELECT,
    "home_body_type_return_mode": MODE_HOME_SECTION_SELECT,
    "home_body_raw_type_return_mode": MODE_HOME_BODY_TYPE_EDIT,
    "home_body_content_return_mode": MODE_HOME_BODY_SELECT,
    "home_body_select_return_mode": MODE_HOME_SECTION_SELECT,
    "home_response_select_return_mode": MODE_NORMAL,
    "home_editor_tab": HOME_EDITOR_TAB_REQUEST,
}
for _home_only_field_name, _home_only_default in _HOME_SCREEN_ONLY_DEFAULTS.items():
    setattr(
        PiespectorState,
        _home_only_field_name,
        _screen_only_field_property("home", _home_only_field_name, _home_only_default),
    )

# Env screen — UI state lives exclusively on EnvScreen reactive attrs.
_ENV_SCREEN_DEFAULTS: dict[str, object] = {
    "selected_env_index": 0,
    "selected_env_field_index": 0,
    "env_scroll_offset": 0,
    "env_creating_new": False,
}
for _env_field_name, _env_default in _ENV_SCREEN_DEFAULTS.items():
    setattr(
        PiespectorState,
        _env_field_name,
        _screen_only_field_property("env", _env_field_name, _env_default),
    )

# History screen — UI state lives exclusively on HistoryScreen reactive attrs.
_HISTORY_SCREEN_DEFAULTS: dict[str, object] = {
    "selected_history_index": 0,
    "history_scroll_offset": 0,
    "selected_history_detail_block": HISTORY_DETAIL_BLOCK_RESPONSE,
    "selected_history_request_tab": RESPONSE_TAB_BODY,
    "selected_history_response_tab": RESPONSE_TAB_BODY,
    "history_request_scroll_offset": 0,
    "history_response_scroll_offset": 0,
    "history_response_select_return_mode": MODE_NORMAL,
}
for _history_field_name, _history_default in _HISTORY_SCREEN_DEFAULTS.items():
    setattr(
        PiespectorState,
        _history_field_name,
        _screen_only_field_property("history", _history_field_name, _history_default),
    )

del _home_only_field_name, _home_only_default
del _env_field_name, _env_default
del _history_field_name, _history_default
