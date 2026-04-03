from __future__ import annotations

from dataclasses import dataclass

from textual.geometry import Offset
from textual.widget import Widget


@dataclass(frozen=True)
class JumpTarget:
    key: str
    target_id: str
    widget: Widget


@dataclass(frozen=True)
class JumpOverlayItem:
    key: str
    target_id: str
    offset: Offset


class Jumper:
    def __init__(self, targets: tuple[JumpTarget, ...]) -> None:
        self._targets = targets

    def overlay_items(self) -> tuple[JumpOverlayItem, ...]:
        items: list[JumpOverlayItem] = []
        for target in self._targets:
            region = target.widget.region
            if (
                not target.widget.display
                or region.width <= 0
                or region.height <= 0
            ):
                continue
            items.append(
                JumpOverlayItem(
                    key=target.key,
                    target_id=target.target_id,
                    offset=Offset(region.x, max(region.y - 1, 0)),
                )
            )
        return tuple(items)
