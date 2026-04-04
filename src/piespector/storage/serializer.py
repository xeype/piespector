from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from piespector.domain.history import HistoryEntry
from piespector.domain.requests import (
    EnvVariable,
    RequestAuth,
    RequestBody,
    RequestDefinition,
    RequestKeyValue,
)
from piespector.domain.workspace import CollectionDefinition, FolderDefinition

from .paths import ensure_parent_dir


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
    """Import env sets as plain key/value dicts (used for merging into state)."""
    if path.suffix.lower() == ".json":
        env_names, env_sets_rich, _selected_env_name = load_env_workspace(path, None)
        if env_names:
            # Convert list[EnvVariable] → dict[str, str] for import API
            return (
                env_names,
                {
                    name: {v.key: v.value for v in variables}
                    for name, variables in env_sets_rich.items()
                },
            )

    env_name = path.stem.strip() or "Imported"
    return ([env_name], {env_name: load_env_pairs(path)})


def load_env_workspace(
    path: Path,
    legacy_env_path: Path | None = None,
) -> tuple[list[str], dict[str, list[EnvVariable]], str]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_envs = payload.get("envs", [])
            env_order: list[str] = []
            env_sets: dict[str, list[EnvVariable]] = {}
            for item in raw_envs:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name or name in env_sets:
                    continue
                variables = _load_env_variables(item)
                env_order.append(name)
                env_sets[name] = variables
            if env_order:
                selected_env_name = str(payload.get("selected_env_name", "")).strip()
                if selected_env_name not in env_sets:
                    selected_env_name = env_order[0]
                return (env_order, env_sets, selected_env_name)

    if legacy_env_path is not None and legacy_env_path.exists():
        pairs = load_env_pairs(legacy_env_path)
        variables = [EnvVariable(key=k, value=v) for k, v in pairs.items() if k]
        return (["Default"], {"Default": variables}, "Default")

    return (["Default"], {"Default": []}, "Default")


def _load_env_variables(item: dict) -> list[EnvVariable]:
    """Load env variables from a JSON env object, supporting both old and new formats."""
    # New format: variables list
    raw_variables = item.get("variables")
    if isinstance(raw_variables, list):
        result: list[EnvVariable] = []
        for v in raw_variables:
            if not isinstance(v, dict):
                continue
            key = str(v.get("key", "")).strip()
            if not key:
                continue
            result.append(EnvVariable(
                key=key,
                value=str(v.get("value", "")),
                sensitive=bool(v.get("sensitive", False)),
                description=str(v.get("description", "")),
            ))
        return result

    # Legacy format: pairs dict
    raw_pairs = item.get("pairs", {})
    if isinstance(raw_pairs, dict):
        return [
            EnvVariable(key=str(k).strip(), value=str(v))
            for k, v in raw_pairs.items()
            if str(k).strip()
        ]

    return []


def save_env_workspace(
    path: Path,
    env_order: list[str],
    env_sets: dict[str, list[EnvVariable]],
    selected_env_name: str,
) -> None:
    ordered_names = [name for name in env_order if name in env_sets]
    if not ordered_names:
        ordered_names = ["Default"]
        env_sets = {"Default": []}
        selected_env_name = "Default"
    if selected_env_name not in env_sets:
        selected_env_name = ordered_names[0]
    payload = {
        "selected_env_name": selected_env_name,
        "envs": [
            {
                "name": name,
                "variables": [
                    {
                        "key": v.key,
                        "value": v.value,
                        "sensitive": v.sensitive,
                        "description": v.description,
                    }
                    for v in env_sets.get(name, [])
                ],
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
    if not isinstance(payload, dict):
        return ([], [], [], set(), set())

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

    requests = _load_requests_payload(payload.get("requests"))
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
            _serialize_request_definition(request)
            for request in requests
            if not request.transient
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
    ensure_parent_dir(path)
    with path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(_serialize_history_entry(entry)) + "\n")


def save_history_entries(path: Path, entries: list[HistoryEntry]) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as history_file:
        for entry in reversed(entries):
            history_file.write(json.dumps(_serialize_history_entry(entry)) + "\n")


def _load_requests_payload(payload: object) -> list[RequestDefinition]:
    if not isinstance(payload, list):
        return []

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
                query_items=_load_request_items(item.get("query_items")),
                header_items=_load_request_items(item.get("header_items")),
                auth=_load_request_auth(item.get("auth")),
                disabled_auto_headers=_load_disabled_auto_headers(
                    item.get("disabled_auto_headers")
                ),
                body=_load_request_body(item.get("body")),
                description=str(item.get("description", "")),
                verify_ssl=bool(item.get("verify_ssl", False)),
                follow_redirects=bool(item.get("follow_redirects", True)),
            )
        )
    return requests


