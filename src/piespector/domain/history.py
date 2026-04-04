from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class HistoryEntry:
    history_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = ""
    source_request_id: str | None = None
    source_request_name: str = ""
    source_request_path: str = ""
    method: str = "GET"
    url: str = ""
    auth_type: str = "none"
    auth_location: str = ""
    auth_name: str = ""
    request_headers: list[tuple[str, str]] = field(default_factory=list)
    request_body: str = ""
    request_body_type: str = "none"
    status_code: int | None = None
    elapsed_ms: float | None = None
    response_size: int = 0
    response_headers: list[tuple[str, str]] = field(default_factory=list)
    response_body: str = ""
    error: str = ""


_BODY_SEARCH_LIMIT = 4096


def history_entry_matches(entry: HistoryEntry, raw_query: str) -> bool:
    query = raw_query.strip().lower()
    if not query:
        return True
    status = str(entry.status_code) if entry.status_code is not None else "err"
    request_name = entry.source_request_name.strip()
    request_path = entry.source_request_path.strip()
    url = entry.url.strip()
    haystacks = (
        request_name,
        request_path,
        url,
        entry.method,
        status,
        f"{entry.method} {status}",
        f"{request_name} {url}",
        f"{request_path} {url}",
        f"{entry.method} {status} {request_name} {url}",
        f"{entry.method} {status} {request_path} {url}",
        entry.response_body[:_BODY_SEARCH_LIMIT],
        entry.request_body[:_BODY_SEARCH_LIMIT],
    )
    return any(query in value.lower() for value in haystacks if value)
