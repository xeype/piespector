from __future__ import annotations

from importlib.resources import files

from piespector.domain.http import HTTP_METHODS


def build_app_css() -> str:
    method_select_width = max(len(method) for method in HTTP_METHODS) + 3
    select_css = files("piespector.widget.select").joinpath("styles.tcss").read_text(encoding="utf-8")
    css = select_css + """
Screen {
    layout: vertical;
}

#workspace {
    height: 1fr;
}

#home-screen {
    height: 1fr;
    layout: vertical;
    padding: 0 2;
}

#home-workspace {
    height: 1fr;
    layout: horizontal;
}

#sidebar-container {
    width: 40;
    min-width: 36;
    max-width: 46;
    height: 1fr;
    border: solid $surface-lighten-2;
    border-title-align: right;
    border-title-color: $text-muted;
    padding: 0 1;
}

#sidebar-container.piespector-focus-frame,
#request-panel.piespector-focus-frame,
#response-panel.piespector-focus-frame {
    border: solid $accent;
    border-title-color: $text;
}

#sidebar-title,
#request-title,
#response-title {
    display: none;
}

#sidebar-subtitle {
    dock: bottom;
}

#sidebar-tree {
    height: 1fr;
    background: $background;
    scrollbar-size: 1 1;

    & > .tree--cursor {
        background: transparent;
    }

    & > .tree--guides-selected {
        color: $text-muted;
    }

    &:focus {
        background: $background;
        background-tint: 0%;

        & > .tree--cursor {
            color: $text;
            background: $accent;
            text-style: none;
        }

        & > .tree--guides-selected {
            color: $accent;
        }
    }
}

#home-main {
    height: 1fr;
    width: 1fr;
}

#url-bar-container {
    height: 5;
    padding: 0;
    border: solid $surface-lighten-2;
}

#url-bar-container.piespector-focus-frame {
    border: solid $accent;
}

#open-request-tabs {
    height: 2;
}

#open-request-tabs Tab {
    color: $text-muted;
    background: transparent;
    text-style: none;
}

#open-request-tabs Tab:hover {
    color: $text;
}

#open-request-tabs Tab:focus {
    background-tint: 0%;
    outline: none;
}

#open-request-tabs .-active {
    color: $text;
    background: transparent;
    text-style: none;
}

#open-request-tabs Underline > .underline--bar {
    color: $accent;
    background: transparent;
}

#url-line {
    layout: horizontal;
    height: 1;
}

#method-select {
    width: __METHOD_SELECT_WIDTH__;
    min-width: __METHOD_SELECT_WIDTH__;
    max-width: __METHOD_SELECT_WIDTH__;
}

#method-select > SelectCurrent {
    padding: 0 1;
}

#method-select.piespector-selected-element > SelectCurrent {
    outline: solid $accent;
}

#url-bar-subtitle {
    height: 1;
}

#url-display {
    width: 1fr;
}

#url-input {
    width: 1fr;
}

#request-panel {
    height: 5fr;
    border: solid $surface-lighten-2;
    border-title-align: right;
    border-title-color: $text-muted;
    padding: 0 1;
}


#request-tabs {
    height: 1fr;
}

#request-tabs ContentTab {
    color: $text-muted;
    background: transparent;
    text-style: none;
}

#request-tabs ContentTab:hover {
    color: $text;
}

#request-tabs ContentTabs:focus {
    background-tint: 0%;
    outline: none;
}

#request-tabs ContentTabs:focus .-active {
    color: $text;
    background: $accent;
}

#request-tabs ContentTab:focus {
    background-tint: 0%;
    outline: none;
}

#request-tabs ContentTab.-active:focus {
    color: $text;
    background: $accent;
    background-tint: 0%;
}

#request-panel.piespector-tab-select #request-tabs ContentTab.-active {
    background: $accent;
    color: $text;
}

#request-tabs Underline > .underline--bar {
    color: $accent;
    background: transparent;
}

#request-tabs ContentSwitcher {
    height: 1fr;
}

#request-tabs TabPane {
    height: 1fr;
    layout: vertical;
}

#auth-option-label,
#request-content-note,
#response-note {
    height: auto;
}

#request-overview-content,
#request-auth-content,
#request-body-preview,
#response-body-content,
#response-headers-content {
    height: 1fr;
}


#auth-type-select.piespector-selected-element > SelectCurrent,
#auth-option-select.piespector-selected-element > SelectCurrent,
#body-type-select.piespector-selected-element > SelectCurrent,
#body-raw-type-select.piespector-selected-element > SelectCurrent {
    outline: solid $accent;
}

#request-params-table,
#request-headers-table,
#request-body-table {
    height: 1fr;
}

#request-overview-input,
#request-params-input,
#request-headers-input {
    height: 1;
}

#response-panel {
    height: 4fr;
    border: solid $surface-lighten-2;
    border-title-align: right;
    border-title-color: $text-muted;
    padding: 0 1;
}

#response-header-row {
    layout: horizontal;
    height: 2;
}

#response-tabs {
    width: 18;
    min-width: 18;
    max-width: 18;
    height: 2;
}

#response-tabs Tab {
    color: $text-muted;
    background: transparent;
    text-style: none;
}

#response-tabs Tab:hover {
    color: $text;
}

#response-tabs Tab:focus {
    background-tint: 0%;
    outline: none;
}

#response-tabs Tab.-active:focus {
    color: $text;
    background: $accent;
    background-tint: 0%;
}

#response-tabs:focus {
    background-tint: 0%;
    outline: none;
}

#response-tabs:focus .-active {
    color: $text;
    background: $accent;
}

#response-panel.piespector-tab-select #response-tabs Tab.-active {
    background: $accent;
    color: $text;
}

#response-tabs Underline > .underline--bar {
    color: $accent;
    background: transparent;
}

#response-summary {
    width: 1fr;
    height: 1;
    content-align: right top;
}

#response-content {
    height: 1fr;
}

#env-screen {
    height: 1fr;
    layout: horizontal;
}

#env-sidebar-container {
    width: 36;
    min-width: 28;
    max-width: 48;
    height: 1fr;
    border: solid $surface-lighten-2;
    border-title-align: left;
    border-title-color: $text-muted;
    padding: 0 1;
}

#env-sidebar-container.piespector-focus-frame {
    border: solid $accent;
    border-title-color: $text;
}

#env-sidebar-title {
    display: none;
}

#env-sidebar-subtitle {
    dock: bottom;
}

#env-sidebar-tree {
    height: 1fr;
    background: $background;
    scrollbar-size: 1 1;

    & > .tree--cursor {
        color: $text;
        background: $accent;
    }

    & > .tree--guides-selected {
        color: $accent;
    }

    &:focus {
        background: $background;
        background-tint: 0%;

        & > .tree--cursor {
            color: $text;
            background: $accent;
            text-style: none;
        }

        & > .tree--guides-selected {
            color: $accent;
        }
    }
}

#env-main {
    height: 1fr;
    width: 1fr;
    border: solid $surface-lighten-2;
    padding: 0 1;
}

#env-main.piespector-focus-frame {
    border: solid $accent;
}

#env-table {
    height: 1fr;
}

#env-table > .env-table--add-row {
    background: $surface-darken-1 40%;
}

#history-screen {
    height: 1fr;
    layout: horizontal;
}

#history-sidebar-container {
    width: 1fr;
    height: 1fr;
    border: solid $surface-lighten-2;
    border-title-align: left;
    border-title-color: $text-muted;
    padding: 0 1;
}

#history-sidebar-container.piespector-focus-frame {
    border: solid $accent;
    border-title-color: $text;
}

#history-list {
    height: 1fr;
}

#history-sidebar-subtitle {
    dock: bottom;
}

#history-detail-container {
    height: 1fr;
    width: 1fr;
    border: solid $surface-lighten-2;
    border-title-align: left;
    border-title-color: $text-muted;
    padding: 0 1;
}

#history-detail-container.piespector-focus-frame {
    border: solid $accent;
    border-title-color: $text;
}

#history-detail {
    height: 1fr;
}

#help-content {
    height: 1fr;
}

DataTable {
    height: 1fr;
    background: $background;
    scrollbar-size: 1 1;

    & > .datatable--odd-row,
    & > .datatable--even-row {
        background: $background;
    }

    & > .datatable--cursor,
    & > .datatable--fixed-cursor {
        color: $text;
        background: $accent;
    }

    &:focus {
        background: $background;
        background-tint: 0%;

        & > .datatable--cursor,
        & > .datatable--fixed-cursor {
            color: $text;
            background: $accent;
            text-style: none;
        }
    }
}

#request-params-table > .request-params-table--add-row,
#request-headers-table > .request-headers-table--add-row,
#request-body-table > .request-body-table--add-row {
    background: $surface-darken-1 40%;
}

TextArea {
    scrollbar-size: 1 1;
}

#status-line {
    height: 1;
    padding: 0 1;
    color: $footer-foreground;
    background: $background;
}

#status-line FooterLabel {
    width: auto;
    height: 1;
    text-wrap: nowrap;
    background: transparent;
}

#status-line .piespector-footer__env {
    dock: right;
    width: auto;
    height: 1;
    layout: horizontal;
    margin: 0 1 0 1;
    background: transparent;
}

#status-line .piespector-footer__mode {
    margin: 0 1 0 0;
    color: $footer-key-foreground;
    background: transparent;
}

#status-line .piespector-footer__context {
    margin: 0 1 0 0;
    color: $footer-description-foreground;
    background: transparent;
}

#status-line .piespector-footer__env-key {
    margin: 0 1 0 0;
    color: $footer-key-foreground;
    background: transparent;
}

#status-line .piespector-footer__env-value {
    margin: 0;
    color: $footer-description-foreground;
    background: transparent;
}

#command-line {
    layout: horizontal;
    align: left middle;
    height: 1;
    padding: 0 1;
    color: $footer-foreground;
    background: $background;
}

#command-prompt {
    width: auto;
    color: $footer-key-foreground;
    background: transparent;
}

#command-line-content {
    width: 1fr;
    color: $footer-description-foreground;
    background: transparent;
}

#command-input {
    width: 1fr;
    height: 1;
    background: $background;
    color: $footer-foreground;
    border: none;

    &:focus {
        background: $background;
        background-tint: 0%;
        border: none;
    }
}

#body-editor-header {
    height: auto;
}

#body-editor {
    height: 1fr;
}

#body-editor-hint {
    position: absolute;
    layer: above;
    width: auto;
    height: 1;
}

#url-input-hint {
    position: absolute;
    layer: above;
    width: auto;
    height: 1;
}

#body-editor-footer {
    height: auto;
}

#response-modal {
    width: 92%;
    height: 92%;
    max-width: 160;
    margin: 1 2;
}

#response-modal-editor {
    height: 1fr;
}

.hidden {
    display: none;
}
"""
    return css.replace("__METHOD_SELECT_WIDTH__", str(method_select_width))
