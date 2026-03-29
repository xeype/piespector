from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from piespector.domain.history import HistoryEntry
from piespector.domain.requests import (
    RequestDefinition,
    RequestKeyValue,
    parse_headers_text,
    parse_query_text,
)
from piespector.domain.workspace import (
    CollectionDefinition,
    FolderDefinition,
)


ENV_FILE_NAME = ".env"
ENV_WORKSPACE_FILE_NAME = ".piespector.env.json"
REQUESTS_FILE_NAME = ".piespector.requests.json"
HISTORY_FILE_NAME = ".piespector.history.jsonl"
APP_DATA_DIRECTORY_NAME = "piespector"


def app_data_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return base_dir

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_DATA_DIRECTORY_NAME
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return Path(appdata).expanduser() / APP_DATA_DIRECTORY_NAME
        return home / "AppData" / "Roaming" / APP_DATA_DIRECTORY_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / APP_DATA_DIRECTORY_NAME
    return home / ".local" / "share" / APP_DATA_DIRECTORY_NAME


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def env_file_path(base_dir: Path | None = None) -> Path:
    root = app_data_dir(base_dir)
    return root / ENV_FILE_NAME


def env_workspace_path(base_dir: Path | None = None) -> Path:
    root = app_data_dir(base_dir)
    return root / ENV_WORKSPACE_FILE_NAME


def requests_file_path(base_dir: Path | None = None) -> Path:
    root = app_data_dir(base_dir)
    return root / REQUESTS_FILE_NAME


def history_file_path(base_dir: Path | None = None) -> Path:
    root = app_data_dir(base_dir)
    return root / HISTORY_FILE_NAME


