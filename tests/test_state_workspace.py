from __future__ import annotations

import unittest

from piespector.state import (
    CollectionDefinition,
    FolderDefinition,
    PiespectorState,
    RequestDefinition,
)


class WorkspaceIndexTests(unittest.TestCase):
    def test_id_lookups_reindex_on_direct_assignment(self) -> None:
        state = PiespectorState()
        collection = CollectionDefinition(collection_id="c1", name="Alpha")
        folder = FolderDefinition(
            folder_id="f1",
            name="Auth",
            collection_id=collection.collection_id,
        )
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
            folder_id=folder.folder_id,
        )

        state.collections = [collection]
        state.folders = [folder]
        state.requests = [request]

        self.assertIs(state.get_collection_by_id(collection.collection_id), collection)
        self.assertIs(state.get_folder_by_id(folder.folder_id), folder)
        self.assertIs(state.get_request_by_id(request.request_id), request)

    def test_copy_collection_updates_lookup_indices_for_new_items(self) -> None:
        collection = CollectionDefinition(collection_id="c1", name="Alpha")
        folder = FolderDefinition(
            folder_id="f1",
            name="Auth",
            collection_id=collection.collection_id,
        )
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
            folder_id=folder.folder_id,
        )
        state = PiespectorState(
            collections=[collection],
            folders=[folder],
            requests=[request],
        )

        copied_collection = state.copy_collection(collection.collection_id)

        self.assertIsNotNone(copied_collection)
        assert copied_collection is not None
        copied_folder = next(
            item
            for item in state.folders
            if item.collection_id == copied_collection.collection_id
        )
        copied_request = next(
            item
            for item in state.requests
            if item.collection_id == copied_collection.collection_id
        )
        self.assertIs(
            state.get_collection_by_id(copied_collection.collection_id),
            copied_collection,
        )
        self.assertIs(state.get_folder_by_id(copied_folder.folder_id), copied_folder)
        self.assertIs(state.get_request_by_id(copied_request.request_id), copied_request)

    def test_delete_selected_request_removes_request_lookup(self) -> None:
        request = RequestDefinition(request_id="r1", name="Health")
        state = PiespectorState(requests=[request])
        state.ensure_request_workspace()
        state._set_selected_sidebar_by_request_id(request.request_id)

        deleted = state.delete_selected_request()

        self.assertIs(deleted, request)
        self.assertIsNone(state.get_request_by_id(request.request_id))

    def test_delete_selected_collection_removes_nested_lookups(self) -> None:
        collection = CollectionDefinition(collection_id="c1", name="Alpha")
        folder = FolderDefinition(
            folder_id="f1",
            name="Auth",
            collection_id=collection.collection_id,
        )
        request = RequestDefinition(
            request_id="r1",
            name="Health",
            collection_id=collection.collection_id,
            folder_id=folder.folder_id,
        )
        state = PiespectorState(
            collections=[collection],
            folders=[folder],
            requests=[request],
        )
        state._set_selected_sidebar_node("collection", collection.collection_id)

        deleted = state.delete_selected_collection()

        self.assertIs(deleted, collection)
        self.assertIsNone(state.get_collection_by_id(collection.collection_id))
        self.assertIsNone(state.get_folder_by_id(folder.folder_id))
        self.assertIsNone(state.get_request_by_id(request.request_id))


if __name__ == "__main__":
    unittest.main()
