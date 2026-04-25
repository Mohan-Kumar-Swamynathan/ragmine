"""
ragmine.cli
~~~~~~~~~~~~
Interactive CLI with OpenCode-style experience.

    ragmine                        → interactive chat mode
    ragmine ingest ./docs          → ingest files
    ragmine query "how does X?"    → one-shot query
    ragmine tui                    → Textual TUI mode
"""

from __future__ import annotations

import asyncio
import os
import shlex
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.rule import Rule
from rich.table import Table
from rich.theme import Theme

THEME = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "muted": "dim",
    "accent": "bold magenta",
    "source": "blue",
    "score": "yellow",
    "user": "bold cyan",
    "assistant": "white",
})

console = Console(theme=THEME)

LOGO = """[bold magenta]
   ⛏️  ragmine[/bold magenta] [dim]v0.2.0[/dim]
   [dim]Mine your documents. Local RAG that works.[/dim]
"""

HELP_TEXT = """[dim]  Commands:
    [cyan]/ingest <path>[/cyan]       — add documents
    [cyan]/sources[/cyan]             — list sources
    [cyan]/status[/cyan]              — show stats
    [cyan]/search <q>[/cyan]          — search only
    [cyan]/query <q>[/cyan]           — ask question
    [cyan]/connect <name>[/cyan]     — connect data source
    [cyan]/delete <source>[/cyan]     — remove source
    [cyan]/clear[/cyan]               — clear screen
    [cyan]/help [topic][/cyan]        — show help
    [cyan]/quit[/cyan]                — exit

  Or just ask a question to get an answer.[/dim]


[dim]  Connectors:
    [cyan]web[/cyan]         — fetch web pages
    [cyan]github[/cyan]     — GitHub repos, issues, PRs
    [cyan]confluence[/cyan]  — Confluence spaces & pages
    [cyan]slack[/cyan]      — Slack channels & messages
    [cyan]notion[/cyan]     — Notion pages & databases
    [cyan]database[/cyan]    — SQL schemas & queries
    [cyan]rss[/cyan]        — RSS/Atom feeds
    [cyan]s3[/cyan]         — S3/GCS bucket files
    [cyan]metabase[/cyan]   — Metabase metadata

  Use /help <connector> for usage details.[/dim]


[dim]  Shortcuts:
    [cyan]i <path>[/cyan]    — ingest           [cyan]s <q>[/cyan]     — search
    [cyan]q <q>[/cyan]      — query            [cyan]?[/cyan]        — help[/dim]"""


CONNECTOR_CLI_MAP = {
    "web": ("ragmine.connectors.web", "WebConnectorCLI"),
    "github": ("ragmine.connectors.github", "GitHubConnectorCLI"),
    "confluence": ("ragmine.connectors.confluence", "ConfluenceConnectorCLI"),
    "slack": ("ragmine.connectors.slack", "SlackConnectorCLI"),
    "notion": ("ragmine.connectors.notion", "NotionConnectorCLI"),
    "database": ("ragmine.connectors.database", "DatabaseConnectorCLI"),
    "rss": ("ragmine.connectors.rss", "RSSConnectorCLI"),
    "s3": ("ragmine.connectors.s3", "S3ConnectorCLI"),
    "metabase": ("ragmine.connectors.metabase", "MetabaseConnector"),
}


def print_banner():
    console.print(LOGO)


def print_sources_table(sources: list, total: int = 0):
    if not sources:
        console.print("  [warning]No sources yet.[/warning]")
        return

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Source", style="source")
    table.add_column("Type", style="muted", width=12)

    for i, s in enumerate(sources, 1):
        path = Path(s)
        name = path.name if path.parts else s
        stype = path.suffix or "dir"
        table.add_row(str(i), name, stype)

    console.print()
    console.print(Panel(
        table,
        title=f"[dim]📁 sources ({len(sources)})[/dim]",
        border_style="dim",
        padding=(0, 1),
    ))


