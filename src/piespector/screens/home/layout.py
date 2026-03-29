from __future__ import annotations


def home_sidebar_width(viewport_width: int | None) -> int:
    if viewport_width is None:
        return 34
    return max(min(viewport_width // 4, 36), 28)


def home_request_list_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 14
    return max(viewport_height - 3, 6)


def home_response_visible_rows(viewport_height: int | None) -> int:
    if viewport_height is None:
        return 10
    return max(viewport_height - 22, 6)


def response_scroll_step(viewport_height: int | None) -> int:
    return max(home_response_visible_rows(viewport_height) // 2, 1)

