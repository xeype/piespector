from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Static, Tab, Tabs

from piespector.domain.http import HTTP_METHODS
from piespector.domain.modes import (
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_URL_EDIT,
)
from piespector.placeholders import placeholder_match
from piespector.screens.home.request.method_selection import method_color
from piespector.screens.home.request.url_bar import (
    render_request_url_display,
)
from piespector.screens.home.selection import home_selection
from piespector.ui.input import PiespectorInput
from piespector.ui.selection import effective_mode, set_selected
from piespector.widget.select import (
    PiespectorSelect,
    SelectionChanged,
    deactivate,
    option_list,
    sync,
)

if TYPE_CHECKING:
    from piespector.domain.requests import RequestDefinition
    from piespector.state import PiespectorState


class UrlBar(Vertical):
    editing = reactive(False)

    class OpenRequestActivated(Message):
        def __init__(self, url_bar: UrlBar, request_id: str) -> None:
            super().__init__()
            self.url_bar = url_bar
            self.request_id = request_id

        @property
        def control(self) -> UrlBar:
            return self.url_bar

    class MethodChanged(Message):
        def __init__(self, url_bar: UrlBar, method: str) -> None:
            super().__init__()
            self.url_bar = url_bar
            self.method = method

        @property
        def control(self) -> UrlBar:
            return self.url_bar

    class UrlSaved(Message):
        def __init__(self, url_bar: UrlBar, value: str) -> None:
            super().__init__()
            self.url_bar = url_bar
            self.value = value

        @property
        def control(self) -> UrlBar:
            return self.url_bar

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._url_env_completion_anchor = ""
        self._url_env_completion_matches: list[str] = []
        self._url_env_completion_index = -1
        self._url_completion_request_id: str | None = None
        self._hint_refresh_scheduled = False

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    @property
    def _state(self) -> PiespectorState | None:
        app = self._owner_app()
        return None if app is None else app.state

    def compose(self) -> ComposeResult:
        subtitle = Static("", classes="panel-subtitle", id="url-bar-subtitle")
        subtitle.display = False
        url_input = PiespectorInput(
            "",
            id="url-input",
            compact=True,
            select_on_focus=False,
        )
        url_input.display = False

        yield Tabs(id="open-request-tabs")
        with Horizontal(id="url-line"):
            yield PiespectorSelect(
                option_list(*((method, method) for method in HTTP_METHODS)),
                id="method-select",
                allow_blank=False,
                value="GET",
                compact=True,
            )
            yield Static("", id="url-display")
            yield url_input
        yield subtitle
        yield Static("", id="url-input-hint", classes="hidden")

    def on_mount(self) -> None:
        self.query_one("#open-request-tabs", Tabs).can_focus = False

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        active_request = state.get_active_request()
        self.editing = effective_mode(state) == MODE_HOME_URL_EDIT

        self.query_one("#url-bar-subtitle", Static).update("")
        self.query_one("#url-bar-subtitle", Static).display = False

        self._refresh_open_request_tabs(state)
        self._sync_method_select(state, active_request)
        self._sync_url_line(state, active_request)
        self._sync_hint(state)

    def refresh_hint_from_state(self) -> None:
        state = self._state
        if state is None:
            return
        self._sync_hint(state)

    def _method_select(self) -> PiespectorSelect:
        return self.query_one("#method-select", PiespectorSelect)

    def _url_display(self) -> Static:
        return self.query_one("#url-display", Static)

    def _url_input(self) -> Input:
        return self.query_one("#url-input", Input)

    def _url_hint(self) -> Static:
        return self.query_one("#url-input-hint", Static)

    def _open_tabs(self) -> Tabs:
        return self.query_one("#open-request-tabs", Tabs)

    def _sync_method_select(
        self,
        state: PiespectorState,
        active_request: RequestDefinition | None,
    ) -> None:
        method_select = self._method_select()
        set_selected(method_select, home_selection(state).method_selected)

        if active_request is None:
            deactivate(method_select)
            method_select.display = False
            method_select.can_focus = False
            return

        method_select.can_focus = state.mode == MODE_HOME_REQUEST_METHOD_EDIT
        method_options = option_list(
            *((method, Text(method, style=method_color(method))) for method in HTTP_METHODS)
        )

        sync(
            method_select,
            method_options,
            active_request.method.upper(),
            auto_open_token=(
                ("method-select", active_request.request_id, state.mode)
                if state.mode == MODE_HOME_REQUEST_METHOD_EDIT
                else None
            ),
        )
        method_select.display = True

        if effective_mode(state) in {
            MODE_HOME_REQUEST_METHOD_SELECT,
            MODE_HOME_REQUEST_METHOD_EDIT,
        }:
            return

        try:
            label_widget = method_select.query_one("SelectCurrent Static#label", Static)
            label_widget.styles.color = method_color(active_request.method.upper())
        except NoMatches:
            pass

    def _sync_url_line(
        self,
        state: PiespectorState,
        active_request: RequestDefinition | None,
    ) -> None:
        url_display = self._url_display()
        url_input = self._url_input()

        if active_request is None:
            self._reset_url_completion()
            self._sync_input_widget(url_input, "", display=False)
            url_display.display = True
            url_display.update(Text("No opened request."))
            url_display._piespector_signature = ("no-opened-request",)
            return

        if self.editing:
            self._sync_input_widget(
                url_input,
                active_request.url or "",
                display=True,
                placeholder="Request URL",
                focus_token=("url", active_request.request_id, state.mode),
            )
            url_display.display = False
            if self._url_completion_request_id != active_request.request_id:
                self._reset_url_completion()
                self._url_completion_request_id = active_request.request_id
            return

        self._reset_url_completion()
        self._sync_input_widget(url_input, "", display=False)
        url_display.display = True
        url_display_signature = self._url_line_state_signature(state, active_request)
        if getattr(url_display, "_piespector_signature", None) == url_display_signature:
            return

        url_display.update(render_request_url_display(active_request))
        url_display._piespector_signature = url_display_signature

    def _sync_hint(self, state: PiespectorState) -> None:
        url_input = self._url_input()
        url_hint = self._url_hint()

        if self.editing and url_input.display:
            match = placeholder_match(
                url_input.value,
                url_input.cursor_position,
                sorted(state.env_pairs),
            )
            if match is not None and match.suggestion != match.prefix:
                cursor_offset = url_input.cursor_screen_offset
                url_hint.update(match.suggestion)
                url_hint.offset = (cursor_offset.x, cursor_offset.y + 1)
                url_hint.remove_class("hidden")
                return

        url_hint.add_class("hidden")

    def _refresh_open_request_tabs(self, state: PiespectorState) -> None:
        tabs = self._open_tabs()
        visible_requests = self._visible_open_requests(state)

        signature = self._open_request_tabs_signature(state)
        if getattr(tabs, "_piespector_signature", None) != signature:
            self._mount_open_request_tabs(state, tabs)
            tabs._piespector_signature = signature
        else:
            self._sync_active_tab(state, tabs)

        tabs.display = bool(visible_requests)

    def _mount_open_request_tabs(self, state: PiespectorState, tabs: Tabs) -> None:
        try:
            tabs_list = tabs.query_one("#tabs-list")
        except NoMatches:
            return

        open_requests = self._visible_open_requests(state)
        existing_tabs = {
            tab.id: tab
            for tab in tabs.query("#tabs-list > Tab")
            if tab.id is not None
        }
        desired_ids = {
            f"open-req-{request.request_id}"
            for request in open_requests
        }

        for tab_id, tab in existing_tabs.items():
            if tab_id not in desired_ids:
                tab.remove()

        for request in open_requests:
            spinner = self._tab_spinner(state, request.request_id)
            tab_id = f"open-req-{request.request_id}"
            label_signature = (request.method, request.name, spinner)
            existing = existing_tabs.get(tab_id)
            if existing is not None:
                if getattr(existing, "_piespector_label_sig", None) != label_signature:
                    existing.update(self._open_request_tab_label(request.method, request.name, spinner))
                    existing._piespector_label_sig = label_signature
                continue

            new_tab = Tab(
                self._open_request_tab_label(request.method, request.name, spinner),
                id=tab_id,
            )
            new_tab._piespector_label_sig = label_signature
            tabs_list.mount(new_tab)

        self._sync_active_tab(state, tabs)

    def _sync_active_tab(self, state: PiespectorState, tabs: Tabs) -> None:
        if state.active_request_id:
            active_tab_id = f"open-req-{state.active_request_id}"
            if tabs.active != active_tab_id and tabs.query(f"#tabs-list > #{active_tab_id}"):
                tabs.active = active_tab_id
            return

        if tabs.active:
            tabs.active = ""

    def _open_request_tab_label(self, method: str, name: str, spinner: str) -> Text:
        label = Text()
        if spinner:
            label.append(spinner)
        label.append(method, style=method_color(method))
        label.append(f" {name}")
        return label

    def _tab_spinner(self, state: PiespectorState, request_id: str) -> str:
        if request_id != state.pending_request_id:
            return ""
        spinner_frames = ("|", "/", "-", "\\")
        return f"{spinner_frames[state.pending_request_spinner_tick % len(spinner_frames)]} "

    def _open_request_tabs_signature(
        self,
        state: PiespectorState,
    ) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            (
                request.request_id,
                request.method,
                request.name,
                self._tab_spinner(state, request.request_id),
            )
            for request in self._visible_open_requests(state)
        )

    def _visible_open_requests(self, state: PiespectorState) -> list[RequestDefinition]:
        open_requests = state.get_open_requests()
        if open_requests:
            return open_requests
        active_request = state.get_active_request()
        if active_request is None:
            return []
        return [active_request]

    def _url_line_state_signature(
        self,
        state: PiespectorState,
        active_request: RequestDefinition | None,
    ) -> tuple[object, ...]:
        if active_request is None:
            return ("no-opened-request",)

        mode = effective_mode(state)
        query_signature = tuple(
            (item.key, item.value, item.enabled)
            for item in active_request.query_items
        )
        auth_signature = (
            active_request.auth_type,
            active_request.auth_api_key_location,
            active_request.auth_api_key_name,
            active_request.auth_api_key_value,
        )

        if mode in {MODE_HOME_REQUEST_METHOD_EDIT, MODE_HOME_REQUEST_METHOD_SELECT}:
            return (
                "method-select",
                active_request.request_id,
                active_request.method,
                active_request.url,
                query_signature,
                auth_signature,
            )

        return (
            "url-preview",
            active_request.request_id,
            active_request.method,
            active_request.url,
            query_signature,
            auth_signature,
        )

    def _sync_input_widget(
        self,
        input_widget: Input,
        value: str,
        *,
        display: bool,
        placeholder: str = "",
        focus_token: object | None = None,
    ) -> None:
        input_widget.display = display
        input_widget.placeholder = placeholder

        if not display:
            if input_widget.has_focus:
                input_widget.blur()
            input_widget._piespector_focus_token = None
            if input_widget.value:
                input_widget.value = ""
            return

        if focus_token is None:
            if input_widget.value != value:
                input_widget.value = value
            return

        if getattr(input_widget, "_piespector_focus_token", None) == focus_token:
            return

        input_widget._piespector_focus_token = focus_token
        input_widget.value = value
        input_widget.cursor_position = len(value)
        input_widget.focus()

    def _reset_url_completion(self) -> None:
        self._url_env_completion_anchor = ""
        self._url_env_completion_matches = []
        self._url_env_completion_index = -1
        if not self.editing:
            self._url_completion_request_id = None

    def _schedule_hint_refresh(self) -> None:
        if self._hint_refresh_scheduled:
            return

        self._hint_refresh_scheduled = True

        def refresh_hint() -> None:
            self._hint_refresh_scheduled = False
            self.refresh_hint_from_state()

        self.call_after_refresh(refresh_hint)

    @on(SelectionChanged, "#method-select")
    def _on_method_selected(self, event: SelectionChanged) -> None:
        state = self._state
        if state is None or state.mode != MODE_HOME_REQUEST_METHOD_EDIT:
            return
        event.stop()
        self.post_message(self.MethodChanged(self, event.value))

    @on(Input.Submitted, "#url-input")
    def _on_url_submitted(self, event: Input.Submitted) -> None:
        state = self._state
        if state is None or state.mode != MODE_HOME_URL_EDIT:
            return
        event.stop()
        self.post_message(self.UrlSaved(self, event.value))

    @on(Input.Changed, "#url-input")
    def _on_url_changed(self, event: Input.Changed) -> None:
        state = self._state
        if state is None or state.mode != MODE_HOME_URL_EDIT:
            return
        text = event.value
        cursor = event.input.cursor_position
        if cursor >= 2 and text[cursor - 2 : cursor] == "{{" and text[cursor : cursor + 2] != "}}":
            event.input.value = text[:cursor] + "}}" + text[cursor:]
            event.input.cursor_position = cursor
        self._schedule_hint_refresh()
        event.stop()

    @on(Tabs.TabActivated, "#open-request-tabs")
    def _on_open_request_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id
        if not tab_id or not tab_id.startswith("open-req-"):
            return
        event.stop()
        self.post_message(self.OpenRequestActivated(self, tab_id.removeprefix("open-req-")))

    @on(events.Click, "#url-display")
    def _on_url_display_clicked(self, event: events.Click) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None or state.mode == MODE_HOME_URL_EDIT:
            return
        app.action_copy_active_request_url()
        event.stop()

    def on_key(self, event: events.Key) -> None:
        state = self._state
        app = self._owner_app()
        if state is None or app is None or event.key != "tab":
            return

        focused = app.focused
        if not isinstance(focused, Input) or focused.id != "url-input":
            return
        if state.mode != MODE_HOME_URL_EDIT:
            return

        env_keys = sorted(state.env_pairs)
        match = placeholder_match(focused.value, focused.cursor_position, env_keys)
        if match is not None:
            anchor = self._url_env_completion_anchor
            stored = self._url_env_completion_matches
            if anchor and match.prefix in stored:
                matches = stored
                new_idx = (self._url_env_completion_index + 1) % len(matches)
            else:
                anchor = match.prefix
                matches = [key for key in env_keys if key.startswith(anchor)]
                new_idx = 0
            if matches:
                self._url_env_completion_anchor = anchor
                self._url_env_completion_matches = matches
                self._url_env_completion_index = new_idx
                suggestion = matches[new_idx]
                before = focused.value[: match.start]
                after = focused.value[match.end :]
                completed = f"{before}{{{{{suggestion}}}}}{after}"
                new_cursor = len(before) + 2 + len(suggestion)
                focused.value = completed
                focused.cursor_position = new_cursor
                self._schedule_hint_refresh()

        event.stop()