def print_results_table(results: list):
    if not results:
        console.print("  [warning]No results found.[/warning]")
        return

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Source", style="source", width=30)
    table.add_column("Score", style="score", width=8)
    table.add_column("Text", style="white", width=40)

    for i, r in enumerate(results, 1):
        name = Path(r.source).name if r.source else "?"
        text = r.chunk.text[:60].strip().replace("\n", " ")
        score = f"⬤ {r.score:.3f}"
        table.add_row(str(i), name, score, text + "...")

    console.print()
    console.print(Panel(
        table,
        title=f"[dim]🔍 results ({len(results)})[/dim]",
        border_style="blue",
        padding=(0, 1),
    ))


def print_status(rm):
    s = rm.status()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan")
    table.add_column(style="green")
    table.add_row("Chunks", str(s["total_chunks"]))
    table.add_row("Sources", str(s["total_sources"]))
    table.add_row("Embedding", s["embedding_model"])
    table.add_row("LLM", s["llm_model"])
    table.add_row("Backend", s["store_backend"])

    console.print()
    console.print(Panel(
        table,
        title="[dim]📊 status[/dim]",
        border_style="dim",
        padding=(0, 1),
    ))


def print_answer(response):
    console.print()
    console.print(Rule("[accent]⛏️  ragmine[/accent]", style="magenta"))

    if response.sources:
        console.print()
        console.print(Panel(
            response.answer,
            title="[dim]💬 answer[/dim]",
            border_style="green",
            padding=(0, 1),
        ))

        console.print()
        sources = [f"[source]{i}.[/source] {Path(r.source).name}" for i, r in enumerate(response.sources, 1)]
        console.print(Panel(
            "\n".join(sources),
            title="[dim]📎 sources[/dim]",
            border_style="dim",
            padding=(0, 1),
        ))
    else:
        console.print(Panel(
            response.answer,
            title="[dim]⚠️ notice[/dim]",
            border_style="yellow",
            padding=(0, 1),
        ))

    console.print(f"  [muted]⏱ {response.latency_ms:.0f}ms[/muted]")
    console.print()


