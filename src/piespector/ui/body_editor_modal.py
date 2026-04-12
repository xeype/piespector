from __future__ import annotations

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


def body_text_editor_is_open(subject) -> bool:
    app = subject if hasattr(subject, "screen_stack") else getattr(subject, "_app", None)
    if app is None:
        app = getattr(subject, "app", None)
    if app is None or not getattr(app, "screen_stack", None):
        return False
    screen = getattr(app, "screen", None)
    return bool(
        screen is not None
        and getattr(screen, "is_modal", False)
        and isinstance(screen, BodyEditorModal)
    )


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
    BINDINGS = [
        Binding(KEY_SAVE, "save_body", "Save", show=False),
        Binding(KEY_ESCAPE, "cancel_body", "Cancel", show=False),
    ]

    def _modal(self) -> BodyEditorModal | None:
        return self.screen if isinstance(self.screen, BodyEditorModal) else None

    def action_save_body(self) -> None:
        modal = self._modal()
        if modal is not None:
            modal.close_body_text_editor(save=True)

    def action_cancel_body(self) -> None:
        modal = self._modal()
        if modal is not None:
            modal.close_body_text_editor(save=False)

    def action_copy_body(self) -> None:
        app = self.app
        if app is None:
            return
        content = self.selected_text or self.text
        copied = app._copy_text(content)
        if copied:
            app.state.message = (
                "Copied selection."
                if self.selected_text
                else "Copied full body."
            )
        else:
            app.state.message = "Copy failed."

    def on_mount(self) -> None:
        self.theme = "css"

    def on_key(self, event: events.Key) -> None:
        app = self.app
        modal = self._modal()
        if event.key == KEY_SAVE:
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
        if modal is None:
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
    """

    BINDINGS = [
        Binding(KEY_ESCAPE, "cancel_body", "Cancel", show=False),
    ]

    def __init__(self, request: RequestDefinition) -> None:
        super().__init__()
        self._title = body_editor_header_text(request)
        self._footer = body_editor_footer_text(request)
        self._body = request.body_text
        self._language = text_area_syntax_language(request_body_syntax_language(request))

    def compose(self) -> ComposeResult:
        with Vertical(id="body-editor-modal"):
            yield Static(self._title, id="body-editor-header")
            yield BodyTextEditor(
                self._body,
                id="body-editor",
                language="json",
                theme="css",
                soft_wrap=False,
                show_line_numbers=True,
                tab_behavior="indent",
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
        if app is not None:
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
                editor.region.x + cursor_offset.x + 1,
                editor.region.y + cursor_offset.y,
            )
            hint.remove_class("hidden")
            return
        hint.add_class("hidden")

    def close_body_text_editor(self, save: bool) -> None:
        app = self.app
        if app is None:
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
