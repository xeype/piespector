from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from piespector.screens.env import render as env_render
from piespector.screens.history import render as history_render
from piespector.screens.home import render as home_render
from piespector.commands import (
    command_completion_matches,
    filesystem_path_completions,
    help_commands,
)
from piespector.domain.editor import TAB_ENV, TAB_HELP, TAB_HISTORY, TAB_HOME, TAB_LABELS
from piespector.domain.modes import (
    MODE_COMMAND,
    MODE_CONFIRM,
    MODE_ENV_EDIT,
    MODE_ENV_SELECT,
    MODE_HISTORY_RESPONSE_SELECT,
    MODE_HISTORY_RESPONSE_TEXTAREA,
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
    MODE_HOME_RESPONSE_TEXTAREA,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
    MODE_SEARCH,
    display_mode,
)
from piespector.formatting import format_bytes
from piespector.search import search_completion, search_matches
from piespector.search import (
    history_search_completion,
    history_search_display,
    history_search_matches,
)
from piespector.state import PiespectorState
from piespector.placeholders import placeholder_match
from piespector.ui.command_line_content import command_line_content
from piespector.ui.help_content import (
    HELP_IMPORT_EXPORT_LINES,
    HELP_INTRO_CONTEXT,
    HELP_INTRO_ESCAPE,
    HELP_INTRO_ESCAPE_SUFFIX,
    HELP_INTRO_OPENED_FROM,
    HELP_SECTION_COMMANDS,
    HELP_SECTION_IMPORTS,
    HELP_SECTION_KEYS,
    HELP_SUBTITLE_SUFFIX,
    HELP_TITLE,
    help_command_context_mode,
    help_key_lines,
)
from piespector.ui import rendering_helpers
from piespector.ui import rich_styles as ui_styles
from piespector.ui.status_content import STATUS_ENV_BADGE_LABEL, mode_and_context
from piespector.ui.status_hints import status_hint_items

detect_text_syntax_language = rendering_helpers.detect_text_syntax_language
format_response_body = rendering_helpers.format_response_body
request_body_syntax_language = rendering_helpers.request_body_syntax_language
text_area_syntax_language = rendering_helpers.text_area_syntax_language


def render_viewport(
    state: PiespectorState,
    viewport_height: int | None = None,
    viewport_width: int | None = None,
) -> RenderableType:
    if state.current_tab == TAB_HOME:
        return home_render.render_home_viewport(state, viewport_height, viewport_width)

    if state.current_tab == TAB_ENV:
        return env_render.render_env_viewport(state, viewport_height)

    if state.current_tab == TAB_HISTORY:
        return history_render.render_history_viewport(state, viewport_height, viewport_width)

    if state.current_tab == TAB_HELP:
        return _render_help_viewport(state)

    return Text()


def _render_help_viewport(state: PiespectorState) -> RenderableType:
    source_tab = state.help_source_tab
    source_mode = state.help_source_mode
    context_label = TAB_LABELS.get(source_tab, TAB_LABELS[TAB_HELP])

    intro = Text()
    intro.append(f"{HELP_INTRO_CONTEXT} ", style=ui_styles.secondary_style(bold=True))
    intro.append(context_label, style=ui_styles.TEXT_SUCCESS)
    if source_mode != MODE_NORMAL:
        intro.append(f"  {HELP_INTRO_OPENED_FROM} ", style=ui_styles.TEXT_MUTED)
        intro.append(source_mode.replace("_", " ").title(), style=ui_styles.TEXT_PRIMARY)
    intro.append("  ", style="")
    intro.append(HELP_INTRO_ESCAPE, style=ui_styles.pill_style(ui_styles.TEXT_SUCCESS))
    intro.append(f" {HELP_INTRO_ESCAPE_SUFFIX}", style=ui_styles.TEXT_MUTED)

    commands = Text()
    commands.append(f"{HELP_SECTION_COMMANDS}\n", style=ui_styles.primary_style(bold=True))
    command_mode = help_command_context_mode(source_tab, source_mode)
    for label in help_commands(state, source_tab, command_mode):
        commands.append(f"  {label}\n", style=ui_styles.TEXT_PRIMARY)

    navigation = Text()
    navigation.append(f"{HELP_SECTION_KEYS}\n", style=ui_styles.primary_style(bold=True))
    for line in help_key_lines(source_tab, source_mode):
        navigation.append(f"  {line}\n", style=ui_styles.TEXT_PRIMARY)

    imports = Text()
    imports.append(f"{HELP_SECTION_IMPORTS}\n", style=ui_styles.primary_style(bold=True))
    for line in HELP_IMPORT_EXPORT_LINES:
        imports.append(f"  {line}\n", style=ui_styles.TEXT_PRIMARY)

    return Panel(
        Group(intro, Text(""), commands, Text(""), navigation, Text(""), imports),
        title=HELP_TITLE,
        subtitle=f"{context_label} {HELP_SUBTITLE_SUFFIX}",
        subtitle_align="left",
        border_style=ui_styles.BORDER,
        box=box.ROUNDED,
        padding=(1, 2),
    )


