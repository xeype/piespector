from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class CollectionDefinition:
    collection_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Collection"


@dataclass
class FolderDefinition:
    folder_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "New Folder"
    collection_id: str = ""
    parent_folder_id: str | None = None


@dataclass
class SidebarNode:
    kind: str
    node_id: str
    label: str
    depth: int = 0
    request_id: str | None = None
    request_index: int | None = None
    method: str = ""
