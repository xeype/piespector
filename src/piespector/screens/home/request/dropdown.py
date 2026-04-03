from __future__ import annotations

from rich.text import Text
from textual.widgets import Select

from piespector.ui.selection import selected_element_style


def render_dropdown_value(label: str, *, selected: bool, subject=None) -> Text:
    return Text(
        f" {label} ▾ ",
        style=selected_element_style(subject, selected=selected),
    )


def _deactivate_select_widget(select: Select) -> None:
    select._piespector_auto_open_token = None
    if getattr(select, "expanded", False):
        select.expanded = False
    if not select.has_focus_within:
        return
    app = select.app
    if app is not None:
        app.set_focus(None)
        return
    select.blur()


def sync_select_widget(
    select: Select,
    options: tuple[tuple[str, str | Text], ...],
    current_value: str,
    *,
    display: bool = True,
    auto_open_token: object | None = None,
) -> None:
    select.display = display
    if not display or not options:
        _deactivate_select_widget(select)
        return

    option_values = {value for value, _label in options}
    normalized_value = current_value if current_value in option_values else options[0][0]
    signature = (options, normalized_value)

    if getattr(select, "_piespector_signature", None) != signature:
        select._piespector_syncing = True
        select._piespector_suppress_changes = True
        select._piespector_ignored_change_value = normalized_value
        try:
            select.set_options([(label, value) for value, label in options])
            select.value = normalized_value
            select._piespector_signature = signature
        finally:
            select._piespector_syncing = False
            select.call_after_refresh(
                lambda: setattr(select, "_piespector_suppress_changes", False)
            )

    if auto_open_token is None:
        _deactivate_select_widget(select)
        return

    if getattr(select, "_piespector_auto_open_token", None) == auto_open_token:
        return

    select._piespector_auto_open_token = auto_open_token
    select.focus()
    if not select.expanded:
        select.action_show_overlay()
