from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ScreenStackError
from textual.widgets import Input, Select, Tree

from piespector.domain.modes import MODE_HOME_SECTION_SELECT

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class HomeControllerBase:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def move_request_block(self, step: int) -> None:
        self.state.cycle_home_editor_tab(step)
        self.app.home_controller.enter_current_home_value_select_mode()

    def enter_response_block(self, tab_id: str) -> None:
        self.state.selected_home_response_tab = tab_id
        self.state.enter_home_response_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)

    def sidebar_tree(self) -> Tree | None:
        try:
            return self.app._query_current("#sidebar-tree", Tree)
        except ScreenStackError:
            return None

    def live_select(self, selector: str) -> Select | None:
        try:
            return self.app._query_current(selector, Select)
        except Exception:
            return None

    def live_input(self, selector: str) -> Input | None:
        try:
            return self.app._query_current(selector, Input)
        except Exception:
            return None
