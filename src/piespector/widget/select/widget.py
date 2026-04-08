from __future__ import annotations

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Select
from textual.widgets._select import SelectCurrent, SelectOverlay

from .events import SelectionChanged
from .models import OptionList, SelectOption
from .state import SelectSyncState


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
    """Select widget with vim keybindings and typed sync state.

    Differences from Textual's ``Select``:

    - Posts :class:`~piespector.widget.select.events.SelectionChanged` instead
      of ``Select.Changed`` — including when the same value is re-confirmed.
    - Vim keybindings: ``j``/``k`` open the overlay from closed state;
      ``j``/``k`` navigate and ``e``/``enter`` confirm when the overlay is open.
    - All sync bookkeeping lives in ``.sync_state`` (:class:`SelectSyncState`)
      instead of scattered monkey-patched attributes.
    """

    BINDINGS = [
        *Select.BINDINGS,
        Binding("e", "show_overlay", "Show menu", show=False),
        Binding("j", "show_overlay", "Show menu", show=False),
        Binding("k", "show_overlay", "Show menu", show=False),
    ]

    def __init__(self, options: OptionList, **kwargs) -> None:
        super().__init__([opt.as_textual() for opt in options], **kwargs)
        self.sync_state = SelectSyncState()

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield PiespectorSelectOverlay(
            type_to_search=self._type_to_search
        ).data_bind(compact=Select.compact)

    @on(SelectOverlay.UpdateSelection)
    def _on_update_selection(self, event: SelectOverlay.UpdateSelection) -> None:
        event.stop()

        value = self._options[event.option_index][1]
        label = self._options[event.option_index][0]
        state = self.sync_state

        if value != self.value:
            # Triggers Select.Changed internally; adapted by _on_native_changed.
            self.value = value
        elif self._should_ignore_changed(value):
            return

        self.focus()
        self.expanded = False
        self.post_message(SelectionChanged(self, SelectOption(value=value, label=label)))

    @on(Select.Changed)
    def _on_native_changed(self, event: Select.Changed) -> None:
        """Adapt Textual's Select.Changed into piespector's SelectionChanged."""
        event.stop()
        value = event.value
        if self._should_ignore_changed(value):
            return
        self.post_message(
            SelectionChanged(
                self,
                SelectOption(value=value, label=self._label_for_value(value)),
            )
        )

    def _should_ignore_changed(self, value) -> bool:
        del value
        state = self.sync_state
        if state.signature is None:
            return True
        if state.syncing or state.suppress_changes:
            return True
        return False

    def _label_for_value(self, value) -> object:
        for label, option_value in self._options:
            if option_value == value:
                return label
        return value
