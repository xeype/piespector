from __future__ import annotations

import unittest
from unittest.mock import patch

from textual.binding import Binding

from piespector.app import PiespectorApp
from piespector.commands import command_palette_commands
from piespector.domain.editor import TAB_HOME
from piespector.domain.modes import (
    MODE_HOME_AUTH_EDIT,
    MODE_HOME_AUTH_LOCATION_EDIT,
    MODE_HOME_AUTH_SELECT,
    MODE_HOME_AUTH_TYPE_EDIT,
    MODE_HOME_BODY_EDIT,
    MODE_HOME_BODY_RAW_TYPE_EDIT,
    MODE_HOME_BODY_SELECT,
    MODE_HOME_BODY_TYPE_EDIT,
    MODE_ENV_SELECT,
    MODE_HOME_HEADERS_EDIT,
    MODE_NORMAL,
    MODE_HOME_HEADERS_SELECT,
    MODE_HOME_PARAMS_EDIT,
    MODE_HOME_PARAMS_SELECT,
    MODE_HOME_REQUEST_EDIT,
    MODE_HOME_REQUEST_METHOD_EDIT,
    MODE_HOME_REQUEST_METHOD_SELECT,
    MODE_HOME_REQUEST_SELECT,
    MODE_HOME_RESPONSE_SELECT,
    MODE_HOME_SECTION_SELECT,
    MODE_HOME_URL_EDIT,
    MODE_JUMP,
)
from piespector.screens.home.controller import HomeController
from piespector.domain.workspace import CollectionDefinition, FolderDefinition
from piespector.widget.tree import PiespectorTree as SidebarTree
from piespector.state import PiespectorState, RequestDefinition
from piespector.ui.help_panel import _hide_binding
from piespector.ui.input import PiespectorInput


