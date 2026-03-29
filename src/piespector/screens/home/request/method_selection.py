from __future__ import annotations

from rich.text import Text

from piespector.domain.http import HTTP_METHODS
from piespector.domain.modes import MODE_HOME_REQUEST_METHOD_EDIT
from piespector.domain.requests import RequestDefinition
from piespector.screens.home import styles
from piespector.state import PiespectorState


def render_method_selector_value(
    request: RequestDefinition,
    state: PiespectorState,
) -> Text:
    selected = (
        state.edit_buffer.upper()
        if state.mode == MODE_HOME_REQUEST_METHOD_EDIT and state.selected_request_field()[0] == "method"
        else request.method.upper()
    )
    text = Text()
    for index, method in enumerate(HTTP_METHODS):
        if index:
            text.append(" ")
        style = (
            styles.pill_style(styles.method_color(method))
            if method == selected
            else styles.pill_style(styles.PILL_INACTIVE, foreground=styles.TEXT_SECONDARY)
        )
        text.append(f" {method} ", style=style)
    return text
