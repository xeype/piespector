from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from piespector.commands import help_commands
from piespector.domain.editor import TAB_HELP, TAB_LABELS
from piespector.domain.modes import MODE_NORMAL
from piespector.state import PiespectorState
from piespector.ui.help_content import (
    HELP_IMPORT_EXPORT_LINES,
    HELP_INTRO_CONTEXT,
    HELP_INTRO_ESCAPE,
    HELP_INTRO_ESCAPE_SUFFIX,
    HELP_INTRO_OPENED_FROM,
    HELP_SECTION_COMMANDS,
    HELP_SECTION_IMPORTS,
    HELP_SECTION_KEYS,
    help_command_context_mode,
    help_key_lines,
)


def render_help_viewport(state: PiespectorState) -> RenderableType:
    source_tab = state.help_source_tab
    source_mode = state.help_source_mode
    context_label = TAB_LABELS.get(source_tab, TAB_LABELS[TAB_HELP])

    intro = Text()
    intro.append(f"{HELP_INTRO_CONTEXT} ")
    intro.append(context_label)
    if source_mode != MODE_NORMAL:
        intro.append(f"  {HELP_INTRO_OPENED_FROM} ")
        intro.append(source_mode.replace("_", " ").title())
    intro.append("  ")
    intro.append(HELP_INTRO_ESCAPE)
    intro.append(f" {HELP_INTRO_ESCAPE_SUFFIX}")

    commands = Text()
    commands.append(f"{HELP_SECTION_COMMANDS}\n")
    command_mode = help_command_context_mode(source_tab, source_mode)
    for label in help_commands(state, source_tab, command_mode):
        commands.append(f"  {label}\n")

    navigation = Text()
    navigation.append(f"{HELP_SECTION_KEYS}\n")
    for line in help_key_lines(source_tab, source_mode):
        navigation.append(f"  {line}\n")

    imports = Text()
    imports.append(f"{HELP_SECTION_IMPORTS}\n")
    for line in HELP_IMPORT_EXPORT_LINES:
        imports.append(f"  {line}\n")

    return Group(intro, Text(""), commands, Text(""), navigation, Text(""), imports)
