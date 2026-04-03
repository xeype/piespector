"""Shared UI modules for piespector."""

from textual.binding import Binding

from piespector.interactions.keys import (
    KEY_COMMAND_PALETTE,
    KEY_JUMP,
    KEY_VIM_DOWN,
    KEY_VIM_LEFT,
    KEY_VIM_RIGHT,
    KEY_VIM_UP,
    KEY_WORKSPACE_SEARCH,
)
from piespector.ui.css import build_app_css

APP_CSS = build_app_css()

APP_BINDINGS = [
    Binding(KEY_VIM_UP, "home_browse_up", "Browse Up", show=False),
    Binding(KEY_VIM_DOWN, "home_browse_down", "Browse Down", show=False),
    Binding("K", "home_previous_folder", "Previous Folder", show=False),
    Binding("J", "home_next_folder", "Next Folder", show=False),
    Binding("ctrl+k", "home_previous_collection", "Previous Collection", show=False),
    Binding("ctrl+j", "home_next_collection", "Next Collection", show=False),
    Binding(KEY_VIM_LEFT, "home_previous_open_request", "Previous Pinned Request", show=False),
    Binding(KEY_VIM_RIGHT, "home_next_open_request", "Next Pinned Request", show=False),
    Binding(KEY_WORKSPACE_SEARCH, "search_workspace", "Search", show=False),
    Binding(KEY_COMMAND_PALETTE, "command_palette", "Command Palette", show=False),
    Binding(KEY_JUMP, "enter_jump_mode", "Jump", show=False),
]

__all__ = [
    "APP_BINDINGS",
    "APP_CSS",
]
