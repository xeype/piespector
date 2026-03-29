from __future__ import annotations

from rich.style import Style
from rich.text import Text

from piespector.domain.requests import RequestDefinition
from piespector.http_client import preview_request_url
from piespector.screens.home import styles
from piespector.state import PiespectorState


def render_request_url_preview(
    request: RequestDefinition,
    state: PiespectorState,
) -> str:
    return preview_request_url(request, state.env_pairs)


def render_request_url_bar(
    request: RequestDefinition,
    state: PiespectorState,
) -> Text:
    method_line = Text()
    method_line.append(
        f" {request.method} ",
        style=styles.pill_style(styles.method_color(request.method)),
    )
    method_line.append("  ")
    request_url_preview = render_request_url_preview(request, state)
    method_line.append(
        request_url_preview or "No URL set",
        style=(
            Style(color=styles.TEXT_URL, meta={"@click": "app.copy_active_request_url"})
            if request_url_preview
            else styles.TEXT_MUTED
        ),
    )
    return method_line