def _serialize_request_definition(request: RequestDefinition) -> dict[str, object]:
    return {
        "request_id": request.request_id,
        "name": request.name,
        "method": request.method,
        "url": request.url,
        "collection_id": request.collection_id,
        "folder_id": request.folder_id,
        "query_items": _serialize_request_items(request.query_items),
        "header_items": _serialize_request_items(request.header_items),
        "auth": _serialize_request_auth(request.auth),
        "disabled_auto_headers": request.disabled_auto_headers,
        "body": _serialize_request_body(request.body),
        "description": request.description,
        "verify_ssl": request.verify_ssl,
        "follow_redirects": request.follow_redirects,
    }


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


def _serialize_history_entry(entry: HistoryEntry) -> dict[str, object]:
    return {
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

    return []


def _load_body_text_map(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    body_texts: dict[str, str] = {}
    for key, value in payload.items():
        normalized_key = _normalize_raw_subtype(key)
        body_texts[normalized_key] = str(value)
    return body_texts


def _load_disabled_auto_headers(payload: object) -> list[str]:
    if isinstance(payload, list):
        return [str(value).strip() for value in payload if str(value).strip()]
    return []


def _load_request_auth(payload: object) -> RequestAuth:
    if not isinstance(payload, dict):
        return RequestAuth()

    return RequestAuth(
        type=_normalize_auth_type(payload.get("type", "none")),
        basic_username=str(payload.get("basic_username", "")),
        basic_password=str(payload.get("basic_password", "")),
        bearer_prefix=str(payload.get("bearer_prefix", "Bearer")),
        bearer_token=str(payload.get("bearer_token", "")),
        api_key_name=str(payload.get("api_key_name", "X-API-Key")),
        api_key_value=str(payload.get("api_key_value", "")),
        api_key_location=_normalize_auth_api_key_location(
            payload.get("api_key_location", "header")
        ),
        cookie_name=str(payload.get("cookie_name", "session")),
        cookie_value=str(payload.get("cookie_value", "")),
        custom_header_name=str(payload.get("custom_header_name", "X-Auth-Token")),
        custom_header_value=str(payload.get("custom_header_value", "")),
        oauth_token_url=str(payload.get("oauth_token_url", "")),
        oauth_client_id=str(payload.get("oauth_client_id", "")),
        oauth_client_secret=str(payload.get("oauth_client_secret", "")),
        oauth_client_authentication=_normalize_auth_oauth_client_authentication(
            payload.get("oauth_client_authentication", "basic-header")
        ),
        oauth_header_prefix=str(payload.get("oauth_header_prefix", "Bearer")),
        oauth_scope=str(payload.get("oauth_scope", "")),
    )


def _load_request_body(payload: object) -> RequestBody:
    if not isinstance(payload, dict):
        return RequestBody()

    return RequestBody(
        type=_normalize_body_type(payload.get("type", "none")),
        raw_subtype=_normalize_raw_subtype(payload.get("raw_subtype", "json")),
        text=str(payload.get("text", "")),
        raw_texts=_load_body_text_map(payload.get("raw_texts")),
        graphql_text=str(payload.get("graphql_text", "")),
        binary_file_path=str(payload.get("binary_file_path", "")),
        form_items=_load_request_items(payload.get("form_items")),
        urlencoded_items=_load_request_items(payload.get("urlencoded_items")),
    )


def _serialize_request_items(items: list[RequestKeyValue]) -> list[dict[str, object]]:
    return [
        {
            "key": item.key,
            "value": item.value,
            "enabled": item.enabled,
        }
        for item in items
    ]


def _serialize_request_auth(auth: RequestAuth) -> dict[str, object]:
    return {
        "type": auth.type,
        "basic_username": auth.basic_username,
        "basic_password": auth.basic_password,
        "bearer_prefix": auth.bearer_prefix,
        "bearer_token": auth.bearer_token,
        "api_key_name": auth.api_key_name,
        "api_key_value": auth.api_key_value,
        "api_key_location": auth.api_key_location,
        "cookie_name": auth.cookie_name,
        "cookie_value": auth.cookie_value,
        "custom_header_name": auth.custom_header_name,
        "custom_header_value": auth.custom_header_value,
        "oauth_token_url": auth.oauth_token_url,
        "oauth_client_id": auth.oauth_client_id,
        "oauth_client_secret": auth.oauth_client_secret,
        "oauth_client_authentication": auth.oauth_client_authentication,
        "oauth_header_prefix": auth.oauth_header_prefix,
        "oauth_scope": auth.oauth_scope,
    }


def _serialize_request_body(body: RequestBody) -> dict[str, object]:
    return {
        "type": body.type,
        "raw_subtype": body.raw_subtype,
        "text": body.text,
        "raw_texts": body.raw_texts,
        "graphql_text": body.graphql_text,
        "binary_file_path": body.binary_file_path,
        "form_items": _serialize_request_items(body.form_items),
        "urlencoded_items": _serialize_request_items(body.urlencoded_items),
    }


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
