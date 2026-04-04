from __future__ import annotations

from functools import lru_cache

from rich.style import Style

from piespector.domain.modes import MODE_JUMP

SELECTED_ELEMENT_CLASS = "piespector-selected-element"
FOCUS_FRAME_CLASS = "piespector-focus-frame"


def effective_mode(state) -> str:
    return state.jump_return_mode if state.mode == MODE_JUMP else state.mode


def set_selected(widget, selected: bool, *, class_name: str = SELECTED_ELEMENT_CLASS) -> None:
    widget.set_class(selected, class_name)


def selected_element_style(
    subject=None,
    *,
    selected: bool,
    foreground: str | None = None,
) -> Style | None:
    if not selected:
        return None

    app = _resolve_app(subject)
    if app is None:
        return None

    theme = getattr(app, "theme_variables", {})
    background = theme.get("accent")
    color = foreground or theme.get("button-color-foreground")

    if not background or not color:
        return None

    return _cached_selected_element_style(color, background)


def _resolve_app(subject):
    if subject is None:
        return None
    if hasattr(subject, "theme_variables"):
        return subject
    return getattr(subject, "_app", None) or getattr(subject, "app", None)


@lru_cache(maxsize=64)
def _cached_selected_element_style(color: str, background: str) -> Style:
    return Style(color=color, bgcolor=background)
