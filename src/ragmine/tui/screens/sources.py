"""
ragmine.tui.screens.sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sources browser screen.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Input
from textual.widget import Widget

from ragmine.pipeline import Ragmine


class SourceItem(Widget):
    """A single source item."""

    def __init__(self, source: str, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        path = Path(source)
        self.name = path.name if path.parts else source
        self.type = path.suffix or "dir"

    def compose(self) -> ComposeResult:
        color = "blue" if self.type.startswith(".") else "white"
        yield Label(f"[{color}]{self.name}[/{color}]  [dim]{self.source}[/dim]", markup=True)


class SourcesScreen(Widget):
    """Screen for browsing sources."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ragmine: Ragmine | None = None

    def set_ragmine(self, rm: Ragmine) -> None:
        self._ragmine = rm
        self._refresh()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="sources-container"):
            yield Label("[bold]Sources[/bold]", markup=True)
            yield Input(placeholder="Filter sources...", id="sources-filter")
            yield VerticalScroll(id="sources-list")

    def _refresh(self) -> None:
        if not self._ragmine:
            return

        container = self.query_one("#sources-list", VerticalScroll)
        container.remove_children()

        sources = self._ragmine.store.list_sources(limit=100)
        for source in sources:
            container.mount(SourceItem(source))

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower()
        container = self.query_one("#sources-list", VerticalScroll)

        for item in container.query(SourceItem):
            item.display = query in item.source.lower() if query else True