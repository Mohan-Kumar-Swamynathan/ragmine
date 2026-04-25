"""
ragmine.tui.screens.chat
~~~~~~~~~~~~~~~~~~~~~~~~
Main chat screen with message history and input.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Label
from textual.widget import Widget

from ragmine.core.protocols import RAGResponse, SearchResult
from ragmine.pipeline import Ragmine


class ChatMessage(Widget):
    """A chat message."""

    def __init__(self, role: str, content: str, sources: list[SearchResult] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.sources = sources or []

    def compose(self) -> ComposeResult:
        role_color = "cyan" if self.role == "user" else "white"
        role_label = "You" if self.role == "user" else "⛏️  ragmine"

        yield Label(f"[{role_color}]{role_label}:[/{role_color}]", markup=True)
        yield Label(self.content)

        if self.sources:
            yield Label("[dim]Sources:[/dim]", markup=True)
            for i, src in enumerate(self.sources, 1):
                name = Path(src.source).name if src.source else "unknown"
                yield Label(f"  [blue]{i}.[/blue] {name} ({src.score:.2f})", markup=True)


class ChatInput(Widget):
    """Chat input with send button."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield Input(placeholder="Ask a question...", id="chat-input-field")
            yield Label("[ ⛏️ ]", markup=True, id="send-btn")


class ChatScreen(Widget):
    """Main chat interface."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ragmine: Ragmine | None = None
        self._messages: list[dict] = []
        self._loading = False
        self._stream_task: asyncio.Task | None = None

    def set_ragmine(self, rm: Ragmine) -> None:
        self._ragmine = rm

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield VerticalScroll(id="messages-scroll")
            with Vertical(id="input-area"):
                yield ChatInput()

    def on_mount(self) -> None:
        input_field = self.query_one("#chat-input-field", Input)
        input_field.focus()
        self._update_status()

    def _update_status(self) -> None:
        if self._ragmine:
            status = self._ragmine.status()
            self.app.query_one("#status-bar", Widget).update(
                chunks=status.get("total_chunks", 0),
                sources=status.get("total_sources", 0),
                model=status.get("llm_model", ""),
            )

    def clear_messages(self) -> None:
        container = self.query_one("#messages-scroll", VerticalScroll)
        container.remove_children()
        self._messages.clear()

    def interrupt(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._loading or not event.value.strip():
            return

        query = event.value.strip()
        self._add_message("user", query)

        input_field = self.query_one("#chat-input-field", Input)
        input_field.value = ""

        asyncio.create_task(self._run_query(query))

    async def _run_query(self, query: str) -> None:
        if not self._ragmine:
            return

        self._loading = True

        try:
            response = await self._ragmine.aquery(query)
            self._add_message("assistant", response.answer, response.sources)
        except Exception as e:
            self._add_message("assistant", f"Error: {str(e)}")
        finally:
            self._loading = False

    def _add_message(self, role: str, content: str, sources: list[SearchResult] | None = None) -> None:
        container = self.query_one("#messages-scroll", VerticalScroll)

        msg = ChatMessage(role=role, content=content, sources=sources)
        container.mount(msg)
        container.scroll_end(animate=False)

        self._messages.append({"role": role, "content": content})