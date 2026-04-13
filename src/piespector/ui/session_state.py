from __future__ import annotations

from dataclasses import dataclass, fields

from piespector.domain.editor import TAB_HOME
from piespector.domain.modes import MODE_NORMAL


@dataclass
class UISessionState:
    mode: str = MODE_NORMAL
    current_tab: str = TAB_HOME
    jump_return_mode: str = MODE_NORMAL
    message: str = ""
    open_request_ids: list[str] | None = None
    active_request_id: str | None = None
    preview_request_id: str | None = None
    request_workspace_initialized: bool = False
    selected_sidebar_index: int = 0
    selected_request_index: int = 0
    pending_request_id: str | None = None
    pending_request_spinner_tick: int = 0
    env_pairs: dict[str, str] | None = None
    history_filter_query: str = ""
    help_return_tab: str = TAB_HOME
    help_source_tab: str = TAB_HOME
    help_source_mode: str = MODE_NORMAL

    def __post_init__(self) -> None:
        if self.open_request_ids is None:
            self.open_request_ids = []
        if self.env_pairs is None:
            self.env_pairs = {}


HOME_SCREEN_FIELD_NAMES: tuple[()] = ()
SESSION_ROOT_FIELD_NAMES = tuple(f.name for f in fields(UISessionState))
