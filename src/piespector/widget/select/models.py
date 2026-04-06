from __future__ import annotations

from typing import NamedTuple

from rich.text import Text


class SelectOption(NamedTuple):
    """A single select option with a stable value and a display label.

    Defined as a NamedTuple so existing code that unpacks raw ``(value, label)``
    tuples — e.g. ``for value, label in options`` — continues to work without
    changes.
    """

    value: str
    label: str | Text

    def as_textual(self) -> tuple[str | Text, str]:
        """Return ``(label, value)`` as expected by Textual's Select widget."""
        return (self.label, self.value)


OptionList = tuple[SelectOption, ...]


def option_list(*pairs: tuple[str, str | Text]) -> OptionList:
    """Build an :data:`OptionList` from ``(value, label)`` pairs.

    Example::

        options = option_list(("none", "No Auth"), ("basic", "Basic Auth"))
    """
    return tuple(SelectOption(value=v, label=l) for v, l in pairs)
