from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from textual import events
from textual.widgets import Input, Select

from piespector.widget.tree import PiespectorTree

from piespector.domain.modes import MODE_HOME_SECTION_SELECT

if TYPE_CHECKING:
    from piespector.app import PiespectorApp

HomeModeHandler = Callable[[events.Key], None]


class HomeControllerBase:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def mode_handlers(self) -> dict[str, HomeModeHandler]:
        return {}

    def move_request_block(self, step: int) -> None:
        self.state.cycle_home_editor_tab(step)
        self.app.home_controller.enter_current_home_value_select_mode()

    def enter_response_block(self, tab_id: str) -> None:
        self.state.selected_home_response_tab = tab_id
        self.state.enter_home_response_select_mode(origin_mode=MODE_HOME_SECTION_SELECT)

    def home_screen(self):
        return getattr(self.app, "_home_screen", None)

    def sidebar_tree(self) -> PiespectorTree | None:
        screen = self.home_screen()
        if screen is None:
            return None
        return screen.sidebar_tree()

    def live_select(self, selector: str) -> Select | None:
        screen = self.home_screen()
        if screen is None:
            return None
        return screen.live_select(selector)

    def live_input(self, selector: str) -> Input | None:
        screen = self.home_screen()
        if screen is None:
            return None
        return screen.live_input(selector)
