"""Shared UI modules for piespector."""

from textual.binding import Binding

from piespector.ui.css import build_app_css

APP_CSS = build_app_css()

APP_BINDINGS = [
    Binding(":", "enter_command_mode", "Command", show=False),
]

__all__ = [
    "APP_BINDINGS",
    "APP_CSS",
]
