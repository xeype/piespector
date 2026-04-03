from __future__ import annotations

from collections import defaultdict
from itertools import groupby
from operator import itemgetter

from rich import box
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import HelpPanel, KeyPanel, Markdown
from textual.widgets._key_panel import BindingsTable

HIDDEN_BINDING_KEYS = frozenset({"ctrl+c", "super+c"})


def _hide_binding(binding: Binding) -> bool:
    return any(key.strip() in HIDDEN_BINDING_KEYS for key in binding.key.split(","))


class PiespectorBindingsTable(BindingsTable):
    def render_bindings_table(self) -> Table:
        bindings = [
            binding_info
            for binding_info in self.screen.active_bindings.values()
            if not _hide_binding(binding_info[1])
        ]

        key_style = self.get_component_rich_style("bindings-table--key")
        divider_transparent = (
            self.get_component_styles("bindings-table--divider").color.a == 0
        )
        table = Table(
            padding=(0, 0),
            show_header=False,
            box=box.SIMPLE if divider_transparent else box.HORIZONTALS,
            border_style=self.get_component_rich_style("bindings-table--divider"),
        )
        table.add_column("", justify="right")

        header_style = self.get_component_rich_style("bindings-table--header")
        previous_namespace: object = None
        for namespace, namespace_bindings in groupby(bindings, key=itemgetter(0)):
            table_bindings = list(namespace_bindings)
            if not table_bindings:
                continue

            if namespace.BINDING_GROUP_TITLE:
                title = Text(namespace.BINDING_GROUP_TITLE, end="")
                title.stylize(header_style)
                table.add_row("", title)

            action_to_bindings: defaultdict[str, list[tuple[Binding, bool, str]]]
            action_to_bindings = defaultdict(list)
            for _, binding, enabled, tooltip in table_bindings:
                if not binding.system:
                    action_to_bindings[binding.action].append(
                        (binding, enabled, tooltip)
                    )

            description_style = self.get_component_rich_style(
                "bindings-table--description"
            )

            def render_description(binding: Binding) -> Text:
                text = Text.from_markup(
                    binding.description, end="", style=description_style
                )
                if binding.tooltip:
                    if binding.description:
                        text.append(" ")
                    text.append(binding.tooltip, "dim")
                return text

            get_key_display = self.app.get_key_display
            for multi_bindings in action_to_bindings.values():
                binding, enabled, tooltip = multi_bindings[0]
                keys_display = " ".join(
                    dict.fromkeys(
                        get_key_display(binding) for binding, _, _ in multi_bindings
                    )
                )
                table.add_row(
                    Text(keys_display, style=key_style),
                    render_description(binding),
                )
            if namespace != previous_namespace:
                table.add_section()

            previous_namespace = namespace

        return table


class PiespectorKeyPanel(KeyPanel):
    def compose(self) -> ComposeResult:
        yield PiespectorBindingsTable(shrink=True, expand=False)


class PiespectorHelpPanel(HelpPanel):
    def compose(self) -> ComposeResult:
        yield Markdown(id="widget-help")
        yield PiespectorKeyPanel(id="keys-help")
