"""Shared UI modules for piespector."""

from textual.binding import Binding

from piespector.interactions.keys import (
    KEY_COMMAND_PALETTE,
    KEY_JUMP,
)
from piespector.ui.css import build_app_css

APP_CSS = build_app_css()

APP_BINDINGS = [
    Binding(KEY_COMMAND_PALETTE, "command_palette", "Command Palette", show=False),
    Binding(KEY_JUMP, "enter_jump_mode", "Jump", show=False),
]

__all__ = [
    "APP_BINDINGS",
    "APP_CSS",
]
