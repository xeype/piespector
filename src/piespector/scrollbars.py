from __future__ import annotations

from math import ceil

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.scrollbar import ScrollBarRender


class ThinScrollBarRender(ScrollBarRender):
    """Render scroll thumbs as thin lines instead of solid blocks."""

    VERTICAL_THUMB = "┃"
    HORIZONTAL_THUMB = "━"

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color = Color.parse("#555555"),
        bar_color: Color = Color.parse("bright_magenta"),
    ) -> Segments:
        width_thickness = thickness if vertical else 1
        blank = cls.BLANK_GLYPH * width_thickness
        thumb = (cls.VERTICAL_THUMB if vertical else cls.HORIZONTAL_THUMB) * width_thickness

        _Segment = Segment
        _Style = Style

        foreground_meta = {"@mouse.down": "grab"}
        upper = {"@mouse.down": "scroll_up"}
        lower = {"@mouse.down": "scroll_down"}

        if window_size and size and virtual_size and size != virtual_size:
            bar_ratio = virtual_size / size
            thumb_size = max(1, window_size / bar_ratio)
            position_ratio = (
                position / (virtual_size - window_size)
                if virtual_size > window_size
                else 0
            )
            thumb_position = (size - thumb_size) * position_ratio

            start_index = max(0, int(thumb_position))
            end_index = min(int(size), max(start_index + 1, ceil(thumb_position + thumb_size)))

            upper_back_segment = Segment(blank, _Style(bgcolor=back_color, meta=upper))
            lower_back_segment = Segment(blank, _Style(bgcolor=back_color, meta=lower))
            thumb_segment = Segment(
                thumb,
                _Style(color=bar_color, bgcolor=back_color, meta=foreground_meta),
            )

            segments = [upper_back_segment] * int(size)
            segments[end_index:] = [lower_back_segment] * (size - end_index)
            segments[start_index:end_index] = [thumb_segment] * (end_index - start_index)
        else:
            segments = [_Segment(blank, style=_Style(bgcolor=back_color))] * int(size)

        if vertical:
            return Segments(segments, new_lines=True)
        return Segments((segments + [_Segment.line()]) * thickness, new_lines=False)
