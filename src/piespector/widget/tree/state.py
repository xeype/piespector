from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TreeSyncState:
    """Per-widget synchronization state for :class:`PiespectorTree`.

    Replaces the scattered ``_piespector_*`` attributes that were previously
    monkey-patched onto Textual's ``Tree`` widget.

    Attributes:
        signature: Last content signature used to detect whether a rebuild is
            actually required.
        ignore_highlight_index: One-shot guard set before a programmatic cursor
            move; the first ``NodeHighlighted`` event carrying this index is
            dropped, then cleared.
    """

    signature: Any | None = None
    ignore_highlight_index: int | None = None
