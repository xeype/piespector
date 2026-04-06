from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message

from .models import SelectOption

if TYPE_CHECKING:
    from .widget import PiespectorSelect


class SelectionChanged(Message):
    """Posted by :class:`PiespectorSelect` when the user confirms a selection.

    Key differences from Textual's ``Select.Changed``:

    - Fires even when the same value is re-confirmed (no silent swallowing).
    - Carries the full :class:`SelectOption` (value + label), not just the value.
    - Carries a typed reference to the originating widget.

    Screen-level handlers should use ``@on(SelectionChanged, "#widget-id")``
    instead of a single ``on_select_changed`` dispatcher.
    """

    def __init__(self, select: PiespectorSelect, option: SelectOption) -> None:
        super().__init__()
        self.select = select
        self.option = option

    @property
    def control(self) -> PiespectorSelect:
        """Required by Textual so ``@on(SelectionChanged, "#id")`` selectors work."""
        return self.select

    @property
    def value(self) -> str:
        return self.option.value

    @property
    def select_id(self) -> str:
        return self.select.id or ""
