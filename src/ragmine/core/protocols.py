"""
ragmine.core.protocols
~~~~~~~~~~~~~~~~~~~~~~
Every component is a Protocol. Swap any piece.

    from ragmine.core.protocols import Embedder, VectorStore, Chunker

Implement the protocol, register it, done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Data Models ──────────────────────────────────────────────


@dataclass
class Chunk:
    """A piece of a document, ready for embedding."""

    id: str
    text: str
    source: str
    source_type: str = "text"
    chunk_index: int = 0
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class SearchResult:
    """A retrieved chunk with relevance score."""

    chunk: Chunk
    score: float
    source: str = ""

    def __post_init__(self):
        if not self.source:
            self.source = self.chunk.source


@dataclass
class ParsedDocument:
    """Output of a parser."""

    text: str
    source: str
    source_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[str] | None = None


@dataclass
class RAGResponse:
    """Final RAG answer."""

    answer: str
    sources: list[SearchResult]
    query: str
    latency_ms: float = 0.0


# ── Protocols (the pluggable interfaces) ─────────────────────


@runtime_checkable
class Embedder(Protocol):
    """Turns text into vectors. Swap models freely."""

    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    async def aembed_texts(self, texts: list[str]) -> list[list[float]]:
        """Async version - default falls back to sync."""
        return self.embed_texts(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Async version - default falls back to sync."""
        return self.embed_query(text)


@dataclass
class SearchFilter:
    """Filter for metadata-based search."""
    source: str | None = None
    source_type: str | None = None
    metadata: dict[str, Any] | None = None


@runtime_checkable
class VectorStore(Protocol):
    """Stores and searches chunks. Swap backends freely."""

    def add_chunks(self, chunks: list[Chunk]) -> int: ...

    def update_chunks(self, chunks: list[Chunk]) -> int:
        """Upsert chunks (insert or update existing). Default just deletes and re-adds."""
        return 0

    def vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]: ...

    def fts_search(self, query: str, limit: int = 10) -> list[SearchResult]: ...

    def delete_by_source(self, source: str) -> int: ...

    def list_sources(self, limit: int = 100, offset: int = 0) -> list[str]: ...

    def count(self) -> int: ...

    async def aadd_chunks(self, chunks: list[Chunk]) -> int:
        """Async version - default falls back to sync."""
        return self.add_chunks(chunks)

    async def aupdate_chunks(self, chunks: list[Chunk]) -> int:
        """Async version - default falls back to sync."""
        return self.update_chunks(chunks)

    async def adelete_by_source(self, source: str) -> int:
        """Async version - default falls back to sync."""
        return self.delete_by_source(source)


@runtime_checkable
class Chunker(Protocol):
    """Splits documents into chunks. Swap strategies freely."""

    def chunk(self, doc: ParsedDocument) -> list[Chunk]: ...


@runtime_checkable
class Parser(Protocol):
    """Extracts text from files. Swap parsers freely."""

    def parse(self, file_path: str) -> ParsedDocument: ...

    def supports(self, file_path: str) -> bool: ...


@runtime_checkable
class LLMClient(Protocol):
    """Generates text from prompts. Swap providers freely."""

    def generate(self, prompt: str, system: str | None = None) -> str: ...

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        """Async version - default falls back to sync."""
        return self.generate(prompt, system)


@runtime_checkable
class Reranker(Protocol):
    """Reranks search results. Optional, swap models freely."""

    def rerank(self, query: str, results: list[SearchResult], top_k: int = 5) -> list[SearchResult]:
        ...
