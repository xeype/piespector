from __future__ import annotations


def home_top_bar_height() -> int:
    return 5


def home_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 40
    return max(min(viewport_width // 3, 44), 32)


def home_request_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 3, 6)


def home_request_panel_body_height(viewport_height: int | None) -> int:
    request_rows, _ = _home_workspace_split(viewport_height)
    return request_rows


def home_response_panel_body_height(viewport_height: int | None) -> int:
    _, response_rows = _home_workspace_split(viewport_height)
    return response_rows


def home_response_visible_rows(viewport_height: int | None) -> int:
    return max(home_response_panel_body_height(viewport_height) - 2, 1)


def response_scroll_step(viewport_height: int | None) -> int:
    return max(home_response_visible_rows(viewport_height) // 2, 1)


def _home_workspace_split(viewport_height: int | None) -> tuple[int, int]:
    if viewport_height is None:
        return (9, 8)

    total_body_rows = max(viewport_height - home_top_bar_height(), 4)
    min_request_rows = 5 if total_body_rows >= 12 else 3
    min_response_rows = 5 if total_body_rows >= 12 else 3

    request_rows = max((total_body_rows * 5) // 9, min_request_rows)
    max_request_rows = max(total_body_rows - min_response_rows, min_request_rows)
    request_rows = min(request_rows, max_request_rows)
    response_rows = max(total_body_rows - request_rows, min_response_rows)
    return (request_rows, response_rows)