def ingest_with_progress(rm, path: str, recursive: bool, glob: str) -> int:
    p = Path(path)

    if p.is_file():
        files = [p]
    elif p.is_dir():
        patterns = glob.split(",") if "," in glob else [glob]
        files = []
        for pattern in patterns:
            found = list(p.rglob(pattern.strip()) if recursive else p.glob(pattern.strip()))
            files.extend(f for f in found if f.is_file() and rm.parser.supports(str(f)))
        files = sorted(set(files))
    else:
        console.print(f"  [error]Path not found: {path}[/error]")
        return 0

    if not files:
        console.print(f"  [warning]No supported files in {path}[/warning]")
        return 0

    total_chunks = 0

    with Progress(
        SpinnerColumn("dots", style="magenta"),
        TextColumn("  [bold]{task.description}[/bold]"),
        BarColumn(bar_width=30, complete_style="magenta", finished_style="green"),
        TaskProgressColumn(),
        TextColumn("[muted]{task.fields[status]}[/muted]"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Mining", total=len(files), status="")

        for f in files:
            progress.update(task, status=f.name[:35])
            try:
                count = rm._ingest_file(f)
                total_chunks += count
            except Exception as e:
                console.print(f"  [error]✗ {f.name}: {e}[/error]")
            progress.advance(task)

        progress.update(task, status="[green]✓ done[/green]")

    return total_chunks


def run_chat():
    from ragmine.pipeline import Ragmine

    print_banner()

    rm = Ragmine()
    s = rm.status()

    if s["total_chunks"] > 0:
        console.print(f"  [success]●[/success] {s['total_chunks']} chunks from {s['total_sources']} sources ready")
    else:
        console.print("  [warning]●[/warning] Empty KB. [cyan]/ingest <path>[/cyan] to start.")

    console.print(HELP_TEXT)

    history = []

    while True:
        try:
            console.print()
            user_input = console.input("[bold magenta]  ⛏️  › [/bold magenta]").strip()

            if not user_input:
                continue

            history.append(("user", user_input))

            if user_input.startswith("/") or user_input.startswith("?"):
                _handle_cmd(rm, user_input, history)
                continue

            cmd_shortcuts = {
                "/i ": "/ingest ",
                "/s ": "/search ",
                "/q ": "/query ",
                "i ": "/ingest ",
                "s ": "/search ",
                "q ": "/query ",
            }
            for short, long in cmd_shortcuts.items():
                if user_input.startswith(short):
                    user_input = long + user_input[len(short):]
                    break

            if user_input.startswith("/ingest ") or user_input.startswith("i "):
                _handle_cmd(rm, "/ingest " + user_input.split(maxsplit=1)[1] if " " in user_input else "", history)
                continue

            if user_input.startswith("/search ") or user_input.startswith("s "):
                _handle_cmd(rm, "/search " + user_input.split(maxsplit=1)[1] if " " in user_input else "", history)
                continue

            if user_input.startswith("/query ") or user_input.startswith("q ") or (user_input and not user_input.startswith("/")):
                if user_input.startswith("q ") or user_input.startswith("/query "):
                    query = user_input.split(maxsplit=1)[1] if " " in user_input else ""
                else:
                    query = user_input

                if rm.store.count() == 0:
                    console.print("  [warning]No documents yet. [cyan]/ingest <path>[/cyan] first.[/warning]")
                    continue

                with console.status("  [magenta]Searching & thinking...[/magenta]", spinner="dots"):
                    response = rm.query(query)

                history.append(("assistant", response.answer))

                if response.sources:
                    print_answer(response)
                else:
                    console.print(f"  [warning]{response.answer}[/warning]")

        except KeyboardInterrupt:
            console.print("\n  [muted]Ctrl+C or /quit to exit[/muted]")
            try:
                console.input("[bold magenta]  ⛏️  › [/bold magenta]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n  [muted]Goodbye! ⛏️[/muted]")
                break
        except EOFError:
            console.print("\n  [muted]Goodbye! ⛏️[/muted]")
            break


def _handle_cmd(rm, cmd: str, history: list):
    try:
        parts = shlex.split(cmd) if " " in cmd else [cmd]
    except ValueError:
        parts = cmd.split()

    command = parts[0].lower()
    arg = " ".join(parts[1:]) if len(parts) > 1 else ""

    if command in ("/quit", "/exit", "/q"):
        console.print("  [muted]Goodbye! ⛏️[/muted]")
        sys.exit(0)

    elif command in ("/help", "?"):
        if not arg:
            console.print(HELP_TEXT)
        elif arg == "connectors":
            _show_connectors_help()
        elif arg in CONNECTOR_CLI_MAP:
            _show_connector_help(arg)
        else:
            console.print(f"  [warning]Unknown help topic: {arg}[/warning]")
            console.print("  [dim]Try: /help connectors or /help <connector-name>[/dim]")

    elif command == "/clear":
        os.system("clear" if os.name != "nt" else "cls")
        print_banner()

    elif command == "/status":
        print_status(rm)

    elif command == "/sources":
        src_list = rm.store.list_sources(limit=50)
        print_sources_table(src_list)

    elif command == "/ingest":
        if not arg:
            console.print("  [error]Usage: /ingest <path> [--glob *.py,*.md][/error]")
            return

        glob = "*"
        if "--glob" in arg:
            p = arg.split("--glob")
            arg = p[0].strip()
            glob = p[1].strip() if len(p) > 1 else "*"

        console.print()
        count = ingest_with_progress(rm, arg, recursive=True, glob=glob)
        console.print()
        console.print(f"  [success]✓[/success] Mined [bold]{count}[/bold] chunks")
        s = rm.status()
        console.print(f"  [muted]Total: {s['total_chunks']} chunks from {s['total_sources']} sources[/muted]")

    elif command == "/search":
        if not arg:
            console.print("  [error]Usage: /search <query>[/error]")
            return
        with console.status("  [magenta]Searching...[/magenta]", spinner="dots"):
            results = rm.search(arg)
        print_results_table(results)

    elif command == "/query":
        if not arg:
            console.print("  [error]Usage: /query <question>[/error]")
            return
        if rm.store.count() == 0:
            console.print("  [warning]No documents yet. [cyan]/ingest <path>[/cyan] first.[/warning]")
            return
        with console.status("  [magenta]Searching & thinking...[/magenta]", spinner="dots"):
            response = rm.query(arg)
        print_answer(response)

    elif command == "/delete":
        if not arg:
            console.print("  [error]Usage: /delete <source>[/error]")
            return
        count = rm.store.delete_by_source(arg)
        console.print(f"  [success]✓[/success] Deleted {count} chunks")

    elif command == "/connect":
        if not arg:
            console.print("  [error]Usage: /connect <name> [options][/error]")
            console.print("  [dim]Available: " + ", ".join(CONNECTOR_CLI_MAP.keys()) + "[/dim]")
            console.print("  [dim]Use /help connectors for details[/dim]")
            return

        connector_name = arg.split()[0].lower()
        connector_args = " ".join(arg.split()[1:])

        _handle_connect(rm, connector_name, connector_args)

    else:
        console.print(f"  [error]Unknown command: {command}[/error]")
        console.print("  [muted]Type /help for commands[/muted]")


def _show_connectors_help():
    from ragmine.connectors import CONNECTORS

    console.print()
    console.print(Panel(
        "\n".join([
            "[bold]Available Connectors:[/bold]",
            "",
            *[f"  [cyan]{name}[/cyan]  — {info.description}" for name, info in CONNECTORS.items()],
            "",
            "[dim]Usage: /connect <name> [options][/dim]",
            "[dim]Help:  /help <connector-name>[/dim]",
        ]),
        title="[dim]📎 Connectors[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def _show_connector_help(name: str):
    if name not in CONNECTOR_CLI_MAP:
        console.print(f"  [error]Unknown connector: {name}[/error]")
        return

    module_path, cli_class = CONNECTOR_CLI_MAP[name]
    try:
        module = __import__(module_path, fromlist=[cli_class])
        cli_class_obj = getattr(module, cli_class)
        help_text = getattr(cli_class_obj, "help_text", lambda: "No help available")()

        console.print()
        console.print(Panel(
            help_text,
            title=f"[cyan]/connect {name}[/cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))
        console.print()
    except ImportError as e:
        console.print(f"  [warning]Connector not available: {e}[/warning]")
        console.print(f"  [dim]Install with: pip install 'ragmine[connector-{name}]'[/dim]")


def _handle_connect(rm, name: str, args: str):
    if name not in CONNECTOR_CLI_MAP:
        console.print(f"  [error]Unknown connector: {name}[/error]")
        console.print(f"  [dim]Available: {', '.join(CONNECTOR_CLI_MAP.keys())}[/dim]")
        console.print(f"  [dim]Use /help connectors for details[/dim]")
        return

    module_path, cli_class = CONNECTOR_CLI_MAP[name]

    try:
        module = __import__(module_path, fromlist=[cli_class])
        cli_class_obj = getattr(module, cli_class)

        if hasattr(cli_class_obj, "parse_args"):
            connector, source = cli_class_obj.parse_args(args)
        else:
            console.print(f"  [error]Connector {name} not properly configured[/error]")
            return

        console.print(f"  [info]Connecting to {name}...[/info]")

        with console.status(f"  [magenta]Fetching chunks from {name}...[/magenta]", spinner="dots"):
            chunks = connector.fetch_chunks()

        console.print(f"  [info]Got {len(chunks)} chunks, embedding...")

        count = rm.ingest_chunks(chunks, source=source)
        console.print(f"  [success]✓[/success] Ingested [bold]{count}[/bold] chunks from {name}")

        s = rm.status()
        console.print(f"  [muted]Total: {s['total_chunks']} chunks from {s['total_sources']} sources[/muted]")

    except ImportError as e:
        console.print(f"  [error]Missing dependency: {e}[/error]")
        console.print(f"  [dim]Install with: pip install 'ragmine[connector-{name}]'[/dim]")
    except ValueError as e:
        console.print(f"  [error]{e}[/error]")
        console.print(f"  [dim]Use /help {name} for usage[/dim]")
    except Exception as e:
        console.print(f"  [error]Error: {e}[/error]")


@click.group(invoke_without_command=True)
@click.version_option(package_name="ragmine")
@click.pass_context
def main(ctx):
    """⛏️  ragmine — Mine your documents. Local RAG that works."""
    if ctx.invoked_subcommand is None:
        run_chat()


@main.command()
@click.argument("path")
@click.option("--recursive/--no-recursive", default=True)
@click.option("--glob", default="*")
def ingest(path: str, recursive: bool, glob: str):
    """Ingest files into the knowledge base."""
    from ragmine.pipeline import Ragmine

    print_banner()
    rm = Ragmine()
    console.print()
    count = ingest_with_progress(rm, path, recursive=recursive, glob=glob)
    console.print()
    console.print(f"  [success]✓[/success] Mined [bold]{count}[/bold] chunks")
    s = rm.status()
    console.print(f"  [muted]Total: {s['total_chunks']} chunks from {s['total_sources']} sources[/muted]")
    console.print()


@main.command()
@click.argument("question")
@click.option("--top-k", default=None, type=int)
@click.option("--no-generate", is_flag=True)
def query(question: str, top_k: int | None, no_generate: bool):
    """Ask a question against your knowledge base."""
    from ragmine.pipeline import Ragmine

    rm = Ragmine()

    if no_generate:
        with console.status("  [magenta]Searching...[/magenta]", spinner="dots"):
            results = rm.search(question, limit=top_k)
        print_results_table(results)
        return

    with console.status("  [magenta]Searching & thinking...[/magenta]", spinner="dots"):
        response = rm.query(question)

    if response.sources:
        print_answer(response)
    else:
        console.print(f"  [warning]{response.answer}[/warning]")


@main.command()
def status():
    """Show knowledge base status."""
    from ragmine.pipeline import Ragmine

    rm = Ragmine()
    print_banner()
    print_status(rm)
    console.print()


@main.command()
@click.option("--limit", default=50, type=int)
@click.option("--offset", default=0, type=int)
def sources(limit: int, offset: int):
    """List all ingested sources."""
    from ragmine.pipeline import Ragmine

    rm = Ragmine()
    src_list = rm.store.list_sources(limit=limit, offset=offset)
    print_sources_table(src_list)
    console.print(f"\n  [muted]{len(src_list)} sources shown[/muted]")


@main.command()
@click.argument("source")
def delete(source: str):
    """Remove a source from the knowledge base."""
    from ragmine.pipeline import Ragmine

    rm = Ragmine()
    count = rm.store.delete_by_source(source)
    console.print(f"  [success]✓[/success] Deleted {count} chunks from {source}")


@main.command()
def serve():
    """Start the REST API server."""
    try:
        from ragmine.server.api import create_app
        import uvicorn
    except ImportError:
        console.print("  [error]Install extras: pip install 'ragmine[serve]'[/error]")
        return
    from ragmine.core.config import get_settings
    s = get_settings()
    print_banner()
    console.print(f"  [success]●[/success] API on [bold]http://{s.host}:{s.port}[/bold]")
    console.print(f"  [muted]Ctrl+C to stop[/muted]\n")
    uvicorn.run(create_app(), host=s.host, port=s.port, log_level="warning")


@main.command()
def mcp():
    """Start as MCP server (for Claude, Cursor, etc.)."""
    try:
        from ragmine.server.mcp_server import run_mcp
    except ImportError:
        console.print("  [error]Install extras: pip install 'ragmine[mcp]'[/error]")
        return
    run_mcp()


@main.command()
def tui():
    """Start the Textual TUI (terminal user interface)."""
    try:
        from ragmine.tui.app import RagmineTUI
    except ImportError:
        console.print("  [error]Install TUI: pip install 'ragmine[tui]'[/error]")
        return

    print_banner()
    console.print("  [info]Starting TUI...[/info]\n")
    app = RagmineTUI()
    app.run()


@main.command()
def help():
    """Show help for all commands and connectors."""
    console.print(HELP_TEXT)


if __name__ == "__main__":
    main()