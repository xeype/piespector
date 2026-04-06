from __future__ import annotations

from typing import TYPE_CHECKING

from .logic import compute_signature, normalize_value, sync_needed
from .models import OptionList

if TYPE_CHECKING:
    from .widget import PiespectorSelect


def deactivate(select: PiespectorSelect) -> None:
    """Collapse the overlay, clear auto-open token, and release focus if held."""
    select.sync_state.auto_open_token = None
    if getattr(select, "expanded", False):
        select.expanded = False
    if not select.has_focus_within:
        return
    app = select.app
    if app is not None:
        app.set_focus(None)
    else:
        select.blur()


def sync(
    select: PiespectorSelect,
    options: OptionList,
    current_value: str,
    *,
    display: bool = True,
    auto_open_token: object | None = None,
) -> None:
    """Synchronize *select* to *options* and *current_value*.

    Only mutates the widget when the signature changes (options or value differ
    from the previous call).  Schedules focus and overlay open when
    *auto_open_token* is new.
    """
    select.display = display

    if not display or not options:
        deactivate(select)
        return

    value = normalize_value(current_value, options)
    state = select.sync_state

    if sync_needed(options, value, state.signature):
        state.syncing = True
        state.suppress_changes = True
        state.ignored_change_value = value
        try:
            select.set_options([opt.as_textual() for opt in options])
            select.value = value
            state.signature = compute_signature(options, value)
        finally:
            state.syncing = False
            select.call_after_refresh(
                lambda: setattr(state, "suppress_changes", False)
            )

    _maybe_auto_open(select, auto_open_token, state)


def _maybe_auto_open(
    select: PiespectorSelect,
    auto_open_token: object | None,
    state,
) -> None:
    if auto_open_token is None:
        deactivate(select)
        return

    if state.auto_open_token == auto_open_token:
        return

    state.auto_open_token = auto_open_token
    select.focus()
    if not select.expanded:
        select.action_show_overlay()
