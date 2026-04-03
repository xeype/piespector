from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from piespector.domain.editor import TAB_ENV, TAB_HISTORY, TAB_HOME
from piespector.domain.modes import (
    MODE_COMMAND,
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
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_NORMAL,
)
from piespector.search import move_destination_matches, resolve_move_destination
from piespector.state import PiespectorState
from piespector.storage import (
    export_collection_workspace,
    export_env_pairs,
    import_collection_workspace,
    import_env_sets,
)


@dataclass
class CommandOutcome:
    should_exit: bool = False
    save_requests: bool = False
    save_env_pairs: bool = False
    send_request: bool = False


@dataclass(frozen=True)
class CommandSpec:
    tokens: tuple[str, ...]
    takes_value: bool = False


@dataclass(frozen=True)
class ParsedCommand:
    raw: str
    tokens: tuple[str, ...]
    error: str = ""


@dataclass(frozen=True)
class PaletteCommand:
    label: str
    text: str
    help: str
    runnable: bool


REQUEST_COMMAND_CONTEXT_MODES = frozenset(
    {
        MODE_HOME_SECTION_SELECT,
        MODE_HOME_REQUEST_SELECT,
        MODE_HOME_REQUEST_METHOD_SELECT,
        MODE_HOME_REQUEST_EDIT,
        MODE_HOME_REQUEST_METHOD_EDIT,
        MODE_HOME_AUTH_SELECT,
        MODE_HOME_AUTH_EDIT,
        MODE_HOME_AUTH_TYPE_EDIT,
        MODE_HOME_AUTH_LOCATION_EDIT,
        MODE_HOME_PARAMS_SELECT,
        MODE_HOME_PARAMS_EDIT,
        MODE_HOME_HEADERS_SELECT,
        MODE_HOME_HEADERS_EDIT,
        MODE_HOME_BODY_SELECT,
        MODE_HOME_BODY_TYPE_EDIT,
        MODE_HOME_BODY_RAW_TYPE_EDIT,
        MODE_HOME_BODY_EDIT,
        MODE_HOME_BODY_TEXTAREA,
    }
)
HOME_PAGE_COMMAND_CONTEXT_MODES = frozenset({MODE_NORMAL})


def command_context_mode(state: PiespectorState) -> str:
    if state.mode == MODE_COMMAND:
        return state.command_context_mode or MODE_NORMAL
    return state.mode


def _command_source(
    state: PiespectorState,
    context_mode: str,
) -> tuple[str, str] | None:
    if context_mode in REQUEST_COMMAND_CONTEXT_MODES:
        request = state.get_active_request()
        if request is not None:
            return ("request", request.request_id)

    node = state.get_selected_sidebar_node()
    if node is None:
        return None
    if node.kind == "request" and node.request_id is not None:
        return ("request", node.request_id)
    if node.kind == "folder":
        return ("folder", node.node_id)
    if node.kind == "collection":
        return ("collection", node.node_id)
    return None


def _path_value_completion(
    state: PiespectorState,
    raw_buffer: str,
    context_mode: str,
    specs: list[CommandSpec],
) -> str | None:
    matches = _path_value_completions(state, raw_buffer, context_mode, specs)
    return matches[0] if matches else None


def _path_value_completions(
    state: PiespectorState,
    raw_buffer: str,
    context_mode: str,
    specs: list[CommandSpec],
) -> list[str]:
    buffer = raw_buffer.lstrip()
    source = _command_source(state, context_mode)

    for command in ("mv", "cp"):
        if not any(spec.tokens == (command,) for spec in specs):
            continue
        if source is None:
            continue
        if command == "cp" and source[0] == "collection":
            continue

        if buffer.lower() == command:
            return [f"{command} "]
        if not buffer.lower().startswith(f"{command} "):
            continue

        value = buffer[len(command) :].lstrip()
        normalized_value = _unquote_command_value(value)
        matches = move_destination_matches(
            state,
            normalized_value,
            source_kind=source[0],
            source_id=source[1],
        )
        if not matches:
            return None

        prefix_matches = [
            match
            for match in matches
            if not normalized_value or match.display.lower().startswith(normalized_value.lower())
        ]
        if not prefix_matches:
            return []
        return [
            f"{command} {_quote_command_value(match.display, raw_value=value)}"
            for match in prefix_matches
        ]

    for command in ("import", "export"):
        if not any(spec.tokens == (command,) for spec in specs):
            continue
        if buffer.lower() == command:
            return [f"{command} "]
        if not buffer.lower().startswith(f"{command} "):
            continue

        value = buffer[len(command) :].lstrip()
        completed_values = _filesystem_path_completions(value)
        if not completed_values:
            return []
        return [f"{command} {completed_value}" for completed_value in completed_values]

    return []


