from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from piespector.interactions.keys import KEY_ESCAPE
from piespector.ui.jumper import Jumper


class JumpOverlay(ModalScreen[str | None]):
    DEFAULT_CSS = """
    JumpOverlay {
        background: black 25%;
    }

    .jump-overlay__label {
        position: absolute;
        layer: above;
        width: auto;
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $background;
        text-style: bold;
    }

    #jump-overlay-footer-container {
        layer: above;
        dock: bottom;
        width: 1fr;
        height: 2;
    }

    #jump-overlay-footer {
        height: 1;
        background: $accent;
        color: $background;
        text-style: bold;
        content-align: center middle;
    }

    #jump-overlay-dismiss {
        height: 1;
        color: $text;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding(KEY_ESCAPE, "dismiss_overlay", "Dismiss", show=False),
    ]

    def __init__(self, jumper: Jumper) -> None:
        super().__init__()
        self._jumper = jumper
        self._keys_to_targets: dict[str, str] = {}

    def _sync(self) -> tuple:
        items = self._jumper.overlay_items()
        self._keys_to_targets = {
            item.key: item.target_id
            for item in items
        }
        return items

    def compose(self) -> ComposeResult:
        for item in self._sync():
            label = Label(item.key, classes="jump-overlay__label")
            label.offset = (item.offset.x, item.offset.y)
            yield label
        dismiss_text = Text()
        dismiss_text.append("ESC", style="bold")
        dismiss_text.append(" to dismiss")
        with Vertical(id="jump-overlay-footer-container"):
            yield Static(
                Text("Press a key to jump", style="bold"),
                id="jump-overlay-footer",
            )
            yield Static(dismiss_text, id="jump-overlay-dismiss")

    def on_key(self, event: events.Key) -> None:
        jump_key = (event.key or event.character or "").lower()
        event.stop()
        event.prevent_default()
        if jump_key == KEY_ESCAPE:
            self.dismiss(None)
            return
        target_id = self._keys_to_targets.get(jump_key)
        if target_id is not None:
            self.dismiss(target_id)

    def action_dismiss_overlay(self) -> None:
        self.dismiss(None)

    def on_resize(self) -> None:
        self.refresh(recompose=True)
