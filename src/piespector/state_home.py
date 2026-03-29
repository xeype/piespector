from __future__ import annotations

from piespector.domain.editor import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS,
    AUTH_TYPE_OPTIONS,
    BODY_KEY_VALUE_TYPES,
    BODY_TEXT_EDITOR_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_AUTH,
    HOME_EDITOR_TAB_BODY,
    HOME_EDITOR_TAB_HEADERS,
    HOME_EDITOR_TAB_PARAMS,
    TAB_HOME,
    RAW_SUBTYPE_OPTIONS,
    REQUEST_EDITOR_TABS,
    REQUEST_FIELDS_BY_EDITOR_TAB,
    RESPONSE_TAB_BODY,
    RESPONSE_TABS,
)
from piespector.domain.http import HTTP_METHODS
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_RESPONSE_TEXTAREA,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)
from piespector.domain.requests import RequestDefinition, RequestKeyValue


class HomeStateMixin:
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
            self.mode = MODE_NORMAL
            return
        self.current_tab = TAB_HOME
        self.ensure_request_workspace()
        self.pin_active_request()
        self.mode = MODE_HOME_SECTION_SELECT
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
            self.mode = MODE_NORMAL
            return
        self.current_tab = TAB_HOME
        self.ensure_request_workspace()
        self.pin_active_request()
        self.mode = MODE_HOME_REQUEST_SELECT
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
            return (
                ("auth_bearer_prefix", "Header Prefix"),
                ("auth_bearer_token", "Token"),
            )
        if current.auth_type == "api-key":
            return (
                ("auth_api_key_location", "Add To"),
                ("auth_api_key_name", "Key"),
                ("auth_api_key_value", "Value"),
            )
        if current.auth_type == "cookie":
            return (
                ("auth_cookie_name", "Cookie"),
                ("auth_cookie_value", "Value"),
            )
        if current.auth_type == "custom-header":
            return (
                ("auth_custom_header_name", "Header"),
                ("auth_custom_header_value", "Value"),
            )
        if current.auth_type == "oauth2-client-credentials":
            return (
                ("auth_oauth_token_url", "Token URL"),
                ("auth_oauth_client_id", "Client ID"),
                ("auth_oauth_client_secret", "Client Secret"),
                ("auth_oauth_client_authentication", "Client Auth"),
                ("auth_oauth_header_prefix", "Header Prefix"),
                ("auth_oauth_scope", "Scope"),
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

    def auth_oauth_client_authentication_label(self, value: str | None = None) -> str:
        current = value
        if current is None:
            request = self.get_active_request()
            current = (
                request.auth_oauth_client_authentication
                if request is not None
                else "basic-header"
            )
        for option_value, label in AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS:
            if option_value == current:
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
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.current_tab = TAB_HOME
        self.pin_active_request()
        self.mode = MODE_HOME_AUTH_SELECT
        if self.auth_fields(request):
            self.selected_auth_index = 1
        else:
            self.selected_auth_index = 0
        self.message = ""

    def enter_home_auth_edit_mode(self) -> None:
        request = self.get_active_request()
        field = self.selected_auth_field()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        if field is None:
            self.mode = MODE_HOME_AUTH_SELECT
            self.message = "Select an auth field to edit."
            return
        field_name, _field_label = field
        if field_name in {"auth_api_key_location", "auth_oauth_client_authentication"}:
            self.mode = MODE_HOME_AUTH_LOCATION_EDIT
            self.message = ""
            return
        self.mode = MODE_HOME_AUTH_EDIT
        self.set_edit_buffer(str(getattr(request, field_name) or ""), replace_on_next_input=False)
        self.message = ""

    def leave_home_auth_edit_mode(self) -> None:
        self.mode = MODE_HOME_AUTH_SELECT
        self.clamp_selected_auth_index()
        self.clear_edit_buffer()
        self.message = ""

    def enter_home_auth_type_edit_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.home_auth_type_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_AUTH_TYPE_EDIT
        self.message = ""

    def leave_home_auth_type_edit_mode(self) -> None:
        if self.home_auth_type_return_mode == MODE_HOME_SECTION_SELECT:
            self.enter_home_section_select_mode()
            return
        self.mode = MODE_HOME_AUTH_SELECT
        self.clamp_selected_auth_index()
        self.message = ""

    def leave_home_auth_location_edit_mode(self) -> None:
        self.mode = MODE_HOME_AUTH_SELECT
        self.clamp_selected_auth_index()
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

    def cycle_auth_oauth_client_authentication(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        values = [value for value, _label in AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS]
        if request.auth_oauth_client_authentication not in values:
            request.auth_oauth_client_authentication = values[0]
        index = values.index(request.auth_oauth_client_authentication)
        request.auth_oauth_client_authentication = values[(index + step) % len(values)]
        self.message = (
            "OAuth client authentication: "
            f"{self.auth_oauth_client_authentication_label(request.auth_oauth_client_authentication)}."
        )
        return request.auth_oauth_client_authentication

    def save_selected_auth_field(self) -> str | None:
        request = self.get_active_request()
        field = self.selected_auth_field()
        if request is None or field is None:
            return None
        field_name, field_label = field
        strip_fields = {"auth_api_key_name", "auth_cookie_name", "auth_custom_header_name"}
        strip_fields.update(
            {
                "auth_bearer_prefix",
                "auth_oauth_token_url",
                "auth_oauth_client_id",
                "auth_oauth_header_prefix",
                "auth_oauth_scope",
            }
        )
        value = self.edit_buffer.strip() if field_name in strip_fields else self.edit_buffer
        if field_name == "auth_api_key_name" and not value.strip():
            self.message = "Key cannot be empty."
            return None
        if field_name == "auth_cookie_name" and not value.strip():
            self.message = "Cookie cannot be empty."
            return None
        if field_name == "auth_custom_header_name" and not value.strip():
            self.message = "Header cannot be empty."
            return None
        if field_name == "auth_oauth_token_url" and not value.strip():
            self.message = "Token URL cannot be empty."
            return None
        if field_name == "auth_oauth_client_id" and not value.strip():
            self.message = "Client ID cannot be empty."
            return None
        setattr(request, field_name, value)
        self.mode = MODE_HOME_AUTH_SELECT
        self.clamp_selected_auth_index()
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
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.current_tab = TAB_HOME
        self.pin_active_request()
        self.mode = MODE_HOME_PARAMS_SELECT
        self.selected_param_field_index = 0
        self.params_creating_new = False
        self.clamp_selected_param_index()
        self.message = ""

    def enter_home_params_edit_mode(self, creating: bool = False) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        items = self.get_active_request_params()
        self.clamp_selected_param_index()
        self.mode = MODE_HOME_PARAMS_EDIT
        self.params_creating_new = creating
        if creating:
            self.selected_param_field_index = 0
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return
        if not items:
            self.mode = MODE_HOME_PARAMS_SELECT
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
        self.mode = MODE_HOME_PARAMS_SELECT
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
            self.mode = MODE_HOME_PARAMS_EDIT
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
        self.mode = MODE_HOME_PARAMS_SELECT
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
        self.mode = MODE_HOME_PARAMS_SELECT
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
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.current_tab = TAB_HOME
        self.pin_active_request()
        self.mode = MODE_HOME_HEADERS_SELECT
        self.selected_header_field_index = 0
        self.headers_creating_new = False
        self.clamp_selected_header_index()
        self.message = ""

    def enter_home_headers_edit_mode(self, creating: bool = False) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        items = self.get_active_request_headers()
        self.clamp_selected_header_index()
        self.mode = MODE_HOME_HEADERS_EDIT
        self.headers_creating_new = creating
        if creating:
            self.selected_header_field_index = 0
            self.set_edit_buffer("", replace_on_next_input=False)
            self.message = ""
            return
        if not items:
            self.mode = MODE_HOME_HEADERS_SELECT
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
        self.mode = MODE_HOME_HEADERS_SELECT
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
            self.mode = MODE_HOME_HEADERS_EDIT
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
        self.mode = MODE_HOME_HEADERS_SELECT
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
        self.mode = MODE_HOME_HEADERS_SELECT
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
        request.sync_active_body_text()
        values = [value for value, _label in BODY_TYPE_OPTIONS]
        if request.body_type not in values:
            request.body_type = values[0]
        index = values.index(request.body_type)
        request.body_type = values[(index + step) % len(values)]
        request.restore_active_body_text()
        self.selected_body_index = 0
        self.message = f"Body type: {self.body_type_label(request.body_type)}."
        return request.body_type

    def cycle_raw_subtype(self, step: int) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        request.sync_active_body_text()
        values = [value for value, _label in RAW_SUBTYPE_OPTIONS]
        if request.raw_subtype not in values:
            request.raw_subtype = values[0]
        index = values.index(request.raw_subtype)
        request.raw_subtype = values[(index + step) % len(values)]
        request.restore_active_body_text()
        self.message = f"Raw format: {self.raw_subtype_label(request.raw_subtype)}."
        return request.raw_subtype

    def clamp_selected_body_index(self) -> None:
        request = self.get_active_request()
        if request is None:
            self.selected_body_index = 0
            return
        if request.body_type in BODY_KEY_VALUE_TYPES:
            min_index = 1
            max_index = len(self.get_active_request_body_items()) + 1
        elif request.body_type in BODY_TEXT_EDITOR_TYPES | {"binary"}:
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
        if request.body_type in BODY_KEY_VALUE_TYPES:
            min_index = 1
            max_index = len(self.get_active_request_body_items()) + 1
        elif request.body_type in BODY_TEXT_EDITOR_TYPES | {"binary"}:
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
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.current_tab = TAB_HOME
        self.pin_active_request()
        self.home_body_select_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_BODY_SELECT
        self.clamp_selected_body_index()
        self.message = ""

    def leave_home_body_select_mode(self) -> None:
        self.clear_edit_buffer()
        if self.home_body_select_return_mode == MODE_HOME_BODY_TYPE_EDIT:
            self.mode = MODE_HOME_BODY_TYPE_EDIT
            self.message = ""
            return
        self.enter_home_section_select_mode()

    def enter_home_body_type_edit_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.home_body_type_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_BODY_TYPE_EDIT
        self.message = ""

    def enter_home_body_raw_type_edit_mode(
        self,
        origin_mode: str | None = None,
    ) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.home_body_raw_type_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_BODY_RAW_TYPE_EDIT
        self.message = ""

    def enter_home_body_text_editor_mode(self, origin_mode: str | None = None) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.home_body_content_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_BODY_TEXTAREA
        self.message = ""

    def enter_home_response_view_mode(self, origin_mode: str | None = None) -> bool:
        request = self.get_active_request()
        if request is None or request.last_response is None:
            self.message = "No response to view."
            return False
        self.home_response_view_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_RESPONSE_TEXTAREA
        self.message = ""
        return True

    def enter_home_response_select_mode(self, origin_mode: str | None = None) -> bool:
        request = self.get_active_request()
        if request is None or request.last_response is None:
            self.message = "No response to inspect."
            return False
        self.home_response_select_return_mode = origin_mode or self.mode
        self.mode = MODE_HOME_RESPONSE_SELECT
        self.message = ""
        return True

    def leave_home_response_select_mode(self) -> None:
        self.mode = self.home_response_select_return_mode or MODE_NORMAL
        self.message = ""

    def leave_home_response_view_mode(self) -> None:
        self.mode = self.home_response_view_return_mode or MODE_NORMAL
        self.message = ""

    def enter_home_body_edit_mode(
        self,
        creating: bool = False,
        origin_mode: str | None = None,
    ) -> None:
        request = self.get_active_request()
        if request is None:
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        self.home_body_content_return_mode = origin_mode or self.mode
        self.clamp_selected_body_index()
        if request.body_type in BODY_TEXT_EDITOR_TYPES:
            self.enter_home_body_text_editor_mode(
                origin_mode=self.home_body_content_return_mode
            )
            return
        if request.body_type == "binary":
            self.mode = MODE_HOME_BODY_EDIT
            self.set_edit_buffer(request.body_text, replace_on_next_input=False)
            self.message = ""
            return
        self.mode = MODE_HOME_BODY_EDIT
        if request.body_type in BODY_KEY_VALUE_TYPES:
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
        if self.home_body_type_return_mode == MODE_HOME_BODY_SELECT:
            self.enter_home_body_select_mode(origin_mode=MODE_HOME_BODY_TYPE_EDIT)
            return
        self.enter_home_section_select_mode()

    def leave_home_body_raw_type_edit_mode(self) -> None:
        if self.home_body_raw_type_return_mode == MODE_HOME_BODY_SELECT:
            self.enter_home_body_select_mode(origin_mode=MODE_HOME_BODY_RAW_TYPE_EDIT)
            return
        self.mode = MODE_HOME_BODY_TYPE_EDIT
        self.message = ""

    def leave_home_body_text_editor_mode(self) -> None:
        self._restore_home_body_parent_mode()

    def save_raw_body_text(self, value: str) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        request.body_text = value
        request.sync_active_body_text()
        self._restore_home_body_parent_mode()
        self.message = "Updated body."
        return "body_text"

    def save_body_selection(self) -> str | None:
        request = self.get_active_request()
        if request is None:
            return None
        if request.body_type == "binary":
            request.body_text = self.edit_buffer.strip()
            request.sync_active_body_text()
            self.clear_edit_buffer()
            self._restore_home_body_parent_mode()
            self.message = "Updated binary file path."
            return "body_text"
        if request.body_type in BODY_KEY_VALUE_TYPES:
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
        if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
            return None
        items = self.get_active_request_body_items()
        item_index = self.selected_body_index - 1
        if item_index < 0 or item_index >= len(items):
            self.message = "No body field selected."
            return None
        key = items.pop(item_index).key
        self.clamp_selected_body_index()
        self.mode = MODE_HOME_BODY_SELECT
        self.message = f"Deleted body field {key}."
        return key

    def toggle_selected_body_field(self) -> str | None:
        request = self.get_active_request()
        if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
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
        if self.home_body_content_return_mode == MODE_HOME_BODY_RAW_TYPE_EDIT:
            self.mode = MODE_HOME_BODY_RAW_TYPE_EDIT
            self.message = ""
            return
        if self.home_body_content_return_mode == MODE_HOME_BODY_TYPE_EDIT:
            self.mode = MODE_HOME_BODY_TYPE_EDIT
            self.message = ""
            return
        self.clamp_selected_body_index()
        self.mode = MODE_HOME_BODY_SELECT
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
            self.mode = MODE_NORMAL
            self.message = "No requests to edit."
            return
        field_name, _ = self.selected_request_field()
        if field_name == "method":
            self.mode = MODE_HOME_REQUEST_METHOD_EDIT
            self.set_edit_buffer(request.method.upper() or "GET", replace_on_next_input=False)
            self.message = ""
            return
        self.mode = MODE_HOME_REQUEST_EDIT
        self.set_edit_buffer(str(getattr(request, field_name)), replace_on_next_input=False)
        self.message = ""

    def leave_home_request_edit_mode(self) -> None:
        self.mode = MODE_HOME_REQUEST_SELECT
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
        self.mode = MODE_HOME_REQUEST_SELECT
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
        self.mode = MODE_HOME_REQUEST_SELECT
        self.clear_edit_buffer()
        self.message = f"Updated {field_label}."
        return field_name

    def scroll_response(self, step: int) -> None:
        self.response_scroll_offset = max(0, self.response_scroll_offset + step)

    def clamp_response_scroll_offset(self, total_rows: int, visible_rows: int) -> None:
        max_offset = max(total_rows - max(visible_rows, 1), 0)
        self.response_scroll_offset = max(0, min(self.response_scroll_offset, max_offset))

    def cycle_home_response_tab(self, step: int) -> None:
        tabs = RESPONSE_TABS
        current = (
            self.selected_home_response_tab
            if self.selected_home_response_tab in tabs
            else RESPONSE_TAB_BODY
        )
        index = tabs.index(current)
        self.selected_home_response_tab = tabs[(index + step) % len(tabs)]
        self.response_scroll_offset = 0