def _filesystem_path_completion(raw_value: str) -> str | None:
    completions = _filesystem_path_completions(raw_value)
    return completions[0] if completions else None


def filesystem_path_completions(raw_value: str) -> list[str]:
    return _filesystem_path_completions(raw_value)


def _filesystem_path_completions(raw_value: str) -> list[str]:
    quote_char = raw_value[:1] if raw_value[:1] in {'"', "'"} else ""
    value = raw_value[1:] if quote_char else raw_value
    if quote_char and value.endswith(quote_char):
        value = value[:-1]

    if not value:
        base_dir = Path.cwd()
        prefix = ""
        raw_parent = ""
    elif value.endswith("/"):
        base_dir = _command_path(value)
        prefix = ""
        raw_parent = value.rstrip("/")
    else:
        if "/" in value:
            raw_parent, prefix = value.rsplit("/", 1)
            base_dir = _command_path(raw_parent or "/")
        else:
            raw_parent = ""
            prefix = value
            base_dir = Path.cwd()

    try:
        entries = sorted(base_dir.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError:
        return []

    candidates = [
        entry
        for entry in entries
        if entry.name.startswith(prefix)
        and (prefix.startswith(".") or not entry.name.startswith("."))
    ]
    if not candidates:
        return []

    completions: list[str] = []
    for chosen in candidates:
        chosen_name = chosen.name + ("/" if chosen.is_dir() else "")
        if not raw_parent:
            completed = chosen_name
        elif raw_parent == "/":
            completed = f"/{chosen_name}"
        else:
            completed = f"{raw_parent}/{chosen_name}"
        completions.append(
            _quote_command_value(
                completed,
                raw_value=raw_value,
                keep_open=chosen.is_dir(),
            )
        )
    return completions


def _command_specs(state: PiespectorState, context_mode: str) -> list[CommandSpec]:
    if state.current_tab == TAB_ENV:
        return [
            CommandSpec(("home",)),
            CommandSpec(("env",)),
            CommandSpec(("history",)),
            CommandSpec(("new",), takes_value=True),
            CommandSpec(("rename",), takes_value=True),
            CommandSpec(("import",), takes_value=True),
            CommandSpec(("export",), takes_value=True),
            CommandSpec(("set",), takes_value=True),
            CommandSpec(("del",)),
            CommandSpec(("del",), takes_value=True),
            CommandSpec(("edit",)),
        ]

    if state.current_tab == TAB_HISTORY:
        return [
            CommandSpec(("home",)),
            CommandSpec(("env",)),
            CommandSpec(("history",)),
            CommandSpec(("replay",)),
        ]

    node = state.get_selected_sidebar_node()

    if context_mode == MODE_HOME_SECTION_SELECT:
        return [
            CommandSpec(("history",)),
            CommandSpec(("env",)),
        ]

    if context_mode in REQUEST_COMMAND_CONTEXT_MODES:
        return [
            CommandSpec(("history",)),
            CommandSpec(("env",)),
        ]

    if node is not None and node.kind == "request":
        return [
            CommandSpec(("new",)),
            CommandSpec(("new", "collection"), takes_value=True),
            CommandSpec(("new", "folder"), takes_value=True),
            CommandSpec(("import",), takes_value=True),
            CommandSpec(("export",), takes_value=True),
            CommandSpec(("edit",)),
            CommandSpec(("rename",), takes_value=True),
            CommandSpec(("cp",), takes_value=True),
            CommandSpec(("mv",), takes_value=True),
            CommandSpec(("del",)),
            CommandSpec(("history",)),
            CommandSpec(("env",)),
        ]

    if node is not None and node.kind == "folder":
        return [
            CommandSpec(("new",)),
            CommandSpec(("new", "collection"), takes_value=True),
            CommandSpec(("new", "folder"), takes_value=True),
            CommandSpec(("import",), takes_value=True),
            CommandSpec(("export",), takes_value=True),
            CommandSpec(("rename",), takes_value=True),
            CommandSpec(("cp",), takes_value=True),
            CommandSpec(("mv",), takes_value=True),
            CommandSpec(("del",)),
            CommandSpec(("history",)),
            CommandSpec(("env",)),
        ]

    if node is not None and node.kind == "collection":
        return [
            CommandSpec(("new",)),
            CommandSpec(("new", "collection"), takes_value=True),
            CommandSpec(("new", "folder"), takes_value=True),
            CommandSpec(("import",), takes_value=True),
            CommandSpec(("export",), takes_value=True),
            CommandSpec(("rename",), takes_value=True),
            CommandSpec(("cp",)),
            CommandSpec(("del",)),
            CommandSpec(("history",)),
            CommandSpec(("env",)),
        ]

    return [
        CommandSpec(("new",)),
        CommandSpec(("new", "collection"), takes_value=True),
        CommandSpec(("import",), takes_value=True),
        CommandSpec(("export",), takes_value=True),
        CommandSpec(("history",)),
        CommandSpec(("env",)),
    ]


def _spec_display(spec: CommandSpec) -> str:
    command = " ".join(spec.tokens)
    if spec.tokens == ("cp",) and spec.takes_value:
        return "cp PATH"
    if spec.tokens == ("mv",) and spec.takes_value:
        return "mv PATH"
    if spec.tokens in {("import",), ("export",)}:
        return f"{command} PATH"
    if spec.tokens == ("set",):
        return "set KEY=value"
    if spec.tokens == ("new",) and spec.takes_value:
        return "new NAME"
    if spec.tokens == ("del",) and spec.takes_value:
        return "del KEY"
    if spec.takes_value:
        return f"{command} NAME"
    return command


def _help_message(state: PiespectorState, context_mode: str) -> str:
    commands = help_commands(state, state.current_tab, context_mode)
    return f"Commands: {', '.join(commands)}"


def _command_text(spec: CommandSpec) -> str:
    command = " ".join(spec.tokens)
    if spec.takes_value:
        return f"{command} "
    return command


def _command_help(spec: CommandSpec, current_tab: str) -> str:
    if spec.tokens == ("home",):
        return "Switch to Home."
    if spec.tokens == ("env",):
        return "Switch to Env."
    if spec.tokens == ("history",):
        return "Switch to History."
    if spec.tokens == ("replay",):
        return "Replay the selected history entry."
    if spec.tokens == ("edit",):
        return "Edit the selected item."
    if spec.tokens == ("new",):
        if spec.takes_value and current_tab == TAB_ENV:
            return "Continue typing the new env set name."
        return "Create a new request."
    if spec.tokens == ("new", "collection"):
        return "Continue typing the collection name."
    if spec.tokens == ("new", "folder"):
        return "Continue typing the folder name."
    if spec.tokens == ("import",):
        return "Continue typing the import path."
    if spec.tokens == ("export",):
        return "Continue typing the export path."
    if spec.tokens == ("rename",):
        return "Continue typing the new name."
    if spec.tokens == ("cp",):
        return "Continue typing the copy destination."
    if spec.tokens == ("mv",):
        return "Continue typing the move destination."
    if spec.tokens == ("set",):
        return "Continue typing KEY=value."
    if spec.tokens == ("del",):
        if spec.takes_value:
            return "Continue typing the env key to delete."
        return "Delete the selected item."
    return "Run command."


def command_palette_commands(
    state: PiespectorState,
    context_mode: str | None = None,
) -> list[PaletteCommand]:
    active_context_mode = context_mode or command_context_mode(state)
    commands: list[PaletteCommand] = []
    seen: set[tuple[str, str, bool]] = set()
    for spec in _command_specs(state, active_context_mode):
        entry = PaletteCommand(
            label=_spec_display(spec),
            text=_command_text(spec),
            help=_command_help(spec, state.current_tab),
            runnable=not spec.takes_value,
        )
        key = (entry.label, entry.text, entry.runnable)
        if key in seen:
            continue
        seen.add(key)
        commands.append(entry)
    return commands


def help_commands(
    state: PiespectorState,
    context_tab: str,
    context_mode: str,
) -> list[str]:
    original_tab = state.current_tab
    state.current_tab = context_tab
    try:
        specs = _command_specs(state, context_mode)
    finally:
        state.current_tab = original_tab

    commands: list[str] = []
    for spec in specs:
        display = _spec_display(spec)
        if display not in commands:
            commands.append(display)

    if (
        context_tab == TAB_HOME
        and "new collection NAME" in commands
        and "new folder NAME" in commands
    ):
        collection_index = commands.index("new collection NAME")
        folder_index = commands.index("new folder NAME")
        commands.pop(max(collection_index, folder_index))
        commands.pop(min(collection_index, folder_index))
        commands.insert(min(collection_index, folder_index), "new collection/folder NAME")

    return commands


def command_completion(state: PiespectorState, raw_buffer: str) -> str | None:
    matches = command_completion_matches(state, raw_buffer)
    return matches[0] if matches else None


def command_completion_matches(state: PiespectorState, raw_buffer: str) -> list[str]:
    context_mode = command_context_mode(state)
    specs = _command_specs(state, context_mode)
    path_completions = _path_value_completions(state, raw_buffer, context_mode, specs)
    if path_completions:
        return path_completions

    buffer = raw_buffer.lstrip()
    trailing_space = buffer.endswith(" ")
    tokens = buffer.split()

    if trailing_space:
        completed_prefix = tokens
        token_index = len(tokens)
        current_prefix = ""
    elif tokens:
        completed_prefix = tokens[:-1]
        token_index = len(tokens) - 1
        current_prefix = tokens[-1].lower()
    else:
        completed_prefix = []
        token_index = 0
        current_prefix = ""

    candidates: list[str] = []
    for spec in specs:
        if len(spec.tokens) <= token_index:
            continue
        if tuple(completed_prefix) != spec.tokens[:token_index]:
            continue
        candidate = spec.tokens[token_index]
        if not candidate.startswith(current_prefix):
            continue
        if candidate not in candidates:
            candidates.append(candidate)

    if not candidates:
        return []

    completions: list[str] = []
    for chosen in candidates:
        new_tokens = [*completed_prefix, chosen]
        completed = " ".join(new_tokens)

        exact_specs = [spec for spec in specs if spec.tokens == tuple(new_tokens)]
        has_children = any(
            len(spec.tokens) > len(new_tokens) and spec.tokens[: len(new_tokens)] == tuple(new_tokens)
            for spec in specs
        )
        needs_value = any(spec.takes_value for spec in exact_specs)
        if has_children or needs_value:
            completed += " "
        completions.append(completed)
    return completions


def _command_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _parse_command(raw_command: str) -> ParsedCommand:
    stripped = raw_command.strip()
    if stripped.startswith(":"):
        stripped = stripped[1:].strip()
    if not stripped:
        return ParsedCommand(raw="", tokens=())
    lexer = shlex.shlex(stripped, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return ParsedCommand(raw=stripped, tokens=tuple(lexer))
    except ValueError as error:
        return ParsedCommand(raw=stripped, tokens=(), error=str(error))


def _command_value(tokens: tuple[str, ...], start_index: int) -> str:
    return " ".join(tokens[start_index:]).strip()


def _unquote_command_value(raw_value: str) -> str:
    if len(raw_value) >= 2 and raw_value[0] in {'"', "'"} and raw_value[-1] == raw_value[0]:
        return raw_value[1:-1]
    if raw_value[:1] in {'"', "'"}:
        return raw_value[1:]
    return raw_value


def _quote_command_value(
    value: str,
    *,
    raw_value: str = "",
    keep_open: bool = False,
) -> str:
    quote_char = raw_value[:1] if raw_value[:1] in {'"', "'"} else ""
    needs_quotes = bool(quote_char) or any(character.isspace() for character in value)
    if not needs_quotes:
        return value
    quote = quote_char or '"'
    closing = "" if keep_open else quote
    escaped = value.replace(quote, f"\\{quote}")
    return f"{quote}{escaped}{closing}"


def run_command(state: PiespectorState, raw_command: str) -> CommandOutcome:
    previous_mode = command_context_mode(state)
    if state.mode == MODE_COMMAND:
        state.leave_command_mode()

    parsed = _parse_command(raw_command)
    if parsed.error:
        state.message = (
            "Unclosed quote in command."
            if "quotation" in parsed.error.lower()
            else f"Could not parse command: {parsed.error}"
        )
        return CommandOutcome()

    if not parsed.raw:
        state.message = ""
        return CommandOutcome()

    raw_command = parsed.raw
    tokens = parsed.tokens
    normalized_tokens = tuple(token.lower() for token in tokens)
    normalized = " ".join(normalized_tokens)

    if normalized in {"quit", "exit"}:
        return CommandOutcome(should_exit=True)

    if normalized in {"home", "tab home"}:
        state.switch_tab(TAB_HOME, "Home")
        return CommandOutcome()

    if normalized in {"env", "tab env"}:
        state.switch_tab(TAB_ENV, "Env")
        return CommandOutcome()

    if normalized in {"history", "tab history"}:
        state.switch_tab(TAB_HISTORY, "History")
        return CommandOutcome()

    if normalized == "replay":
        if state.current_tab != TAB_HISTORY:
            state.message = "Replay is only available on History."
            return CommandOutcome()
        replayed = state.replay_selected_history_entry()
        return CommandOutcome(save_requests=replayed is not None)

    if normalized == "new":
        if state.current_tab != TAB_HOME:
            state.message = "New is only available on Home."
            return CommandOutcome()
        state.create_request()
        return CommandOutcome(save_requests=True)

    if normalized_tokens[:2] == ("new", "collection"):
        if state.current_tab != TAB_HOME:
            state.message = "New collection is only available on Home."
            return CommandOutcome()
        name = _command_value(tokens, 2)
        if not name:
            state.message = "Usage: new collection NAME"
            return CommandOutcome()
        state.create_collection(name)
        return CommandOutcome(save_requests=True)

    if normalized_tokens[:2] == ("new", "folder"):
        if state.current_tab != TAB_HOME:
            state.message = "New folder is only available on Home."
            return CommandOutcome()
        name = _command_value(tokens, 2)
        if not name:
            state.message = "Usage: new folder NAME"
            return CommandOutcome()
        created = state.create_folder(name)
        return CommandOutcome(save_requests=created is not None)

    if normalized_tokens[:1] == ("new",) and state.current_tab == TAB_ENV:
        name = _command_value(tokens, 1)
        if not name:
            state.message = "Usage: new NAME"
            return CommandOutcome()
        created = state.create_env_set(name)
        return CommandOutcome(save_env_pairs=created)

    if normalized_tokens[:1] == ("import",):
        if state.current_tab == TAB_ENV:
            import_path_value = _command_value(tokens, 1)
            if not import_path_value:
                state.message = "Usage: import PATH"
                return CommandOutcome()
            import_path = _command_path(import_path_value)
            if not import_path.exists():
                state.message = f"Import file not found: {import_path}"
                return CommandOutcome()
            try:
                env_names, env_sets = import_env_sets(import_path)
            except (OSError, ValueError) as error:
                state.message = f"Import failed: {error}"
                return CommandOutcome()
            imported = state.import_env_sets(env_names, env_sets)
            return CommandOutcome(save_env_pairs=imported > 0)

        if state.current_tab != TAB_HOME or previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Import is only available from the Home or Env page."
            return CommandOutcome()
        import_path_value = _command_value(tokens, 1)
        if not import_path_value:
            state.message = "Usage: import PATH"
            return CommandOutcome()
        import_path = _command_path(import_path_value)
        if not import_path.exists():
            state.message = f"Import file not found: {import_path}"
            return CommandOutcome()

        try:
            collections, folders, requests = import_collection_workspace(import_path)
        except (OSError, ValueError) as error:
            state.message = f"Import failed: {error}"
            return CommandOutcome()
        imported = state.import_collections(collections, folders, requests)
        return CommandOutcome(save_requests=imported > 0)

    if normalized_tokens[:1] == ("export",):
        if state.current_tab == TAB_ENV:
            export_path_value = _command_value(tokens, 1)
            if not export_path_value:
                state.message = "Usage: export PATH"
                return CommandOutcome()
            export_path = _command_path(export_path_value)
            try:
                export_env_pairs(export_path, state.env_pairs)
            except OSError as error:
                state.message = f"Export failed: {error}"
                return CommandOutcome()
            state.message = f"Exported env to {export_path}."
            return CommandOutcome()

        if state.current_tab != TAB_HOME or previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Export is only available from the Home or Env page."
            return CommandOutcome()
        export_path_value = _command_value(tokens, 1)
        if not export_path_value:
            state.message = "Usage: export PATH"
            return CommandOutcome()
        export_path = _command_path(export_path_value)

        node = state.get_selected_sidebar_node()
        collection_ids = None
        if node is not None and node.kind == "collection":
            collection_ids = {node.node_id}
        try:
            exported = export_collection_workspace(
                export_path,
                state.collections,
                state.folders,
                state.requests,
                collection_ids=collection_ids,
            )
        except OSError as error:
            state.message = f"Export failed: {error}"
            return CommandOutcome()
        if exported <= 0:
            state.message = "No collections available to export."
            return CommandOutcome()
        state.message = (
            f"Exported {exported} collection to {export_path}."
            if exported == 1
            else f"Exported {exported} collections to {export_path}."
        )
        return CommandOutcome()

    if normalized_tokens[:1] == ("rename",):
        if state.current_tab == TAB_ENV:
            name = _command_value(tokens, 1)
            if not name:
                state.message = "Usage: rename NAME"
                return CommandOutcome()
            renamed = state.rename_selected_env_set(name)
            return CommandOutcome(save_env_pairs=renamed)
        if state.current_tab != TAB_HOME or previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Rename is only available from the Home or Env page."
            return CommandOutcome()
        source = _command_source(state, previous_mode)
        if source is None:
            state.message = "Select a request, folder, or collection first."
            return CommandOutcome()
        name = _command_value(tokens, 1)
        if not name:
            state.message = "Usage: rename NAME"
            return CommandOutcome()
        if source[0] == "request":
            renamed = state.rename_request(source[1], name)
        elif source[0] == "folder":
            renamed = state.rename_folder(source[1], name)
        else:
            renamed = state.rename_collection(source[1], name)
        return CommandOutcome(save_requests=renamed)

    if normalized_tokens[:1] == ("mv",):
        if state.current_tab != TAB_HOME or previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Move is only available from the Home page."
            return CommandOutcome()
        source = _command_source(state, previous_mode)
        if source is None:
            state.message = "Select a request or folder first."
            return CommandOutcome()

        destination_buffer = _command_value(tokens, 1)
        if not destination_buffer:
            state.message = "Usage: mv PATH"
            return CommandOutcome()

        destination = resolve_move_destination(
            state,
            destination_buffer,
            source_kind=source[0],
            source_id=source[1],
        )
        if destination is None:
            matches = move_destination_matches(
                state,
                destination_buffer,
                source_kind=source[0],
                source_id=source[1],
            )
            if not matches:
                state.message = "Destination not found."
            else:
                state.message = "Destination is ambiguous. Use a fuller path."
            return CommandOutcome()

        if source[0] == "request":
            moved = state.move_request_to(
                source[1],
                destination.collection_id,
                destination.folder_id,
            )
        else:
            moved = state.move_folder_to(
                source[1],
                destination.collection_id,
                destination.folder_id,
            )
        return CommandOutcome(save_requests=moved)

    if normalized_tokens[:1] == ("cp",):
        if state.current_tab != TAB_HOME or previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Copy is only available from the Home page."
            return CommandOutcome()
        source = _command_source(state, previous_mode)
        if source is None:
            state.message = "Select a request, folder, or collection first."
            return CommandOutcome()

        if source[0] == "collection":
            if normalized != "cp":
                state.message = "Usage: cp"
                return CommandOutcome()
            copied_collection = state.copy_collection(source[1])
            return CommandOutcome(save_requests=copied_collection is not None)

        destination_buffer = _command_value(tokens, 1)
        if not destination_buffer:
            state.message = "Usage: cp PATH"
            return CommandOutcome()

        destination = resolve_move_destination(
            state,
            destination_buffer,
            source_kind=source[0],
            source_id=source[1],
        )
        if destination is None:
            matches = move_destination_matches(
                state,
                destination_buffer,
                source_kind=source[0],
                source_id=source[1],
            )
            if not matches:
                state.message = "Destination not found."
            else:
                state.message = "Destination is ambiguous. Use a fuller path."
            return CommandOutcome()

        if source[0] == "request":
            copied = state.copy_request_to(
                source[1],
                destination.collection_id,
                destination.folder_id,
            )
            return CommandOutcome(save_requests=copied is not None)

        copied_folder = state.copy_folder_to(
            source[1],
            destination.collection_id,
            destination.folder_id,
        )
        return CommandOutcome(save_requests=copied_folder is not None)

    if normalized_tokens[:1] == ("set",):
        payload = _command_value(tokens, 1)
        if "=" not in payload:
            state.message = "Usage: set KEY=value"
            return CommandOutcome()

        key, value = payload.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            state.message = "Usage: set KEY=value"
            return CommandOutcome()

        state.env_pairs[key] = value
        state.message = f"Saved {key}."
        state.current_tab = TAB_ENV
        state.selected_env_index = max(0, len(state.env_pairs) - 1)
        return CommandOutcome(save_env_pairs=True)

    if normalized_tokens[:1] in {("del",), ("delete",)} and len(tokens) > 1:
        if state.current_tab != TAB_ENV:
            state.message = "Usage: del"
            return CommandOutcome()

        key = _command_value(tokens, 1)
        if not key:
            state.message = "Usage: del KEY"
            return CommandOutcome()

        if state.delete_env_key(key):
            return CommandOutcome(save_env_pairs=True)

        state.message = f"No such key: {key}"
        return CommandOutcome()

    if normalized in {"del", "delete"}:
        if state.current_tab == TAB_ENV:
            deleted = state.delete_selected_env_set()
            return CommandOutcome(save_env_pairs=deleted)
        if state.current_tab != TAB_HOME:
            state.message = "Usage: del KEY"
            return CommandOutcome()
        if previous_mode not in HOME_PAGE_COMMAND_CONTEXT_MODES:
            state.message = "Delete is only available from the Home page."
            return CommandOutcome()
        node = state.get_selected_sidebar_node()
        if node is not None and node.kind == "collection":
            state.enter_confirm_mode(
                prompt=f"Delete collection {node.label} and all nested folders/requests? (y/n)",
                action="delete_collection",
                target_id=node.node_id,
            )
            return CommandOutcome()
        if node is not None and node.kind == "folder":
            state.enter_confirm_mode(
                prompt=f"Delete folder {node.label} and all nested folders/requests? (y/n)",
                action="delete_folder",
                target_id=node.node_id,
            )
            return CommandOutcome()
        deleted = state.delete_selected_request()
        if deleted is None:
            state.message = "No request selected."
            return CommandOutcome()
        return CommandOutcome(save_requests=True)

    if normalized == "edit":
        if state.current_tab == TAB_HOME:
            if state.get_selected_request() is None:
                state.message = "Select a request first."
                return CommandOutcome()
            state.enter_home_section_select_mode()
            return CommandOutcome()
        if state.current_tab == TAB_ENV:
            if not state.env_pairs:
                state.message = "Nothing to edit."
                return CommandOutcome()
            state.enter_env_select_mode()
            state.message = "Select with j/k or arrows, Enter to edit, d to delete."
            return CommandOutcome()
        state.message = "Edit is not available on this tab."
        return CommandOutcome()

    if normalized == "clear":
        state.message = ""
        return CommandOutcome()

    state.message = f"Unknown command: {raw_command}"
    return CommandOutcome()
