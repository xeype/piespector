from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from urllib import parse
from uuid import uuid4

from piespector.placeholders import apply_placeholder_completion, auto_pair_placeholder, placeholder_match

TAB_ORDER = ("home", "env", "history")
REQUEST_EDITOR_TABS: tuple[tuple[str, str], ...] = (
    ("request", "Request"),
    ("auth", "Auth"),
    ("params", "Params"),
    ("headers", "Headers"),
    ("body", "Body"),
)
AUTH_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "No Auth"),
    ("basic", "Basic Auth"),
    ("bearer", "Bearer Token"),
    ("api-key", "API Key"),
)
AUTH_API_KEY_LOCATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("header", "Header"),
    ("query", "Query"),
)
BODY_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("form-data", "Form-Data"),
    ("x-www-form-urlencoded", "x-www-form-urlencoded"),
    ("raw", "Raw"),
)
RAW_SUBTYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("text", "Text"),
    ("json", "JSON"),
    ("xml", "XML"),
)
HTTP_METHODS: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE")
REQUEST_FIELDS_BY_EDITOR_TAB: dict[str, tuple[tuple[str, str], ...]] = {
    "request": (
        ("name", "Name"),
        ("method", "Method"),
        ("url", "URL"),
    ),
    "auth": (("auth_type", "Type"),),
    "params": (("query_text", "Params"),),
    "headers": (("headers_text", "Headers"),),
    "body": (("body_type", "Body Type"), ("body_text", "Body")),
}
REQUEST_FIELDS: tuple[tuple[str, str], ...] = tuple(
    field
    for tab_id, _label in REQUEST_EDITOR_TABS
    for field in REQUEST_FIELDS_BY_EDITOR_TAB[tab_id]
)


@dataclass
class ResponseSummary:
    status_code: int | None = None
    elapsed_ms: float | None = None
    body_length: int = 0
    body_text: str = ""
    error: str = ""
    response_headers: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class RequestKeyValue:
    key: str
    value: str = ""
    enabled: bool = True


@dataclass
class CollectionDefinition:
    collection_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Collection"


@dataclass
class FolderDefinition:
    folder_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Folder"
    collection_id: str = ""
    parent_folder_id: str | None = None


@dataclass
class SidebarNode:
    kind: str
    node_id: str
    label: str
    depth: int = 0
    request_id: str | None = None
    request_index: int | None = None
    method: str = ""


@dataclass
class RequestDefinition:
    request_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    collection_id: str | None = None
    folder_id: str | None = None
    query_items: list[RequestKeyValue] = field(default_factory=list)
    header_items: list[RequestKeyValue] = field(default_factory=list)
    auth_type: str = "none"
    auth_basic_username: str = ""
    auth_basic_password: str = ""
    auth_bearer_token: str = ""
    auth_api_key_name: str = "X-API-Key"
    auth_api_key_value: str = ""
    auth_api_key_location: str = "header"
    transient: bool = False
    body_type: str = "none"
    raw_subtype: str = "json"
    body_text: str = ""
    body_form_items: list[RequestKeyValue] = field(default_factory=list)
    body_urlencoded_items: list[RequestKeyValue] = field(default_factory=list)
    body_form_text: str = ""
    disabled_auto_headers: list[str] = field(default_factory=list)
    last_response: ResponseSummary | None = None


@dataclass
class HistoryEntry:
    history_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = ""
    source_request_id: str | None = None
    source_request_name: str = ""
    source_request_path: str = ""
    method: str = "GET"
    url: str = ""
    auth_type: str = "none"
    auth_location: str = ""
    auth_name: str = ""
    request_headers: list[tuple[str, str]] = field(default_factory=list)
    request_body: str = ""
    request_body_type: str = "none"
    status_code: int | None = None
    elapsed_ms: float | None = None
    response_size: int = 0
    response_headers: list[tuple[str, str]] = field(default_factory=list)
    response_body: str = ""
    error: str = ""


def history_entry_matches(entry: HistoryEntry, raw_query: str) -> bool:
    query = raw_query.strip().lower()
    if not query:
        return True
    status = str(entry.status_code) if entry.status_code is not None else "err"
    request_name = entry.source_request_name.strip()
    request_path = entry.source_request_path.strip()
    url = entry.url.strip()
    haystacks = (
        request_name,
        request_path,
        url,
        entry.method,
        status,
        f"{entry.method} {status}",
        f"{request_name} {url}",
        f"{request_path} {url}",
        f"{entry.method} {status} {request_name} {url}",
        f"{entry.method} {status} {request_path} {url}",
    )
    return any(query in value.lower() for value in haystacks if value)


