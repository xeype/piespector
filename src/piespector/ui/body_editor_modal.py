from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from piespector.domain.requests import RequestDefinition
from piespector.interactions.keys import KEY_ESCAPE, KEY_SAVE, KEY_TAB
from piespector.placeholders import (
    apply_placeholder_completion,
    auto_pair_placeholder,
    placeholder_match,
)
from piespector.request_builder import validate_raw_body
from piespector.ui.rendering_helpers import (
    request_body_syntax_language,
    text_area_syntax_language,
)
from piespector.ui.text_area_languages import (
    register_graphql_text_area_language,
    set_text_area_language,
)


@dataclass(frozen=True)
class BodyEditorModalContent:
    title: str
    footer: str
    body: str
    language: str | None
    read_only: bool = False
    copy_subject: str = "body"


def _active_body_editor_modal(subject) -> BodyEditorModal | None:
    app = subject if hasattr(subject, "screen_stack") else getattr(subject, "_app", None)
    if app is None:
        app = getattr(subject, "app", None)
    if app is None or not getattr(app, "screen_stack", None):
        return None
    screen = getattr(app, "screen", None)
    if screen is None or not getattr(screen, "is_modal", False):
        return None
    return screen if isinstance(screen, BodyEditorModal) else None


def body_text_editor_is_open(subject) -> bool:
    modal = _active_body_editor_modal(subject)
    return bool(modal is not None and not modal.read_only)


def body_editor_header_text(request: RequestDefinition | None) -> str:
    request_name = request.name if request is not None else "Request"
    if request is not None and request.body_type == "binary":
        return f"Binary File Path  [{request_name}]"
    if request is not None and request.body_type == "graphql":
        return f"GraphQL Editor  [{request_name}]"
    return f"Body Editor  [{request_name}]"


def body_editor_footer_text(request: RequestDefinition | None) -> str:
    if request is not None and request.body_type == "binary":
        return "Enter or paste a file path. Ctrl+S saves, Esc cancels."
    if request is not None and request.body_type == "graphql":
        return "Edit the GraphQL document. Ctrl+S saves, Esc cancels."
    return "Paste and edit freely. Ctrl+S saves, Esc cancels."


class BodyTextEditor(TextArea):
    DEFAULT_CSS = """
    BodyTextEditor {
        background: transparent;
    }
    """

    BINDINGS = [
        Binding(KEY_SAVE, "save_body", "Save", show=False),
        Binding(KEY_ESCAPE, "cancel_body", "Cancel", show=False),
    ]

    def _modal(self) -> BodyEditorModal | None:
        return self.screen if isinstance(self.screen, BodyEditorModal) else None

    def action_save_body(self) -> None:
        modal = self._modal()
        if modal is not None and not modal.read_only:
            modal.close_body_text_editor(save=True)

    def action_cancel_body(self) -> None:
        modal = self._modal()
        if modal is not None:
            modal.close_body_text_editor(save=False)

    def action_copy_body(self) -> None:
        app = self.app
        if app is None:
            return
        modal = self._modal()
        content = self.selected_text or self.text
        copied = app._copy_text(content)
        if copied:
            app.state.message = (
                "Copied selection."
                if self.selected_text
                else f"Copied full {(modal.copy_subject if modal is not None else 'body')}."
            )
        else:
            app.state.message = "Copy failed."

    def on_mount(self) -> None:
        self.theme = "css"

    def on_key(self, event: events.Key) -> None:
        app = self.app
        modal = self._modal()
        if event.key == KEY_SAVE and modal is not None and not modal.read_only:
            self.action_save_body()
            event.prevent_default()
            event.stop()
            return
        if event.key == KEY_ESCAPE:
            self.action_cancel_body()
            event.prevent_default()
            event.stop()
            return
        if app is not None and event.key in app.response_copy_keys:
            self.action_copy_body()
            event.prevent_default()
            event.stop()
            return
        if modal is None or modal.read_only:
            return
        if event.key == KEY_TAB and modal.autocomplete_body_editor_placeholder():
            event.prevent_default()
            event.stop()
            return
        if event.character == "{":
            app.call_after_refresh(modal.postprocess_body_editor_brace)
            return
        if app is not None:
            app.call_after_refresh(modal.refresh_hint)


