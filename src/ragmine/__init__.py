"""
ragmine — Mine your documents. Local RAG that works.

    from ragmine import Ragmine

    rm = Ragmine()
    rm.ingest("./docs")
    answer = rm.query("How does auth work?")
    print(answer.answer)
"""

__version__ = "0.2.0"

from ragmine.pipeline import Ragmine
from ragmine.core.protocols import (
    Chunk,
    Embedder,
    LLMClient,
    ParsedDocument,
    Parser,
    RAGResponse,
    Reranker,
    SearchResult,
    VectorStore,
    Chunker,
)
from ragmine.core.registry import registry
from ragmine.core.config import Settings, get_settings

__all__ = [
    "Ragmine",
    "registry",
    "Settings",
    "get_settings",
    # Protocols (for plugins)
    "Embedder",
    "VectorStore",
    "Chunker",
    "Parser",
    "LLMClient",
    "Reranker",
    # Data models
    "Chunk",
    "SearchResult",
    "ParsedDocument",
    "RAGResponse",
]
