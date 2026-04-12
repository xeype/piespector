from __future__ import annotations

import io
import unittest

from rich.console import Console

from piespector.app import PiespectorApp
from piespector.domain.requests import EnvVariable
from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    HistoryEntry,
    RequestDefinition,
    ResponseSummary,
)
from piespector.ui.body_editor_modal import BodyEditorModal
from textual.command import CommandInput, CommandPalette
from textual.widgets import Input, Static, Tabs


def render_plain(renderable, *, width: int = 140) -> str:
    console = Console(record=True, width=width, file=io.StringIO())
    console.print(renderable)
    return console.export_text()


def build_test_app() -> PiespectorApp:
    app = PiespectorApp()
    app._load_env_workspace = lambda: None
    app._load_history = lambda: None
    app._load_request_workspace = lambda: None
    return app


class TextualUiSafetyNetTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_palette_opens_from_keyboard(self) -> None:
        app = build_test_app()

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()

            self.assertTrue(CommandPalette.is_open(app))
            self.assertIsInstance(app.screen.query_one(CommandInput), CommandInput)

    async def test_app_switches_between_home_env_and_history_screens(self) -> None:
        app = build_test_app()

        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "home")
            self.assertEqual(app.screen.query_one("#home-screen").id, "home-screen")

            app.action_show_env()
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "env")
            self.assertEqual(app.screen.query_one("#env-screen").id, "env-screen")

            app.action_show_history()
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "history")
            self.assertEqual(app.screen.query_one("#history-screen").id, "history-screen")

            app.action_show_home()
            await pilot.pause()

            self.assertEqual(app.state.current_tab, "home")
            self.assertEqual(app.screen.query_one("#home-screen").id, "home-screen")

    async def test_response_viewer_modal_opens_and_closes_from_response_panel(self) -> None:
        app = build_test_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            last_response=ResponseSummary(
                status_code=200,
                elapsed_ms=12.3,
                body_length=11,
                body_text='{"ok":true}',
            ),
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            await pilot.press("ctrl+o", "a")
            await pilot.pause()

            self.assertEqual(app.state.mode, "HOME_RESPONSE_SELECT")

            await pilot.press("enter")
            await pilot.pause()

            editor = app.screen.query_one("#body-editor")
            self.assertTrue(app.screen.is_modal)
            self.assertIsInstance(app.screen, BodyEditorModal)
            self.assertTrue(app.screen.read_only)
            self.assertIn('"ok"', editor.text)

            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.current_tab, "home")

    async def test_body_editor_opens_as_modal_screen_and_closes(self) -> None:
        app = build_test_app()
        request = RequestDefinition(
            request_id="r1",
            name="Upload",
            body_type="raw",
            raw_subtype="json",
            body_text='{"ok":true}',
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app.get_screen("home").open_body_text_editor(origin_mode="HOME_BODY_SELECT")
            await pilot.pause()

            editor = app.screen.query_one("#body-editor")
            self.assertTrue(app.screen.is_modal)
            self.assertIsInstance(app.screen, BodyEditorModal)
            self.assertIn('"ok"', editor.text)

            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.current_tab, "home")

    async def test_collection_delete_uses_confirm_modal_and_deletes_on_yes(self) -> None:
        app = build_test_app()
        collection = CollectionDefinition(name="Books")
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
        )
        app.state.collections = [collection]
        app.state.requests = [request]
        app.state.ensure_request_workspace()
        app.state._set_selected_sidebar_node("collection", collection.collection_id)

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app.execute_command("del")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)

            await pilot.press("y")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.collections, [])
            self.assertEqual(app.state.requests, [])
            self.assertEqual(app.state.message, "Deleted collection Books.")

    async def test_folder_delete_uses_confirm_modal_and_deletes_on_enter(self) -> None:
        app = build_test_app()
        collection = CollectionDefinition(name="Books")
        folder = FolderDefinition(
            folder_id="f1",
            name="Auth",
            collection_id=collection.collection_id,
        )
        nested_folder = FolderDefinition(
            folder_id="f2",
            name="Nested",
            collection_id=collection.collection_id,
            parent_folder_id=folder.folder_id,
        )
        request = RequestDefinition(
            request_id="r1",
            name="Login",
            collection_id=collection.collection_id,
            folder_id=nested_folder.folder_id,
        )
        app.state.collections = [collection]
        app.state.folders = [folder, nested_folder]
        app.state.requests = [request]
        app.state.ensure_request_workspace()
        app.state._set_selected_sidebar_node("folder", folder.folder_id)

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            app.execute_command("del")
            await pilot.pause()

            self.assertTrue(app.screen.is_modal)

            await pilot.press("enter")
            await pilot.pause()

            self.assertFalse(app.screen.is_modal)
            self.assertEqual(app.state.folders, [])
            self.assertEqual(app.state.requests, [])
            self.assertEqual(app.state.message, "Deleted folder Auth.")

    async def test_confirm_modal_returns_focus_to_sidebar_tree_after_esc_n_and_y(self) -> None:
        for dismiss_key in ("escape", "n", "y"):
            with self.subTest(dismiss_key=dismiss_key):
                app = build_test_app()
                first = CollectionDefinition(collection_id="c1", name="Books")
                second = CollectionDefinition(collection_id="c2", name="Movies")
                app.state.collections = [first, second]
                app.state.ensure_request_workspace()
                app.state._set_selected_sidebar_node("collection", first.collection_id)

                async with app.run_test(size=(140, 40)) as pilot:
                    app._refresh_screen()
                    await pilot.pause()

                    tree = app.screen.query_one("#sidebar-tree")
                    self.assertTrue(tree.has_focus)

                    app.execute_command("del")
                    await pilot.pause()

                    self.assertTrue(app.screen.is_modal)

                    await pilot.press(dismiss_key)
                    await pilot.pause()

                    tree = app.screen.query_one("#sidebar-tree")
                    self.assertFalse(app.screen.is_modal)
                    self.assertTrue(tree.has_focus)
                    if dismiss_key == "y":
                        self.assertEqual(
                            [collection.name for collection in app.state.collections],
                            ["Movies"],
                        )
                    else:
                        self.assertEqual(
                            [collection.name for collection in app.state.collections],
                            ["Books", "Movies"],
                        )

    async def test_url_submit_updates_active_request(self) -> None:
        app = build_test_app()
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            url="https://example.com/health",
        )
        app.state.requests = [request]
        app.state.active_request_id = request.request_id

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            await pilot.press("ctrl+o", "2")
            await pilot.pause()

            inline_input = app.screen.query_one("#url-input", Input)
            self.assertTrue(inline_input.display)
            self.assertTrue(inline_input.has_focus)

            inline_input.value = "https://example.com/ready"
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(request.url, "https://example.com/ready")
            self.assertEqual(app.state.mode, "NORMAL")
            self.assertFalse(app.screen.query_one("#url-input", Input).display)

    async def test_sidebar_request_selection_opens_request(self) -> None:
        app = build_test_app()
        first = RequestDefinition(request_id="r1", name="Health")
        second = RequestDefinition(request_id="r2", name="Ready")
        app.state.requests = [first, second]
        app.state.open_request_ids = [first.request_id]
        app.state.active_request_id = first.request_id
        app.state.ensure_request_workspace()
        app.state._set_selected_sidebar_by_request_id(first.request_id)

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            tree = app.screen.query_one("#sidebar-tree")
            tree.focus()
            await pilot.pause()

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(app.state.get_selected_request().request_id, second.request_id)

            tree.action_confirm()
            await pilot.pause()

            tabs = app.screen.query_one("#open-request-tabs", Tabs)
            self.assertEqual(app.state.active_request_id, second.request_id)
            self.assertIn(second.request_id, app.state.open_request_ids)
            self.assertEqual(tabs.active, f"open-req-{second.request_id}")

    async def test_env_table_row_selection_enters_edit_and_create_flows(self) -> None:
        app = build_test_app()
        app.state.current_tab = "env"
        app.state.env_names = ["Default"]
        app.state.env_sets = {
            "Default": [EnvVariable(key="API_KEY", value="secret", description="token")]
        }
        app.state.selected_env_name = "Default"
        app.state.ensure_env_workspace()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()

            table = app.screen.query_one("#env-table")
            self.assertEqual(app.state.mode, "ENV_SELECT")

            table.action_select_cursor()
            await pilot.pause()

            env_input = app.screen.query_one("#env-field-input", Input)
            self.assertEqual(app.state.mode, "ENV_EDIT")
            self.assertFalse(app.state.env_creating_new)
            self.assertTrue(env_input.display)
            self.assertEqual(env_input.value, "API_KEY")

            await pilot.press("escape")
            await pilot.pause()

            table.move_cursor(row=1, column=0, animate=False)
            table.action_select_cursor()
            await pilot.pause()

            self.assertEqual(app.state.mode, "ENV_EDIT")
            self.assertTrue(app.state.env_creating_new)
            self.assertTrue(env_input.display)
            self.assertEqual(env_input.value, "")
            self.assertEqual(env_input.placeholder, "Env variable")

    async def test_env_field_selection_updates_edit_input_value(self) -> None:
        app = build_test_app()
        app.state.current_tab = "env"
        app.state.env_names = ["Default"]
        app.state.env_sets = {
            "Default": [EnvVariable(key="API_KEY", value="secret", description="token")]
        }
        app.state.selected_env_name = "Default"
        app.state.ensure_env_workspace()

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            await pilot.press("e")
            await pilot.pause()

            await pilot.press("l")
            await pilot.pause()

            table = app.screen.query_one("#env-table")
            table.action_select_cursor()
            await pilot.pause()

            env_input = app.screen.query_one("#env-field-input", Input)
            self.assertEqual(app.state.mode, "ENV_EDIT")
            self.assertEqual(env_input.value, "secret")
            self.assertEqual(env_input.placeholder, "Env value")

    async def test_history_selection_updates_detail_view(self) -> None:
        app = build_test_app()
        app.state.current_tab = "history"
        app.state.history_entries = [
            HistoryEntry(
                history_id="h1",
                source_request_name="Health Check",
                source_request_path="Demo / Health Check",
                method="GET",
                url="https://example.com/health",
                auth_type="none",
                auth_location="header",
                auth_name="Authorization",
                response_body='{"ok":true}',
                status_code=200,
                response_size=11,
            ),
            HistoryEntry(
                history_id="h2",
                source_request_name="Readiness Probe",
                source_request_path="Demo / Readiness Probe",
                method="POST",
                url="https://example.com/ready",
                auth_type="none",
                auth_location="header",
                auth_name="Authorization",
                response_body='{"ready":true}',
                status_code=202,
                response_size=14,
            ),
        ]

        async with app.run_test(size=(140, 40)) as pilot:
            app._refresh_screen()
            await pilot.pause()

            history_list = app.screen.query_one("#history-list")
            history_detail = app.screen.query_one("#history-detail", Static)
            before = render_plain(getattr(history_detail, "_Static__content"))

            self.assertEqual(history_list.cursor_row, 0)
            self.assertIn("Health Check", before)

            await pilot.press("j")
            await pilot.pause()

            after = render_plain(getattr(history_detail, "_Static__content"))

            self.assertEqual(app.state.selected_history_index, 1)
            self.assertEqual(history_list.cursor_row, 1)
            self.assertIn("Readiness Probe", after)
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
