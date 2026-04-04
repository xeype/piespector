from __future__ import annotations

import platform

KEY_ESCAPE = "escape"
KEY_ENTER = "enter"
KEY_TAB = "tab"
KEY_LEFT = "left"
KEY_RIGHT = "right"
KEY_UP = "up"
KEY_DOWN = "down"
KEY_BACKSPACE = "backspace"
KEY_DELETE = "delete"
KEY_HOME = "home"
KEY_END = "end"
KEY_SPACE = "space"
KEY_PAGE_UP = "pageup"
KEY_PAGE_DOWN = "pagedown"

KEY_ADD = "a"
KEY_CLOSE = "c"
KEY_DELETE_ROW = "d"
KEY_EDIT = "e"
KEY_HELP = "?"
KEY_NO = "n"
KEY_SEND = "s"
KEY_VIEW = "v"
KEY_YES = "y"
KEY_VIM_SHIFT_LEFT = "H"
KEY_VIM_SHIFT_RIGHT = "L"
KEY_VIM_LEFT = "h"
KEY_VIM_RIGHT = "l"
KEY_VIM_UP = "k"
KEY_VIM_DOWN = "j"

KEY_JUMP = "ctrl+o"
KEY_COMMAND_PALETTE = "ctrl+p"
KEY_WORKSPACE_SEARCH = "/"

KEY_COPY = "ctrl+c"
KEY_COPY_ALT = "ctrl+insert"
KEY_RESPONSE_COPY = "ctrl+shift+c"
KEY_PASTE = "ctrl+v"
KEY_PASTE_ALT = "ctrl+shift+v"
KEY_PASTE_ALT_2 = "shift+insert"
KEY_SAVE = "ctrl+s"
KEY_SCROLL_DOWN = "ctrl+d"
KEY_SCROLL_UP = "ctrl+u"

ARROW_LEFT_KEYS = frozenset({KEY_LEFT})
ARROW_RIGHT_KEYS = frozenset({KEY_RIGHT})
ARROW_UP_KEYS = frozenset({KEY_UP})
ARROW_DOWN_KEYS = frozenset({KEY_DOWN})
TAB_PREVIOUS_KEYS = frozenset({KEY_VIM_LEFT})
TAB_NEXT_KEYS = frozenset({KEY_VIM_RIGHT})
FIELD_PREVIOUS_KEYS = frozenset({KEY_VIM_SHIFT_LEFT})
FIELD_NEXT_KEYS = frozenset({KEY_VIM_SHIFT_RIGHT})
LEFT_KEYS = frozenset({KEY_LEFT, KEY_VIM_LEFT})
RIGHT_KEYS = frozenset({KEY_RIGHT, KEY_VIM_RIGHT})
UP_KEYS = frozenset({KEY_UP, KEY_VIM_UP})
DOWN_KEYS = frozenset({KEY_DOWN, KEY_VIM_DOWN})
PREVIOUS_KEYS = frozenset({"left", "h", "up", "k"})
NEXT_KEYS = frozenset({"right", "l", "down", "j"})
OPEN_KEYS = frozenset({KEY_EDIT, KEY_ENTER})
TOGGLE_KEYS = frozenset({KEY_EDIT, KEY_ENTER, KEY_SPACE})
COPY_KEYS = frozenset({KEY_COPY, KEY_COPY_ALT})
PASTE_KEYS = frozenset({KEY_PASTE, KEY_PASTE_ALT, KEY_PASTE_ALT_2})
CONFIRM_CANCEL_KEYS = frozenset({KEY_ESCAPE, KEY_NO})
CONFIRM_ACCEPT_KEYS = frozenset({KEY_YES, KEY_ENTER})
RESPONSE_SCROLL_KEYS = frozenset({KEY_SCROLL_DOWN, KEY_SCROLL_UP})


def response_copy_keys(system: str | None = None) -> tuple[str, ...]:
    current_system = system or platform.system()
    if current_system == "Darwin":
        return (KEY_COPY,)
    if current_system == "Windows":
        return (KEY_RESPONSE_COPY, KEY_COPY_ALT)
    return (KEY_RESPONSE_COPY,)


def response_copy_hint(system: str | None = None) -> str:
    current_system = system or platform.system()
    if current_system == "Darwin":
        return "Ctrl+C"
    if current_system == "Windows":
        return "Ctrl+Shift+C/Ctrl+Insert"
    return "Ctrl+Shift+C"


def response_copy_hint_items(system: str | None = None) -> list[tuple[str, str]]:
    current_system = system or platform.system()
    if current_system == "Darwin":
        return [(KEY_COPY, "copy"), ("esc", "back")]
    if current_system == "Windows":
        return [
            (KEY_RESPONSE_COPY, "copy"),
            (KEY_COPY_ALT, "copy"),
            ("esc", "back"),
        ]
    return [(KEY_RESPONSE_COPY, "copy"), ("esc", "back")]
