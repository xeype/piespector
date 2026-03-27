from __future__ import annotations

from textual.binding import Binding

APP_CSS = """
Screen {
    layout: vertical;
    background: #2c2c2c;
    color: #d7dae0;
}

#workspace {
    height: 1fr;
}

#viewport {
    height: 1fr;
    padding: 0;
    background: #2c2c2c;
}

#body-editor-panel {
    height: 1fr;
    padding: 1;
    background: #2c2c2c;
}

#body-editor-header {
    padding: 0 1;
    color: #d7dae0;
}

#body-editor {
    height: 1fr;
    border: round #4b5263;
    background: #1f2329;
    color: #d7dae0;
}

#body-editor-hint {
    position: absolute;
    layer: above;
    width: auto;
    height: 1;
    padding: 0 1;
    background: #3a3f4b;
    color: #7f848e;
}

#body-editor-footer {
    padding: 0 1;
    color: #7f848e;
}

#response-viewer-header {
    padding: 0 1;
    color: #d7dae0;
}

#response-viewer {
    height: 1fr;
    border: round #4b5263;
    background: #1f2329;
    color: #d7dae0;
    scrollbar-size-vertical: 1;
    scrollbar-size-horizontal: 1;
    scrollbar-background: #1f2329;
    scrollbar-background-hover: #1f2329;
    scrollbar-background-active: #1f2329;
    scrollbar-color: #54597a;
    scrollbar-color-hover: #54597a;
    scrollbar-color-active: #54597a;
    scrollbar-corner-color: #1f2329;
}

#response-viewer-footer {
    padding: 0 1;
    color: #7f848e;
}

#status-line {
    height: 1;
    background: #3a3f4b;
}

#command-line {
    height: 1;
    padding: 0 1;
    background: #2c2c2c;
    color: #d7dae0;
}

.hidden {
    display: none;
}
"""

APP_BINDINGS = [
    Binding(":", "enter_command_mode", "Command", show=False),
]
