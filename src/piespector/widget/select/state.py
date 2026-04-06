from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SelectSyncState:
    """Per-widget synchronization state for :class:`PiespectorSelect`.

    Replaces the scattered ``_piespector_*`` attributes that were previously
    monkey-patched onto Textual's ``Select`` widget.

    Attributes:
        syncing: True while ``set_options``/``value`` are being set programmatically.
        suppress_changes: True from the start of a sync until after the next
            frame refresh, blocking any stale ``Changed`` events.
        ignored_change_value: One-shot guard value set during sync; the first
            ``SelectionChanged`` carrying this value is dropped, then cleared.
        signature: Last ``(options, value)`` tuple used to detect whether a sync
            is actually required.
        auto_open_token: Opaque token identifying the current auto-focus context;
            the overlay is opened only when the token changes.
    """

    syncing: bool = False
    suppress_changes: bool = False
    ignored_change_value: str | None = None
    signature: tuple[Any, ...] | None = None
    auto_open_token: object | None = None
