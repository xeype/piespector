from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING

from piespector.formatting import format_bytes
from piespector.history import build_history_entry
from piespector.http_client import perform_request
from piespector.search import request_path
from piespector.storage import ensure_parent_dir

if TYPE_CHECKING:
    from piespector.app import PiespectorApp


class RequestExecutor:
    """Coordinates sending a request and applying the result."""

    def __init__(self, app: PiespectorApp) -> None:
        self.app = app

    @property
    def state(self):
        return self.app.state

    def send_selected_request(self) -> None:
        if self.state.get_active_request() is None and self.state.get_selected_request() is not None:
            self.state.open_selected_request()
        request = self.state.get_active_request()
        if request is None:
            self.state.message = "No request selected."
            self.app._refresh_screen()
            return
        self.state.pending_request_id = request.request_id
        self.state.pending_request_spinner_tick = 0
        self.state.response_scroll_offset = 0
        request_definition = deepcopy(request)
        request_env_pairs = dict(self.state.env_pairs)
        source_request_path = request_path(self.state, request)
        self._append_request_log(
            f"START {request.method} {request.url or '<empty-url>'} name={request.name!r}"
        )
        self.app._refresh_screen()
        self.app._perform_request_in_worker(
            request.request_id,
            request_definition,
            request_env_pairs,
            source_request_path,
        )

    def perform_request_in_worker(
        self,
        request_id: str,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
    ) -> None:
        response = perform_request(
            definition,
            env_pairs,
            timeout_seconds=self.app.REQUEST_TIMEOUT_SECONDS,
        )
        self.app.call_from_thread(
            self.apply_request_result,
            request_id,
            definition,
            env_pairs,
            source_request_path,
            response,
        )

    def apply_request_result(
        self,
        request_id: str,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
        response,
    ) -> None:
        request = self.state.get_request_by_id(request_id)
        self.state.pending_request_id = None
        self.state.pending_request_spinner_tick = 0
        self._record_history_entry(definition, env_pairs, source_request_path, response)
        if request is None:
            self._append_request_log(
                f"END missing-request id={request_id} error={response.error or '<none>'}"
            )
            self.app._refresh_screen()
            return

        request.last_response = response
        self.state.response_scroll_offset = 0
        if response.error and response.status_code is None:
            self.state.message = f"Request failed: {response.error}"
            self._append_request_log(
                f"END {request.method} {request.url or '<empty-url>'} failed error={response.error!r}"
            )
        else:
            status = response.status_code or "-"
            self.state.message = ""
            self._append_request_log(
                f"END {request.method} {request.url or '<empty-url>'} status={status} elapsed_ms={response.elapsed_ms or 0:.1f} size={format_bytes(response.body_length)}"
            )
        self.app._refresh_screen()

    def _record_history_entry(
        self,
        definition,
        env_pairs: dict[str, str],
        source_request_path: str,
        response,
    ) -> None:
        entry = build_history_entry(
            definition,
            env_pairs,
            response,
            source_request_path,
        )
        self.state.prepend_history_entry(entry)

    def _append_request_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ensure_parent_dir(self.app._log_file_path)
        with self.app._log_file_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
