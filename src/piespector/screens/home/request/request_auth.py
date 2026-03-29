from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS,
    AUTH_TYPE_OPTIONS,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import messages, styles
from piespector.state import PiespectorState


def render_request_auth_editor(
    request: RequestDefinition,
    state: PiespectorState,
) -> RenderableType:
    selector = Text()
    for index, (value, label) in enumerate(AUTH_TYPE_OPTIONS):
        if index:
            selector.append(" ")
        is_active = request.auth_type == value
        is_selected = state.mode == MODE_HOME_AUTH_TYPE_EDIT and is_active
        style = (
            styles.pill_style(styles.TEXT_WARNING)
            if is_selected
            else styles.pill_style(styles.TEXT_URL)
            if is_active
            else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
        )
        selector.append(f" {label} ", style=style)

    fields = state.auth_fields(request)
    if not fields:
        empty = Text()
        empty.append(messages.HOME_NO_AUTH, style=f"bold {styles.TEXT_PRIMARY}")
        return Group(
            selector,
            Panel(empty, border_style=styles.SUB_BORDER, box=box.SIMPLE_HEAVY),
        )

    table = Table(
        expand=True,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        border_style=styles.SUB_BORDER,
        padding=(0, 1),
    )
    table.add_column("Field", width=12, style=f"bold {styles.TEXT_SECONDARY}")
    table.add_column("Value", ratio=1, style=styles.TEXT_PRIMARY)

    for index, (field_name, label) in enumerate(fields, start=1):
        current_value: RenderableType
        if field_name == "auth_api_key_location":
            current_value = Text()
            for option_index, (value, option_label) in enumerate(AUTH_API_KEY_LOCATION_OPTIONS):
                if option_index:
                    current_value.append(" ")
                is_active = request.auth_api_key_location == value
                is_selected = state.mode == MODE_HOME_AUTH_LOCATION_EDIT and is_active
                style = (
                    styles.pill_style(styles.TEXT_WARNING)
                    if is_selected
                    else styles.pill_style(styles.TEXT_URL)
                    if is_active
                    else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
                )
                current_value.append(f" {option_label} ", style=style)
        elif field_name == "auth_oauth_client_authentication":
            current_value = Text()
            for option_index, (value, option_label) in enumerate(
                AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS
            ):
                if option_index:
                    current_value.append(" ")
                is_active = request.auth_oauth_client_authentication == value
                is_selected = state.mode == MODE_HOME_AUTH_LOCATION_EDIT and is_active
                style = (
                    styles.pill_style(styles.TEXT_WARNING)
                    if is_selected
                    else styles.pill_style(styles.TEXT_URL)
                    if is_active
                    else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
                )
                current_value.append(f" {option_label} ", style=style)
        else:
            raw_value = str(getattr(request, field_name) or "")
            if field_name in {
                "auth_basic_password",
                "auth_bearer_token",
                "auth_api_key_value",
                "auth_cookie_value",
                "auth_custom_header_value",
                "auth_oauth_client_secret",
            }:
                display_value = render_auth_secret(raw_value)
            else:
                display_value = raw_value or "-"
            current_value = Text(display_value, style=styles.TEXT_PRIMARY)

        row_style = None
        if state.mode == MODE_HOME_AUTH_LOCATION_EDIT and field_name in {
            "auth_api_key_location",
            "auth_oauth_client_authentication",
        }:
            row_style = styles.pill_style(styles.TEXT_WARNING)
        elif (
            state.mode in {MODE_HOME_AUTH_SELECT, MODE_HOME_AUTH_EDIT, MODE_HOME_AUTH_LOCATION_EDIT}
            and index == state.selected_auth_index
        ):
            row_style = styles.pill_style(styles.TEXT_SUCCESS)
        table.add_row(label, current_value, style=row_style)

    footer = Text(messages.auth_footer_text(state, request), style=styles.TEXT_MUTED)
    return Group(selector, table, footer)


def render_auth_secret(value: str) -> str:
    if not value:
        return "-"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(len(value) - 4, 4)}{value[-4:]}"
