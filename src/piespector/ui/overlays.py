from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from piespector.interactions.keys import KEY_ESCAPE
from piespector.ui.text_area_languages import (
    register_graphql_text_area_language,
    set_text_area_language,
)


@dataclass(frozen=True)
class ResponseModalContent:
    title: str
    footer: str
    body: str
    language: str | None


class ResponseModalEditor(TextArea):
    BINDINGS = [
        Binding(KEY_ESCAPE, "close_response", "Close", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("read_only", True)
        super().__init__(*args, **kwargs)

    def action_close_response(self) -> None:
        app = self.app
        if app is not None:
            app._close_response_viewer()

    def action_copy_response(self) -> None:
        app = self.app
        if app is None:
            return
        content = self.selected_text or self.text
        copied = app._copy_text(content)
        if copied:
            app.state.message = (
                "Copied selection."
                if self.selected_text
                else "Copied full response."
            )
        else:
            app.state.message = "Copy failed."

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if app is not None and event.key in app.response_copy_keys:
            self.action_copy_response()
            event.stop()
            return
        if event.key == KEY_ESCAPE:
            self.action_close_response()
            event.stop()
            return


class ResponseModal(ModalScreen[None]):
    BINDINGS = [
        Binding(KEY_ESCAPE, "close_response", "Close", show=False),
    ]

    def __init__(self, content: ResponseModalContent) -> None:
        super().__init__()
        self._content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="response-modal"):
            yield Static(self._content.title, id="response-modal-header")
            yield ResponseModalEditor(
                self._content.body,
                id="response-modal-editor",
                language=None,
                theme="css",
                soft_wrap=False,
                show_line_numbers=True,
            )
            yield Static(self._content.footer, id="response-modal-footer")

    def on_mount(self) -> None:
        editor = self.query_one("#response-modal-editor", TextArea)
        editor.theme = "css"
        register_graphql_text_area_language(editor)
        set_text_area_language(editor, self._content.language)
        editor.load_text(self._content.body)
        editor.move_cursor((0, 0))
        editor.focus()

    def action_close_response(self) -> None:
        app = self.app
        if app is not None:
            app._close_response_viewer()
