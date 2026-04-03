from __future__ import annotations

from functools import lru_cache

from rich.style import Style

from piespector.domain.modes import MODE_JUMP

SELECTED_ELEMENT_CLASS = "piespector-selected-element"
FOCUS_FRAME_CLASS = "piespector-focus-frame"

_DEFAULT_SELECTED_ELEMENT_FOREGROUND = "#E0E0E0"
_DEFAULT_SELECTED_ELEMENT_BACKGROUND = "#1B6F8C"


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

    background = _theme_variable(
        subject,
        "accent-darken-2",
        _DEFAULT_SELECTED_ELEMENT_BACKGROUND,
    )
    color = foreground or _theme_variable(
        subject,
        "foreground",
        _DEFAULT_SELECTED_ELEMENT_FOREGROUND,
    )
    return _cached_selected_element_style(color, background)


def _theme_variable(subject, name: str, default: str) -> str:
    app = _resolve_app(subject)
    if app is None:
        return default
    return getattr(app, "theme_variables", {}).get(name, default)


def _resolve_app(subject):
    if subject is None:
        return None
    if hasattr(subject, "theme_variables"):
        return subject
    return getattr(subject, "_app", None) or getattr(subject, "app", None)


@lru_cache(maxsize=64)
def _cached_selected_element_style(color: str, background: str) -> Style:
    return Style(color=color, bgcolor=background, bold=True)