def render_status_line(state: PiespectorState) -> Text:
    text = Text()
    mode_label, context_label = mode_and_context(state)
    text.append(f" {display_mode(mode_label)} ", style=ui_styles.pill_style(ui_styles.TEXT_URL))
    text.append(" | ", style=ui_styles.text_style(ui_styles.TEXT_SECONDARY, bold=True, background=ui_styles.TAB_INACTIVE))
    text.append(
        f" {context_label} ",
        style=ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE),
    )
    for index, (key, label) in enumerate(status_hint_items(state)):
        text.append("  ", style="")
        text.append(f" {key} ", style=ui_styles.pill_style(ui_styles.TEXT_SUCCESS))
        text.append(
            f" {label} ",
            style=ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE),
        )
    if state.current_tab == TAB_HOME:
        text.append("  ", style="")
        text.append(f" {STATUS_ENV_BADGE_LABEL} ", style=ui_styles.pill_style(ui_styles.TEXT_WARNING))
        text.append(
            f" {state.active_env_label()} ",
            style=ui_styles.text_style(ui_styles.TEXT_PRIMARY, bold=True, background=ui_styles.TAB_INACTIVE),
        )
    return text


def _append_edit_buffer_preview(text: Text, state: PiespectorState) -> None:
    cursor_index = max(0, min(state.edit_cursor_index, len(state.edit_buffer)))
    before = state.edit_buffer[:cursor_index]
    after = state.edit_buffer[cursor_index:]
    text.append(before, style=ui_styles.primary_style(bold=True))
    text.append("|", style=ui_styles.text_style(ui_styles.TEXT_URL, bold=True))
    text.append(after, style=ui_styles.primary_style(bold=True))
    match = placeholder_match(
        state.edit_buffer,
        cursor_index,
        sorted(state.env_pairs),
    )
    if match is not None and match.suggestion != match.prefix:
        text.append(f"  env: {match.suggestion}", style=ui_styles.TEXT_MUTED)


def _append_completion_hint(text: Text, current_value: str, matches: list[str]) -> None:
    if not matches:
        return
    first = matches[0]
    if first != current_value and first.startswith(current_value):
        suffix = first[len(current_value) :]
        if suffix:
            text.append(suffix, style=ui_styles.TEXT_MUTED)
    else:
        previews = matches[:3]
        text.append("  ", style="")
        text.append("  |  ".join(previews), style=ui_styles.TEXT_MUTED)
        if len(matches) > 3:
            text.append(f"  (+{len(matches) - 3} more)", style=ui_styles.TEXT_TREE_GUIDE)
        return
    if len(matches) > 1:
        text.append(f"  (+{len(matches) - 1} more)", style=ui_styles.TEXT_TREE_GUIDE)


def _append_path_completion_hint(text: Text, current_value: str) -> None:
    _append_completion_hint(text, current_value, filesystem_path_completions(current_value))


def _append_search_completion_hint(text: Text, state: PiespectorState) -> None:
    completion = (
        history_search_completion(state, state.command_buffer)
        if state.current_tab == TAB_HISTORY
        else search_completion(state, state.command_buffer)
    )
    if (
        completion is not None
        and completion != state.command_buffer
        and completion.lower().startswith(state.command_buffer.lower())
    ):
        suffix = completion[len(state.command_buffer) :]
        if suffix:
            text.append(suffix, style=ui_styles.TEXT_MUTED)
        return

    matches = (
        history_search_matches(state, state.command_buffer)
        if state.current_tab == TAB_HISTORY
        else search_matches(state, state.command_buffer)
    )
    if not matches:
        return

    previews = [
        history_search_display(match)
        if state.current_tab == TAB_HISTORY
        else match.display
        for match in matches[:3]
    ]
    text.append("  ", style="")
    text.append("  |  ".join(previews), style=ui_styles.TEXT_MUTED)
    if len(matches) > 3:
        text.append(f"  (+{len(matches) - 3} more)", style=ui_styles.TEXT_TREE_GUIDE)


def _command_line_style(tone: str) -> str:
    if tone == "warning":
        return ui_styles.warning_style(bold=True)
    if tone == "danger":
        return ui_styles.danger_style(bold=True)
    return ui_styles.primary_style(bold=True)


def render_command_line(state: PiespectorState) -> Text:
    text = Text()
    content = command_line_content(state)
    if content is None:
        return text

    text.append(content.text, style=_command_line_style(content.tone))

    if content.use_edit_buffer:
        _append_edit_buffer_preview(text, state)

    if content.completion_kind == "command":
        _append_completion_hint(
            text,
            state.command_buffer,
            command_completion_matches(state, state.command_buffer),
        )
    elif content.completion_kind == "search":
        _append_search_completion_hint(text, state)
    elif content.completion_kind == "path":
        _append_path_completion_hint(text, state.edit_buffer)

    return text
