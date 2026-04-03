from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text

from piespector.screens.env import render as env_render
from piespector.screens.history import render as history_render
from piespector.screens.home import render as home_render
from piespector.commands import help_commands
from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_EDIT,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TEXTAREA,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_HOME_HEADERS_EDIT,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)
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
from piespector.ui import rendering_helpers

detect_text_syntax_language = rendering_helpers.detect_text_syntax_language
format_response_body = rendering_helpers.format_response_body
request_body_syntax_language = rendering_helpers.request_body_syntax_language
text_area_syntax_language = rendering_helpers.text_area_syntax_language


def render_viewport(
    state: PiespectorState,
    viewport_height: int | None = None,
    viewport_width: int | None = None,
) -> RenderableType:
    """Legacy function kept for test compatibility."""
    if state.current_tab == TAB_HOME:
        return home_render.render_home_viewport(state, viewport_height, viewport_width)

    if state.current_tab == TAB_ENV:
        return env_render.render_env_viewport(state, viewport_height)

    if state.current_tab == TAB_HISTORY:
        return history_render.render_history_viewport(state, viewport_height, viewport_width)

    if state.current_tab == TAB_HELP:
        return render_help_content(state)

    return Text()


def render_help_content(state: PiespectorState) -> RenderableType:
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
