from __future__ import annotations

from typing import TYPE_CHECKING

from piespector.domain.history import HistoryEntry
from piespector.storage import (
    append_history_entry,
    save_env_workspace,
    save_history_entries,
    save_request_workspace,
)

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class PersistenceManager:
    """Centralizes persisted state writes for the application."""

    def __init__(self, app: PiespectorApp, *, enabled: bool = True) -> None:
        self.app = app
        self.enabled = enabled
        self._subscribe_to_state_mutations()

    @property
    def state(self):
        return self.app.state

    def _subscribe_to_state_mutations(self) -> None:
        self.state.subscribe("requests", lambda: self.app._persist_requests())
        self.state.subscribe("env", lambda: self.app._persist_env_pairs())
        self.state.subscribe(
            "history_entry_appended",
            lambda entry: self.app._append_history_entry(entry),
        )

    def persist_env_workspace(self) -> None:
        if not self.enabled:
            return
        save_env_workspace(
            self.app._env_workspace_path,
            self.state.env_names,
            self.state.env_sets,
            self.state.selected_env_name,
        )

    def persist_request_workspace(self) -> None:
        if not self.enabled:
            return
        save_request_workspace(
            self.app._requests_file_path,
            self.state.collections,
            self.state.folders,
            self.state.requests,
            self.state.collapsed_collection_ids,
            self.state.collapsed_folder_ids,
        )

    def persist_history_entries(self) -> None:
        if not self.enabled:
            return
        save_history_entries(self.app._history_file_path, self.state.history_entries)

    def append_history_entry(self, entry: HistoryEntry) -> None:
        if not self.enabled:
            return
        append_history_entry(self.app._history_file_path, entry)
