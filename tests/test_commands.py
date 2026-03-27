from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from piespector.commands import command_completion, help_commands, run_command
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    PiespectorState,
    RequestDefinition,
)
from piespector.storage import save_request_workspace


@contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class CommandTests(unittest.TestCase):
    def test_rename_supports_quoted_name(self) -> None:
        state = PiespectorState(current_tab="home")
        collection = CollectionDefinition(name="Books")
        request = RequestDefinition(name="getBooks", collection_id=collection.collection_id)
        state.collections = [collection]
        state.requests = [request]
        state.ensure_request_workspace()
        state._set_selected_sidebar_by_request_id(request.request_id)

        outcome = run_command(state, 'rename "Books API v2"')

        self.assertTrue(outcome.save_requests)
        self.assertEqual(request.name, "Books API v2")
        self.assertEqual(state.message, "Renamed request Books API v2.")

    def test_import_supports_quoted_path_with_spaces(self) -> None:
        state = PiespectorState(current_tab="home")
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            import_path = root / "My Collections.json"
            save_request_workspace(
                import_path,
                [CollectionDefinition(collection_id="c1", name="Books")],
                [],
                [],
                set(),
                set(),
            )

            outcome = run_command(state, f'import "{import_path}"')

        self.assertTrue(outcome.save_requests)
        self.assertEqual([collection.name for collection in state.collections], ["Books"])
        self.assertEqual(state.message, "Imported 1 collection.")

    def test_mv_supports_quoted_destination_path(self) -> None:
        source_collection = CollectionDefinition(name="Source")
        target_collection = CollectionDefinition(name="Target")
        target_folder = FolderDefinition(
            name="Auth Folder",
            collection_id=target_collection.collection_id,
        )
        request = RequestDefinition(
            name="login",
            collection_id=source_collection.collection_id,
        )
        state = PiespectorState(current_tab="home")
        state.collections = [source_collection, target_collection]
        state.folders = [target_folder]
        state.requests = [request]
        state.ensure_request_workspace()
        state.collapsed_collection_ids.discard(source_collection.collection_id)
        state.collapsed_collection_ids.discard(target_collection.collection_id)
        state._set_selected_sidebar_by_request_id(request.request_id)

        outcome = run_command(state, 'mv "Target / Auth Folder"')

        self.assertTrue(outcome.save_requests)
        self.assertEqual(request.collection_id, target_collection.collection_id)
        self.assertEqual(request.folder_id, target_folder.folder_id)
        self.assertEqual(state.message, "Moved request login.")

    def test_import_completion_quotes_filesystem_paths_with_spaces(self) -> None:
        state = PiespectorState(current_tab="env", mode="COMMAND", command_context_mode="NORMAL")
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "My Env.env").write_text("A=1\n", encoding="utf-8")
            with chdir(root):
                completion = command_completion(state, 'import "My')

        self.assertEqual(completion, 'import "My Env.env"')

    def test_mv_completion_quotes_destination_paths_with_spaces(self) -> None:
        source_collection = CollectionDefinition(name="Source")
        target_collection = CollectionDefinition(name="Target")
        target_folder = FolderDefinition(
            name="Auth Folder",
            collection_id=target_collection.collection_id,
        )
        request = RequestDefinition(
            name="login",
            collection_id=source_collection.collection_id,
        )
        state = PiespectorState(current_tab="home", mode="COMMAND", command_context_mode="NORMAL")
        state.collections = [source_collection, target_collection]
        state.folders = [target_folder]
        state.requests = [request]
        state.ensure_request_workspace()
        state.collapsed_collection_ids.discard(source_collection.collection_id)
        state.collapsed_collection_ids.discard(target_collection.collection_id)
        state._set_selected_sidebar_by_request_id(request.request_id)

        completion = command_completion(state, 'mv "Target / A')

        self.assertEqual(completion, 'mv "Target / Auth Folder"')

    def test_env_import_creates_new_env_set_instead_of_merging(self) -> None:
        state = PiespectorState(current_tab="env")
        state.env_names = ["Default"]
        state.env_sets = {"Default": {"EXISTING": "x"}}
        state.selected_env_name = "Default"
        state.ensure_env_workspace()
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "staging.env"
            path.write_text("A=1\nB=two\n", encoding="utf-8")

            outcome = run_command(state, f'import "{path}"')

        self.assertTrue(outcome.save_env_pairs)
        self.assertEqual(state.selected_env_name, "staging")
        self.assertEqual(state.env_pairs, {"A": "1", "B": "two"})
        self.assertEqual(state.env_sets["Default"], {"EXISTING": "x"})

    def test_page_only_commands_are_blocked_in_request_editor_context(self) -> None:
        state = PiespectorState(current_tab="home", mode="HOME_SECTION_SELECT", command_context_mode="HOME_SECTION_SELECT")

        self.assertIsNone(command_completion(state, "imp"))
        self.assertIsNone(command_completion(state, "cp"))
        self.assertIsNone(command_completion(state, "mv"))
        self.assertIsNone(command_completion(state, "de"))

        run_command(state, "import foo.json")
        self.assertEqual(state.message, "Import is only available from the Home or Env page.")

        run_command(state, "rename Test")
        self.assertEqual(state.message, "Rename is only available from the Home or Env page.")

        run_command(state, "cp Somewhere")
        self.assertEqual(state.message, "Copy is only available from the Home page.")

        run_command(state, "mv Somewhere")
        self.assertEqual(state.message, "Move is only available from the Home page.")

        run_command(state, "del")
        self.assertEqual(state.message, "Delete is only available from the Home page.")

    def test_env_help_commands_include_page_commands(self) -> None:
        state = PiespectorState(current_tab="env")

        commands = help_commands(state, "env", "NORMAL")

        self.assertIn("rename NAME", commands)
        self.assertIn("import PATH", commands)
        self.assertIn("export PATH", commands)

    def test_home_help_commands_include_mv_when_request_is_selected(self) -> None:
        state = PiespectorState(current_tab="home")
        collection = CollectionDefinition(name="Books")
        request = RequestDefinition(name="getBooks", collection_id=collection.collection_id)
        state.collections = [collection]
        state.requests = [request]
        state.ensure_request_workspace()
        state._set_selected_sidebar_by_request_id(request.request_id)

        commands = help_commands(state, "home", "NORMAL")

        self.assertIn("mv PATH", commands)

    def test_unclosed_quote_reports_parse_error(self) -> None:
        state = PiespectorState(current_tab="home")

        outcome = run_command(state, 'import "broken')

        self.assertFalse(outcome.save_requests)
        self.assertEqual(state.message, "Unclosed quote in command.")


if __name__ == "__main__":
    unittest.main()
