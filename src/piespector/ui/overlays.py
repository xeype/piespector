from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual._tree_sitter import get_language
from textual.binding import Binding
from textual.widgets import Static, TextArea
from textual.widgets._text_area import LanguageDoesNotExist

from piespector.domain.editor import HISTORY_DETAIL_BLOCK_REQUEST, RESPONSE_TAB_HEADERS
from piespector.domain.modes import (
    MODE_HISTORY_RESPONSE_TEXTAREA,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_RESPONSE_TEXTAREA,
)
from piespector.http_client import validate_raw_body
from piespector.interactions.keys import KEY_ESCAPE, KEY_SAVE, KEY_TAB
from piespector.placeholders import apply_placeholder_completion, auto_pair_placeholder, placeholder_match
from piespector.rendering import (
    detect_text_syntax_language,
    format_response_body,
    request_body_syntax_language,
    text_area_syntax_language,
)
from piespector.scrollbars import ThinScrollBarRender

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


GRAPHQL_TEXTAREA_LANGUAGE = "piespector-graphql"
GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY = """
[
  "{"
  "}"
] @punctuation.bracket

((identifier) @keyword
 (#match? @keyword "^(query|mutation|subscription|fragment|on)$"))

((identifier) @class
 (#match? @class "^[A-Z][A-Za-z0-9_]*$"))

((identifier) @function
 (#match? @function "^[a-z_][A-Za-z0-9_]*$"))
"""


class BodyTextEditor(TextArea):
    BINDINGS = [
        Binding(KEY_SAVE, "save_body", "Save", show=False),
        Binding(KEY_ESCAPE, "cancel_body", "Cancel", show=False),
    ]

    def action_save_body(self) -> None:
        app = self.app
        if app is not None:
            app._close_body_text_editor(save=True)

    def action_cancel_body(self) -> None:
        app = self.app
        if app is not None:
            app._close_body_text_editor(save=False)

    def on_key(self, event: events.Key) -> None:
        app = self.app
        if event.key == KEY_SAVE:
            self.action_save_body()
            event.stop()
            return
        if event.key == KEY_ESCAPE:
            self.action_cancel_body()
            event.stop()
            return
        if app is not None:
            if event.key == KEY_TAB and app._autocomplete_body_editor_placeholder():
                event.stop()
                return
            if event.character == "{":
                app.call_after_refresh(app._postprocess_body_editor_brace)
                return
            app.call_after_refresh(app._refresh_overlay_editors)


