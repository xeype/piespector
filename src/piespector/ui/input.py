from __future__ import annotations

from rich.highlighter import Highlighter
from rich.text import Text
from textual.widgets import Input

from piespector.placeholders import PLACEHOLDER_HIGHLIGHT_COLOR, PLACEHOLDER_RE


class PlaceholderHighlighter(Highlighter):
    def highlight(self, text: Text) -> None:
        text.highlight_regex(PLACEHOLDER_RE, PLACEHOLDER_HIGHLIGHT_COLOR)


PLACEHOLDER_INPUT_HIGHLIGHTER = PlaceholderHighlighter()


class PiespectorInput(Input):
    BINDINGS = [
        binding
        for binding in Input.BINDINGS
        if getattr(binding, "action", None) != "copy"
    ]

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("highlighter", PLACEHOLDER_INPUT_HIGHLIGHTER)
        super().__init__(*args, **kwargs)
