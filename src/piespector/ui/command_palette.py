from __future__ import annotations

from asyncio import sleep as async_sleep
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.command import (
    Command,
    CommandInput,
    CommandList,
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
    BINDINGS = [
        Binding("tab", "tab_complete", "Autocomplete", show=False),
    ]

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

    def action_tab_complete(self) -> None:
        command_input = self.query_one(CommandInput)
        command_list = self.query_one(CommandList)

        index = command_list.highlighted
        if index is None and command_list.option_count > 0:
            index = 0

        if index is not None:
            option = command_list.get_option_at_index(index)
            if isinstance(option, Command):
                text = str(option.hit.text)
                if text != command_input.value:
                    command_input.value = text
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
        await async_sleep(0)
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
        await async_sleep(0)
        matcher = self.matcher(query)
        for index, target in enumerate(search_targets(self.piespector_app.state)):
            score = max(matcher.match(term) for term in target.query_terms)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(target.display),
                    self._target_callback(target),
                    text=target.display,
                    help=self._target_help(target),
                )
            if index % 10 == 9:
                await async_sleep(0)


class PiespectorHistorySearchProvider(PiespectorProvider):
    def _entry_display(self, entry) -> str:
        from piespector.search import history_search_display
        return history_search_display(entry)

    def _entry_callback(self, entry):
        return lambda e=entry: self.piespector_app.navigate_to_history_entry(e.history_id)

    async def discover(self):
        for entry in self.piespector_app.state.history_entries:
            display = self._entry_display(entry)
            yield DiscoveryHit(display, self._entry_callback(entry), text=display, help="Navigate to this history entry.")

    async def search(self, query: str):
        await async_sleep(0)
        from piespector.search import history_search_display
        matcher = self.matcher(query)
        state = self.piespector_app.state
        for index, entry in enumerate(state.history_entries):
            display = history_search_display(entry)
            score = matcher.match(display)
            if score > 0:
                yield Hit(score, matcher.highlight(display), self._entry_callback(entry), text=display, help="Navigate to this history entry.")
            if index % 25 == 24:
                await async_sleep(0)


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
