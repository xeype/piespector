from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Select, Static, TabbedContent

from piespector.commands import filesystem_path_completions
from piespector.domain.editor import (
    BODY_KEY_VALUE_TYPES,
    BODY_TEXT_EDITOR_TYPES,
    BODY_TYPE_OPTIONS,
    HOME_EDITOR_TAB_BODY,
    RAW_SUBTYPE_OPTIONS,
)
from piespector.domain.modes import (
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
)
from piespector.domain.requests import RequestDefinition
from piespector.interactions.keys import (
    ARROW_LEFT_KEYS,
    ARROW_RIGHT_KEYS,
    DOWN_KEYS,
    FIELD_NEXT_KEYS,
    FIELD_PREVIOUS_KEYS,
    KEY_ADD,
    KEY_DELETE_ROW,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_SEND,
    KEY_SPACE,
    OPEN_KEYS,
    TAB_NEXT_KEYS,
    TAB_PREVIOUS_KEYS,
    UP_KEYS,
)
from piespector.screens.home import messages
from piespector.screens.home.request.request_body import (
    RequestBodyTable,
    refresh_request_body_table,
    render_request_body_preview,
)
from piespector.screens.home.selection import home_selection, request_panel_selected
from piespector.ui.input import PiespectorInput
from piespector.ui.selection import set_selected
from piespector.widget.select import PiespectorSelect, SelectionChanged, option_list, sync

if TYPE_CHECKING:
    from piespector.state import PiespectorState


