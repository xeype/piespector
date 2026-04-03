from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from textual import events

from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
)
from piespector.screens.home.controllers.auth import HomeAuthController
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
        self._dispatch: dict[str, Callable[[events.Key], None]] = {
            MODE_HOME_SECTION_SELECT: self.navigation.handle_home_section_select_key,
            MODE_HOME_REQUEST_SELECT: self.request.handle_home_request_select_key,
            MODE_HOME_REQUEST_EDIT: self.request.handle_home_request_edit_key,
            MODE_HOME_REQUEST_METHOD_SELECT: self.request.handle_home_request_method_select_key,
            MODE_HOME_REQUEST_METHOD_EDIT: self.request.handle_home_request_method_edit_key,
            MODE_HOME_URL_EDIT: self.request.handle_home_url_edit_key,
            MODE_HOME_AUTH_SELECT: self.auth.handle_home_auth_select_key,
            MODE_HOME_AUTH_EDIT: self.auth.handle_home_auth_edit_key,
            MODE_HOME_AUTH_TYPE_EDIT: self.auth.handle_home_auth_type_edit_key,
            MODE_HOME_AUTH_LOCATION_EDIT: self.auth.handle_home_auth_location_edit_key,
            MODE_HOME_PARAMS_SELECT: self.params.handle_home_params_select_key,
            MODE_HOME_PARAMS_EDIT: self.params.handle_home_params_edit_key,
            MODE_HOME_HEADERS_SELECT: self.headers.handle_home_headers_select_key,
            MODE_HOME_HEADERS_EDIT: self.headers.handle_home_headers_edit_key,
            MODE_HOME_BODY_SELECT: self.body.handle_home_body_select_key,
            MODE_HOME_BODY_TYPE_EDIT: self.body.handle_home_body_type_edit_key,
            MODE_HOME_BODY_RAW_TYPE_EDIT: self.body.handle_home_body_raw_type_edit_key,
            MODE_HOME_BODY_EDIT: self.body.handle_home_body_edit_key,
            MODE_HOME_RESPONSE_SELECT: self.response.handle_home_response_select_key,
        }

    @property
    def state(self):
        return self.app.state

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
