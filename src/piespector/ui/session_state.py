from __future__ import annotations

from dataclasses import dataclass, field, fields

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_RESPONSE,
    HOME_EDITOR_TAB_REQUEST,
    RESPONSE_TAB_BODY,
    TAB_HOME,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)


@dataclass
class HomeScreenState:
    request_scroll_offset: int = 0
    response_scroll_offset: int = 0
    selected_home_response_tab: str = RESPONSE_TAB_BODY
    home_editor_tab: str = HOME_EDITOR_TAB_REQUEST
    selected_request_field_index: int = 0
    selected_auth_index: int = 0
    selected_param_index: int = 0
    selected_param_field_index: int = 0
    selected_header_index: int = 0
    selected_header_field_index: int = 0
    selected_body_index: int = 0
    home_top_bar_return_mode: str = MODE_NORMAL
    home_top_bar_edit_return_mode: str = MODE_NORMAL
    selected_top_bar_field: str = "method"
    home_auth_type_return_mode: str = MODE_HOME_AUTH_SELECT
    home_body_type_return_mode: str = MODE_HOME_SECTION_SELECT
    home_body_raw_type_return_mode: str = MODE_HOME_BODY_TYPE_EDIT
    home_body_content_return_mode: str = MODE_HOME_BODY_SELECT
    home_body_select_return_mode: str = MODE_HOME_SECTION_SELECT
    home_response_select_return_mode: str = MODE_NORMAL
    params_creating_new: bool = False
    headers_creating_new: bool = False


@dataclass
class EnvScreenState:
    selected_env_index: int = 0
    selected_env_field_index: int = 0
    env_scroll_offset: int = 0
    env_creating_new: bool = False


@dataclass
class HistoryScreenState:
    selected_history_index: int = 0
    history_scroll_offset: int = 0
    selected_history_detail_block: str = HISTORY_DETAIL_BLOCK_RESPONSE
    selected_history_request_tab: str = RESPONSE_TAB_BODY
    selected_history_response_tab: str = RESPONSE_TAB_BODY
    history_request_scroll_offset: int = 0
    history_response_scroll_offset: int = 0
    history_response_select_return_mode: str = MODE_NORMAL


@dataclass
class UISessionState:
    mode: str = MODE_NORMAL
    current_tab: str = TAB_HOME
    command_context_mode: str = MODE_NORMAL
    jump_return_mode: str = MODE_NORMAL
    message: str = ""
    confirm_prompt: str = ""
    confirm_action: str | None = None
    confirm_target_id: str | None = None
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
    home: HomeScreenState = field(default_factory=HomeScreenState, repr=False)
    env: EnvScreenState = field(default_factory=EnvScreenState, repr=False)
    history: HistoryScreenState = field(default_factory=HistoryScreenState, repr=False)

    def __post_init__(self) -> None:
        if self.open_request_ids is None:
            self.open_request_ids = []
        if self.env_pairs is None:
            self.env_pairs = {}


HOME_SCREEN_FIELD_NAMES = tuple(field.name for field in fields(HomeScreenState))
ENV_SCREEN_FIELD_NAMES = tuple(field.name for field in fields(EnvScreenState))
HISTORY_SCREEN_FIELD_NAMES = tuple(field.name for field in fields(HistoryScreenState))
INLINE_EDIT_FIELD_NAMES: tuple[str, ...] = ()
SESSION_ROOT_FIELD_NAMES = tuple(
    session_field.name
    for session_field in fields(UISessionState)
    if session_field.name not in {"home", "env", "history"}
)
SESSION_FIELD_NAMES = (
    SESSION_ROOT_FIELD_NAMES
    + HOME_SCREEN_FIELD_NAMES
    + ENV_SCREEN_FIELD_NAMES
    + HISTORY_SCREEN_FIELD_NAMES
)