class FakeKeyEvent:
    def __init__(self, key: str, character: str | None = None) -> None:
        self.key = key
        self.character = character
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class AppCommandModeTests(unittest.TestCase):
    def assertBoundMethod(self, actual, expected) -> None:
        self.assertIs(actual.__self__, expected.__self__)
        self.assertIs(actual.__func__, expected.__func__)

    def test_home_controller_builds_dispatch_from_section_registrations(self) -> None:
        app = PiespectorApp()

        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_SECTION_SELECT],
            app.home_controller.navigation.handle_home_section_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_REQUEST_SELECT],
            app.home_controller.request.handle_home_request_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_REQUEST_EDIT],
            app.home_controller.request.handle_home_request_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_REQUEST_METHOD_SELECT],
            app.home_controller.request.handle_home_request_method_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_URL_EDIT],
            app.home_controller.request.handle_home_url_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_AUTH_SELECT],
            app.home_controller.auth.handle_home_auth_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_AUTH_EDIT],
            app.home_controller.auth.handle_home_auth_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_AUTH_TYPE_EDIT],
            app.home_controller.auth.handle_home_auth_type_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_AUTH_LOCATION_EDIT],
            app.home_controller.auth.handle_home_auth_location_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_PARAMS_SELECT],
            app.home_controller.params.handle_home_params_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_PARAMS_EDIT],
            app.home_controller.params.handle_home_params_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_HEADERS_SELECT],
            app.home_controller.headers.handle_home_headers_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_HEADERS_EDIT],
            app.home_controller.headers.handle_home_headers_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_BODY_SELECT],
            app.home_controller.body.handle_home_body_select_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_BODY_TYPE_EDIT],
            app.home_controller.body.handle_home_body_type_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_BODY_RAW_TYPE_EDIT],
            app.home_controller.body.handle_home_body_raw_type_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_BODY_EDIT],
            app.home_controller.body.handle_home_body_edit_key,
        )
        self.assertBoundMethod(
            app.home_controller._dispatch[MODE_HOME_RESPONSE_SELECT],
            app.home_controller.response.handle_home_response_select_key,
        )

    def test_home_controller_rejects_duplicate_mode_registrations(self) -> None:
        app = PiespectorApp()

        class DuplicateModeController:
            def __init__(self, handler):
                self._handler = handler

            def mode_handlers(self) -> dict[str, object]:
                return {MODE_HOME_REQUEST_SELECT: self._handler}

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate home mode handler registration for HOME_REQUEST_SELECT",
        ):
            HomeController._build_dispatch(
                (
                    app.home_controller.request,
                    DuplicateModeController(app.home_controller.auth.handle_home_auth_select_key),
                )
            )

    def test_session_moves_screen_local_fields_out_of_session_root(self) -> None:
        state = PiespectorState(
            home_editor_tab="auth",
            selected_env_index=2,
            selected_history_response_tab="headers",
        )

        self.assertFalse(hasattr(state.session, "home_editor_tab"))
        self.assertFalse(hasattr(state.session, "selected_env_index"))
        self.assertFalse(hasattr(state.session, "selected_history_response_tab"))
        self.assertEqual(state.session.home.home_editor_tab, "auth")
        self.assertEqual(state.session.env.selected_env_index, 2)
        self.assertEqual(state.session.history.selected_history_response_tab, "headers")

    def test_app_keeps_home_state_in_session_and_attaches_other_screen_state(self) -> None:
        app = PiespectorApp()

        app.state.home_editor_tab = "auth"
        app.state.selected_env_index = 3
        app.state.selected_history_response_tab = "headers"

        self.assertEqual(app.state.session.home.home_editor_tab, "auth")
        self.assertFalse(hasattr(app._home_screen, "home_editor_tab"))
        self.assertEqual(app._env_screen.selected_env_index, 3)
        self.assertEqual(app._history_screen.selected_history_response_tab, "headers")

    def test_command_mode_escape_leaves_mode(self) -> None:
        app = PiespectorApp()
        app.state.enter_command_mode()
        event = FakeKeyEvent("escape")

        with patch.object(
            app,
            "_refresh_screen",
        ):
            app.interaction_controller.handle_command_key(event)

        self.assertEqual(app.state.mode, MODE_NORMAL)
        self.assertTrue(event.stopped)

    def test_command_mode_suggestions_follow_current_tab_context(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.mode = MODE_NORMAL

        labels = [entry.label for entry in command_palette_commands(app.state)]

        self.assertIn("import PATH", labels)
        self.assertNotIn("q", labels)

    def test_system_commands_rename_keys_to_help(self) -> None:
        app = PiespectorApp()

        async def exercise() -> None:
            async with app.run_test(size=(140, 40)):
                titles = [command.title for command in app.get_system_commands(app.screen)]

                self.assertIn("Help", titles)
                self.assertNotIn("Keys", titles)

        import asyncio

        asyncio.run(exercise())

    def test_home_command_palette_does_not_include_send(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.current_tab = "home"
        app.state.requests = [request]
        app.state.ensure_request_workspace()
        app.state._set_selected_sidebar_by_request_id(request.request_id)

        labels = [entry.label for entry in command_palette_commands(app.state)]

        self.assertNotIn("send", labels)
        self.assertNotIn("close", labels)

    def test_home_normal_s_sends_selected_request(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = TAB_HOME
        app.state.mode = MODE_NORMAL
        event = FakeKeyEvent("s", "s")

        with patch.object(app, "_send_selected_request") as send_request:
            handled = app.home_controller.handle_home_view_key(event)

        self.assertTrue(handled)
        send_request.assert_called_once_with()
        self.assertTrue(event.stopped)

    def test_home_normal_c_closes_opened_request(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.current_tab = TAB_HOME
        app.state.mode = MODE_NORMAL
        app.state.requests = [request]
        app.state.open_request_ids = [request.request_id]
        app.state.active_request_id = request.request_id
        event = FakeKeyEvent("c", "c")

        with patch.object(app, "_refresh_viewport") as refresh_viewport:
            handled = app.home_controller.handle_home_view_key(event)

        self.assertTrue(handled)
        self.assertIsNone(app.state.active_request_id)
        self.assertEqual(app.state.open_request_ids, [])
        refresh_viewport.assert_called_once_with()
        self.assertTrue(event.stopped)

    def test_history_response_select_j_cycles_detail_block(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "history"
        app.state.mode = "HISTORY_RESPONSE_SELECT"
        app.state.selected_history_detail_block = "request"
        event = FakeKeyEvent("j")

        with patch.object(app, "_refresh_viewport"):
            app.history_controller.handle_history_response_select_key(event)

        self.assertEqual(app.state.selected_history_detail_block, "response")
        self.assertTrue(event.stopped)

    def test_history_response_select_h_and_l_cycle_tabs(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "history"
        app.state.mode = "HISTORY_RESPONSE_SELECT"
        app.state.selected_history_detail_block = "response"
        app.state.selected_history_response_tab = "body"
        left_event = FakeKeyEvent("h")
        right_event = FakeKeyEvent("l")

        with patch.object(app, "_refresh_viewport"):
            app.history_controller.handle_history_response_select_key(left_event)
            left_tab = app.state.selected_history_response_tab
            app.history_controller.handle_history_response_select_key(right_event)

        self.assertEqual(left_tab, "headers")
        self.assertEqual(app.state.selected_history_response_tab, "body")
        self.assertTrue(left_event.stopped)
        self.assertTrue(right_event.stopped)

    def test_auth_select_escape_returns_to_auth_type_tabs(self) -> None:
        app = PiespectorApp()
        app.state.home_editor_tab = "auth"
        request = RequestDefinition(auth_type="bearer", auth_bearer_token="token")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.mode = "HOME_AUTH_SELECT"
        app.state.selected_auth_index = 2
        event = FakeKeyEvent("escape")

        with patch.object(app, "_refresh_screen"):
            app.home_controller.auth.handle_home_auth_select_key(event)

        self.assertEqual(app.state.mode, "HOME_SECTION_SELECT")
        self.assertEqual(app.state.auth_type_label(), "Bearer Token")
        self.assertTrue(event.stopped)

    def test_jump_escape_restores_previous_mode(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.mode = MODE_ENV_SELECT
        app.state.enter_jump_mode()
        event = FakeKeyEvent("escape")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.mode, MODE_ENV_SELECT)
        self.assertEqual(app.state.current_tab, "env")
        self.assertTrue(event.stopped)

    def test_jump_unknown_key_stays_in_jump_mode(self) -> None:
        app = PiespectorApp()
        app.state.mode = MODE_ENV_SELECT
        app.state.enter_jump_mode()
        event = FakeKeyEvent("x", "x")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.mode, MODE_JUMP)
        self.assertTrue(event.stopped)

    def test_jump_to_request_lands_on_request_tab_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.current_tab = "env"
        app.state.mode = MODE_ENV_SELECT
        app.state.enter_jump_mode()
        event = FakeKeyEvent("q", "q")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.current_tab, TAB_HOME)
        self.assertEqual(app.state.mode, MODE_HOME_SECTION_SELECT)
        self.assertEqual(app.state.home_editor_tab, "request")
        self.assertTrue(event.stopped)

    def test_jump_tab_returns_to_home_collections_block(self) -> None:
        app = PiespectorApp()
        app.state.current_tab = "env"
        app.state.mode = MODE_ENV_SELECT
        app.state.enter_jump_mode()
        event = FakeKeyEvent("tab")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.current_tab, TAB_HOME)
        self.assertEqual(app.state.mode, MODE_NORMAL)
        self.assertTrue(event.stopped)

    def test_jump_to_headers_lands_on_headers_tab_select(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_jump_mode()
        event = FakeKeyEvent("r", "r")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.current_tab, TAB_HOME)
        self.assertEqual(app.state.mode, MODE_HOME_SECTION_SELECT)
        self.assertEqual(app.state.home_editor_tab, "headers")
        self.assertTrue(event.stopped)

    def test_jump_to_response_headers_enters_response_select_mode(self) -> None:
        app = PiespectorApp()
        request = RequestDefinition(name="Health")
        app.state.requests = [request]
        app.state.active_request_id = request.request_id
        app.state.enter_jump_mode()
        event = FakeKeyEvent("s", "s")

        with patch.object(app, "_refresh_screen"):
            app.interaction_controller.handle_jump_key(event)

        self.assertEqual(app.state.current_tab, TAB_HOME)
        self.assertEqual(app.state.mode, MODE_HOME_RESPONSE_SELECT)
        self.assertEqual(app.state.selected_home_response_tab, "headers")
        self.assertTrue(event.stopped)

    def test_select_folder_traverses_nested_collection_folders_and_expands_ancestors(self) -> None:
        state = PiespectorState()
        collection = CollectionDefinition(collection_id="c1", name="Alpha")
        parent_folder = FolderDefinition(
            folder_id="f1",
            name="Parent",
            collection_id=collection.collection_id,
        )
        child_folder = FolderDefinition(
            folder_id="f2",
            name="Child",
            collection_id=collection.collection_id,
            parent_folder_id=parent_folder.folder_id,
        )
        sibling_folder = FolderDefinition(
            folder_id="f3",
            name="Sibling",
            collection_id=collection.collection_id,
        )
        state.collections = [collection]
        state.folders = [parent_folder, child_folder, sibling_folder]
        state.collapsed_collection_ids = {collection.collection_id}
        state.collapsed_folder_ids = {parent_folder.folder_id}
        state.selected_sidebar_index = 0

        self.assertTrue(state.select_folder(1))
        first_node = state.get_selected_sidebar_node()
        self.assertIsNotNone(first_node)
        self.assertEqual(first_node.kind, "folder")
        self.assertEqual(first_node.node_id, parent_folder.folder_id)
        self.assertIn(parent_folder.folder_id, state.collapsed_folder_ids)

        self.assertTrue(state.select_folder(1))
        second_node = state.get_selected_sidebar_node()
        self.assertIsNotNone(second_node)
        self.assertEqual(second_node.kind, "folder")
        self.assertEqual(second_node.node_id, child_folder.folder_id)
        self.assertNotIn(collection.collection_id, state.collapsed_collection_ids)
        self.assertNotIn(parent_folder.folder_id, state.collapsed_folder_ids)

    def test_home_action_ctrl_j_moves_between_collections(self) -> None:
        app = PiespectorApp()
        first_collection = CollectionDefinition(collection_id="c1", name="Alpha")
        second_collection = CollectionDefinition(collection_id="c2", name="Beta")
        app.state.collections = [first_collection, second_collection]
        app.state.selected_sidebar_index = 0

        with patch.object(app, "_refresh_viewport"), patch.object(app, "_sync_home_sidebar_cursor"):
            app.action_home_next_collection()

        selected = app.state.get_selected_sidebar_node()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.kind, "collection")
        self.assertEqual(selected.node_id, second_collection.collection_id)

    def test_home_view_arrow_down_does_not_move_sidebar(self) -> None:
        app = PiespectorApp()
        requests = [
            RequestDefinition(request_id="r1", name="One", method="GET"),
            RequestDefinition(request_id="r2", name="Two", method="GET"),
        ]
        app.state.requests = requests
        app.state.selected_sidebar_index = 0
        event = FakeKeyEvent("down")

        handled = app.home_controller.handle_home_view_key(event)

        self.assertFalse(handled)
        self.assertEqual(app.state.selected_sidebar_index, 0)
        self.assertFalse(event.stopped)

    def test_home_view_arrow_right_does_not_cycle_open_requests(self) -> None:
        app = PiespectorApp()
        requests = [
            RequestDefinition(request_id="r1", name="One", method="GET"),
            RequestDefinition(request_id="r2", name="Two", method="GET"),
        ]
        app.state.requests = requests
        app.state.open_request_ids = [request.request_id for request in requests]
        app.state.active_request_id = requests[0].request_id
        event = FakeKeyEvent("right")

        handled = app.home_controller.handle_home_view_key(event)

        self.assertFalse(handled)
        self.assertEqual(app.state.active_request_id, requests[0].request_id)
        self.assertFalse(event.stopped)

    def test_home_action_l_cycles_open_requests(self) -> None:
        app = PiespectorApp()
        requests = [
            RequestDefinition(request_id="r1", name="One", method="GET"),
            RequestDefinition(request_id="r2", name="Two", method="GET"),
        ]
        app.state.requests = requests
        app.state.open_request_ids = [request.request_id for request in requests]
        app.state.active_request_id = requests[0].request_id

        with patch.object(app, "_refresh_viewport"):
            app.action_home_next_open_request()

        self.assertEqual(app.state.active_request_id, requests[1].request_id)

    def test_sidebar_tree_bindings(self) -> None:
        binding_keys = {binding.key for binding in SidebarTree.BINDINGS}

        # Arrow keys and Enter stripped — app controller drives these via
        # programmatic action calls to avoid conflicts with normal-mode navigation.
        self.assertNotIn("up", binding_keys)
        self.assertNotIn("down", binding_keys)
        self.assertNotIn("left", binding_keys)
        self.assertNotIn("right", binding_keys)
        self.assertNotIn("shift+left", binding_keys)
        self.assertNotIn("shift+right", binding_keys)
        self.assertNotIn("shift+up", binding_keys)
        self.assertNotIn("shift+down", binding_keys)
        self.assertNotIn("enter", binding_keys)

        # Vim aliases handled directly on the widget when it owns focus.
        self.assertIn("j", binding_keys)
        self.assertIn("k", binding_keys)
        self.assertIn("e", binding_keys)
        self.assertNotIn("space", binding_keys)
        self.assertNotIn("shift+space", binding_keys)

    def test_home_bindings_include_j_k_variants_for_keys_panel(self) -> None:
        binding_by_key = {binding.key: binding for binding in PiespectorApp.BINDINGS}

        self.assertEqual(binding_by_key["j"].description, "Browse Down")
        self.assertEqual(binding_by_key["k"].description, "Browse Up")
        self.assertEqual(binding_by_key["J"].description, "Next Folder")
        self.assertEqual(binding_by_key["K"].description, "Previous Folder")
        self.assertEqual(binding_by_key["ctrl+j"].description, "Next Collection")
        self.assertEqual(binding_by_key["ctrl+k"].description, "Previous Collection")
        self.assertEqual(binding_by_key["h"].description, "Previous Pinned Request")
        self.assertEqual(binding_by_key["l"].description, "Next Pinned Request")

    def test_piespector_input_removes_copy_binding(self) -> None:
        self.assertFalse(
            any(binding.action == "copy" for binding in PiespectorInput.BINDINGS)
        )

    def test_help_panel_filters_ctrl_c_and_super_c_bindings(self) -> None:
        self.assertTrue(_hide_binding(Binding("ctrl+c,super+c", "copy", "Copy")))
        self.assertFalse(_hide_binding(Binding("ctrl+v", "paste", "Paste")))


if __name__ == "__main__":
    unittest.main()
