from __future__ import annotations

from typing import TYPE_CHECKING

from textual.command import (
    CommandInput,
    CommandPalette,
    DiscoveryHit,
    Hit,
    Provider,
)
from textual.events import Mount

from piespector.commands import command_completion_matches, command_palette_commands
from piespector.search import search_targets

if TYPE_CHECKING:
    from piespector.app import PiespectorApp
    from piespector.commands import PaletteCommand
    from piespector.search import SearchTarget


class PiespectorPalette(CommandPalette):
    def __init__(
        self,
        *args,
        initial_value: str = "",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._initial_value = initial_value

    def _on_mount(self, event: Mount) -> None:
        super()._on_mount(event)
        if not self._initial_value:
            return
        command_input = self.query_one(CommandInput)
        command_input.value = self._initial_value
        command_input.action_end()


class PiespectorProvider(Provider):
    @property
    def piespector_app(self) -> PiespectorApp:
        return self.app  # type: ignore[return-value]


class PiespectorCommandProvider(PiespectorProvider):
    def _system_command_names(self) -> set[str]:
        return {
            name.strip().casefold()
            for name, *_rest in self.piespector_app.get_system_commands(self.screen)
        }

    def _entry_callback(self, entry: PaletteCommand):
        if entry.runnable:
            return lambda command=entry.text.strip(): self.piespector_app.interaction_controller.run_command(
                command
            )
        return lambda command=entry.text: self.piespector_app.open_command_palette(command)

    async def discover(self):
        for entry in command_palette_commands(self.piespector_app.state):
            yield DiscoveryHit(
                entry.label,
                self._entry_callback(entry),
                text=entry.text,
                help=entry.help,
            )

    async def search(self, query: str):
        entries = command_palette_commands(self.piespector_app.state)
        entry_by_text = {entry.text.strip(): entry for entry in entries}

        completions = command_completion_matches(self.piespector_app.state, query)
        for index, completion in enumerate(completions):
            normalized = completion.strip()
            entry = entry_by_text.get(normalized)
            if entry is not None:
                yield Hit(
                    max(0.0, 1.0 - (index * 0.01)),
                    entry.label,
                    self._entry_callback(entry),
                    text=entry.text,
                    help=entry.help,
                )
                continue
            yield Hit(
                max(0.0, 1.0 - (index * 0.01)),
                completion,
                lambda command=completion: self.piespector_app.interaction_controller.run_command(
                    command
                ),
                text=completion,
                help="Run this command.",
            )

        if completions:
            return

        non_runnable_commands = {entry.text.strip() for entry in entries if not entry.runnable}
        normalized_query = query.strip()
        if (
            not normalized_query
            or normalized_query in non_runnable_commands
            or normalized_query.casefold() in self._system_command_names()
        ):
            return

        yield Hit(
            0.05,
            f"Run {normalized_query}",
            lambda command=normalized_query: self.piespector_app.interaction_controller.run_command(
                command
            ),
            text=normalized_query,
            help="Run the command exactly as typed.",
        )


class PiespectorSearchProvider(PiespectorProvider):
    def _target_callback(self, target: SearchTarget):
        return lambda target=target: self.piespector_app.interaction_controller.open_search_target(
            target
        )

    def _target_help(self, target: SearchTarget) -> str:
        return f"Open this {target.kind}."

    async def discover(self):
        for target in search_targets(self.piespector_app.state):
            yield DiscoveryHit(
                target.display,
                self._target_callback(target),
                text=target.display,
                help=self._target_help(target),
            )

    async def search(self, query: str):
        matcher = self.matcher(query)
        hits: list[tuple[float, SearchTarget]] = []
        for target in search_targets(self.piespector_app.state):
            score = max(matcher.match(term) for term in target.query_terms)
            if score <= 0:
                continue
            hits.append((score, target))

        for score, target in sorted(
            hits,
            key=lambda hit: (-hit[0], hit[1].display.casefold()),
        ):
            yield Hit(
                score,
                matcher.highlight(target.display),
                self._target_callback(target),
                text=target.display,
                help=self._target_help(target),
            )


class PiespectorThemeProvider(PiespectorProvider):
    @property
    def commands(self) -> list[tuple[str, object]]:
        return [
            (
                theme.name,
                lambda theme_name=theme.name: self.piespector_app.apply_theme(theme_name),
            )
            for theme in sorted(
                self.piespector_app.available_themes.values(),
                key=lambda theme: theme.name,
            )
            if theme.name != "textual-ansi"
        ]

    async def discover(self):
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str):
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)