class RequestBodyPane(Vertical):
    DEFAULT_CSS = """
    RequestBodyPane {
        height: 1fr;
        layout: vertical;
    }
    """

    def _owner_app(self):
        owner_app = getattr(self, "_piespector_app", None)
        if owner_app is not None:
            return owner_app
        try:
            return self.app
        except Exception:
            return None

    def compose(self) -> ComposeResult:
        yield PiespectorSelect(
            option_list(*BODY_TYPE_OPTIONS),
            id="body-type-select",
            allow_blank=False,
            value=BODY_TYPE_OPTIONS[0][0],
            compact=True,
        )

        raw_type_select = PiespectorSelect(
            option_list(*RAW_SUBTYPE_OPTIONS),
            id="body-raw-type-select",
            allow_blank=False,
            value=RAW_SUBTYPE_OPTIONS[1][0],
            compact=True,
        )
        raw_type_select.display = False
        yield raw_type_select

        body_table = RequestBodyTable(
            id="request-body-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        body_table.display = False
        yield body_table

        body_input = PiespectorInput(
            "",
            id="request-body-input",
            compact=True,
            select_on_focus=False,
        )
        body_input.display = False
        yield body_input

        body_preview = Static("", id="request-body-preview")
        body_preview.display = False
        yield body_preview

    def refresh_from_state(self, state: PiespectorState) -> None:
        if not self.is_mounted:
            return

        request = state.get_active_request()
        body_type_select = self._body_type_select()
        body_raw_type_select = self._body_raw_type_select()
        body_table = self._body_table()
        body_input = self._body_input()
        body_preview = self._body_preview()

        selection = home_selection(state)
        set_selected(body_type_select, selection.body_type_selected)
        set_selected(body_raw_type_select, selection.body_raw_type_selected)
        set_selected(body_preview, False)

        if request is None:
            body_preview.update(messages.HOME_NO_ACTIVE_REQUEST)
            body_type_select.display = False
            body_raw_type_select.display = False
            body_table.clear(columns=True)
            body_table.add_columns("Request")
            body_table.add_row(messages.HOME_NO_ACTIVE_REQUEST)
            body_table.cursor_type = "none"
            body_table.display = False
            self._sync_input_widget(body_input, "", display=False)
            body_preview.display = True
            return

        body_type_select.display = state.home_editor_tab == HOME_EDITOR_TAB_BODY
        body_raw_type_select.display = False
        body_table.display = False
        body_preview.display = False
        self._sync_input_widget(body_input, "", display=False)

        if state.home_editor_tab != HOME_EDITOR_TAB_BODY:
            return

        sync(
            body_type_select,
            option_list(*BODY_TYPE_OPTIONS),
            request.body_type,
            auto_open_token=(
                ("body-type", request.request_id, state.mode)
                if state.mode == MODE_HOME_BODY_TYPE_EDIT
                else None
            ),
        )

        if request.body_type == "raw":
            sync(
                body_raw_type_select,
                option_list(*RAW_SUBTYPE_OPTIONS),
                request.raw_subtype,
                display=True,
                auto_open_token=(
                    ("body-raw-type", request.request_id, state.mode)
                    if state.mode == MODE_HOME_BODY_RAW_TYPE_EDIT
                    else None
                ),
            )
            body_raw_type_select.display = True

        if request.body_type in BODY_KEY_VALUE_TYPES:
            refresh_request_body_table(body_table, request, state)
            body_table.display = True
            items = state.get_active_request_body_items()
            field_name, field_label = state.selected_body_field()
            if state.mode == MODE_HOME_BODY_EDIT:
                item_index = state.selected_body_index - 1
                if state.body_creating_new:
                    body_initial = ""
                elif 0 <= item_index < len(items):
                    item = items[item_index]
                    body_initial = item.key if field_name == "key" else item.value
                else:
                    body_initial = ""
                self._sync_input_widget(
                    body_input,
                    body_initial,
                    display=True,
                    placeholder=f"Body {field_label.lower()}",
                    focus_token=(
                        (
                            "body-field",
                            request.request_id,
                            state.body_creating_new,
                            state.selected_body_index,
                            state.selected_body_field_index,
                        )
                    ),
                )
            else:
                self._sync_input_widget(body_input, "", display=False)
                body_table_selected = (
                    request_panel_selected(state)
                    and state.mode == MODE_HOME_BODY_SELECT
                    and state.selected_body_index > 0
                )
                if body_table_selected and body_table.can_focus and not body_table.has_focus:
                    body_table.focus()
                elif not body_table_selected:
                    self._deactivate_table_widget(body_table)
            return

        preview_selected = self._body_preview_is_selected(
            request,
            state,
            panel_selected=request_panel_selected(state),
        )
        preview_width, preview_height = self._body_preview_dimensions(
            body_preview,
            request,
            body_type_select,
            body_raw_type_select,
        )
        body_preview.update(
            render_request_body_preview(
                request,
                state,
                preview_width,
                include_raw_selector=False,
                panel_height=preview_height,
                selected=preview_selected,
            )
        )
        if state.mode == MODE_HOME_BODY_EDIT and request.body_type == "binary":
            self._sync_input_widget(
                body_input,
                request.body_text or "",
                display=True,
                placeholder="File path",
                focus_token=("body-binary", request.request_id),
            )
            body_preview.display = False
        else:
            self._sync_input_widget(body_input, "", display=False)
            body_preview.display = True

    def start_current_edit(self, *, origin_mode: str = MODE_HOME_BODY_SELECT) -> bool:
        app = self._owner_app()
        if app is None:
            return False

        if app.state.selected_body_index == 0:
            app.state.enter_home_body_type_edit_mode(origin_mode=origin_mode)
            return False

        request = app.state.get_active_request()
        if request is not None and request.body_type == "raw" and app.state.selected_body_index == 1:
            app.state.enter_home_body_raw_type_edit_mode(origin_mode=origin_mode)
            return False
        if request is not None and request.body_type in BODY_TEXT_EDITOR_TYPES:
            self._open_body_text_editor(origin_mode=origin_mode)
            return True

        app.state.enter_home_body_edit_mode(origin_mode=origin_mode)
        return False

    def handle_select_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        if event.key == KEY_ESCAPE:
            app.state.leave_home_body_select_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key in UP_KEYS:
            if app.state.selected_body_index <= 0:
                app.state.enter_home_section_select_mode()
                app._refresh_screen()
                event.stop()
                return
            app.state.select_body_row(-1)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key in DOWN_KEYS:
            app.state.select_body_row(1)
            app._home_screen.refresh_request_panel()
            event.stop()
            return

        if event.key in TAB_PREVIOUS_KEYS:
            self._move_request_block(-1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in TAB_NEXT_KEYS:
            self._move_request_block(1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in FIELD_PREVIOUS_KEYS:
            request = app.state.get_active_request()
            if (
                request is not None
                and request.body_type in BODY_KEY_VALUE_TYPES
                and 0 < app.state.selected_body_index <= len(app.state.get_active_request_body_items())
            ):
                app.state.cycle_body_field(-1)
                app._home_screen.refresh_request_panel()
                event.stop()
            return

        if event.key in FIELD_NEXT_KEYS:
            request = app.state.get_active_request()
            if (
                request is not None
                and request.body_type in BODY_KEY_VALUE_TYPES
                and 0 < app.state.selected_body_index <= len(app.state.get_active_request_body_items())
            ):
                app.state.cycle_body_field(1)
                app._home_screen.refresh_request_panel()
                event.stop()
            return

        if event.key == KEY_ADD:
            request = app.state.get_active_request()
            if request is not None and request.body_type in {"form-data", "x-www-form-urlencoded"}:
                app.state.enter_home_body_edit_mode(
                    creating=True,
                    origin_mode=MODE_HOME_BODY_SELECT,
                )
                app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_SPACE:
            app.state.toggle_selected_body_field()
            app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            opened_editor = self.start_current_edit(origin_mode=MODE_HOME_BODY_SELECT)
            if not opened_editor:
                app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_DELETE_ROW:
            app.state.delete_selected_body_field()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_SEND:
            app._send_selected_request()
            event.stop()

    def handle_type_edit_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        if event.key == KEY_ESCAPE:
            app.state.leave_home_body_type_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        body_type_select = self._optional_body_type_select()
        if body_type_select is not None:
            if event.key in OPEN_KEYS:
                body_type_select.focus()
                if not body_type_select.expanded:
                    body_type_select.action_show_overlay()
                event.stop()
                return
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            app.state.cycle_body_type(-1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            request = app.state.get_active_request()
            if request is None:
                app.state.leave_home_body_type_edit_mode()
                app._refresh_screen()
                event.stop()
                return

            app.state.selected_body_index = 0
            app.state.mode = MODE_HOME_BODY_SELECT
            app.state.message = ""
            app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            app.state.cycle_body_type(1)
            app._refresh_screen()
            event.stop()

    def handle_raw_type_edit_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        if event.key == KEY_ESCAPE:
            app.state.leave_home_body_raw_type_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        raw_type_select = self._optional_body_raw_type_select()
        if raw_type_select is not None and raw_type_select.display:
            if event.key in OPEN_KEYS:
                raw_type_select.focus()
                if not raw_type_select.expanded:
                    raw_type_select.action_show_overlay()
                event.stop()
                return
            return

        if event.key in UP_KEYS | ARROW_LEFT_KEYS:
            app.state.cycle_raw_subtype(-1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in DOWN_KEYS | ARROW_RIGHT_KEYS:
            app.state.cycle_raw_subtype(1)
            app._refresh_screen()
            event.stop()
            return

        if event.key in OPEN_KEYS:
            app.state.mode = MODE_HOME_BODY_SELECT
            app.state.message = ""
            app._refresh_screen()
            event.stop()

    def handle_edit_key(self, event: events.Key) -> None:
        app = self._owner_app()
        if app is None:
            return

        body_input = self._optional_body_input()
        if body_input is not None and body_input.display:
            if event.key == KEY_ESCAPE:
                app.state.leave_home_body_edit_mode()
                app._refresh_screen()
                event.stop()
            return

        if event.key == KEY_ESCAPE:
            app.state.leave_home_body_edit_mode()
            app._refresh_screen()
            event.stop()
            return

        if event.key == KEY_ENTER:
            app.state.save_body_selection()
            app._refresh_screen()
            event.stop()

    def handle_input_key(self, event: events.Key) -> bool:
        app = self._owner_app()
        body_input = self._optional_body_input()
        if (
            app is None
            or app.state.mode != MODE_HOME_BODY_EDIT
            or body_input is None
            or not body_input.display
            or event.key != "tab"
        ):
            return False

        current = body_input.value
        anchor = app._edit_path_completion_anchor or current
        matches = filesystem_path_completions(anchor)
        if matches:
            if app._edit_path_completion_anchor != anchor:
                app._edit_path_completion_anchor = anchor
                app._edit_path_completion_index = 0
            else:
                app._edit_path_completion_index = (
                    app._edit_path_completion_index + 1
                ) % len(matches)
            completed = matches[app._edit_path_completion_index]
            body_input.value = completed
            body_input.cursor_position = len(completed)

        event.stop()
        return True

    def _move_request_block(self, step: int) -> None:
        app = self._owner_app()
        if app is None:
            return
        app.state.cycle_home_editor_tab(step)
        app.home_controller.enter_current_home_value_select_mode()

    def _open_body_text_editor(self, *, origin_mode: str) -> None:
        app = self._owner_app()
        if app is None:
            return
        app._home_screen.open_body_text_editor(origin_mode=origin_mode)

    def _body_type_select(self) -> Select:
        return self.query_one("#body-type-select", Select)

    def _body_raw_type_select(self) -> Select:
        return self.query_one("#body-raw-type-select", Select)

    def _body_table(self) -> RequestBodyTable:
        return self.query_one("#request-body-table", RequestBodyTable)

    def _body_input(self) -> Input:
        return self.query_one("#request-body-input", Input)

    def _body_preview(self) -> Static:
        return self.query_one("#request-body-preview", Static)

    def _optional_body_type_select(self) -> Select | None:
        try:
            return self._body_type_select()
        except NoMatches:
            return None

    def _optional_body_raw_type_select(self) -> Select | None:
        try:
            return self._body_raw_type_select()
        except NoMatches:
            return None

    def _optional_body_input(self) -> Input | None:
        try:
            return self._body_input()
        except NoMatches:
            return None

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

    def _deactivate_table_widget(self, table: DataTable) -> None:
        if not table.has_focus:
            return
        app = table.app
        if app is not None:
            app.set_focus(None)
        else:
            table.blur()

    def _body_preview_is_selected(
        self,
        request: RequestDefinition | None,
        state: PiespectorState,
        *,
        panel_selected: bool,
    ) -> bool:
        if request is None or not panel_selected or state.home_editor_tab != HOME_EDITOR_TAB_BODY:
            return False
        if state.mode != MODE_HOME_BODY_SELECT:
            return False
        if request.body_type == "raw":
            return state.selected_body_index == 2
        if request.body_type in BODY_KEY_VALUE_TYPES | {"none"}:
            return False
        return state.selected_body_index == 1

    def _body_preview_dimensions(
        self,
        body_preview: Static,
        request: RequestDefinition,
        body_type_select: Select,
        body_raw_type_select: Select,
    ) -> tuple[int | None, int | None]:
        parent = body_preview.parent
        app = getattr(body_preview, "app", None)
        request_tabs = None
        if app is not None and app.screen is not None:
            try:
                request_tabs = app.screen.query_one("#request-tabs", TabbedContent)
            except NoMatches:
                request_tabs = None

        layout_key = "raw" if request.body_type == "raw" else "single"
        cached_sizes = getattr(body_preview, "_piespector_preview_sizes", {})
        if not isinstance(cached_sizes, dict):
            cached_sizes = {}

        preview_width = next(
            (
                value
                for value in (
                    body_preview.region.width,
                    body_preview.size.width,
                    parent.region.width if parent is not None else 0,
                    parent.size.width if parent is not None else 0,
                    request_tabs.region.width if request_tabs is not None else 0,
                    request_tabs.size.width if request_tabs is not None else 0,
                )
                if value > 0
            ),
            None,
        )

        container_height = next(
            (
                value
                for value in (
                    parent.region.height if parent is not None else 0,
                    parent.size.height if parent is not None else 0,
                    max(request_tabs.region.height - 2, 0) if request_tabs is not None else 0,
                    max(request_tabs.size.height - 2, 0) if request_tabs is not None else 0,
                )
                if value > 0
            ),
            None,
        )
        if container_height is None:
            preview_height = next(
                (
                    value
                    for value in (
                        body_preview.region.height,
                        body_preview.size.height,
                    )
                    if value > 0
                ),
                None,
            )
            if preview_width is None or preview_height is None:
                return cached_sizes.get(layout_key, (preview_width, preview_height))
            cached_sizes[layout_key] = (preview_width, preview_height)
            body_preview._piespector_preview_sizes = cached_sizes
            return (preview_width, preview_height)

        occupied_height = 0
        if body_type_select.display:
            occupied_height += 1
        if body_raw_type_select.display:
            occupied_height += 1

        preview_height = max(container_height - occupied_height, 3)
        if preview_width is None:
            return cached_sizes.get(layout_key, (preview_width, preview_height))

        cached_sizes[layout_key] = (preview_width, preview_height)
        body_preview._piespector_preview_sizes = cached_sizes
        return (preview_width, preview_height)

    def _sync_request_table_row(self, cursor_row: int) -> bool:
        app = self._owner_app()
        if app is None or cursor_row < 0:
            return False

        request = app.state.get_active_request()
        if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
            return False

        selected_index = cursor_row + 1
        if app.state.selected_body_index == selected_index:
            return False

        app.state.selected_body_index = selected_index
        return True

    @on(SelectionChanged, "#body-type-select")
    def _on_body_type_selected(self, event: SelectionChanged) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_BODY_TYPE_EDIT:
            return
        app.state.save_home_body_type_selection(event.value)
        app.set_focus(None)
        app._refresh_screen()

    @on(SelectionChanged, "#body-raw-type-select")
    def _on_body_raw_type_selected(self, event: SelectionChanged) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_BODY_RAW_TYPE_EDIT:
            return
        app.state.save_home_body_raw_type_selection(event.value)
        app.set_focus(None)
        app._refresh_screen()

    @on(DataTable.RowHighlighted, "#request-body-table")
    def _on_body_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        app = self._owner_app()
        if (
            app is None
            or app.state.mode != MODE_HOME_BODY_SELECT
            or app.state.selected_body_index <= 0
        ):
            return
        self._sync_request_table_row(event.cursor_row)

    @on(DataTable.RowSelected, "#request-body-table")
    def _on_body_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self._owner_app()
        if app is None:
            return

        self._sync_request_table_row(event.cursor_row)

        request = app.state.get_active_request()
        if request is None or request.body_type not in BODY_KEY_VALUE_TYPES:
            return

        app.state.enter_home_body_edit_mode(origin_mode=MODE_HOME_BODY_SELECT)
        app._refresh_screen()

    @on(Input.Submitted, "#request-body-input")
    def _on_body_input_submitted(self, event: Input.Submitted) -> None:
        app = self._owner_app()
        if app is None or app.state.mode != MODE_HOME_BODY_EDIT:
            return

        app.state.save_body_selection(event.value)
        app.set_focus(None)
        app._refresh_screen()
        event.stop()
