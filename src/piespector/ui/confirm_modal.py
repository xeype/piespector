from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from piespector.interactions.keys import KEY_ESCAPE, KEY_NO, KEY_YES


class ConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
        background: $background 70%;
    }

    #confirm-modal {
        width: auto;
        height: auto;
        border: round $accent;
        
    }

    #confirm-modal-panel {
        width: auto;
        height: auto;
        min-width: 60;
        max-width: 80;
    }

    #confirm-modal-inner {
        width: auto;
        height: auto;
        padding: 1 2;
    }

    #confirm-modal-title {
        width: auto;
        height: auto;
        margin-bottom: 1;
        text-style: bold;
        color: $accent;
    }

    #confirm-modal-prompt {
        width: auto;
        height: auto;
        margin-bottom: 1;
        color: $text;
    }

    #confirm-modal-actions {
        width: auto;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
        align: center middle;
    }

    #confirm-modal-actions Button {
        width: 14;
        min-width: 14;
        margin: 0 1;
        border: round $panel;
        background: transparent;
        color: $text;
    }

    #confirm-modal-actions Button:focus {
        border: round $accent;
        text-style: bold;
    }

    #confirm-modal-footer {
        width: auto;
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding(KEY_YES, "confirm", "Confirm", show=False),
        Binding(KEY_NO, "cancel", "Cancel", show=False),
        Binding(KEY_ESCAPE, "cancel", "Cancel", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-modal"):
            with Vertical(id="confirm-modal-panel"):
                with Vertical(id="confirm-modal-inner"):
                    yield Static("Confirm Delete", id="confirm-modal-title")
                    yield Static(self._prompt, id="confirm-modal-prompt")
                    with Horizontal(id="confirm-modal-actions"):
                        yield Button("Yes", id="confirm-modal-yes")
                        yield Button("No", id="confirm-modal-no")
                    yield Static("Y confirms. N or Esc cancels.", id="confirm-modal-footer")

    def on_mount(self) -> None:
        self.query_one("#confirm-modal-yes", Button).focus()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm-modal-yes")
    def on_confirm_pressed(self, event: Button.Pressed) -> None:
        del event
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-modal-no")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        del event
        self.dismiss(False)
