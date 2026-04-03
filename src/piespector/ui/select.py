from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Select
from textual.widgets._select import SelectCurrent, SelectOverlay


class PiespectorSelectOverlay(SelectOverlay):
    BINDINGS = [
        *SelectOverlay.BINDINGS,
        Binding("e", "select", "Select", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    async def _on_key(self, event: events.Key) -> None:
        if event.key in {"e", "enter"}:
            event.stop()
            event.prevent_default()
            self.action_select()
            return
        if event.key == "j":
            event.stop()
            event.prevent_default()
            self.action_cursor_down()
            return
        if event.key == "k":
            event.stop()
            event.prevent_default()
            self.action_cursor_up()
            return
        await super()._on_key(event)


class PiespectorSelect(Select):
    BINDINGS = [
        *Select.BINDINGS,
        Binding("e", "show_overlay", "Show menu", show=False),
        Binding("j", "show_overlay", "Show menu", show=False),
        Binding("k", "show_overlay", "Show menu", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield PiespectorSelectOverlay(type_to_search=self._type_to_search).data_bind(
            compact=Select.compact
        )

    @on(SelectOverlay.UpdateSelection)
    def _update_selection(self, event: SelectOverlay.UpdateSelection) -> None:
        event.stop()
        value = self._options[event.option_index][1]
        if value != self.value:
            self.value = value
        else:
            self._piespector_ignored_change_value = None
            self.post_message(self.Changed(self, value))

        self.focus()
        self.expanded = False
