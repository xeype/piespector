from __future__ import annotations

from piespector.domain.http import HTTP_METHODS


def build_app_css() -> str:
    method_select_width = max(len(method) for method in HTTP_METHODS) + 3
    css = """
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

#sidebar-container:hover {
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
        color: $text;
        background: $accent-darken-2;
        text-style: bold;
    }

    & > .tree--guides-selected {
        color: $accent;
    }

    &:focus {
        background: $background;
        background-tint: 0%;

        & > .tree--cursor {
            color: $text;
            background: $accent-darken-2;
            text-style: bold;
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

Select.piespector-selected-element > SelectCurrent {
    background: $accent-darken-2;
    color: $text;
    text-style: bold;
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

#method-select > SelectCurrent:hover,
#method-select.piespector-selected-element > SelectCurrent {
    outline: solid $accent;
}

Select > SelectCurrent {
    background: $surface;
}

Select:focus > SelectCurrent {
    background: $surface;
    background-tint: 0%;
}

Select > SelectOverlay {
    background: $surface;
}

Select > SelectOverlay:focus {
    background: $surface;
    background-tint: 0%;
}

Select > SelectOverlay > .option-list--option,
Select > SelectOverlay > .option-list--option-disabled,
Select > SelectOverlay > .option-list--option-hover {
    background: $surface;
}

Select > SelectOverlay > .option-list--option-highlighted,
Select > SelectOverlay:focus > .option-list--option-highlighted {
    color: $text;
    background: $accent-darken-2;
    text-style: bold;
}

Select > SelectOverlay > .option-list--option-hover {
    background: $accent-darken-2;
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

#request-tabs ContentTabs:focus .-active {
    color: $text;
    background: $accent-darken-2;
    text-style: bold;
}

#request-panel.piespector-tab-select #request-tabs ContentTab.-active {
    background: $accent;
    color: $background;
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

#request-overview-content:hover,
#request-auth-content:hover,
#request-body-preview:hover,
#request-params-table:hover,
#request-headers-table:hover,
#request-body-table:hover,
#request-overview-input:hover,
#auth-field-input:hover,
#request-params-input:hover,
#request-headers-input:hover,
#request-body-input:hover {
    outline: solid $accent;
}

#auth-type-select > SelectCurrent:hover,
#auth-type-select.piespector-selected-element > SelectCurrent,
#auth-option-select > SelectCurrent:hover,
#auth-option-select.piespector-selected-element > SelectCurrent,
#body-type-select > SelectCurrent:hover,
#body-type-select.piespector-selected-element > SelectCurrent,
#body-raw-type-select > SelectCurrent:hover,
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

#response-tabs:focus .-active {
    color: $text;
    background: $accent-darken-2;
    text-style: bold;
}

#response-panel.piespector-tab-select #response-tabs Tab.-active {
    background: $accent;
    color: $background;
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
}

#env-select {
    margin: 0 0 1 0;
}

#env-table {
    height: 1fr;
}

#history-screen {
    height: 1fr;
    layout: horizontal;
}

#history-sidebar-container {
    width: 42;
    min-width: 38;
    max-width: 52;
    height: 1fr;
}

#history-list {
    height: 1fr;
}

#history-detail-container {
    height: 1fr;
    width: 1fr;
}

#history-detail {
    height: 1fr;
}

#help-content {
    height: 1fr;
}

DataTable {
    height: 1fr;
    scrollbar-size: 1 1;

    & > .datatable--cursor,
    & > .datatable--fixed-cursor {
        color: $text;
        background: $accent-darken-2;
        text-style: bold;
    }

    &:focus {
        & > .datatable--cursor,
        & > .datatable--fixed-cursor {
            color: $text;
            background: $accent-darken-2;
            text-style: bold;
        }
    }
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
    text-style: bold;
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
    text-style: bold;
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
    text-style: bold;
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
