from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from piespector.domain.editor import (
    AUTH_API_KEY_LOCATION_OPTIONS,
    AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS,
)
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.secrets import mask_secret_display
from piespector.screens.home import messages
from piespector.screens.home.request.dropdown import render_dropdown_value
from piespector.state import PiespectorState
from piespector.ui.rendering_helpers import render_placeholder_text
from piespector.ui.selection import effective_mode, selected_element_style


def render_request_auth_editor(
    request: RequestDefinition,
    state: PiespectorState,
    *,
    include_type_selector: bool = True,
) -> RenderableType:
    mode = effective_mode(state)
    content: list[RenderableType] = []
    if include_type_selector:
        content.append(
            render_dropdown_value(
                state.auth_type_label(request.auth_type),
                selected=(
                    mode == MODE_HOME_AUTH_TYPE_EDIT
                    or (
                        mode in {MODE_HOME_AUTH_SELECT, MODE_HOME_AUTH_EDIT}
                        and state.selected_auth_index == 0
                    )
                ),
                subject=state,
            )
        )

    fields = state.auth_fields(request)
    if not fields:
        empty = Text()
        empty.append(messages.HOME_NO_AUTH)
        content.append(Panel(empty, box=box.SIMPLE))
        return Group(*content)

    table = Table(
        expand=True,
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("Field", width=12)
    table.add_column("Value", ratio=1)

    for index, (field_name, label) in enumerate(fields, start=1):
        current_value: RenderableType
        if field_name == "auth_api_key_location":
            current_value = render_dropdown_value(
                state.auth_api_key_location_label(request.auth_api_key_location),
                selected=(
                    mode == MODE_HOME_AUTH_LOCATION_EDIT
                    and index == state.selected_auth_index
                ),
                subject=state,
            )
        elif field_name == "auth_oauth_client_authentication":
            current_value = render_dropdown_value(
                state.auth_oauth_client_authentication_label(
                    request.auth_oauth_client_authentication
                ),
                selected=(
                    mode == MODE_HOME_AUTH_LOCATION_EDIT
                    and index == state.selected_auth_index
                ),
                subject=state,
            )
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
            current_value = render_placeholder_text(display_value)

        row_style = selected_element_style(
            state,
            selected=(
                (
                    mode == MODE_HOME_AUTH_LOCATION_EDIT
                    and field_name in {
                        "auth_api_key_location",
                        "auth_oauth_client_authentication",
                    }
                )
                or (
                    mode in {
                        MODE_HOME_AUTH_SELECT,
                        MODE_HOME_AUTH_EDIT,
                        MODE_HOME_AUTH_LOCATION_EDIT,
                    }
                    and index == state.selected_auth_index
                )
            ),
        )
        table.add_row(label, current_value, style=row_style)

    footer = Text(messages.auth_footer_text(state, request))
    content.extend((table, footer))
    return Group(*content)


def auth_option_select_context(
    request: RequestDefinition,
    state: PiespectorState,
) -> tuple[str, tuple[tuple[str, str], ...], str] | None:
    field = state.selected_auth_field()
    if field is None:
        return None

    field_name, label = field
    if field_name == "auth_api_key_location":
        return (
            label,
            AUTH_API_KEY_LOCATION_OPTIONS,
            request.auth_api_key_location,
        )

    if field_name == "auth_oauth_client_authentication":
        return (
            label,
            AUTH_OAUTH_CLIENT_AUTHENTICATION_OPTIONS,
            request.auth_oauth_client_authentication,
        )

    return None


def render_auth_secret(value: str) -> str:
    return mask_secret_display(value)
