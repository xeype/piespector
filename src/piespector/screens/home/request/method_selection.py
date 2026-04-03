from __future__ import annotations

from rich.text import Text

from piespector.domain.requests import RequestDefinition
from piespector.state import PiespectorState
from piespector.ui.selection import selected_element_style

_METHOD_COLORS: dict[str, str] = {
    "GET": "#00ff00",
    "POST": "#ffff00",
    "PUT": "#5555ff",
    "PATCH": "#00ffff",
    "DELETE": "#ff0000",
    "HEAD": "#ff00ff",
    "OPTIONS": "#aaaaaa",
}


def method_color(method: str) -> str:
    return _METHOD_COLORS.get(method.upper(), "white")


def selected_method_value(
    request: RequestDefinition,
    state: PiespectorState,
) -> str:
    return request.method.upper()


def render_method_selector_value(
    request: RequestDefinition,
    state: PiespectorState,
    *,
    selected: bool,
    show_caret: bool = False,
) -> Text:
    current_method = selected_method_value(request, state)
    label = f" {current_method}"
    if show_caret:
        label += " ▾"
    label += " "
    return Text(
        label,
        style=selected_element_style(
            state,
            selected=selected,
            foreground=method_color(current_method),
        ),
    )
