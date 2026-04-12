from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from piespector.domain.editor import (
    HISTORY_DETAIL_BLOCK_REQUEST,
    RESPONSE_TAB_HEADERS,
)
from piespector.interactions.keys import KEY_ESCAPE
from piespector.ui.rendering_helpers import (
    detect_text_syntax_language,
    format_response_body,
    text_area_syntax_language,
)
from piespector.ui.text_area_languages import (
    register_graphql_text_area_language,
    set_text_area_language,
)

if TYPE_CHECKING:
    from piespector.app import PiespectorApp

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


def build_input_hint_widgets() -> tuple[Static, ...]:
    return (
        Static("", id="url-input-hint", classes="hidden"),
        Static("", id="params-input-hint", classes="hidden"),
        Static("", id="headers-input-hint", classes="hidden"),
        Static("", id="auth-field-input-hint", classes="hidden"),
    )


class OverlayController:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def open_response_viewer(self, origin_mode: str | None = None) -> None:
        request = self.state.get_active_request()
        if request is None or request.last_response is None:
            self.state.message = "No response to view."
            self.app._refresh_screen()
            return
        body_text = format_response_body(request.last_response.body_text)
        response = request.last_response
        request_name = request.name if request.name else "Request"
        status = response.status_code if response is not None else "-"
        elapsed = f"{response.elapsed_ms or 0:.1f} ms" if response is not None else "-"
        self.app.push_screen(
            ResponseModal(
                ResponseModalContent(
                    title=f"Response Viewer  [{request_name}]",
                    footer=(
                        f"Status {status}   Time {elapsed}   "
                        f"{self.app.response_copy_hint} copies selection/all   Esc closes"
                    ),
                    body=body_text or request.last_response.body_text or "",
                    language=text_area_syntax_language(
                        detect_text_syntax_language(body_text)
                    ),
                )
            )
        )

    def open_history_response_viewer(self, origin_mode: str | None = None) -> None:
        entry = self.state.get_selected_history_entry()
        if entry is None:
            self.state.message = "No history entry selected."
            self.app._refresh_screen()
            return
        if self.state.selected_history_detail_block == HISTORY_DETAIL_BLOCK_REQUEST:
            if self.state.selected_history_request_tab == RESPONSE_TAB_HEADERS:
                language = None
                content = "\n".join(
                    f"{key}: {value}" for key, value in entry.request_headers
                ) or "-"
            else:
                body_text = format_response_body(entry.request_body)
                language = text_area_syntax_language(
                    detect_text_syntax_language(body_text)
                )
                content = body_text or entry.request_body or ""
        elif self.state.selected_history_response_tab == RESPONSE_TAB_HEADERS:
            language = None
            content = "\n".join(
                f"{key}: {value}" for key, value in entry.response_headers
            ) or "-"
        else:
            body_text = format_response_body(entry.response_body)
            language = text_area_syntax_language(
                detect_text_syntax_language(body_text)
            )
            content = body_text or entry.response_body or ""
        entry_name = (
            entry.source_request_name.strip()
            or entry.source_request_path.strip()
            or "History"
        )
        self.app.push_screen(
            ResponseModal(
                ResponseModalContent(
                    title=f"History Viewer  [{entry_name}]",
                    footer=(
                        f"{self.app.response_copy_hint} copies selection/all   Esc closes"
                    ),
                    body=content,
                    language=language,
                )
            )
        )

    def close_response_viewer(self) -> None:
        if (
            self.app.screen_stack
            and self.app.screen.is_modal
            and isinstance(self.app.screen, ResponseModal)
        ):
            self.app.pop_screen()
        self.app.set_focus(None)
        self.app._refresh_screen()
        self.app.call_after_refresh(self.app._clear_home_jump_focus)