class BodyEditorModal(ModalScreen[None]):
    DEFAULT_CSS = """
    BodyEditorModal {
        align: center middle;
        background: $background 70%;
    }
    
    #body-editor {
        border: none;
    }

    #body-editor-modal {
        width: 92%;
        height: 92%;
        max-width: 160;
        margin: 1 2;
        border: round $accent;
    }

    #body-editor-header {
        height: auto;
        margin-bottom: 1;
        color: $accent;
        text-style: bold;
    }

    #body-editor-hint {
        position: absolute;
        layer: above;
        width: auto;
        height: 1;
    }

    #body-editor-footer {
        height: auto;
        color: $accent;
    }
    """

    BINDINGS = [
        Binding(KEY_ESCAPE, "cancel_body", "Cancel", show=False),
    ]

    def __init__(self, request: RequestDefinition | BodyEditorModalContent) -> None:
        super().__init__()
        if isinstance(request, BodyEditorModalContent):
            content = request
        else:
            content = BodyEditorModalContent(
                title=body_editor_header_text(request),
                footer=body_editor_footer_text(request),
                body=request.body_text,
                language=text_area_syntax_language(request_body_syntax_language(request)),
            )
        self._title = content.title
        self._footer = content.footer
        self._body = content.body
        self._language = content.language
        self._read_only = content.read_only
        self._copy_subject = content.copy_subject

    @classmethod
    def viewer(
        cls,
        *,
        title: str,
        footer: str,
        body: str,
        language: str | None,
        copy_subject: str = "response",
    ) -> BodyEditorModal:
        return cls(
            BodyEditorModalContent(
                title=title,
                footer=footer,
                body=body,
                language=language,
                read_only=True,
                copy_subject=copy_subject,
            )
        )

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def copy_subject(self) -> str:
        return self._copy_subject

    def compose(self) -> ComposeResult:
        with Vertical(id="body-editor-modal"):
            yield Static(self._title, id="body-editor-header")
            yield BodyTextEditor(
                self._body,
                id="body-editor",
                language=None,
                theme="css",
                soft_wrap=False,
                show_line_numbers=True,
                tab_behavior="indent",
                read_only=self._read_only,
            )
            yield Static("", id="body-editor-hint", classes="hidden")
            yield Static(self._footer, id="body-editor-footer")

    def on_mount(self) -> None:
        editor = self.query_one("#body-editor", TextArea)
        register_graphql_text_area_language(editor)
        set_text_area_language(editor, self._language)
        editor.load_text(self._body)
        editor.move_cursor((0, 0))
        editor.focus()
        app = self.app
        if app is not None and not self._read_only:
            app.call_after_refresh(self.refresh_hint)

    def action_cancel_body(self) -> None:
        self.close_body_text_editor(save=False)

    def body_editor_cursor_index(self) -> int:
        editor = self.query_one("#body-editor", TextArea)
        row, column = editor.cursor_location
        lines = editor.text.splitlines(keepends=True)
        if editor.text.endswith("\n"):
            lines.append("")
        if not lines:
            return 0
        row = max(0, min(row, len(lines) - 1))
        return sum(len(lines[index]) for index in range(row)) + column

    def body_editor_location_from_index(
        self,
        text: str,
        index: int,
    ) -> tuple[int, int]:
        index = max(0, min(index, len(text)))
        row = 0
        current = 0
        for chunk in text.splitlines(keepends=True):
            next_current = current + len(chunk)
            if index <= next_current:
                return (row, index - current)
            current = next_current
            row += 1
        return (row, index - current)

    def autocomplete_body_editor_placeholder(self) -> bool:
        if self._read_only:
            return False
        app = self.app
        if app is None:
            return False
        editor = self.query_one("#body-editor", TextArea)
        cursor_index = self.body_editor_cursor_index()
        completed = apply_placeholder_completion(
            editor.text,
            cursor_index,
            sorted(app.state.env_pairs),
        )
        if completed is None:
            return False
        text, new_cursor_index = completed
        editor.load_text(text)
        editor.move_cursor(self.body_editor_location_from_index(text, new_cursor_index))
        self.refresh_hint()
        return True

    def auto_pair_body_editor_placeholder(self) -> bool:
        if self._read_only:
            return False
        editor = self.query_one("#body-editor", TextArea)
        updated = auto_pair_placeholder(
            editor.text,
            self.body_editor_cursor_index(),
        )
        if updated is None:
            return False
        text, new_cursor_index = updated
        editor.load_text(text)
        editor.move_cursor(self.body_editor_location_from_index(text, new_cursor_index))
        self.refresh_hint()
        return True

    def postprocess_body_editor_brace(self) -> None:
        if not self.auto_pair_body_editor_placeholder():
            self.refresh_hint()

    def refresh_hint(self) -> None:
        if self._read_only:
            return
        app = self.app
        if app is None:
            return
        editor = self.query_one("#body-editor", TextArea)
        hint = self.query_one("#body-editor-hint", Static)
        cursor_index = self.body_editor_cursor_index()
        match = placeholder_match(
            editor.text,
            cursor_index,
            sorted(app.state.env_pairs),
        )
        if match is not None and match.suggestion != match.prefix:
            cursor_offset = editor.cursor_screen_offset
            hint.update(match.suggestion)
            hint.offset = (
                cursor_offset.x - 3,
                cursor_offset.y - 3,
            )
            hint.remove_class("hidden")
            return
        hint.add_class("hidden")

    def close_body_text_editor(self, save: bool) -> None:
        app = self.app
        if app is None:
            return
        if self._read_only:
            self.dismiss(None)
            return
        editor = self.query_one("#body-editor", TextArea)
        if save:
            request = app.state.get_active_request()
            validation_error = (
                validate_raw_body(request, editor.text) if request is not None else None
            )
            if validation_error is not None:
                app.state.message = validation_error
                app._refresh_screen()
                return
            app.state.save_raw_body_text(editor.text)
        else:
            app.state.cancel_home_body_text_edit()
        self.dismiss(None)
