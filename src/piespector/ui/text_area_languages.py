from __future__ import annotations

from textual._tree_sitter import get_language
from textual.widgets import TextArea
from textual.widgets._text_area import LanguageDoesNotExist

GRAPHQL_TEXTAREA_LANGUAGE = "piespector-graphql"
GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY = """
[
  "{"
  "}"
] @punctuation.bracket

((identifier) @keyword
 (#match? @keyword "^(query|mutation|subscription|fragment|on)$"))

((identifier) @class
 (#match? @class "^[A-Z][A-Za-z0-9_]*$"))

((identifier) @function
 (#match? @function "^[a-z_][A-Za-z0-9_]*$"))
"""


def set_text_area_language(
    editor: TextArea,
    language: str | None,
) -> None:
    try:
        editor.language = language
    except LanguageDoesNotExist:
        editor.language = None


def register_graphql_text_area_language(editor: TextArea) -> None:
    javascript_language = get_language("javascript")
    if javascript_language is None:
        return
    editor.register_language(
        GRAPHQL_TEXTAREA_LANGUAGE,
        javascript_language,
        GRAPHQL_TEXTAREA_HIGHLIGHT_QUERY,
    )
