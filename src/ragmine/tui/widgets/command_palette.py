"""
ragmine.tui.widgets.command_palette
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Command palette for quick actions.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Label
from textual.widget import Widget


class CommandItem(Widget):
    """A command in the palette."""

    def __init__(self, command: str, description: str, shortcut: str = "", **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self.description = description
        self.shortcut = shortcut
        self.is_selected = False

    def compose(self) -> ComposeResult:
        parts = []
        if self.shortcut:
            parts.append(f"[dim][{self.shortcut}][/dim]  ")
        parts.append(f"[cyan]{self.command}[/cyan]")
        if self.description:
            parts.append(f"  [dim]{self.description}[/dim]")
        yield Label("".join(parts), markup=True)

    def select(self) -> None:
        self.is_selected = True
        self.styles.background = "accent"

    def deselect(self) -> None:
        self.is_selected = False
        self.styles.background = ""


class CommandPalette(Widget):
    """Command palette overlay."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("up", "move_up", "Move Up"),
        ("down", "move_down", "Move Down"),
        ("enter", "execute", "Execute"),
    ]

    selected_index = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._commands: list[dict] = []
        self._filtered: list[dict] = []
        self._search_input = ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="palette-content"):
            yield Input(placeholder="Type a command...", id="palette-input")
            yield VerticalScroll(id="commands-list")

    def on_mount(self) -> None:
        self._load_commands()
        self._refresh()

    def _load_commands(self) -> None:
        from ragmine.connectors import list_connectors, get_connector_help

        self._commands = [
            {"command": "/ingest", "description": "Ingest files", "shortcut": "i"},
            {"command": "/search", "description": "Search knowledge base", "shortcut": "s"},
            {"command": "/query", "description": "Ask a question", "shortcut": "q"},
            {"command": "/sources", "description": "List sources", "shortcut": ""},
            {"command": "/status", "description": "Show status", "shortcut": ""},
            {"command": "/connect", "description": "Connect a data source", "shortcut": ""},
            {"command": "/help", "description": "Show help", "shortcut": "?"},
            {"command": "/clear", "description": "Clear chat", "shortcut": ""},
            {"command": "/quit", "description": "Exit", "shortcut": "Ctrl+C"},
        ]

        for name in list_connectors():
            help_text = get_connector_help(name)
            first_line = help_text.split("\n")[1] if "\n" in help_text else ""
            self._commands.append({
                "command": f"/connect {name}",
                "description": f"Connect to {name}",
                "shortcut": "",
            })

    def _filter_commands(self) -> None:
        query = self._search_input.lower()
        if not query:
            self._filtered = self._commands
        else:
            self._filtered = [
                c for c in self._commands
                if query in c["command"].lower() or query in c["description"].lower()
            ]

    def _refresh(self) -> None:
        container = self.query_one("#commands-list", VerticalScroll)
        container.remove_children()

        for i, cmd in enumerate(self._filtered[:10]):
            item = CommandItem(
                command=cmd["command"],
                description=cmd["description"],
                shortcut=cmd.get("shortcut", ""),
            )
            if i == self.selected_index:
                item.select()
            container.mount(item)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._search_input = event.value
        self.selected_index = 0
        self._filter_commands()
        self._refresh()

    def action_move_up(self) -> None:
        if self._filtered:
            self.selected_index = (self.selected_index - 1) % len(self._filtered[:10])
            self._refresh()

    def action_move_down(self) -> None:
        if self._filtered:
            self.selected_index = (self.selected_index + 1) % len(self._filtered[:10])
            self._refresh()

    def action_execute(self) -> None:
        if self._filtered and self.selected_index < len(self._filtered):
            cmd = self._filtered[self.selected_index]["command"]
            self.post_message(CommandPalette.CommandSelected(cmd))
            self.styles.display = "none"
            self.app.set_focus(self.app.query_one("#chat-screen"))

    def action_close(self) -> None:
        self.styles.display = "none"
        self.app.set_focus(self.app.query_one("#chat-screen"))

    def focus_input(self) -> None:
        input_widget = self.query_one("#palette-input", Input)
        input_widget.focus()

    class CommandSelected(Message):
        """Posted when a command is selected."""

        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command