from __future__ import annotations

from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text as PygmentsText,
)

SYNTAX_BACKGROUND = "#272822"

MONOKAI_TOKEN_STYLES = {
    PygmentsText: "#f8f8f2",
    Comment: "#75715e",
    Keyword: "#f92672",
    Operator: "#f8f8f2",
    Punctuation: "#f8f8f2",
    Name: "#f8f8f2",
    Name.Variable: "#f8f8f2",
    Name.Other: "#f8f8f2",
    Name.Attribute: "#a6e22e",
    Name.Function: "#a6e22e",
    Name.Class: "#a6e22e",
    Name.Tag: "#f92672",
    Number: "#ae81ff",
    String: "#e6db74",
}

GRAPHQL_TOKEN_STYLE_OVERRIDES = {
    Name: "#a6e22e",
    Name.Function: "#66d9ef",
}
