from __future__ import annotations

from textual.widgets import Input


class PiespectorInput(Input):
    BINDINGS = [
        binding
        for binding in Input.BINDINGS
        if getattr(binding, "action", None) != "copy"
    ]
