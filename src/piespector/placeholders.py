from __future__ import annotations

from dataclasses import dataclass
import re

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


@dataclass(frozen=True)
class PlaceholderMatch:
    suggestion: str
    prefix: str
    start: int
    end: int


def resolve_placeholders(text: str, env_pairs: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return env_pairs.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(replace, text)


def auto_pair_placeholder(text: str, cursor_index: int) -> tuple[str, int] | None:
    cursor_index = max(0, min(cursor_index, len(text)))
    if cursor_index >= 2 and text[cursor_index - 2 : cursor_index] == "{{":
        before = text[: cursor_index - 2]
        after = text[cursor_index:]
        return (f"{before}{{{{}}}}{after}", len(before) + 2)
    if cursor_index <= 0 or text[cursor_index - 1] != "{":
        return None

    before = text[: cursor_index - 1]
    after = text[cursor_index:]
    return (f"{before}{{{{}}}}{after}", len(before) + 2)


def placeholder_match(
    text: str,
    cursor_index: int,
    env_keys: list[str],
) -> PlaceholderMatch | None:
    cursor_index = max(0, min(cursor_index, len(text)))
    start = text.rfind("{{", 0, cursor_index)
    if start == -1:
        return None

    inside_before = text[start + 2 : cursor_index]
    if "}}" in inside_before:
        return None

    end = text.find("}}", cursor_index)
    if end == -1:
        return None

    inside_after = text[cursor_index:end]
    if any(char in "{}" for char in inside_before + inside_after):
        return None

    matches = sorted(key for key in env_keys if key.startswith(inside_before))
    if not matches:
        return None

    return PlaceholderMatch(
        suggestion=matches[0],
        prefix=inside_before,
        start=start,
        end=end + 2,
    )


def apply_placeholder_completion(
    text: str,
    cursor_index: int,
    env_keys: list[str],
) -> tuple[str, int] | None:
    match = placeholder_match(text, cursor_index, env_keys)
    if match is None or match.suggestion == match.prefix:
        return None

    before = text[: match.start]
    after = text[match.end :]
    completed = f"{before}{{{{{match.suggestion}}}}}{after}"
    new_cursor_index = len(before) + 2 + len(match.suggestion)
    return (completed, new_cursor_index)
