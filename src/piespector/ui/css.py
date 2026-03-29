from __future__ import annotations

from piespector.ui.themes import DEFAULT_THEME, ThemeTokens


def build_app_css(theme: ThemeTokens = DEFAULT_THEME) -> str:
    return f"""
Screen {{
    layout: vertical;
    background: {theme.screen_background};
    color: {theme.screen_foreground};
}}

#workspace {{
    height: 1fr;
}}

#viewport {{
    height: 1fr;
    padding: 0;
    background: {theme.panel_background};
}}

#body-editor-panel {{
    height: 1fr;
    padding: 1;
    background: {theme.panel_background};
}}

#body-editor-header {{
    padding: 0 1;
    color: {theme.screen_foreground};
}}

#body-editor {{
    height: 1fr;
    border: round {theme.panel_border};
    background: {theme.editor_background};
    color: {theme.screen_foreground};
}}

#body-editor-hint {{
    position: absolute;
    layer: above;
    width: auto;
    height: 1;
    padding: 0 1;
    background: {theme.subtle_background};
    color: {theme.subtle_foreground};
}}

#body-editor-footer {{
    padding: 0 1;
    color: {theme.subtle_foreground};
}}

#response-viewer-header {{
    padding: 0 1;
    color: {theme.screen_foreground};
}}

#response-viewer {{
    height: 1fr;
    border: round {theme.panel_border};
    background: {theme.editor_background};
    color: {theme.screen_foreground};
    scrollbar-size-vertical: 1;
    scrollbar-size-horizontal: 1;
    scrollbar-background: {theme.editor_background};
    scrollbar-background-hover: {theme.editor_background};
    scrollbar-background-active: {theme.editor_background};
    scrollbar-color: {theme.scrollbar_color};
    scrollbar-color-hover: {theme.scrollbar_color};
    scrollbar-color-active: {theme.scrollbar_color};
    scrollbar-corner-color: {theme.editor_background};
}}

#response-viewer-footer {{
    padding: 0 1;
    color: {theme.subtle_foreground};
}}

#status-line {{
    height: 1;
    background: {theme.status_background};
}}

#command-line {{
    height: 1;
    padding: 0 1;
    background: {theme.panel_background};
    color: {theme.screen_foreground};
}}

.hidden {{
    display: none;
}}
"""