def parse_query_text(query_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for chunk in query_text.replace("\n", "&").split("&"):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        key = key.strip()
        value = value.strip()
        if key:
            items.append((key, value))
    return items


def format_query_text(items: list[tuple[str, str]]) -> str:
    return "&".join(f"{key}={value}" if value else key for key, value in items if key)


def parse_headers_text(headers_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for chunk in headers_text.replace(";", "\n").splitlines():
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            key, value = item.split(":", 1)
        elif "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        key = key.strip()
        value = value.strip()
        if key:
            items.append((key, value))
    return items


def format_headers_text(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"{key}: {value}" if value else key for key, value in items if key
    )


@dataclass
class PiespectorState:
    mode: str = "NORMAL"
    current_tab: str = "home"
    command_buffer: str = ""
    search_anchor_buffer: str = ""
    search_completion_index: int = -1
    command_context_mode: str = "NORMAL"
    message: str = ""
    confirm_prompt: str = ""
    confirm_action: str | None = None
    confirm_target_id: str | None = None
    collections: list[CollectionDefinition] = field(default_factory=list)
    folders: list[FolderDefinition] = field(default_factory=list)
    collapsed_collection_ids: set[str] = field(default_factory=set)
    collapsed_folder_ids: set[str] = field(default_factory=set)
    requests: list[RequestDefinition] = field(default_factory=list)
    open_request_ids: list[str] = field(default_factory=list)
    active_request_id: str | None = None
    preview_request_id: str | None = None
    request_workspace_initialized: bool = False
    selected_sidebar_index: int = 0
    selected_request_index: int = 0
    request_scroll_offset: int = 0
    response_scroll_offset: int = 0
    selected_home_response_tab: str = "body"
    pending_request_id: str | None = None
    pending_request_spinner_tick: int = 0
    home_editor_tab: str = "request"
    selected_request_field_index: int = 0
    selected_auth_index: int = 0
    selected_param_index: int = 0
    selected_param_field_index: int = 0
    selected_header_index: int = 0
    selected_header_field_index: int = 0
    selected_body_index: int = 0
    home_auth_type_return_mode: str = "HOME_AUTH_SELECT"
    home_body_type_return_mode: str = "HOME_SECTION_SELECT"
    home_body_raw_type_return_mode: str = "HOME_BODY_TYPE_EDIT"
    home_body_content_return_mode: str = "HOME_BODY_SELECT"
    home_body_select_return_mode: str = "HOME_SECTION_SELECT"
    home_response_select_return_mode: str = "NORMAL"
    home_response_view_return_mode: str = "NORMAL"
    params_creating_new: bool = False
    headers_creating_new: bool = False
    env_names: list[str] = field(default_factory=lambda: ["Default"])
    env_sets: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"Default": {}}
    )
    selected_env_name: str = "Default"
    env_pairs: dict[str, str] = field(default_factory=dict)
    selected_env_index: int = 0
    selected_env_field_index: int = 0
    env_scroll_offset: int = 0
    env_creating_new: bool = False
    history_entries: list[HistoryEntry] = field(default_factory=list)
    history_filter_query: str = ""
    selected_history_index: int = 0
    history_scroll_offset: int = 0
    selected_history_detail_block: str = "response"
    selected_history_request_tab: str = "body"
    selected_history_response_tab: str = "body"
    history_request_scroll_offset: int = 0
    history_response_scroll_offset: int = 0
    history_response_select_return_mode: str = "NORMAL"
    history_response_view_return_mode: str = "NORMAL"
    help_return_tab: str = "home"
    help_source_tab: str = "home"
    help_source_mode: str = "NORMAL"
    edit_buffer: str = ""
    edit_cursor_index: int = 0
    replace_on_next_input: bool = False

    def enter_command_mode(self) -> None:
        self.command_context_mode = self.mode
        self.mode = "COMMAND"
        self.command_buffer = ""
        self.message = ""

    def leave_command_mode(self) -> None:
        self.mode = "NORMAL"
        self.command_buffer = ""

    def enter_search_mode(self) -> None:
        self.mode = "SEARCH"
        self.command_buffer = ""
        self.search_anchor_buffer = ""
        self.search_completion_index = -1
        self.message = ""

    def leave_search_mode(self) -> None:
        self.mode = "NORMAL"
        self.command_buffer = ""
        self.search_anchor_buffer = ""
        self.search_completion_index = -1

    def _clamp_edit_cursor_index(self) -> None:
        self.edit_cursor_index = max(0, min(self.edit_cursor_index, len(self.edit_buffer)))

    def set_edit_buffer(self, value: str, *, replace_on_next_input: bool) -> None:
        self.edit_buffer = value
        self.edit_cursor_index = len(value)
        self.replace_on_next_input = replace_on_next_input

    def clear_edit_buffer(self) -> None:
        self.edit_buffer = ""
        self.edit_cursor_index = 0
        self.replace_on_next_input = False

    def insert_edit_character(self, character: str) -> None:
        if self.replace_on_next_input:
            self.clear_edit_buffer()
        self._clamp_edit_cursor_index()
        if character == "{":
            paired = auto_pair_placeholder(self.edit_buffer, self.edit_cursor_index)
            if paired is not None:
                self.edit_buffer, self.edit_cursor_index = paired
                return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + character
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index += len(character)

    def insert_edit_text(self, value: str) -> None:
        if not value:
            return
        if self.replace_on_next_input:
            self.clear_edit_buffer()
        self._clamp_edit_cursor_index()
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + value
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index += len(value)

    def backspace_edit_character(self) -> None:
        if self.replace_on_next_input:
            self.replace_on_next_input = False
        self._clamp_edit_cursor_index()
        if self.edit_cursor_index <= 0:
            return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index - 1]
            + self.edit_buffer[self.edit_cursor_index :]
        )
        self.edit_cursor_index -= 1

    def delete_edit_character(self) -> None:
        if self.replace_on_next_input:
            self.replace_on_next_input = False
        self._clamp_edit_cursor_index()
        if self.edit_cursor_index >= len(self.edit_buffer):
            return
        self.edit_buffer = (
            self.edit_buffer[: self.edit_cursor_index]
            + self.edit_buffer[self.edit_cursor_index + 1 :]
        )

    def move_edit_cursor(self, step: int) -> int:
        self._clamp_edit_cursor_index()
        self.edit_cursor_index = max(
            0,
            min(self.edit_cursor_index + step, len(self.edit_buffer)),
        )
        return self.edit_cursor_index

    def move_edit_cursor_to_start(self) -> None:
        self.edit_cursor_index = 0

    def move_edit_cursor_to_end(self) -> None:
        self.edit_cursor_index = len(self.edit_buffer)

    def placeholder_completion_hint(self) -> str | None:
        match = placeholder_match(
            self.edit_buffer,
            self.edit_cursor_index,
            sorted(self.env_pairs),
        )
        if match is None or match.suggestion == match.prefix:
            return None
        return match.suggestion

    def autocomplete_edit_placeholder(self) -> bool:
        completed = apply_placeholder_completion(
            self.edit_buffer,
            self.edit_cursor_index,
            sorted(self.env_pairs),
        )
        if completed is None:
            return False
        self.edit_buffer, self.edit_cursor_index = completed
        return True

    def enter_confirm_mode(
        self,
        *,
        prompt: str,
        action: str,
        target_id: str,
    ) -> None:
        self.mode = "CONFIRM"
        self.confirm_prompt = prompt
        self.confirm_action = action
        self.confirm_target_id = target_id

    def leave_confirm_mode(self) -> None:
        self.mode = "NORMAL"
        self.confirm_prompt = ""
        self.confirm_action = None
        self.confirm_target_id = None

    def switch_tab(self, tab_id: str, label: str | None = None) -> None:
        self.current_tab = tab_id
        self.clear_edit_buffer()
        if tab_id == "home":
            self.ensure_request_workspace()
        if tab_id == "history":
            self.clamp_selected_history_index()
        if tab_id == "env":
            self.ensure_env_workspace()
        if label is not None:
            self.message = f"Switched to {label}."

    def cycle_tab(self, step: int) -> None:
        current_tab = (
            self.help_return_tab
            if self.current_tab not in TAB_ORDER
            else self.current_tab
        )
        index = TAB_ORDER.index(current_tab)
        self.current_tab = TAB_ORDER[(index + step) % len(TAB_ORDER)]
        if self.current_tab == "home":
            self.ensure_request_workspace()
        if self.current_tab == "history":
            self.clamp_selected_history_index()

    def open_help_tab(self, *, source_mode: str) -> None:
        source_tab = self.help_source_tab if self.current_tab == "help" else self.current_tab
        return_tab = self.help_return_tab if self.current_tab == "help" else self.current_tab
        self.help_source_tab = source_tab
        self.help_return_tab = return_tab
        self.help_source_mode = source_mode
        self.current_tab = "help"
        self.mode = "NORMAL"
        self.message = ""

    def leave_help_tab(self) -> None:
        target_tab = self.help_return_tab if self.help_return_tab in TAB_ORDER else "home"
        self.switch_tab(target_tab)
        self.mode = "NORMAL"
        if self.current_tab == "env":
            self.ensure_env_workspace()

    def get_selected_history_entry(self) -> HistoryEntry | None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            return None
        self.clamp_selected_history_index()
        return visible_entries[self.selected_history_index]

    def visible_history_entries(self, raw_query: str | None = None) -> list[HistoryEntry]:
        query = self.history_filter_query if raw_query is None else raw_query
        return [
            entry
            for entry in self.history_entries
            if history_entry_matches(entry, query)
        ]

    def clamp_selected_history_index(self) -> None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            self.selected_history_index = 0
            self.history_scroll_offset = 0
            return
        self.selected_history_index = max(
            0, min(self.selected_history_index, len(visible_entries) - 1)
        )

    def clamp_history_scroll_offset(self, visible_rows: int) -> None:
        max_offset = max(len(self.visible_history_entries()) - max(visible_rows, 1), 0)
        self.history_scroll_offset = max(0, min(self.history_scroll_offset, max_offset))

    def select_history_entry(self, step: int) -> None:
        visible_entries = self.visible_history_entries()
        if not visible_entries:
            self.selected_history_index = 0
            return
        self.selected_history_index = (
            self.selected_history_index + step
        ) % len(visible_entries)

    def ensure_history_selection_visible(self, visible_rows: int) -> None:
        self.clamp_selected_history_index()
        if self.selected_history_index < self.history_scroll_offset:
            self.history_scroll_offset = self.selected_history_index
        elif self.selected_history_index >= self.history_scroll_offset + visible_rows:
            self.history_scroll_offset = self.selected_history_index - visible_rows + 1
        self.clamp_history_scroll_offset(visible_rows)

    def prepend_history_entry(self, entry: HistoryEntry) -> None:
        self.history_entries.insert(0, entry)
        self.selected_history_index = 0
        self.history_scroll_offset = 0

    def set_history_filter(self, raw_query: str) -> int:
        self.history_filter_query = raw_query.strip()
        self.selected_history_index = 0
        self.history_scroll_offset = 0
        self.clamp_selected_history_index()
        return len(self.visible_history_entries())

    def cycle_history_detail_block(self, step: int) -> None:
        blocks = ("request", "response")
        current = (
            self.selected_history_detail_block
            if self.selected_history_detail_block in blocks
            else "response"
        )
        index = blocks.index(current)
        self.selected_history_detail_block = blocks[(index + step) % len(blocks)]

    def cycle_history_request_tab(self, step: int) -> None:
        tabs = ("body", "headers")
        current = (
            self.selected_history_request_tab
            if self.selected_history_request_tab in tabs
            else "body"
        )
        index = tabs.index(current)
        self.selected_history_request_tab = tabs[(index + step) % len(tabs)]
        self.history_request_scroll_offset = 0

    def cycle_history_response_tab(self, step: int) -> None:
        tabs = ("body", "headers")
        current = (
            self.selected_history_response_tab
            if self.selected_history_response_tab in tabs
            else "body"
        )
        index = tabs.index(current)
        self.selected_history_response_tab = tabs[(index + step) % len(tabs)]
        self.history_response_scroll_offset = 0

    def enter_history_response_select_mode(self, origin_mode: str | None = None) -> bool:
        if self.get_selected_history_entry() is None:
            self.message = "No history entry selected."
            return False
        self.history_response_select_return_mode = origin_mode or self.mode
        self.mode = "HISTORY_RESPONSE_SELECT"
        self.message = ""
        return True

    def leave_history_response_select_mode(self) -> None:
        self.mode = self.history_response_select_return_mode or "NORMAL"
        self.message = ""

    def enter_history_response_view_mode(self, origin_mode: str | None = None) -> bool:
        if self.get_selected_history_entry() is None:
            self.message = "No history entry selected."
            return False
        self.history_response_view_return_mode = origin_mode or self.mode
        self.mode = "HISTORY_RESPONSE_TEXTAREA"
        self.message = ""
        return True

    def leave_history_response_view_mode(self) -> None:
        self.mode = self.history_response_view_return_mode or "NORMAL"
        self.message = ""

    def scroll_history_request(self, step: int) -> None:
        self.history_request_scroll_offset = max(
            0, self.history_request_scroll_offset + step
        )

    def scroll_history_response(self, step: int) -> None:
        self.history_response_scroll_offset = max(
            0, self.history_response_scroll_offset + step
        )

    def clamp_history_request_scroll_offset(
        self,
        total_rows: int,
        visible_rows: int,
    ) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.history_request_scroll_offset = max(
            0,
            min(self.history_request_scroll_offset, max_offset),
        )

    def clamp_history_response_scroll_offset(
        self,
        total_rows: int,
        visible_rows: int,
    ) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.history_response_scroll_offset = max(
            0,
            min(self.history_response_scroll_offset, max_offset),
        )

    def get_request_items(self) -> list[RequestDefinition]:
        return self.requests

    def ensure_env_workspace(self) -> None:
        if not self.env_names:
            self.env_names = ["Default"]
        if not self.env_sets:
            self.env_sets = {"Default": {}}
        for name in list(self.env_names):
            self.env_sets.setdefault(name, {})
        self.env_names = [name for name in self.env_names if name in self.env_sets]
        if not self.env_names:
            self.env_names = ["Default"]
            self.env_sets = {"Default": {}}
        if self.selected_env_name not in self.env_sets:
            self.selected_env_name = self.env_names[0]
        self.env_pairs = self.env_sets[self.selected_env_name]

    def active_env_label(self) -> str:
        self.ensure_env_workspace()
        return self.selected_env_name

    def select_env_set(self, step: int) -> None:
        self.ensure_env_workspace()
        if not self.env_names:
            return
        current_index = (
            self.env_names.index(self.selected_env_name)
            if self.selected_env_name in self.env_names
            else 0
        )
        self.selected_env_name = self.env_names[
            (current_index + step) % len(self.env_names)
        ]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.clear_edit_buffer()
        self.message = f"Selected env {self.selected_env_name}."

    def create_env_set(self, name: str) -> bool:
        self.ensure_env_workspace()
        env_name = name.strip()
        if not env_name:
            self.message = "Name cannot be empty."
            return False
        if env_name in self.env_sets:
            self.message = f"Env {env_name} already exists."
            return False
        self.env_names.append(env_name)
        self.env_sets[env_name] = {}
        self.selected_env_name = env_name
        self.env_pairs = self.env_sets[env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.mode = "NORMAL"
        self.message = f"Created env {env_name}."
        return True

    def rename_selected_env_set(self, name: str) -> bool:
        self.ensure_env_workspace()
        old_name = self.selected_env_name
        new_name = name.strip()
        if not new_name:
            self.message = "Name cannot be empty."
            return False
        if new_name == old_name:
            self.message = f"Renamed env {new_name}."
            return True
        if new_name in self.env_sets:
            self.message = f"Env {new_name} already exists."
            return False
        pairs = self.env_sets.pop(old_name, {})
        self.env_sets[new_name] = pairs
        self.env_names = [new_name if item == old_name else item for item in self.env_names]
        self.selected_env_name = new_name
        self.env_pairs = pairs
        self.message = f"Renamed env {new_name}."
        return True

    def delete_selected_env_set(self) -> bool:
        self.ensure_env_workspace()
        if len(self.env_names) <= 1:
            self.message = "At least one env must remain."
            return False
        env_name = self.selected_env_name
        current_index = self.env_names.index(env_name)
        self.env_names = [name for name in self.env_names if name != env_name]
        self.env_sets.pop(env_name, None)
        self.selected_env_name = self.env_names[min(current_index, len(self.env_names) - 1)]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.clear_edit_buffer()
        self.mode = "NORMAL"
        self.message = f"Deleted env {env_name}."
        return True

    def import_env_sets(
        self,
        env_names: list[str],
        env_sets: dict[str, dict[str, str]],
    ) -> int:
        self.ensure_env_workspace()
        if not env_names:
            self.message = "No envs found in import file."
            return 0

        used_names = {name.strip().lower() for name in self.env_names}
        imported_names: list[str] = []
        for original_name in env_names:
            pairs = env_sets.get(original_name, {})
            unique_name = self._unique_env_set_name(original_name, used_names)
            self.env_names.append(unique_name)
            self.env_sets[unique_name] = dict(pairs)
            imported_names.append(unique_name)

        if not imported_names:
            self.message = "No envs found in import file."
            return 0

        self.selected_env_name = imported_names[0]
        self.env_pairs = self.env_sets[self.selected_env_name]
        self.selected_env_index = 0
        self.env_scroll_offset = 0
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.clear_edit_buffer()
        self.current_tab = "env"
        self.mode = "NORMAL"
        self.message = (
            f"Imported {len(imported_names)} env."
            if len(imported_names) == 1
            else f"Imported {len(imported_names)} envs."
        )
        return len(imported_names)

    def get_collection_by_id(self, collection_id: str | None) -> CollectionDefinition | None:
        if collection_id is None:
            return None
        for collection in self.collections:
            if collection.collection_id == collection_id:
                return collection
        return None

    def _unique_env_set_name(self, base_name: str, used_names: set[str]) -> str:
        candidate = base_name.strip() or "Imported"
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

    def get_folder_by_id(self, folder_id: str | None) -> FolderDefinition | None:
        if folder_id is None:
            return None
        for folder in self.folders:
            if folder.folder_id == folder_id:
                return folder
        return None

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

    def get_request_by_id(self, request_id: str) -> RequestDefinition | None:
        for request in self.requests:
            if request.request_id == request_id:
                return request
        return None

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
            return True
        if node.kind == "folder":
            if node.node_id in self.collapsed_folder_ids:
                self.collapsed_folder_ids.discard(node.node_id)
            else:
                self.collapsed_folder_ids.add(node.node_id)
            self.clamp_selected_sidebar_index()
            self.active_request_id = None
            self.preview_request_id = None
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
                return True
            return False
        if node.kind == "folder":
            if node.node_id not in self.collapsed_folder_ids:
                self.collapsed_folder_ids.add(node.node_id)
                self.active_request_id = None
                self.preview_request_id = None
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
            return True
        if request.collection_id is not None:
            self.collapsed_collection_ids.add(request.collection_id)
            self._set_selected_sidebar_node("collection", request.collection_id)
            self.active_request_id = None
            self.preview_request_id = None
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
        self.mode = "NORMAL"
        self.clear_edit_buffer()
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
        self.requests.append(request)
        self._expand_request_ancestors(request)
        self.current_tab = "home"
        self.home_editor_tab = "request"
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        self.mode = "HOME_SECTION_SELECT"
        self.message = ""
        return request

    def replay_selected_history_entry(self) -> RequestDefinition | None:
        entry = self.get_selected_history_entry()
        if entry is None:
            self.message = "No history entry selected."
            return None

        redacted_marker = "<redacted>"
        redacted_omitted = False
        auth_api_key_value = ""
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
        if entry.request_body_type == "raw":
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
            auth_type=entry.auth_type if entry.auth_type in {"basic", "bearer", "api-key"} else "none",
            auth_api_key_name=entry.auth_name or "X-API-Key",
            auth_api_key_value=auth_api_key_value,
            auth_api_key_location=entry.auth_location if entry.auth_location in {"header", "query"} else "header",
            transient=True,
            body_type=entry.request_body_type if entry.request_body_type in {"none", "raw", "form-data", "x-www-form-urlencoded"} else "none",
            body_text=body_text,
            body_form_items=body_form_items,
            body_urlencoded_items=body_urlencoded_items,
        )
        self.requests.append(replay)
        self.current_tab = "home"
        self.home_editor_tab = "request"
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        self.mode = "HOME_SECTION_SELECT"
        self.message = (
            "Replayed history into a temporary request. Redacted secrets were omitted."
            if redacted_omitted
            else "Replayed history into a temporary request."
        )
        return replay

    def create_collection(self, name: str) -> CollectionDefinition:
        collection = CollectionDefinition(name=name)
        self.collections.append(collection)
        self.current_tab = "home"
        self.collapsed_collection_ids.add(collection.collection_id)
        self._set_selected_sidebar_node("collection", collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Created collection {name}."
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
        self.folders.append(folder)
        self.current_tab = "home"
        self.collapsed_collection_ids.discard(collection_id)
        if parent_folder_id is not None:
            self.collapsed_folder_ids.discard(parent_folder_id)
        self.collapsed_folder_ids.add(folder.folder_id)
        self._set_selected_sidebar_node("folder", folder.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Created folder {name}."
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
        self.current_tab = "home"
        self.mode = "NORMAL"
        self.message = f"Renamed request {new_name}."
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
        self.current_tab = "home"
        self._set_selected_sidebar_node("collection", collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Renamed collection {new_name}."
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
        self.current_tab = "home"
        self._set_selected_sidebar_node("folder", folder.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Renamed folder {new_name}."
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
        self.requests.append(copied)
        self.current_tab = "home"
        self.home_editor_tab = "request"
        self.selected_request_field_index = 0
        self.activate_request_by_index(len(self.requests) - 1, pin=True)
        request_label = request.name.strip() or "request"
        self.message = f"Copied request {request_label}."
        return copied

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
        folder_id_map: dict[str, str] = {}
        copied_folders: list[FolderDefinition] = []
        for original in subtree:
            new_folder_id = uuid4().hex
            folder_id_map[original.folder_id] = new_folder_id
            copied_folders.append(
                FolderDefinition(
                    folder_id=new_folder_id,
                    name=(
                        f"{original.name} Copy"
                        if original.folder_id == folder.folder_id
                        else original.name
                    ),
                    collection_id=collection_id,
                    parent_folder_id=(
                        parent_folder_id
                        if original.folder_id == folder.folder_id
                        else folder_id_map.get(original.parent_folder_id)
                    ),
                )
            )

        subtree_ids = {item.folder_id for item in subtree}
        copied_requests: list[RequestDefinition] = []
        for request in self.requests:
            if request.folder_id not in subtree_ids:
                continue
            copied = deepcopy(request)
            copied.request_id = uuid4().hex
            copied.collection_id = collection_id
            copied.folder_id = folder_id_map.get(request.folder_id)
            copied_requests.append(copied)

        self.folders.extend(copied_folders)
        self.requests.extend(copied_requests)
        copied_root = copied_folders[0]
        self.current_tab = "home"
        self.collapsed_collection_ids.discard(collection_id)
        if parent_folder_id is not None:
            for ancestor in self.folder_chain(parent_folder_id):
                self.collapsed_folder_ids.discard(ancestor.folder_id)
        self.collapsed_folder_ids.add(copied_root.folder_id)
        self._set_selected_sidebar_node("folder", copied_root.folder_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Copied folder {folder.name}."
        return copied_root

    def copy_collection(self, collection_id: str) -> CollectionDefinition | None:
        collection = self.get_collection_by_id(collection_id)
        if collection is None:
            self.message = "Collection not found."
            return None

        copied_collection = CollectionDefinition(name=f"{collection.name} Copy")
        self.collections.append(copied_collection)

        source_folders = [
            folder
            for folder in self.folders
            if folder.collection_id == collection.collection_id
        ]
        ordered_folders = sorted(source_folders, key=lambda item: len(self.folder_chain(item.folder_id)))
        folder_id_map: dict[str, str] = {}
        copied_folders: list[FolderDefinition] = []
        for original in ordered_folders:
            new_folder_id = uuid4().hex
            folder_id_map[original.folder_id] = new_folder_id
            copied_folders.append(
                FolderDefinition(
                    folder_id=new_folder_id,
                    name=original.name,
                    collection_id=copied_collection.collection_id,
                    parent_folder_id=folder_id_map.get(original.parent_folder_id),
                )
            )

        copied_requests: list[RequestDefinition] = []
        for request in self.requests:
            if request.collection_id != collection.collection_id:
                continue
            copied = deepcopy(request)
            copied.request_id = uuid4().hex
            copied.collection_id = copied_collection.collection_id
            copied.folder_id = (
                folder_id_map.get(request.folder_id)
                if request.folder_id is not None
                else None
            )
            copied_requests.append(copied)

        self.folders.extend(copied_folders)
        self.requests.extend(copied_requests)
        self.current_tab = "home"
        self.collapsed_collection_ids.add(copied_collection.collection_id)
        self._set_selected_sidebar_node("collection", copied_collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = f"Copied collection {collection.name}."
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

        self.collections.extend(imported_collections)
        self.folders.extend(imported_folders)
        self.requests.extend(imported_requests)
        first_collection = imported_collections[0]
        self.current_tab = "home"
        self.collapsed_collection_ids.discard(first_collection.collection_id)
        self._set_selected_sidebar_node("collection", first_collection.collection_id)
        self.active_request_id = None
        self.preview_request_id = None
        self.mode = "NORMAL"
        self.message = (
            f"Imported {len(imported_collections)} collection."
            if len(imported_collections) == 1
            else f"Imported {len(imported_collections)} collections."
        )
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

        deleted = self.requests.pop(self.selected_request_index)
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

        self.clear_edit_buffer()
        self.mode = "NORMAL"
        self.message = f"Deleted {deleted.name}."
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
        self.mode = "NORMAL"
        self.message = f"Deleted collection {collection.name}."
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
        self.mode = "NORMAL"
        self.message = f"Deleted folder {folder.name}."
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

    def set_home_editor_tab(self, tab_id: str) -> None:
        if tab_id not in REQUEST_FIELDS_BY_EDITOR_TAB:
            return
        self.home_editor_tab = tab_id
        self.selected_request_field_index = 0
        self.selected_auth_index = 0
        self.selected_param_index = 0
        self.selected_header_index = 0
        self.selected_body_index = 0
        self._clamp_selected_request_field_index()

    def cycle_home_editor_tab(self, step: int) -> None:
        tab_ids = [tab_id for tab_id, _label in REQUEST_EDITOR_TABS]
        current_index = tab_ids.index(self.home_editor_tab)
        self.home_editor_tab = tab_ids[(current_index + step) % len(tab_ids)]
        self.selected_request_field_index = 0
        self.selected_auth_index = 0
        self.selected_param_index = 0
        self.selected_header_index = 0
        self.selected_body_index = 0
        self._clamp_selected_request_field_index()

    def enter_home_section_select_mode(self) -> None:
        if not self.requests:
            self.message = "No requests to edit."
            self.mode = "NORMAL"
            return
        self.current_tab = "home"
        self.ensure_request_workspace()
        self.pin_active_request()
        self.mode = "HOME_SECTION_SELECT"
        self.clear_edit_buffer()
        self.message = ""

    def current_request_fields(self) -> tuple[tuple[str, str], ...]:
        return REQUEST_FIELDS_BY_EDITOR_TAB[self.home_editor_tab]

    def _clamp_selected_request_field_index(self) -> None:
        fields = self.current_request_fields()
        self.selected_request_field_index = max(
            0, min(self.selected_request_field_index, len(fields) - 1)
        )

    def enter_home_request_select_mode(self) -> None:
        if not self.requests:
            self.message = "No requests to edit."
            self.mode = "NORMAL"
            return
        self.current_tab = "home"
        self.ensure_request_workspace()
        self.pin_active_request()
        self.mode = "HOME_REQUEST_SELECT"
        self.selected_request_field_index = 0
        self._clamp_selected_request_field_index()
        self.message = ""

    def get_active_request_params(self) -> list[tuple[str, str]]:
        request = self.get_active_request()
        if request is None:
            return []
        return request.query_items

    def get_active_request_headers(self) -> list[tuple[str, str]]:
        request = self.get_active_request()
        if request is None:
            return []
        return request.header_items

    def auth_fields(self, request: RequestDefinition | None = None) -> tuple[tuple[str, str], ...]:
        current = request if request is not None else self.get_active_request()
        if current is None:
            return ()
        if current.auth_type == "basic":
            return (
                ("auth_basic_username", "Username"),
                ("auth_basic_password", "Password"),
            )
        if current.auth_type == "bearer":
            return (("auth_bearer_token", "Token"),)
        if current.auth_type == "api-key":
            return (
                ("auth_api_key_location", "Add To"),
                ("auth_api_key_name", "Key"),
                ("auth_api_key_value", "Value"),
            )
        return ()

    def auth_type_label(self, auth_type: str | None = None) -> str:
        current = auth_type
        if current is None:
            request = self.get_active_request()
            current = request.auth_type if request is not None else "none"
        for value, label in AUTH_TYPE_OPTIONS:
            if value == current:
                return label
        return current

    def auth_api_key_location_label(self, location: str | None = None) -> str:
        current = location
        if current is None:
            request = self.get_active_request()
            current = request.auth_api_key_location if request is not None else "header"
        for value, label in AUTH_API_KEY_LOCATION_OPTIONS:
            if value == current:
                return label
        return current

    def clamp_selected_auth_index(self) -> None:
        field_count = len(self.auth_fields())
        if field_count <= 0:
            self.selected_auth_index = 0
            return
        self.selected_auth_index = max(1, min(self.selected_auth_index, field_count))

    def select_auth_row(self, step: int) -> None:
        field_count = len(self.auth_fields())
        if field_count <= 0:
            self.selected_auth_index = 0
            return
        options = list(range(1, field_count + 1))
        current = self.selected_auth_index if self.selected_auth_index in options else options[0]
        self.selected_auth_index = options[
            (options.index(current) + step) % len(options)
        ]

    def selected_auth_field(self) -> tuple[str, str] | None:
        fields = self.auth_fields()
        if self.selected_auth_index <= 0:
            return None
        index = self.selected_auth_index - 1
        if index < 0 or index >= len(fields):
            return None
        return fields[index]

    def enter_home_auth_select_mode(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.current_tab = "home"
        self.pin_active_request()
        self.mode = "HOME_AUTH_SELECT"
        if self.auth_fields(request):
            self.selected_auth_index = 1
        else:
            self.selected_auth_index = 0
        self.message = ""

    def enter_home_auth_edit_mode(self) -> None:
        request = self.get_active_request()
        field = self.selected_auth_field()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        if field is None:
            self.mode = "HOME_AUTH_SELECT"
            self.message = "Select an auth field to edit."
            return
        field_name, _field_label = field
        if field_name == "auth_api_key_location":
            self.mode = "HOME_AUTH_LOCATION_EDIT"
            self.message = ""
            return
        self.mode = "HOME_AUTH_EDIT"
        self.set_edit_buffer(str(getattr(request, field_name) or ""), replace_on_next_input=False)
        self.message = ""

    def leave_home_auth_edit_mode(self) -> None:
        self.mode = "HOME_AUTH_TYPE_EDIT"
        self.selected_auth_index = 0
        self.clear_edit_buffer()
        self.message = ""

    def enter_home_auth_type_edit_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.home_auth_type_return_mode = origin_mode or self.mode
        self.mode = "HOME_AUTH_TYPE_EDIT"
        self.message = ""

    def leave_home_auth_type_edit_mode(self) -> None:
        if self.home_auth_type_return_mode == "HOME_SECTION_SELECT":
            self.enter_home_section_select_mode()
            return
        self.mode = "HOME_AUTH_SELECT"
        self.clamp_selected_auth_index()
        self.message = ""

    def leave_home_auth_location_edit_mode(self) -> None:
        self.mode = "HOME_AUTH_TYPE_EDIT"
        self.selected_auth_index = 0
        self.message = ""

    def cycle_auth_type(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        values = [value for value, _label in AUTH_TYPE_OPTIONS]
        if request.auth_type not in values:
            request.auth_type = values[0]
        index = values.index(request.auth_type)
        request.auth_type = values[(index + step) % len(values)]
        self.clamp_selected_auth_index()
        self.message = f"Auth type: {self.auth_type_label(request.auth_type)}."
        return request.auth_type

    def cycle_auth_api_key_location(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        values = [value for value, _label in AUTH_API_KEY_LOCATION_OPTIONS]
        if request.auth_api_key_location not in values:
            request.auth_api_key_location = values[0]
        index = values.index(request.auth_api_key_location)
        request.auth_api_key_location = values[(index + step) % len(values)]
        self.message = (
            f"API key location: {self.auth_api_key_location_label(request.auth_api_key_location)}."
        )
        return request.auth_api_key_location

    def save_selected_auth_field(self) -> str | None:
        request = self.get_active_request()
        field = self.selected_auth_field()
        if request is None or field is None:
            return None
        field_name, field_label = field
        value = self.edit_buffer.strip() if field_name == "auth_api_key_name" else self.edit_buffer
        if field_name == "auth_api_key_name" and not value.strip():
            self.message = "Key cannot be empty."
            return None
        setattr(request, field_name, value)
        self.mode = "HOME_AUTH_TYPE_EDIT"
        self.selected_auth_index = 0
        self.clear_edit_buffer()
        self.message = f"Updated {field_label.lower()}."
        return field_name


    def get_active_request_body_items(self) -> list[RequestKeyValue]:
        request = self.get_active_request()
        if request is None:
            return []
        if request.body_type == "form-data":
            return request.body_form_items
        if request.body_type == "x-www-form-urlencoded":
            return request.body_urlencoded_items
        return []

    def clamp_selected_param_index(self) -> None:
        item_count = len(self.get_active_request_params())
        max_index = max(0, item_count - 1)
        self.selected_param_index = max(0, min(self.selected_param_index, max_index))

    def select_param_row(self, step: int) -> None:
        item_count = len(self.get_active_request_params())
        if item_count == 0:
            self.selected_param_index = 0
            return
        self.selected_param_index = (self.selected_param_index + step) % item_count

    def cycle_param_field(self, step: int) -> None:
        self.selected_param_field_index = (self.selected_param_field_index + step) % 2

    def selected_param_field(self) -> tuple[str, str]:
        if self.selected_param_field_index == 0:
            return ("key", "Key")
        return ("value", "Value")

    def enter_home_params_select_mode(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.current_tab = "home"
        self.pin_active_request()
        self.mode = "HOME_PARAMS_SELECT"
        self.selected_param_field_index = 0
        self.params_creating_new = False
        self.clamp_selected_param_index()
        self.message = ""

    def enter_home_params_edit_mode(self, creating: bool = False) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        items = self.get_active_request_params()
        self.clamp_selected_param_index()
        self.mode = "HOME_PARAMS_EDIT"
        self.params_creating_new = creating
        if creating:
            self.selected_param_field_index = 0
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return
        if not items:
            self.mode = "HOME_PARAMS_SELECT"
            self.message = "Nothing to edit."
            return
        item = items[self.selected_param_index]
        field_name, _field_label = self.selected_param_field()
        self.set_edit_buffer(
            item.key if field_name == "key" else item.value,
            replace_on_next_input=False,
        )
        self.message = ""

    def leave_home_params_edit_mode(self) -> None:
        self.mode = "HOME_PARAMS_SELECT"
        self.params_creating_new = False
        self.clear_edit_buffer()
        self.message = ""

    def save_selected_param_field(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None

        items = self.get_active_request_params()
        field_name, field_label = self.selected_param_field()
        if self.params_creating_new:
            if field_name != "key":
                return None
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            items.append(RequestKeyValue(key=new_key, value=""))
            self.selected_param_index = max(0, len(items) - 1)
            self.selected_param_field_index = 1
            self.params_creating_new = False
            self.mode = "HOME_PARAMS_EDIT"
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return new_key

        self.clamp_selected_param_index()
        if not items:
            self.message = "Nothing to edit."
            return None
        item = items[self.selected_param_index]
        if field_name == "key":
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            item.key = new_key
            updated = new_key
        else:
            item.value = self.edit_buffer
            updated = item.key
        self.mode = "HOME_PARAMS_SELECT"
        self.params_creating_new = False
        self.clear_edit_buffer()
        self.message = f"Updated {field_label.lower()}."
        return updated

    def delete_selected_param(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        items = self.get_active_request_params()
        if not items:
            self.message = "No param selected."
            return None
        self.clamp_selected_param_index()
        key = items.pop(self.selected_param_index).key
        self.clamp_selected_param_index()
        self.mode = "HOME_PARAMS_SELECT"
        self.message = f"Deleted param {key}."
        return key

    def toggle_selected_param(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        items = self.get_active_request_params()
        if not items:
            self.message = "No param selected."
            return None
        self.clamp_selected_param_index()
        item = items[self.selected_param_index]
        item.enabled = not item.enabled
        self.message = (
            f"{'Enabled' if item.enabled else 'Disabled'} param {item.key}."
        )
        return item.key

    def clamp_selected_header_index(self, total_count: int | None = None) -> None:
        item_count = total_count if total_count is not None else len(self.get_active_request_headers())
        max_index = max(0, item_count - 1)
        self.selected_header_index = max(0, min(self.selected_header_index, max_index))

    def select_header_row(self, step: int, total_count: int | None = None) -> None:
        item_count = total_count if total_count is not None else len(self.get_active_request_headers())
        if item_count == 0:
            self.selected_header_index = 0
            return
        self.selected_header_index = (self.selected_header_index + step) % item_count

    def cycle_header_field(self, step: int) -> None:
        self.selected_header_field_index = (self.selected_header_field_index + step) % 2

    def selected_header_field(self) -> tuple[str, str]:
        if self.selected_header_field_index == 0:
            return ("key", "Key")
        return ("value", "Value")

    def enter_home_headers_select_mode(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.current_tab = "home"
        self.pin_active_request()
        self.mode = "HOME_HEADERS_SELECT"
        self.selected_header_field_index = 0
        self.headers_creating_new = False
        self.clamp_selected_header_index()
        self.message = ""

    def enter_home_headers_edit_mode(self, creating: bool = False) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        items = self.get_active_request_headers()
        self.clamp_selected_header_index()
        self.mode = "HOME_HEADERS_EDIT"
        self.headers_creating_new = creating
        if creating:
            self.selected_header_field_index = 0
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return
        if not items:
            self.mode = "HOME_HEADERS_SELECT"
            self.message = "Nothing to edit."
            return
        item = items[self.selected_header_index]
        field_name, _field_label = self.selected_header_field()
        self.set_edit_buffer(
            item.key if field_name == "key" else item.value,
            replace_on_next_input=False,
        )
        self.message = ""

    def leave_home_headers_edit_mode(self) -> None:
        self.mode = "HOME_HEADERS_SELECT"
        self.headers_creating_new = False
        self.clear_edit_buffer()
        self.message = ""

    def save_selected_header_field(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None

        items = self.get_active_request_headers()
        field_name, field_label = self.selected_header_field()
        if self.headers_creating_new:
            if field_name != "key":
                return None
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            items.append(RequestKeyValue(key=new_key, value=""))
            self.selected_header_index = max(0, len(items) - 1)
            self.selected_header_field_index = 1
            self.headers_creating_new = False
            self.mode = "HOME_HEADERS_EDIT"
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return new_key

        self.clamp_selected_header_index()
        if not items:
            self.message = "Nothing to edit."
            return None
        item = items[self.selected_header_index]
        if field_name == "key":
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            item.key = new_key
            updated = new_key
        else:
            item.value = self.edit_buffer
            updated = item.key
        self.mode = "HOME_HEADERS_SELECT"
        self.headers_creating_new = False
        self.clear_edit_buffer()
        self.message = f"Updated {field_label.lower()}."
        return updated

    def delete_selected_header(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        items = self.get_active_request_headers()
        if not items:
            self.message = "No header selected."
            return None
        self.clamp_selected_header_index()
        key = items.pop(self.selected_header_index).key
        self.clamp_selected_header_index()
        self.mode = "HOME_HEADERS_SELECT"
        self.message = f"Deleted header {key}."
        return key

    def toggle_selected_header(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        items = self.get_active_request_headers()
        if not items:
            self.message = "No header selected."
            return None
        self.clamp_selected_header_index()
        item = items[self.selected_header_index]
        item.enabled = not item.enabled
        self.message = (
            f"{'Enabled' if item.enabled else 'Disabled'} header {item.key}."
        )
        return item.key

    def toggle_auto_header(self, header_name: str) -> bool | None:
        request = self.get_active_request()
        if request is None:
            return None
        normalized = header_name.lower()
        if any(name.lower() == normalized for name in request.disabled_auto_headers):
            request.disabled_auto_headers = [
                name
                for name in request.disabled_auto_headers
                if name.lower() != normalized
            ]
            self.message = f"Enabled auto header {header_name}."
            return True
        request.disabled_auto_headers.append(header_name)
        self.message = f"Disabled auto header {header_name}."
        return False

    def body_type_label(self, body_type: str | None = None) -> str:
        current = body_type
        if current is None:
            request = self.get_active_request()
            current = request.body_type if request is not None else "none"
        for value, label in BODY_TYPE_OPTIONS:
            if value == current:
                return label
        return current

    def raw_subtype_label(self, raw_subtype: str | None = None) -> str:
        current = raw_subtype
        if current is None:
            request = self.get_active_request()
            current = request.raw_subtype if request is not None else "json"
        for value, label in RAW_SUBTYPE_OPTIONS:
            if value == current:
                return label
        return current

    def cycle_body_type(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        values = [value for value, _label in BODY_TYPE_OPTIONS]
        if request.body_type not in values:
            request.body_type = values[0]
        index = values.index(request.body_type)
        request.body_type = values[(index + step) % len(values)]
        self.selected_body_index = 0
        self.message = f"Body type: {self.body_type_label(request.body_type)}."
        return request.body_type

    def cycle_raw_subtype(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        values = [value for value, _label in RAW_SUBTYPE_OPTIONS]
        if request.raw_subtype not in values:
            request.raw_subtype = values[0]
        index = values.index(request.raw_subtype)
        request.raw_subtype = values[(index + step) % len(values)]
        self.message = f"Raw format: {self.raw_subtype_label(request.raw_subtype)}."
        return request.raw_subtype

    def clamp_selected_body_index(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.selected_body_index = 0
            return
        if request.body_type in {"form-data", "x-www-form-urlencoded"}:
            min_index = 1
            max_index = len(self.get_active_request_body_items()) + 1
        elif request.body_type == "raw":
            min_index = 0
            max_index = 1
        else:
            min_index = 0
            max_index = 0
        self.selected_body_index = max(min_index, min(self.selected_body_index, max_index))

    def select_body_row(self, step: int) -> None:
        request = self.get_active_request()
        if request is None:
            self.selected_body_index = 0
            return
        if request.body_type in {"form-data", "x-www-form-urlencoded"}:
            min_index = 1
            max_index = len(self.get_active_request_body_items()) + 1
        elif request.body_type == "raw":
            min_index = 0
            max_index = 1
        else:
            min_index = 0
            max_index = 0
        options = list(range(min_index, max_index + 1))
        if not options:
            self.selected_body_index = 0
            return
        current = self.selected_body_index
        if current not in options:
            current = options[0]
        current_index = options.index(current)
        self.selected_body_index = options[(current_index + step) % len(options)]

    def enter_home_body_select_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.current_tab = "home"
        self.pin_active_request()
        self.home_body_select_return_mode = origin_mode or self.mode
        self.mode = "HOME_BODY_SELECT"
        self.clamp_selected_body_index()
        self.message = ""

    def leave_home_body_select_mode(self) -> None:
        self.clear_edit_buffer()
        if self.home_body_select_return_mode == "HOME_BODY_TYPE_EDIT":
            self.mode = "HOME_BODY_TYPE_EDIT"
            self.message = ""
            return
        self.enter_home_section_select_mode()

    def enter_home_body_type_edit_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.home_body_type_return_mode = origin_mode or self.mode
        self.mode = "HOME_BODY_TYPE_EDIT"
        self.message = ""

    def enter_home_body_raw_type_edit_mode(
        self,
        origin_mode: str | None = None,
    ) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.home_body_raw_type_return_mode = origin_mode or self.mode
        self.mode = "HOME_BODY_RAW_TYPE_EDIT"
        self.message = ""

    def enter_home_body_text_editor_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.home_body_content_return_mode = origin_mode or self.mode
        self.mode = "HOME_BODY_TEXTAREA"
        self.message = ""

    def enter_home_response_view_mode(self, origin_mode: str | None = None) -> bool:
        request = self.get_active_request()
        if request is None or request.last_response is None:
            self.message = "No response to view."
            return False
        self.home_response_view_return_mode = origin_mode or self.mode
        self.mode = "HOME_RESPONSE_TEXTAREA"
        self.message = ""
        return True

    def enter_home_response_select_mode(self, origin_mode: str | None = None) -> bool:
        request = self.get_active_request()
        if request is None or request.last_response is None:
            self.message = "No response to inspect."
            return False
        self.home_response_select_return_mode = origin_mode or self.mode
        self.mode = "HOME_RESPONSE_SELECT"
        self.message = ""
        return True

    def leave_home_response_select_mode(self) -> None:
        self.mode = self.home_response_select_return_mode or "NORMAL"
        self.message = ""

    def leave_home_response_view_mode(self) -> None:
        self.mode = self.home_response_view_return_mode or "NORMAL"
        self.message = ""

    def enter_home_body_edit_mode(
        self,
        creating: bool = False,
        origin_mode: str | None = None,
    ) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        self.home_body_content_return_mode = origin_mode or self.mode
        self.clamp_selected_body_index()
        if request.body_type == "raw":
            self.enter_home_body_text_editor_mode(
                origin_mode=self.home_body_content_return_mode
            )
            return
        self.mode = "HOME_BODY_EDIT"
        if request.body_type in {"form-data", "x-www-form-urlencoded"}:
            items = self.get_active_request_body_items()
            item_index = self.selected_body_index - 1
        if creating or item_index < 0 or item_index >= len(items):
            self.selected_body_index = len(items) + 1
            self.set_edit_buffer("", replace_on_next_input=False)
        else:
            item = items[item_index]
            key, value = item.key, item.value
            self.set_edit_buffer(f"{key}={value}" if value else key, replace_on_next_input=False)
        self.message = ""

    def leave_home_body_edit_mode(self) -> None:
        self.clear_edit_buffer()
        self._restore_home_body_parent_mode()

    def leave_home_body_type_edit_mode(self) -> None:
        if self.home_body_type_return_mode == "HOME_BODY_SELECT":
            self.enter_home_body_select_mode(origin_mode="HOME_BODY_TYPE_EDIT")
            return
        self.enter_home_section_select_mode()

    def leave_home_body_raw_type_edit_mode(self) -> None:
        if self.home_body_raw_type_return_mode == "HOME_BODY_SELECT":
            self.enter_home_body_select_mode(origin_mode="HOME_BODY_RAW_TYPE_EDIT")
            return
        self.mode = "HOME_BODY_TYPE_EDIT"
        self.message = ""

    def leave_home_body_text_editor_mode(self) -> None:
        self._restore_home_body_parent_mode()

    def save_raw_body_text(self, value: str) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        request.body_text = value
        self._restore_home_body_parent_mode()
        self.message = "Updated body."
        return "body_text"

    def save_body_selection(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        if request.body_type in {"form-data", "x-www-form-urlencoded"}:
            payload = self.edit_buffer.strip()
            if not payload:
                self.message = "Use KEY=value"
                return None
            if "=" in payload:
                key, value = payload.split("=", 1)
            else:
                key, value = payload, ""
            key = key.strip()
            value = value.strip()
            if not key:
                self.message = "Use KEY=value"
                return None
            items = self.get_active_request_body_items()
            item_index = self.selected_body_index - 1
            if item_index < 0 or item_index >= len(items):
                items.append(RequestKeyValue(key=key, value=value))
                self.selected_body_index = len(items)
            else:
                items[item_index].key = key
                items[item_index].value = value
                self.selected_body_index = item_index + 1
            self.clear_edit_buffer()
            self._restore_home_body_parent_mode()
            self.message = f"Saved body field {key}."
            return key
        return None

    def delete_selected_body_field(self) -> str | None:
        request = self.get_active_request()
        if request is None or request.body_type not in {"form-data", "x-www-form-urlencoded"}:
            return None
        items = self.get_active_request_body_items()
        item_index = self.selected_body_index - 1
        if item_index < 0 or item_index >= len(items):
            self.message = "No body field selected."
            return None
        key = items.pop(item_index).key
        self.clamp_selected_body_index()
        self.mode = "HOME_BODY_SELECT"
        self.message = f"Deleted body field {key}."
        return key

    def toggle_selected_body_field(self) -> str | None:
        request = self.get_active_request()
        if request is None or request.body_type not in {"form-data", "x-www-form-urlencoded"}:
            return None
        items = self.get_active_request_body_items()
        item_index = self.selected_body_index - 1
        if item_index < 0 or item_index >= len(items):
            self.message = "No body field selected."
            return None
        item = items[item_index]
        item.enabled = not item.enabled
        self.message = (
            f"{'Enabled' if item.enabled else 'Disabled'} body field {item.key}."
        )
        return item.key

    def _restore_home_body_parent_mode(self) -> None:
        if self.home_body_content_return_mode == "HOME_BODY_RAW_TYPE_EDIT":
            self.mode = "HOME_BODY_RAW_TYPE_EDIT"
            self.message = ""
            return
        if self.home_body_content_return_mode == "HOME_BODY_TYPE_EDIT":
            self.mode = "HOME_BODY_TYPE_EDIT"
            self.message = ""
            return
        self.clamp_selected_body_index()
        self.mode = "HOME_BODY_SELECT"
        self.message = ""

    def select_request_field(self, step: int) -> None:
        fields = self.current_request_fields()
        self.selected_request_field_index = (
            self.selected_request_field_index + step
        ) % len(fields)

    def selected_request_field(self) -> tuple[str, str]:
        fields = self.current_request_fields()
        self._clamp_selected_request_field_index()
        return fields[self.selected_request_field_index]

    def enter_home_request_edit_mode(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = "NORMAL"
            self.message = "No requests to edit."
            return
        field_name, _ = self.selected_request_field()
        if field_name == "method":
            self.mode = "HOME_REQUEST_METHOD_EDIT"
            self.set_edit_buffer(request.method.upper() or "GET", replace_on_next_input=False)
            self.message = ""
            return
        self.mode = "HOME_REQUEST_EDIT"
        self.set_edit_buffer(str(getattr(request, field_name)), replace_on_next_input=False)
        self.message = ""

    def leave_home_request_edit_mode(self) -> None:
        self.mode = "HOME_REQUEST_SELECT"
        self.clear_edit_buffer()
        self.message = ""

    def cycle_request_method(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        current = (self.edit_buffer or request.method or "GET").upper()
        if current not in HTTP_METHODS:
            current = "GET"
        index = HTTP_METHODS.index(current)
        self.edit_buffer = HTTP_METHODS[(index + step) % len(HTTP_METHODS)]
        self.edit_cursor_index = len(self.edit_buffer)
        return self.edit_buffer

    def save_selected_request_method(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        request.method = (self.edit_buffer or "GET").upper()
        self.mode = "HOME_REQUEST_SELECT"
        self.clear_edit_buffer()
        self.message = "Updated Method."
        return "method"

    def save_selected_request_field(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        field_name, field_label = self.selected_request_field()
        value = self.edit_buffer
        if field_name == "method":
            value = value.upper() or "GET"
        if field_name == "name" and not value.strip():
            value = "Untitled Request"
        setattr(request, field_name, value)
        self.mode = "HOME_REQUEST_SELECT"
        self.clear_edit_buffer()
        self.message = f"Updated {field_label}."
        return field_name

    def scroll_response(self, step: int) -> None:
        self.response_scroll_offset = max(0, self.response_scroll_offset + step)

    def clamp_response_scroll_offset(self, total_rows: int, visible_rows: int) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.response_scroll_offset = max(0, min(self.response_scroll_offset, max_offset))

    def cycle_home_response_tab(self, step: int) -> None:
        tabs = ("body", "headers")
        current = (
            self.selected_home_response_tab
            if self.selected_home_response_tab in tabs
            else "body"
        )
        index = tabs.index(current)
        self.selected_home_response_tab = tabs[(index + step) % len(tabs)]
        self.response_scroll_offset = 0

    def get_env_items(self) -> list[tuple[str, str]]:
        self.ensure_env_workspace()
        return list(self.env_pairs.items())

    def clamp_selected_env_index(self) -> None:
        items = self.get_env_items()
        if not items:
            self.selected_env_index = 0
            return
        self.selected_env_index = max(0, min(self.selected_env_index, len(items) - 1))

    def clamp_env_scroll_offset(self, visible_rows: int) -> None:
        item_count = len(self.get_env_items())
        max_offset = max(item_count - max(visible_rows, 1), 0)
        self.env_scroll_offset = max(0, min(self.env_scroll_offset, max_offset))

    def select_env_row(self, step: int) -> None:
        items = self.get_env_items()
        if not items:
            self.selected_env_index = 0
            return
        self.selected_env_index = (self.selected_env_index + step) % len(items)

    def ensure_env_selection_visible(self, visible_rows: int) -> None:
        self.clamp_selected_env_index()
        if self.selected_env_index < self.env_scroll_offset:
            self.env_scroll_offset = self.selected_env_index
        elif self.selected_env_index >= self.env_scroll_offset + visible_rows:
            self.env_scroll_offset = self.selected_env_index - visible_rows + 1
        self.clamp_env_scroll_offset(visible_rows)

    def scroll_env_window(self, step: int, visible_rows: int) -> None:
        self.env_scroll_offset += step
        self.clamp_env_scroll_offset(visible_rows)

    def enter_env_select_mode(self) -> None:
        self.ensure_env_workspace()
        self.current_tab = "env"
        self.mode = "ENV_SELECT"
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.message = "h/l fields, e edit, d delete, Esc back."
        self.clamp_selected_env_index()

    def cycle_env_field(self, step: int) -> None:
        self.selected_env_field_index = (self.selected_env_field_index + step) % 2

    def selected_env_field(self) -> tuple[str, str]:
        if self.selected_env_field_index == 0:
            return ("key", "Key")
        return ("value", "Value")

    def enter_env_edit_mode(self) -> None:
        item = self.get_selected_env_item()
        if item is None:
            self.message = "Nothing to edit."
            self.mode = "NORMAL"
            return
        key, value = item
        field_name, _field_label = self.selected_env_field()
        self.mode = "ENV_EDIT"
        if field_name == "key":
            self.set_edit_buffer(key, replace_on_next_input=False)
        else:
            self.set_edit_buffer(value, replace_on_next_input=False)
        self.message = ""

    def enter_env_create_mode(self) -> None:
        self.ensure_env_workspace()
        self.current_tab = "env"
        self.mode = "ENV_EDIT"
        self.selected_env_field_index = 0
        self.env_creating_new = True
        self.set_edit_buffer("", replace_on_next_input=False)
        self.message = ""

    def leave_env_edit_mode(self) -> None:
        self.mode = "ENV_SELECT"
        self.env_creating_new = False
        self.clear_edit_buffer()
        self.message = "h/l fields, e edit, d delete, Esc back."

    def leave_env_interaction(self) -> None:
        self.mode = "NORMAL"
        self.selected_env_field_index = 0
        self.env_creating_new = False
        self.clear_edit_buffer()

    def get_selected_env_item(self) -> tuple[str, str] | None:
        items = self.get_env_items()
        if not items:
            return None
        self.clamp_selected_env_index()
        return items[self.selected_env_index]

    def save_selected_env_field(self) -> str | None:
        self.ensure_env_workspace()
        field_name, field_label = self.selected_env_field()
        if self.env_creating_new:
            if field_name != "key":
                return None
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            if new_key in self.env_pairs:
                self.message = f"Key {new_key} already exists."
                return None
            self.env_pairs[new_key] = ""
            self.env_sets[self.selected_env_name] = self.env_pairs
            self.selected_env_index = max(0, len(self.env_pairs) - 1)
            self.selected_env_field_index = 1
            self.env_creating_new = False
            self.mode = "ENV_EDIT"
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return new_key

        item = self.get_selected_env_item()
        if item is None:
            return None
        key, value = item
        if field_name == "key":
            new_key = self.edit_buffer.strip()
            if not new_key:
                self.message = "Key cannot be empty."
                return None
            if new_key != key and new_key in self.env_pairs:
                self.message = f"Key {new_key} already exists."
                return None
            items = self.get_env_items()
            items[self.selected_env_index] = (new_key, value)
            self.env_pairs = dict(items)
            self.env_sets[self.selected_env_name] = self.env_pairs
            updated = new_key
        else:
            self.env_pairs[key] = self.edit_buffer
            self.env_sets[self.selected_env_name] = self.env_pairs
            updated = key
        self.mode = "ENV_SELECT"
        self.clear_edit_buffer()
        self.message = f"Updated {field_label.lower()}."
        return updated

    def delete_env_key(self, key: str) -> bool:
        self.ensure_env_workspace()
        if key not in self.env_pairs:
            return False
        del self.env_pairs[key]
        self.env_sets[self.selected_env_name] = self.env_pairs
        self.clamp_selected_env_index()
        self.clear_edit_buffer()
        self.mode = "NORMAL"
        self.selected_env_field_index = 0
        self.message = f"Deleted {key}."
        return True

    def delete_selected_env_item(self) -> str | None:
        item = self.get_selected_env_item()
        if item is None:
            return None
        key, _ = item
        deleted = self.delete_env_key(key)
        if not deleted:
            return None
        if self.env_pairs:
            self.mode = "NORMAL"
            self.message = "Deleted row."
        return key
