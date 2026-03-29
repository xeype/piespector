from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class HomeControllerBase:
    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

