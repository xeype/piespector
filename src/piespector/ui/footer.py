from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.widgets import Footer
from textual.widgets._footer import FooterKey, FooterLabel

from piespector.ui.status_content import StatusBarContent


def _default_status_content() -> StatusBarContent:
    return StatusBarContent(
        mode_label="",
        context_label="",
        hints=(),
        env_label=None,
    )


def _hint_click_key(key_display: str) -> str:
    if "/" in key_display:
        key_display = key_display.split("/", 1)[0]
    if key_display == "esc":
        return "escape"
    return key_display


class PiespectorFooter(Footer):
    def __init__(
        self,
        *children,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            *children,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            show_command_palette=False,
            compact=True,
        )
        self._content = _default_status_content()

    def set_status_content(self, content: StatusBarContent) -> None:
        if content == self._content:
            return
        self._content = content
        if self.is_mounted:
            self.call_after_refresh(self.recompose)

    def compose(self) -> ComposeResult:
        yield FooterLabel(
            self._content.mode_label,
            id="footer-mode",
            classes="piespector-footer__mode",
        )
        yield FooterLabel(
            self._content.context_label,
            id="footer-context",
            classes="piespector-footer__context",
        )
        for index, (key_display, description) in enumerate(self._content.hints):
            hint = FooterKey(
                _hint_click_key(key_display),
                key_display,
                description,
                f"piespector_footer_hint_{index}",
                classes="piespector-footer__hint",
            )
            hint.compact = self.compact
            yield hint
        if self._content.env_label is not None:
            with HorizontalGroup(id="footer-env", classes="piespector-footer__env"):
                yield FooterLabel(
                    "env",
                    id="footer-env-key",
                    classes="piespector-footer__env-key",
                )
                yield FooterLabel(
                    self._content.env_label,
                    id="footer-env-value",
                    classes="piespector-footer__env-value",
                )
