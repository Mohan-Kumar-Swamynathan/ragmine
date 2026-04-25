"""
ragmine.tui.app
~~~~~~~~~~~~~~~
Minimal Textual application for ragmine - OpenCode style.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.suggester import SuggestFromList
from textual.widgets import Footer, Header, Input, Label


SUGGESTIONS = [
    "/help", "/ingest", "/connect", "/sources", "/status", "/clear", "/delete", "/export",
    "/connect web --url=", "/connect github --repo=", "/connect rss --feed=",
    "/ingest ./", "/connect confluence --space=", "/connect slack --channel=",
]


class RagmineTUI(App):
    """Minimal TUI - chat only, like OpenCode."""

    CSS = """
    Screen {
        background: $surface;
    }

    #chat-container {
        height: 100%;
        layout: vertical;
    }

    #messages {
        height: 1fr;
        padding: 1 2;
    }

    .message {
        margin-bottom: 1;
    }

    .user-label {
        text-style: bold;
        color: cyan;
    }

    .bot-label {
        text-style: bold;
        color: magenta;
    }

    .cmd-label {
        text-style: bold;
        color: yellow;
    }

    #input-area {
        height: auto;
        padding: 0 2 1 2;
        border-top: solid $border;
        background: $surface;
    }

    #input-field {
        border: none;
        background: transparent;
    }

    .info-text {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("up", "history_up", "History", show=False),
        Binding("down", "history_down", "History", show=False),
        Binding("ctrl+l", "clear_screen", "Clear", show=False),
        Binding("ctrl+k", "scroll_up", "Scroll Up", show=False),
        Binding("ctrl+j", "scroll_down", "Scroll Down", show=False),
    ]

    def __init__(self, **overrides):
        super().__init__()
        self._ragmine = None
        self._loading = False
        self._history: list[str] = []
        self._history_index = -1
        self._init_ragmine(overrides)

    def _init_ragmine(self, overrides):
        try:
            from ragmine.pipeline import Ragmine
            
            env_overrides = overrides.copy()
            if "embedding_provider" not in env_overrides:
                import os as _os
                if _os.environ.get("RAGMINE_EMBEDDING_PROVIDER") != "ollama":
                    env_overrides["embedding_provider"] = "sentence-transformers"
            
            self._ragmine = Ragmine(**env_overrides)
        except Exception as e:
            print(f"Warning: Could not initialize Ragmine: {e}")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="chat-container"):
            with VerticalScroll(id="messages"):
                yield Label("[bold magenta]⛏️  ragmine[/bold magenta]", markup=True)
                yield Label("[dim]Commands: /help, /ingest, /connect, /sources, /status, /clear, /delete[/dim]", markup=True)
                yield Label("[dim]Tip: Press up/down for history | Ctrl+K/J scroll | Esc quit[/dim]", markup=True)
                yield Label("", markup=True)
            with Container(id="input-area"):
                yield Input(
                    placeholder="Ask a question or command...",
                    id="input-field",
                    suggester=SuggestFromList(SUGGESTIONS, case_sensitive=False),
                )
        yield Footer()

    def on_mount(self) -> None:
        input_field = self.query_one("#input-field", Input)
        input_field.focus()
        self._update_status()

    def _update_status(self) -> None:
        if self._ragmine:
            status = self._ragmine.status()
            chunks = status.get("total_chunks", 0)
            sources = status.get("total_sources", 0)
            self.title = f"⛏️  ragmine ({chunks} chunks, {sources} sources)"

    def action_history_up(self) -> None:
        if self._history:
            input_field = self.query_one("#input-field", Input)
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
            input_field.value = self._history[self._history_index]
            input_field.cursor_position = len(input_field.value)

    def action_history_down(self) -> None:
        if self._history:
            input_field = self.query_one("#input-field", Input)
            if self._history_index > 0:
                self._history_index -= 1
                input_field.value = self._history[self._history_index]
            elif self._history_index == 0:
                self._history_index = -1
                input_field.value = ""
            input_field.cursor_position = len(input_field.value)

    def action_clear_screen(self) -> None:
        self._handle_clear()

    def action_scroll_up(self) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        messages.scroll_up()

    def action_scroll_down(self) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        messages.scroll_down()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._loading or not event.value.strip():
            return

        query = event.value.strip()

        if self._history and self._history[0] != query:
            self._history.insert(0, query)
            if len(self._history) > 50:
                self._history.pop()
        elif not self._history:
            self._history.insert(0, query)
        self._history_index = -1

        self._add_message("user", query)

        input_field = self.query_one("#input-field", Input)
        input_field.value = ""

        if not self._ragmine:
            self._add_message("bot", "Ragmine not initialized. Check your settings.")
            return

        asyncio.create_task(self._run_query(query))

    async def _run_query(self, query: str) -> None:
        self._loading = True
        messages = self.query_one("#messages", VerticalScroll)

        try:
            if query.startswith("/"):
                await self._handle_command(query)
            else:
                if self._ragmine.store.count() == 0:
                    self._add_message("bot", "No documents yet. Use /ingest <path> or /connect to add data.")
                else:
                    response = await self._ragmine.aquery(query)
                    self._add_message("bot", response.answer)
                    if response.sources:
                        for i, r in enumerate(response.sources, 1):
                            name = Path(r.source).name if r.source else "unknown"
                            messages.mount(Label(f"  [dim][{i}][/dim] {name}", markup=True))
                    messages.mount(Label("", markup=True))
        except Exception as e:
            self._add_message("bot", f"Error: {str(e)}")
        finally:
            self._loading = False
            messages.scroll_end(animate=True)

    async def _handle_command(self, cmd: str) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        parts = cmd.split(None, 1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command in ["/quit", "/exit", "/q"]:
            self.exit()

        elif command == "/help":
            help_text = """[bold]Commands:[/bold]
[cyan]/ingest <path>[/cyan]     Add documents (e.g., /ingest ./docs)
[cyan]/connect <name>[/cyan]    Connect data source (e.g., /connect web --url=https://...)
[cyan]/sources[/cyan]            List all sources
[cyan]/status[/cyan]             Show KB status
[cyan]/delete <src>[/cyan]        Delete a source
[cyan]/export[/cyan]             Export chat to file
[cyan]/clear[/cyan]              Clear chat
[cyan]/help[/cyan]               Show this help
[cyan]/quit[/cyan]               Exit

[bold]Keyboard:[/bold]
  ↑/↓  History    Tab   Accept suggestion
  Esc  Quit       Ctrl+L  Clear screen

[bold]Connectors:[/bold]
  web, github, confluence, slack, notion,
  database, rss, s3, metabase

[dim]Note: Images require vision-capable LLM (e.g., GPT-4V)[/dim]"""
            self._add_message("bot", help_text)

        elif command == "/connect":
            if not arg:
                self._add_message("bot", """[bold]/connect usage:[/bold]
[cyan]/connect web[/cyan]         --url=<url>
[cyan]/connect github[/cyan]      --repo=<owner/repo> --token=<token>
[cyan]/connect rss[/cyan]         --feed=<url>
[cyan]/connect confluence[/cyan]  --space=<key>
[cyan]/connect slack[/cyan]      --channel=<id>
[cyan]/connect notion[/cyan]     --page=<id>
[cyan]/connect database[/cyan]   --dsn=<connection>
[cyan]/connect s3[/cyan]          --bucket=<name>
[cyan]/connect metabase[/cyan]    --url=<url>""")
                return

            parts = arg.split()
            connector_name = parts[0].lower()
            connector_args = " ".join(parts[1:])

            connectors = ["web", "github", "confluence", "slack", "notion", "database", "rss", "s3", "metabase"]
            if connector_name not in connectors:
                self._add_message("bot", f"Unknown: {connector_name}\nAvailable: {', '.join(connectors)}")
                return

            try:
                if connector_name == "web":
                    from ragmine.connectors.web import WebConnectorCLI
                    connector = WebConnectorCLI.parse_args(connector_args)
                    self._add_message("cmd", f"Fetching: {connector._urls}")
                    chunks = connector.fetch_chunks()
                    source = f"web:{connector._urls[0] if connector._urls else 'url'}"
                    count = self._ragmine.ingest_chunks(chunks, source=source)
                    self._add_message("bot", f"✓ Added {count} chunks from web")
                    self._update_status()

                elif connector_name == "rss":
                    from ragmine.connectors.rss import RSSConnectorCLI
                    connector = RSSConnectorCLI.parse_args(connector_args)
                    self._add_message("cmd", f"Fetching: {connector._feeds}")
                    chunks = connector.fetch_chunks()
                    count = self._ragmine.ingest_chunks(chunks, source="rss:feeds")
                    self._add_message("bot", f"✓ Added {count} chunks from RSS")
                    self._update_status()

                elif connector_name == "github":
                    from ragmine.connectors.github import GitHubConnectorCLI
                    connector, source = GitHubConnectorCLI.parse_args(connector_args)
                    self._add_message("cmd", f"Fetching: {source}")
                    chunks = connector.fetch_chunks()
                    count = self._ragmine.ingest_chunks(chunks, source=source)
                    self._add_message("bot", f"✓ Added {count} chunks from GitHub")
                    self._update_status()

                else:
                    self._add_message("bot", f"Connector '{connector_name}' ready. Full integration coming soon.")

            except ImportError as e:
                self._add_message("bot", f"Missing: {e}\nInstall: pip install 'ragmine[connector-{connector_name}]'")
            except Exception as e:
                error_msg = str(e)
                if "api/embeddings" in error_msg or "404" in error_msg:
                    self._add_message("bot", f"""Error: Embeddings not working.

Ollama embeddings endpoint not available. Fix:

1. Use sentence-transformers (no setup):
   export RAGMINE_EMBEDDING_PROVIDER=sentence-transformers

2. OR install Ollama embeddings model:
   ollama pull nomic-embed-text

Current error: {error_msg[:200]}""")
                else:
                    self._add_message("bot", f"Error: {error_msg[:200]}")

        elif command == "/ingest":
            if not arg:
                self._add_message("bot", "Usage: /ingest <path> [--glob pattern]\nExample: /ingest ./docs --glob *.py,*.md")
                return
            try:
                self._add_message("cmd", f"Ingesting: {arg}")
                count = self._ragmine.ingest(arg)
                self._add_message("bot", f"✓ Ingested {count} chunks")
                self._update_status()
            except Exception as e:
                self._add_message("bot", f"Error: {e}")

        elif command == "/sources":
            if self._ragmine:
                sources = self._ragmine.store.list_sources(limit=50)
                if sources:
                    self._add_message("bot", f"Sources ({len(sources)}):\n" + "\n".join(f"  {s}" for s in sources))
                else:
                    self._add_message("bot", "No sources yet. Use /ingest or /connect to add data.")

        elif command == "/status":
            if self._ragmine:
                status = self._ragmine.status()
                self._add_message("bot", f"""KB Status:
  Chunks: {status['total_chunks']}
  Sources: {status['total_sources']}
  Backend: {status['store_backend']}
  Embedding: {status['embedding_model']}
  LLM: {status['llm_model']}""")

        elif command == "/delete":
            if not arg:
                self._add_message("bot", "Usage: /delete <source>\nUse /sources to see available sources")
                return
            try:
                count = self._ragmine.store.delete_by_source(arg)
                self._add_message("bot", f"✓ Deleted {count} chunks from {arg}")
                self._update_status()
            except Exception as e:
                self._add_message("bot", f"Error: {e}")

        elif command == "/export":
            try:
                import os
                from datetime import datetime
                export_dir = Path.home() / ".ragmine" / "exports"
                export_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = export_dir / f"chat_{timestamp}.txt"
                
                messages = self.query_one("#messages", VerticalScroll)
                lines = []
                for label in messages.query("Label"):
                    if label.renderable:
                        lines.append(str(label.renderable))
                
                filepath.write_text("\n".join(lines))
                self._add_message("bot", f"✓ Chat exported to:\n{filepath}")
            except Exception as e:
                self._add_message("bot", f"Error exporting: {e}")

        elif command == "/clear":
            self._handle_clear()

        else:
            self._add_message("bot", f"Unknown: {command}\nType /help for commands")

    def _handle_clear(self) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        messages.remove_children()
        messages.mount(Label("[bold magenta]⛏️  ragmine[/bold magenta]", markup=True))
        messages.mount(Label("[dim]Chat cleared. Ready for new queries.[/dim]", markup=True))
        messages.mount(Label("", markup=True))

    def _add_message(self, who: str, text: str) -> None:
        messages = self.query_one("#messages", VerticalScroll)

        if who == "user":
            messages.mount(Label("[cyan]You:[cyan]", markup=True))
        elif who == "cmd":
            messages.mount(Label("[yellow]⛏️  Executing...[/yellow]", markup=True))
        else:
            messages.mount(Label("[magenta]⛏️  ragmine:[/magenta]", markup=True))

        for line in text.split("\n"):
            messages.mount(Label(line, markup=True))
        messages.mount(Label("", markup=True))
        messages.scroll_end(animate=False)


def run_tui(**overrides):
    app = RagmineTUI(**overrides)
    app.run()


if __name__ == "__main__":
    run_tui()