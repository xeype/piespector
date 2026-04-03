from __future__ import annotations

from rich.text import Text

JUMP_KEY_STYLE = "reverse"


def render_jump_key_capsule(key: str) -> Text:
    capsule = Text()
    capsule.append(f" {key} ", style=JUMP_KEY_STYLE)
    return capsule


def render_jump_key_row(keys: tuple[str, ...], *, spacing: str = " ") -> Text:
    line = Text()
    for index, key in enumerate(keys):
        if index:
            line.append(spacing)
        line.append_text(render_jump_key_capsule(key))
    return line


def render_positioned_jump_key_row(
    width: int,
    positions: tuple[tuple[int, str], ...],
) -> Text:
    width = max(width, 1)
    cells = [" "] * width
    stylized_ranges: list[tuple[int, int]] = []

    for start, key in positions:
        capsule = f" {key} "
        if len(capsule) >= width:
            start = 0
        else:
            start = max(0, min(start, width - len(capsule)))
        for index, char in enumerate(capsule):
            cells[start + index] = char
        stylized_ranges.append((start, start + len(capsule)))

    line = Text("".join(cells))
    for start, end in stylized_ranges:
        line.stylize(JUMP_KEY_STYLE, start, end)
    return line


def render_jump_border_title(
    width: int,
    label: str,
    positions: tuple[tuple[int, str], ...],
) -> Text:
    width = max(width, max(len(label), 1))
    title = render_positioned_jump_key_row(width, positions)
    label_start = max(width - len(label), 0)
    cells = list(title.plain)
    for index, char in enumerate(label):
        if label_start + index < len(cells):
            cells[label_start + index] = char
    title = Text("".join(cells))
    for span in render_positioned_jump_key_row(width, positions).spans:
        title.spans.append(span)
    return title


def render_panel_title(panel_label: str, *, selected: bool) -> Text:
    del selected
    return Text(panel_label)


def render_jump_target_row(targets: tuple[tuple[str, str], ...]) -> Text:
    line = Text()
    for index, (key, label) in enumerate(targets):
        if index:
            line.append("   ")
        line.append_text(render_jump_key_capsule(key))
        line.append(f" {label}")
    return line


def render_top_bar_jump_hint_line(
    width: int,
    positions: tuple[tuple[int, str], ...],
) -> Text:
    return render_positioned_jump_key_row(width, positions)


def render_jump_panel_title(
    tabs: tuple[tuple[str, str], ...],
    tab_to_key: dict[str, str],
    panel_label: str,
    viewport_width: int | None,
    *,
    panel_label_style: str | None = None,
) -> Text:
    del viewport_width
    del panel_label_style
    title = Text(panel_label)
    targets = tuple(
        (jump_key, label)
        for tab_id, label in tabs
        if (jump_key := tab_to_key.get(tab_id))
    )
    if not targets:
        return title
    title.append("   ")
    title.append_text(render_jump_target_row(targets))
    return title


def render_jump_hint_line(
    tabs: tuple[tuple[str, str], ...],
    tab_to_key: dict[str, str],
) -> Text:
    return render_jump_target_row(
        tuple(
            (jump_key, label)
            for tab_id, label in tabs
            if (jump_key := tab_to_key.get(tab_id))
        )
    )
