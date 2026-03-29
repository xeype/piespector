from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    screen_background: str
    screen_foreground: str
    panel_background: str
    panel_border: str
    panel_border_subtle: str
    subtle_background: str
    subtle_foreground: str
    status_background: str
    editor_background: str
    scrollbar_color: str
    text_inverse: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_url: str
    text_success: str
    text_warning: str
    text_danger: str
    text_patch: str
    text_collection: str
    text_folder: str
    text_auto_header_key: str
    text_auto_header_value: str
    text_tree_guide: str
    row_alt_one_background: str
    row_alt_two_background: str
    row_collection_background: str
    row_folder_background: str
    row_auto_header_background: str
    row_auto_header_foreground: str
    pill_inactive_background: str
    tab_inactive_background: str


DEFAULT_THEME = ThemeTokens(
    screen_background="#2c2c2c",
    screen_foreground="#d7dae0",
    panel_background="#2c2c2c",
    panel_border="#4b5263",
    panel_border_subtle="#3f4550",
    subtle_background="#3a3f4b",
    subtle_foreground="#7f848e",
    status_background="#3a3f4b",
    editor_background="#1f2329",
    scrollbar_color="#54597a",
    text_inverse="#1f2329",
    text_primary="#d7dae0",
    text_secondary="#abb2bf",
    text_muted="#7f848e",
    text_url="#61afef",
    text_success="#98c379",
    text_warning="#e5c07b",
    text_danger="#e06c75",
    text_patch="#c678dd",
    text_collection="#f0cc8f",
    text_folder="#8fb8de",
    text_auto_header_key="#d6ba6d",
    text_auto_header_value="#c8b26a",
    text_tree_guide="#5c6370",
    row_alt_one_background="#2c313a",
    row_alt_two_background="#262b33",
    row_collection_background="#3a3120",
    row_folder_background="#24323b",
    row_auto_header_background="#2a2924",
    row_auto_header_foreground="#9aa1ab",
    pill_inactive_background="#343944",
    tab_inactive_background="#3a3f4b",
)
