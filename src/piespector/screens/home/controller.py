from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from textual import events

from piespector.screens.home.controllers.auth import HomeAuthController
from piespector.screens.home.controllers.base import HomeControllerBase, HomeModeHandler
from piespector.screens.home.controllers.body import HomeBodyController
from piespector.screens.home.controllers.headers import HomeHeadersController
from piespector.screens.home.controllers.navigation import HomeNavigationController
from piespector.screens.home.controllers.params import HomeParamsController
from piespector.screens.home.controllers.request import HomeRequestController
from piespector.screens.home.controllers.response import HomeResponseController

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class HomeController:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app
        self.navigation = HomeNavigationController(app)
        self.response = HomeResponseController(app)
        self.request = HomeRequestController(app)
        self.auth = HomeAuthController(app)
        self.params = HomeParamsController(app)
        self.headers = HomeHeadersController(app)
        self.body = HomeBodyController(app)
        self._dispatch = self._build_dispatch(
            (
                self.navigation,
                self.response,
                self.request,
                self.auth,
                self.params,
                self.headers,
                self.body,
            )
        )

    @property
    def state(self):
        return self.app.state

    @staticmethod
    def _build_dispatch(
        controllers: Iterable[HomeControllerBase],
    ) -> dict[str, HomeModeHandler]:
        dispatch: dict[str, HomeModeHandler] = {}
        for controller in controllers:
            for mode, handler in controller.mode_handlers().items():
                if mode in dispatch:
                    raise ValueError(
                        f"Duplicate home mode handler registration for {mode}: "
                        f"{dispatch[mode].__qualname__} and {handler.__qualname__}"
                    )
                dispatch[mode] = handler
        return dispatch

    def handle_home_view_key(self, event: events.Key) -> bool:
        return self.navigation.handle_home_view_key(event)

    def handle_request_response_shortcuts(self, event: events.Key) -> bool:
        return self.response.handle_request_response_shortcuts(event)

    def enter_current_home_value_select_mode(self) -> None:
        self.navigation.enter_current_home_value_select_mode()

    def dispatch_key(self, mode: str, event: events.Key) -> None:
        handler = self._dispatch.get(mode)
        if handler is not None:
            handler(event)
