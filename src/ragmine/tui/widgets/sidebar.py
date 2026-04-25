"""
ragmine.tui.widgets.sidebar
~~~~~~~~~~~~~~~~~~~~~~~~~~
Sidebar navigation widget.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class SidebarItem(Widget):
    """A clickable item in the sidebar."""

    def __init__(self, label: str, icon: str = "", screen: str = "chat", **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.icon = icon
        self.target_screen = screen
        self.is_active = False

    def compose(self) -> ComposeResult:
        text = f"{self.icon}  {self.label}" if self.icon else self.label
        yield Label(text, markup=True)

    def on_click(self) -> None:
        self.app.navigate_to(self.target_screen)

    def set_active(self, active: bool) -> None:
        self.is_active = active
        if active:
            self.styles.background = "magenta"
        else:
            self.styles.background = ""


class SidebarSection(Widget):
    """A section within the sidebar."""

    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> ComposeResult:
        if self.title:
            yield Label(f"[dim]{self.title}[/dim]", markup=True)
        yield VerticalScroll(id="section-content")


class Sidebar(Widget):
    """Main sidebar navigation."""

    COMPONENT_CLASSES = {"sidebar-item", "sidebar-section"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sources: list[str] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="sidebar-content"):
            yield Label("[bold magenta]⛏️  ragmine[/bold magenta]", markup=True)
            yield Label("[dim]v0.2.0[/dim]", markup=True)
            yield Label("")

            yield SidebarItem("Chat", "💬", "chat", id="nav-chat")
            yield SidebarItem("Sources", "📁", "sources", id="nav-sources")
            yield SidebarItem("Settings", "⚙️", "settings", id="nav-settings")

            yield Label("")
            yield Label("[dim]Sources[/dim]", markup=True)
            yield VerticalScroll(id="sources-list", classes="sidebar-sources")

    def set_active(self, screen: str) -> None:
        for nav_id, target in [("nav-chat", "chat"), ("nav-sources", "sources"), ("nav-settings", "settings")]:
            item = self.query_one(f"#{nav_id}", SidebarItem)
            item.set_active(target == screen)

    def set_sources(self, sources: list[str]) -> None:
        self._sources = sources
        container = self.query_one("#sources-list", VerticalScroll)
        container.remove_children()

        for source in sources[:20]:
            path = Path(source)
            name = path.name if path.parts else source
            ext = path.suffix or ""
            container.mount(Label(f"  {ext} {name}", markup=True))