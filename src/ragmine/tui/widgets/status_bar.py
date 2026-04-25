"""
ragmine.tui.widgets.status_bar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Status bar widget.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label


class StatusBar(Label):
    """Status bar at the bottom of the screen."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._chunks = 0
        self._sources = 0
        self._model = ""
        self._connected = True

    def compose(self) -> ComposeResult:
        yield Label("", id="status-text")

    def update(self, chunks: int = 0, sources: int = 0, model: str = "", connected: bool = True) -> None:
        self._chunks = chunks
        self._sources = sources
        self._model = model
        self._connected = connected

        status = f"  ⛏️  {chunks} chunks · {sources} sources"
        if model:
            status += f" · {model}"
        if not connected:
            status += " · [yellow]offline[/yellow]"
        status += "       [dim]Ctrl+P: Command Palette  Ctrl+B: Toggle Sidebar[/dim]"

        self.query_one("#status-text", Label).update(status)

    def set_loading(self, loading: bool) -> None:
        if loading:
            self.query_one("#status-text", Label).update("  ⛏️  Loading...")
        else:
            self.update(self._chunks, self._sources, self._model, self._connected)