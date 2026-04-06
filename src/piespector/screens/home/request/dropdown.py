from __future__ import annotations

from rich.text import Text

from piespector.ui.selection import selected_element_style


def render_dropdown_value(label: str, *, selected: bool, subject=None) -> Text:
    return Text(
        f" {label} ▾ ",
        style=selected_element_style(subject, selected=selected),
    )
