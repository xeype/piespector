from __future__ import annotations

from piespector.ui.themes import DEFAULT_THEME

TEXT_INVERSE = DEFAULT_THEME.text_inverse
TEXT_PRIMARY = DEFAULT_THEME.text_primary
TEXT_SECONDARY = DEFAULT_THEME.text_secondary
TEXT_MUTED = DEFAULT_THEME.text_muted
TEXT_URL = DEFAULT_THEME.text_url
TEXT_SUCCESS = DEFAULT_THEME.text_success
TEXT_WARNING = DEFAULT_THEME.text_warning
TEXT_DANGER = DEFAULT_THEME.text_danger
TEXT_PATCH = DEFAULT_THEME.text_patch
TEXT_COLLECTION = DEFAULT_THEME.text_collection
TEXT_FOLDER = DEFAULT_THEME.text_folder
TEXT_AUTO_HEADER_KEY = DEFAULT_THEME.text_auto_header_key
TEXT_AUTO_HEADER_VALUE = DEFAULT_THEME.text_auto_header_value
TEXT_TREE_GUIDE = DEFAULT_THEME.text_tree_guide

BORDER = DEFAULT_THEME.panel_border
SUB_BORDER = DEFAULT_THEME.panel_border_subtle

ROW_ALT_ONE = f"on {DEFAULT_THEME.row_alt_one_background}"
ROW_ALT_TWO = f"on {DEFAULT_THEME.row_alt_two_background}"
ROW_COLLECTION = f"on {DEFAULT_THEME.row_collection_background}"
ROW_FOLDER = f"on {DEFAULT_THEME.row_folder_background}"
ROW_AUTO_HEADER = (
    f"{DEFAULT_THEME.row_auto_header_foreground} on {DEFAULT_THEME.row_auto_header_background}"
)

PILL_INACTIVE = DEFAULT_THEME.pill_inactive_background
TAB_INACTIVE = DEFAULT_THEME.tab_inactive_background


def text_style(
    color: str,
    *,
    bold: bool = False,
    background: str | None = None,
) -> str:
    parts: list[str] = []
    if bold:
        parts.append("bold")
    parts.append(color)
    if background is not None:
        parts.extend(("on", background))
    return " ".join(parts)


def pill_style(background: str, *, foreground: str = TEXT_INVERSE) -> str:
    return text_style(foreground, bold=True, background=background)


def muted_style(*, bold: bool = False) -> str:
    return text_style(TEXT_MUTED, bold=bold)


def primary_style(*, bold: bool = False) -> str:
    return text_style(TEXT_PRIMARY, bold=bold)


def secondary_style(*, bold: bool = False) -> str:
    return text_style(TEXT_SECONDARY, bold=bold)


def warning_style(*, bold: bool = False) -> str:
    return text_style(TEXT_WARNING, bold=bold)


def danger_style(*, bold: bool = False) -> str:
    return text_style(TEXT_DANGER, bold=bold)


def success_style(*, bold: bool = False) -> str:
    return text_style(TEXT_SUCCESS, bold=bold)