class ResponseViewer(TextArea):
    BINDINGS = [
        Binding(KEY_ESCAPE, "close_response", "Close", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("read_only", True)
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        self.vertical_scrollbar.renderer = ThinScrollBarRender
        self.horizontal_scrollbar.renderer = ThinScrollBarRender

    def action_close_response(self) -> None:
        app = self.app
        if app is not None:
            app._close_response_viewer()

    def action_copy_response(self) -> None:
        app = self.app
        if app is not None:
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
            app._refresh_command_line()

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


def build_overlay_widgets() -> tuple[Static | TextArea, ...]:
    return (
        Static("", id="body-editor-header", classes="hidden"),
        BodyTextEditor(
            "",
            id="body-editor",
            language="json",
            theme="monokai",
            soft_wrap=False,
            show_line_numbers=True,
            tab_behavior="indent",
            classes="hidden",
        ),
        Static("", id="body-editor-hint", classes="hidden"),
        Static("", id="body-editor-footer", classes="hidden"),
        Static("", id="response-viewer-header", classes="hidden"),
        ResponseViewer(
            "",
            id="response-viewer",
            language=None,
            theme="monokai",
            soft_wrap=False,
            show_line_numbers=True,
            classes="hidden",
        ),
        Static("", id="response-viewer-footer", classes="hidden"),
    )


class OverlayController:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def register_text_area_languages(self) -> None:
        try:
            javascript_language = get_language("javascript")
        except Exception:
            return
        if javascript_language is None:
            return
        for editor_id in ("#body-editor", "#response-viewer"):
            editor = self.app.query_one(editor_id, TextArea)
            editor.register_language(
                GRAPHQL_TEXTAREA_LANGUAGE,
                javascript_language,
                GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY,
            )

    def set_text_area_language(
        self,
        editor: TextArea,
        language: str | None,
    ) -> None:
        try:
            editor.language = language
        except LanguageDoesNotExist:
            editor.language = None

    def body_editor_cursor_index(self) -> int:
        editor = self.app.query_one("#body-editor", TextArea)
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
        editor = self.app.query_one("#body-editor", TextArea)
        cursor_index = self.body_editor_cursor_index()
        completed = apply_placeholder_completion(
            editor.text,
            cursor_index,
            sorted(self.state.env_pairs),
        )
        if completed is None:
            return False
        text, new_cursor_index = completed
        editor.load_text(text)
        editor.move_cursor(self.body_editor_location_from_index(text, new_cursor_index))
        self.refresh()
        return True

    def auto_pair_body_editor_placeholder(self) -> bool:
        editor = self.app.query_one("#body-editor", TextArea)
        cursor_index = self.body_editor_cursor_index()
        text = editor.text
        cursor_index = max(0, min(cursor_index, len(text)))
        if cursor_index >= 2 and text[cursor_index - 2 : cursor_index] == "{{":
            if text[cursor_index : cursor_index + 2] == "}}":
                return False
            updated = text[:cursor_index] + "}}" + text[cursor_index:]
            editor.load_text(updated)
            editor.move_cursor(
                self.body_editor_location_from_index(updated, cursor_index)
            )
            self.refresh()
            return True
        return False

    def postprocess_body_editor_brace(self) -> None:
        if not self.auto_pair_body_editor_placeholder():
            self.refresh()

    def body_editor_header_text(self) -> str:
        request = self.state.get_active_request()
        request_name = request.name if request is not None else "Request"
        if request is not None and request.body_type == "binary":
            return f"Binary File Path  [{request_name}]"
        if request is not None and request.body_type == "graphql":
            return f"GraphQL Editor  [{request_name}]"
        return f"Body Editor  [{request_name}]"

    def body_editor_footer_text(self) -> str:
        request = self.state.get_active_request()
        if request is not None and request.body_type == "binary":
            return "Enter or paste a file path. Ctrl+S saves, Esc cancels."
        if request is not None and request.body_type == "graphql":
            return "Edit the GraphQL document. Ctrl+S saves, Esc cancels."
        return "Paste and edit freely. Ctrl+S saves, Esc cancels."

    def refresh(self) -> None:
        viewport = self.app.query_one("#viewport", Static)
        body_header = self.app.query_one("#body-editor-header", Static)
        body_editor = self.app.query_one("#body-editor", TextArea)
        body_hint = self.app.query_one("#body-editor-hint", Static)
        body_footer = self.app.query_one("#body-editor-footer", Static)
        response_header = self.app.query_one("#response-viewer-header", Static)
        response_editor = self.app.query_one("#response-viewer", TextArea)
        response_footer = self.app.query_one("#response-viewer-footer", Static)

        if self.state.mode == MODE_HOME_BODY_TEXTAREA:
            body_header.update(self.body_editor_header_text())
            cursor_index = self.body_editor_cursor_index()
            match = placeholder_match(body_editor.text, cursor_index, sorted(self.state.env_pairs))
            body_footer.update(self.body_editor_footer_text())
            viewport.add_class("hidden")
            body_header.remove_class("hidden")
            body_editor.remove_class("hidden")
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = body_editor.cursor_screen_offset
                body_hint.update(match.suggestion)
                body_hint.offset = (
                    body_editor.region.x + cursor_offset.x + 1,
                    body_editor.region.y + cursor_offset.y,
                )
                body_hint.remove_class("hidden")
            else:
                body_hint.add_class("hidden")
            body_footer.remove_class("hidden")
            response_header.add_class("hidden")
            response_editor.add_class("hidden")
            response_footer.add_class("hidden")
            body_editor.disabled = False
            response_editor.disabled = True
            if not body_editor.has_focus:
                body_editor.focus()
            return

        if self.state.mode == MODE_HOME_RESPONSE_TEXTAREA:
            request = self.state.get_active_request()
            response = request.last_response if request is not None else None
            request_name = request.name if request is not None else "Request"
            status = response.status_code if response is not None else "-"
            elapsed = f"{response.elapsed_ms or 0:.1f} ms" if response is not None else "-"
            response_header.update(f"Response Viewer  [{request_name}]")
            response_footer.update(
                f"Status {status}   Time {elapsed}   {self.app.response_copy_hint} copies selection/all   Esc closes"
            )
            viewport.add_class("hidden")
            body_header.add_class("hidden")
            body_editor.add_class("hidden")
            body_hint.add_class("hidden")
            body_footer.add_class("hidden")
            response_header.remove_class("hidden")
            response_editor.remove_class("hidden")
            response_footer.remove_class("hidden")
            body_editor.disabled = True
            response_editor.disabled = False
            if not response_editor.has_focus:
                response_editor.focus()
            return

        if self.state.mode == MODE_HISTORY_RESPONSE_TEXTAREA:
            entry = self.state.get_selected_history_entry()
            entry_name = (
                entry.source_request_name.strip()
                or entry.source_request_path.strip()
                or "History"
            ) if entry is not None else "History"
            response_header.update(f"History Viewer  [{entry_name}]")
            response_footer.update(
                f"{self.app.response_copy_hint} copies selection/all   Esc closes"
            )
            viewport.add_class("hidden")
            body_header.add_class("hidden")
            body_editor.add_class("hidden")
            body_hint.add_class("hidden")
            body_footer.add_class("hidden")
            response_header.remove_class("hidden")
            response_editor.remove_class("hidden")
            response_footer.remove_class("hidden")
            body_editor.disabled = True
            response_editor.disabled = False
            if not response_editor.has_focus:
                response_editor.focus()
            return

        viewport.remove_class("hidden")
        body_header.add_class("hidden")
        body_editor.add_class("hidden")
        body_hint.add_class("hidden")
        body_footer.add_class("hidden")
        response_header.add_class("hidden")
        response_editor.add_class("hidden")
        response_footer.add_class("hidden")
        body_editor.disabled = True
        response_editor.disabled = True

    def open_body_text_editor(self, origin_mode: str | None = None) -> None:
        request = self.state.get_active_request()
        if request is None:
            self.state.message = "No requests to edit."
            self.app._refresh_screen()
            return
        self.state.enter_home_body_text_editor_mode(origin_mode=origin_mode)
        editor = self.app.query_one("#body-editor", TextArea)
        self.set_text_area_language(
            editor,
            text_area_syntax_language(request_body_syntax_language(request)),
        )
        editor.load_text(request.body_text)
        editor.move_cursor((0, 0))
        self.app._refresh_screen()

    def close_body_text_editor(self, save: bool) -> None:
        editor = self.app.query_one("#body-editor", TextArea)
        if save:
            request = self.state.get_active_request()
            validation_error = (
                validate_raw_body(request, editor.text) if request is not None else None
            )
            if validation_error is not None:
                self.state.message = validation_error
                self.app._refresh_screen()
                return
            updated_field = self.state.save_raw_body_text(editor.text)
            if updated_field is not None:
                self.app._persist_requests()
        else:
            self.state.leave_home_body_text_editor_mode()
        self.app.set_focus(None)
        self.app._refresh_screen()
        self.app.call_after_refresh(self.app._refresh_screen)

    def open_response_viewer(self, origin_mode: str | None = None) -> None:
        request = self.state.get_active_request()
        if request is None or request.last_response is None:
            self.state.message = "No response to view."
            self.app._refresh_screen()
            return
        if not self.state.enter_home_response_view_mode(origin_mode or self.state.mode):
            self.app._refresh_screen()
            return
        editor = self.app.query_one("#response-viewer", TextArea)
        body_text = format_response_body(request.last_response.body_text)
        self.set_text_area_language(
            editor,
            text_area_syntax_language(detect_text_syntax_language(body_text)),
        )
        editor.load_text(body_text or request.last_response.body_text or "")
        editor.move_cursor((0, 0))
        self.app._refresh_screen()

    def open_history_response_viewer(self, origin_mode: str | None = None) -> None:
        entry = self.state.get_selected_history_entry()
        if entry is None:
            self.state.message = "No history entry selected."
            self.app._refresh_screen()
            return
        if not self.state.enter_history_response_view_mode(origin_mode or self.state.mode):
            self.app._refresh_screen()
            return
        editor = self.app.query_one("#response-viewer", TextArea)
        if self.state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
            if self.state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
                self.set_text_area_language(editor, None)
                content = "\n".join(
                    f"{key}: {value}" for key, value in entry.request_headers
                ) or "-"
            else:
                body_text = format_response_body(entry.request_body)
                self.set_text_area_language(
                    editor,
                    text_area_syntax_language(detect_text_syntax_language(body_text)),
                )
                content = body_text or entry.request_body or ""
        elif self.state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
            self.set_text_area_language(editor, None)
            content = "\n".join(
                f"{key}: {value}" for key, value in entry.response_headers
            ) or "-"
        else:
            body_text = format_response_body(entry.response_body)
            self.set_text_area_language(
                editor,
                text_area_syntax_language(detect_text_syntax_language(body_text)),
            )
            content = body_text or entry.response_body or ""
        editor.load_text(content)
        editor.move_cursor((0, 0))
        self.app._refresh_screen()

    def close_response_viewer(self) -> None:
        if self.state.mode == MODE_HISTORY_RESPONSE_TEXTAREA:
            self.state.leave_history_response_view_mode()
        else:
            self.state.leave_home_response_view_mode()
        self.app.set_focus(None)
        self.app._refresh_screen()
        self.app.call_after_refresh(self.app._refresh_screen)