def load_env_pairs(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    env_pairs: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _parse_env_value(value.strip())
        if key:
            env_pairs[key] = value

    return env_pairs


def save_env_pairs(path: Path, env_pairs: dict[str, str]) -> None:
    lines = [f"{key}={_format_env_value(value)}" for key, value in env_pairs.items()]
    content = "\n".join(lines)
    if content:
        content += "\n"
    ensure_parent_dir(path)
    path.write_text(content, encoding="utf-8")


def export_env_pairs(path: Path, env_pairs: dict[str, str]) -> None:
    save_env_pairs(path, env_pairs)


def import_env_sets(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    if path.suffix.lower() == ".json":
        env_names, env_sets, _selected_env_name = load_env_workspace(path, None)
        if env_names:
            return (env_names, env_sets)

    env_name = path.stem.strip() or "Imported"
    return ([env_name], {env_name: load_env_pairs(path)})


def load_env_workspace(
    path: Path,
    legacy_env_path: Path | None = None,
) -> tuple[list[str], dict[str, dict[str, str]], str]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_envs = payload.get("envs", [])
            env_order: list[str] = []
            env_sets: dict[str, dict[str, str]] = {}
            for item in raw_envs:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name or name in env_sets:
                    continue
                raw_pairs = item.get("pairs", {})
                pairs = (
                    {
                        str(key): str(value)
                        for key, value in raw_pairs.items()
                        if str(key).strip()
                    }
                    if isinstance(raw_pairs, dict)
                    else {}
                )
                env_order.append(name)
                env_sets[name] = pairs
            if env_order:
                selected_env_name = str(payload.get("selected_env_name", "")).strip()
                if selected_env_name not in env_sets:
                    selected_env_name = env_order[0]
                return (env_order, env_sets, selected_env_name)

    if legacy_env_path is not None and legacy_env_path.exists():
        pairs = load_env_pairs(legacy_env_path)
        return (["Default"], {"Default": pairs}, "Default")

    return (["Default"], {"Default": {}}, "Default")


def save_env_workspace(
    path: Path,
    env_order: list[str],
    env_sets: dict[str, dict[str, str]],
    selected_env_name: str,
) -> None:
    ordered_names = [name for name in env_order if name in env_sets]
    if not ordered_names:
        ordered_names = ["Default"]
        env_sets = {"Default": {}}
        selected_env_name = "Default"
    if selected_env_name not in env_sets:
        selected_env_name = ordered_names[0]
    payload = {
        "selected_env_name": selected_env_name,
        "envs": [
            {
                "name": name,
                "pairs": {
                    key: value
                    for key, value in env_sets.get(name, {}).items()
                },
            }
            for name in ordered_names
        ],
    }
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_request_workspace(
    path: Path,
) -> tuple[
    list[CollectionDefinition],
    list[FolderDefinition],
    list[RequestDefinition],
    set[str],
    set[str],
]:
    if not path.exists():
        return ([], [], [], set(), set())

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return ([], [], _load_requests_payload(payload), set(), set())

    collections: list[CollectionDefinition] = []
    for item in payload.get("collections", []):
        if not isinstance(item, dict):
            continue
        collections.append(
            CollectionDefinition(
                collection_id=item.get("collection_id") or uuid4().hex,
                name=str(item.get("name", "New Collection")),
            )
        )

    folders: list[FolderDefinition] = []
    for item in payload.get("folders", []):
        if not isinstance(item, dict):
            continue
        collection_id = str(item.get("collection_id", "")).strip()
        if not collection_id:
            continue
        parent_folder_id = item.get("parent_folder_id")
        folders.append(
            FolderDefinition(
                folder_id=item.get("folder_id") or uuid4().hex,
                name=str(item.get("name", "New Folder")),
                collection_id=collection_id,
                parent_folder_id=str(parent_folder_id) if parent_folder_id else None,
            )
        )

    requests = _load_requests_payload(payload.get("requests", []))
    collection_ids = {collection.collection_id for collection in collections}
    folder_ids = {folder.folder_id for folder in folders}

    raw_collapsed_collections = payload.get("collapsed_collection_ids")
    if isinstance(raw_collapsed_collections, list):
        collapsed_collection_ids = {
            str(item)
            for item in raw_collapsed_collections
            if str(item) in collection_ids
        }
    else:
        collapsed_collection_ids = set(collection_ids)

    raw_collapsed_folders = payload.get("collapsed_folder_ids")
    if isinstance(raw_collapsed_folders, list):
        collapsed_folder_ids = {
            str(item)
            for item in raw_collapsed_folders
            if str(item) in folder_ids
        }
    else:
        collapsed_folder_ids = set(folder_ids)

    return (
        collections,
        folders,
        requests,
        collapsed_collection_ids,
        collapsed_folder_ids,
    )


def load_requests(path: Path) -> list[RequestDefinition]:
    return load_request_workspace(path)[2]


def export_collection_workspace(
    path: Path,
    collections: list[CollectionDefinition],
    folders: list[FolderDefinition],
    requests: list[RequestDefinition],
    *,
    collection_ids: set[str] | None = None,
) -> int:
    included_collection_ids = (
        {
            collection.collection_id
            for collection in collections
        }
        if collection_ids is None
        else {
            collection.collection_id
            for collection in collections
            if collection.collection_id in collection_ids
        }
    )
    exported_collections = [
        collection
        for collection in collections
        if collection.collection_id in included_collection_ids
    ]
    exported_folders = [
        folder
        for folder in folders
        if folder.collection_id in included_collection_ids
    ]
    exported_folder_ids = {folder.folder_id for folder in exported_folders}
    exported_requests = [
        request
        for request in requests
        if (
            not request.transient
            and request.collection_id in included_collection_ids
            and (
                request.folder_id is None
                or request.folder_id in exported_folder_ids
            )
        )
    ]
    save_request_workspace(
        path,
        exported_collections,
        exported_folders,
        exported_requests,
        set(),
        set(),
    )
    return len(exported_collections)


def import_collection_workspace(
    path: Path,
) -> tuple[list[CollectionDefinition], list[FolderDefinition], list[RequestDefinition]]:
    collections, folders, requests, _collapsed_collection_ids, _collapsed_folder_ids = (
        load_request_workspace(path)
    )
    collection_ids = {collection.collection_id for collection in collections}
    folders = [
        folder
        for folder in folders
        if folder.collection_id in collection_ids
    ]
    folder_ids = {folder.folder_id for folder in folders}
    requests = [
        request
        for request in requests
        if request.collection_id in collection_ids
        and (
            request.folder_id is None
            or request.folder_id in folder_ids
        )
    ]
    return (collections, folders, requests)


def load_history_entries(path: Path) -> list[HistoryEntry]:
    if not path.exists():
        return []

    entries: list[HistoryEntry] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        entries.append(_load_history_entry(item))
    entries.reverse()
    return entries


def append_history_entry(path: Path, entry: HistoryEntry) -> None:
    payload = {
        "history_id": entry.history_id,
        "created_at": entry.created_at,
        "source_request_id": entry.source_request_id,
        "source_request_name": entry.source_request_name,
        "source_request_path": entry.source_request_path,
        "method": entry.method,
        "url": entry.url,
        "auth_type": entry.auth_type,
        "auth_location": entry.auth_location,
        "auth_name": entry.auth_name,
        "request_headers": [
            {"key": key, "value": value}
            for key, value in entry.request_headers
        ],
        "request_body": entry.request_body,
        "request_body_type": entry.request_body_type,
        "status_code": entry.status_code,
        "elapsed_ms": entry.elapsed_ms,
        "response_size": entry.response_size,
        "response_headers": [
            {"key": key, "value": value}
            for key, value in entry.response_headers
        ],
        "response_body": entry.response_body,
        "error": entry.error,
    }
    ensure_parent_dir(path)
    with path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(payload) + "\n")


def save_history_entries(path: Path, entries: list[HistoryEntry]) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as history_file:
        for entry in reversed(entries):
            payload = {
                "history_id": entry.history_id,
                "created_at": entry.created_at,
                "source_request_id": entry.source_request_id,
                "source_request_name": entry.source_request_name,
                "source_request_path": entry.source_request_path,
                "method": entry.method,
                "url": entry.url,
                "auth_type": entry.auth_type,
                "auth_location": entry.auth_location,
                "auth_name": entry.auth_name,
                "request_headers": [
                    {"key": key, "value": value}
                    for key, value in entry.request_headers
                ],
                "request_body": entry.request_body,
                "request_body_type": entry.request_body_type,
                "status_code": entry.status_code,
                "elapsed_ms": entry.elapsed_ms,
                "response_size": entry.response_size,
                "response_headers": [
                    {"key": key, "value": value}
                    for key, value in entry.response_headers
                ],
                "response_body": entry.response_body,
                "error": entry.error,
            }
            history_file.write(json.dumps(payload) + "\n")


def _load_requests_payload(payload: object) -> list[RequestDefinition]:
    requests: list[RequestDefinition] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        requests.append(
            RequestDefinition(
                request_id=item.get("request_id") or uuid4().hex,
                name=item.get("name", "New Request"),
                method=item.get("method", "GET"),
                url=item.get("url", ""),
                collection_id=_normalize_optional_id(item.get("collection_id")),
                folder_id=_normalize_optional_id(item.get("folder_id")),
                query_items=_load_request_items(
                    item.get("query_items"),
                    item.get("query_text", ""),
                ),
                header_items=_load_request_items(
                    item.get("header_items"),
                    item.get("headers_text", ""),
                    is_headers=True,
                ),
                auth_type=_normalize_auth_type(item.get("auth_type", "none")),
                auth_basic_username=str(item.get("auth_basic_username", "")),
                auth_basic_password=str(item.get("auth_basic_password", "")),
                auth_bearer_prefix=str(item.get("auth_bearer_prefix", "Bearer")),
                auth_bearer_token=str(item.get("auth_bearer_token", "")),
                auth_api_key_name=str(item.get("auth_api_key_name", "X-API-Key")),
                auth_api_key_value=str(item.get("auth_api_key_value", "")),
                auth_api_key_location=_normalize_auth_api_key_location(
                    item.get("auth_api_key_location", "header")
                ),
                auth_cookie_name=str(item.get("auth_cookie_name", "session")),
                auth_cookie_value=str(item.get("auth_cookie_value", "")),
                auth_custom_header_name=str(
                    item.get("auth_custom_header_name", "X-Auth-Token")
                ),
                auth_custom_header_value=str(item.get("auth_custom_header_value", "")),
                auth_oauth_token_url=str(item.get("auth_oauth_token_url", "")),
                auth_oauth_client_id=str(item.get("auth_oauth_client_id", "")),
                auth_oauth_client_secret=str(item.get("auth_oauth_client_secret", "")),
                auth_oauth_client_authentication=_normalize_auth_oauth_client_authentication(
                    item.get("auth_oauth_client_authentication", "basic-header")
                ),
                auth_oauth_header_prefix=str(item.get("auth_oauth_header_prefix", "Bearer")),
                auth_oauth_scope=str(item.get("auth_oauth_scope", "")),
                disabled_auto_headers=_load_disabled_auto_headers(item),
                body_type=_normalize_body_type(item.get("body_type", "none")),
                raw_subtype=_normalize_raw_subtype(item.get("raw_subtype", "json")),
                body_text=item.get("body_text", ""),
                raw_body_texts=_load_body_text_map(item.get("raw_body_texts")),
                graphql_body_text=str(item.get("graphql_body_text", "")),
                binary_file_path=str(item.get("binary_file_path", "")),
                body_form_items=_load_request_items(
                    item.get("body_form_items"),
                    item.get("body_form_text", ""),
                ),
                body_urlencoded_items=_load_request_items(
                    item.get("body_urlencoded_items"),
                    item.get("body_urlencoded_text", ""),
                ),
                body_form_text=item.get("body_form_text", ""),
            )
        )
    return requests


def _load_history_entry(payload: dict[str, object]) -> HistoryEntry:
    return HistoryEntry(
        history_id=str(payload.get("history_id") or uuid4().hex),
        created_at=str(payload.get("created_at", "")),
        source_request_id=_normalize_optional_id(payload.get("source_request_id")),
        source_request_name=str(payload.get("source_request_name", "")),
        source_request_path=str(payload.get("source_request_path", "")),
        method=str(payload.get("method", "GET")),
        url=str(payload.get("url", "")),
        auth_type=str(payload.get("auth_type", "none")),
        auth_location=str(payload.get("auth_location", "")),
        auth_name=str(payload.get("auth_name", "")),
        request_headers=_load_history_headers(payload.get("request_headers")),
        request_body=str(payload.get("request_body", "")),
        request_body_type=str(payload.get("request_body_type", "none")),
        status_code=_load_history_status_code(payload.get("status_code")),
        elapsed_ms=_load_history_elapsed(payload.get("elapsed_ms")),
        response_size=_load_history_size(payload.get("response_size")),
        response_headers=_load_history_headers(payload.get("response_headers")),
        response_body=str(payload.get("response_body", "")),
        error=str(payload.get("error", "")),
    )


def save_request_workspace(
    path: Path,
    collections: list[CollectionDefinition],
    folders: list[FolderDefinition],
    requests: list[RequestDefinition],
    collapsed_collection_ids: set[str] | None = None,
    collapsed_folder_ids: set[str] | None = None,
) -> None:
    collection_ids = {collection.collection_id for collection in collections}
    folder_ids = {folder.folder_id for folder in folders}
    persisted_requests = [request for request in requests if not request.transient]
    payload = {
        "collections": [
            {
                "collection_id": collection.collection_id,
                "name": collection.name,
            }
            for collection in collections
        ],
        "folders": [
            {
                "folder_id": folder.folder_id,
                "name": folder.name,
                "collection_id": folder.collection_id,
                "parent_folder_id": folder.parent_folder_id,
            }
            for folder in folders
        ],
        "requests": [
            {
                "request_id": request.request_id,
                "name": request.name,
                "method": request.method,
                "url": request.url,
                "collection_id": request.collection_id,
                "folder_id": request.folder_id,
                "query_items": [
                    {
                        "key": item.key,
                        "value": item.value,
                        "enabled": item.enabled,
                    }
                    for item in request.query_items
                ],
                "header_items": [
                    {
                        "key": item.key,
                        "value": item.value,
                        "enabled": item.enabled,
                    }
                    for item in request.header_items
                ],
                "auth_type": request.auth_type,
                "auth_basic_username": request.auth_basic_username,
                "auth_basic_password": request.auth_basic_password,
                "auth_bearer_prefix": request.auth_bearer_prefix,
                "auth_bearer_token": request.auth_bearer_token,
                "auth_api_key_name": request.auth_api_key_name,
                "auth_api_key_value": request.auth_api_key_value,
                "auth_api_key_location": request.auth_api_key_location,
                "auth_cookie_name": request.auth_cookie_name,
                "auth_cookie_value": request.auth_cookie_value,
                "auth_custom_header_name": request.auth_custom_header_name,
                "auth_custom_header_value": request.auth_custom_header_value,
                "auth_oauth_token_url": request.auth_oauth_token_url,
                "auth_oauth_client_id": request.auth_oauth_client_id,
                "auth_oauth_client_secret": request.auth_oauth_client_secret,
                "auth_oauth_client_authentication": request.auth_oauth_client_authentication,
                "auth_oauth_header_prefix": request.auth_oauth_header_prefix,
                "auth_oauth_scope": request.auth_oauth_scope,
                "disabled_auto_headers": request.disabled_auto_headers,
                "body_type": request.body_type,
                "raw_subtype": request.raw_subtype,
                "body_text": request.body_text,
                "raw_body_texts": request.raw_body_texts,
                "graphql_body_text": request.graphql_body_text,
                "binary_file_path": request.binary_file_path,
                "body_form_items": [
                    {
                        "key": item.key,
                        "value": item.value,
                        "enabled": item.enabled,
                    }
                    for item in request.body_form_items
                ],
                "body_urlencoded_items": [
                    {
                        "key": item.key,
                        "value": item.value,
                        "enabled": item.enabled,
                    }
                    for item in request.body_urlencoded_items
                ],
                "body_form_text": "&".join(
                    f"{item.key}={item.value}" if item.value else item.key
                    for item in request.body_form_items
                    if item.key
                ),
                "body_urlencoded_text": "&".join(
                    f"{item.key}={item.value}" if item.value else item.key
                    for item in request.body_urlencoded_items
                    if item.key
                ),
            }
            for request in persisted_requests
        ],
        "collapsed_collection_ids": sorted(
            collection_id
            for collection_id in (collapsed_collection_ids or set())
            if collection_id in collection_ids
        ),
        "collapsed_folder_ids": sorted(
            folder_id
            for folder_id in (collapsed_folder_ids or set())
            if folder_id in folder_ids
        ),
    }
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_requests(path: Path, requests: list[RequestDefinition]) -> None:
    save_request_workspace(path, [], [], requests, set(), set())


def _normalize_body_type(value: object) -> str:
    body_type = str(value or "none")
    if body_type == "raw-json":
        return "raw"
    if body_type not in {
        "none",
        "form-data",
        "x-www-form-urlencoded",
        "raw",
        "graphql",
        "binary",
    }:
        return "none"
    return body_type


def _normalize_raw_subtype(value: object) -> str:
    raw_subtype = str(value or "json").lower()
    if raw_subtype not in {"text", "json", "xml", "html", "javascript"}:
        return "json"
    return raw_subtype


def _normalize_optional_id(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return (
            inner.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def _format_env_value(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _load_request_items(
    items_payload: object,
    fallback_text: str,
    *,
    is_headers: bool = False,
) -> list[RequestKeyValue]:
    if isinstance(items_payload, list):
        items: list[RequestKeyValue] = []
        for item in items_payload:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key:
                continue
            items.append(
                RequestKeyValue(
                    key=key,
                    value=str(item.get("value", "")),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return items

    parser = parse_headers_text if is_headers else parse_query_text
    return [
        RequestKeyValue(key=key, value=value)
        for key, value in parser(fallback_text)
        if key.strip()
    ]


def _load_body_text_map(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    body_texts: dict[str, str] = {}
    for key, value in payload.items():
        normalized_key = _normalize_raw_subtype(key)
        body_texts[normalized_key] = str(value)
    return body_texts


def _load_disabled_auto_headers(item: dict[object, object]) -> list[str]:
    disabled = item.get("disabled_auto_headers")
    if isinstance(disabled, list):
        return [str(value).strip() for value in disabled if str(value).strip()]
    if item.get("auto_headers_enabled", True):
        return []
    return ["Accept", "User-Agent", "Content-Type"]


def _normalize_auth_type(value: object) -> str:
    auth_type = str(value or "none").strip().lower()
    if auth_type in {
        "basic",
        "bearer",
        "api-key",
        "cookie",
        "custom-header",
        "oauth2-client-credentials",
    }:
        return auth_type
    return "none"


def _normalize_auth_api_key_location(value: object) -> str:
    location = str(value or "header").strip().lower()
    if location == "query":
        return "query"
    return "header"


def _normalize_auth_oauth_client_authentication(value: object) -> str:
    authentication = str(value or "basic-header").strip().lower()
    if authentication == "body":
        return "body"
    return "basic-header"


def _load_history_headers(payload: object) -> list[tuple[str, str]]:
    if not isinstance(payload, list):
        return []
    headers: list[tuple[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        headers.append((key, str(item.get("value", ""))))
    return headers


def _load_history_status_code(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_history_elapsed(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_history_size(value: object) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0
