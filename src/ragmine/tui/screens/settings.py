"""
ragmine.tui.screens.settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Settings screen.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Input, Switch
from textual.widget import Widget

from ragmine.pipeline import Ragmine


class SettingsSection(Widget):
    """A settings section."""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.title}[/bold]", markup=True)


class SettingsItem(Widget):
    """A settings item with label and control."""

    def __init__(self, label: str, value: str = "", control=None, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.value = value
        self.control = control

    def compose(self) -> ComposeResult:
        yield Label(f"[cyan]{self.label}:[/cyan]  {self.value}", markup=True)


class SettingsScreen(Widget):
    """Settings/configuration screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ragmine: Ragmine | None = None

    def set_ragmine(self, rm: Ragmine) -> None:
        self._ragmine = rm
        self._refresh()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="settings-container"):
            yield Label("[bold]Settings[/bold]", markup=True)
            yield Label("[dim]Configure ragmine[/dim]", markup=True)
            yield Label("")

            yield SettingsSection(title="Storage")
            yield SettingsItem(label="Data Directory", value="~/.ragmine")
            yield SettingsItem(label="Database", value="default")
            yield SettingsItem(label="Backend", value="lancedb")

            yield Label("")
            yield SettingsSection(title="Embeddings")
            yield SettingsItem(label="Provider", value="sentence-transformers")
            yield SettingsItem(label="Model", value="all-MiniLM-L6-v2")

            yield Label("")
            yield SettingsSection(title="LLM")
            yield SettingsItem(label="Provider", value="ollama")
            yield SettingsItem(label="Model", value="qwen3:8b")
            yield SettingsItem(label="Base URL", value="http://localhost:11434")

            yield Label("")
            yield SettingsSection(title="Retrieval")
            yield SettingsItem(label="Top K", value="5")
            yield SettingsItem(label="Reranking", value="disabled")

            yield Label("")
            yield Label("[dim]Change settings via environment variables:[/dim]", markup=True)
            yield Label("[dim]RAGMINE_DATA_DIR, RAGMINE_EMBEDDING_MODEL, etc.[/dim]", markup=True)

    def _refresh(self) -> None:
        pass