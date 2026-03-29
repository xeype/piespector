from __future__ import annotations

from piespector.ui.rich_styles import (
    BORDER,
    PILL_INACTIVE,
    ROW_ALT_ONE,
    ROW_ALT_TWO,
    ROW_AUTO_HEADER,
    ROW_COLLECTION,
    ROW_FOLDER,
    SUB_BORDER,
    TAB_INACTIVE,
    TEXT_AUTO_HEADER_KEY,
    TEXT_AUTO_HEADER_VALUE,
    TEXT_COLLECTION,
    TEXT_DANGER,
    TEXT_FOLDER,
    TEXT_INVERSE,
    TEXT_MUTED,
    TEXT_PATCH,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_SUCCESS,
    TEXT_TREE_GUIDE,
    TEXT_URL,
    TEXT_WARNING,
    pill_style,
    text_style,
)


def method_color(method: str) -> str:
    palette = {
        "GET": TEXT_SUCCESS,
        "POST": TEXT_WARNING,
        "PUT": TEXT_URL,
        "PATCH": TEXT_PATCH,
        "DELETE": TEXT_DANGER,
    }
    return palette.get(method.upper(), TEXT_SECONDARY)


def method_style(method: str) -> str:
    return text_style(method_color(method), bold=True)
