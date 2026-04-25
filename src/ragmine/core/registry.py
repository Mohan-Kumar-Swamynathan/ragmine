"""
ragmine.core.registry
~~~~~~~~~~~~~~~~~~~~~~
Register and resolve components. Swap anything.

    from ragmine.core.registry import registry

    # Use defaults
    embedder = registry.get_embedder()

    # Or register your own
    registry.register_embedder("my-embedder", MyEmbedder)
    embedder = registry.get_embedder("my-embedder")
"""

from __future__ import annotations

from typing import Any

from ragmine.core.config import Settings, get_settings
from ragmine.core.protocols import Chunker, Embedder, LLMClient, Parser, Reranker, VectorStore


class Registry:
    """Central registry for pluggable components."""

    def __init__(self):
        self._embedders: dict[str, type] = {}
        self._stores: dict[str, type] = {}
        self._chunkers: dict[str, type] = {}
        self._parsers: dict[str, type] = {}
        self._llms: dict[str, type] = {}
        self._rerankers: dict[str, type] = {}
        self._instances: dict[str, Any] = {}

    # ── Registration ──

    def register_embedder(self, name: str, cls: type):
        self._embedders[name] = cls

    def register_store(self, name: str, cls: type):
        self._stores[name] = cls

    def register_chunker(self, name: str, cls: type):
        self._chunkers[name] = cls

    def register_parser(self, name: str, cls: type):
        self._parsers[name] = cls

    def register_llm(self, name: str, cls: type):
        self._llms[name] = cls

    def register_reranker(self, name: str, cls: type):
        self._rerankers[name] = cls

    # ── Resolution (lazy-load defaults) ──

    def get_embedder(self, name: str | None = None, settings: Settings | None = None) -> Embedder:
        s = settings or get_settings()
        key = name or s.embedding_provider
        cache_key = f"embedder:{key}"

        if cache_key not in self._instances:
            if key in self._embedders:
                self._instances[cache_key] = self._embedders[key](s)
            else:
                self._instances[cache_key] = self._load_default_embedder(s)

        return self._instances[cache_key]

    def get_store(self, name: str | None = None, settings: Settings | None = None) -> VectorStore:
        s = settings or get_settings()
        key = name or s.store_backend
        cache_key = f"store:{key}"

        if cache_key not in self._instances:
            if key in self._stores:
                self._instances[cache_key] = self._stores[key](s)
            else:
                self._instances[cache_key] = self._load_default_store(s)

        return self._instances[cache_key]

    def get_chunker(self, name: str = "recursive", settings: Settings | None = None) -> Chunker:
        s = settings or get_settings()
        cache_key = f"chunker:{name}"

        if cache_key not in self._instances:
            if name in self._chunkers:
                self._instances[cache_key] = self._chunkers[name](s)
            else:
                self._instances[cache_key] = self._load_default_chunker(s)

        return self._instances[cache_key]

    def get_parser(self, settings: Settings | None = None) -> Parser:
        s = settings or get_settings()
        cache_key = "parser:default"

        if cache_key not in self._instances:
            self._instances[cache_key] = self._load_default_parser(s)

        return self._instances[cache_key]

    def get_llm(self, name: str | None = None, settings: Settings | None = None) -> LLMClient:
        s = settings or get_settings()
        key = name or s.llm_provider
        cache_key = f"llm:{key}"

        if cache_key not in self._instances:
            if key in self._llms:
                self._instances[cache_key] = self._llms[key](s)
            else:
                self._instances[cache_key] = self._load_default_llm(s)

        return self._instances[cache_key]

    def get_reranker(self, settings: Settings | None = None) -> Reranker | None:
        s = settings or get_settings()
        if not s.rerank_enabled:
            return None
        cache_key = "reranker:default"

        if cache_key not in self._instances:
            self._instances[cache_key] = self._load_default_reranker(s)

        return self._instances[cache_key]

    def clear_cache(self):
        self._instances.clear()

    # ── Default loaders (lazy imports to keep deps optional) ──

    def _load_default_embedder(self, s: Settings) -> Embedder:
        if s.embedding_provider == "ollama":
            from ragmine.core.embedder import OllamaEmbedder
            return OllamaEmbedder(s)
        else:
            from ragmine.core.embedder import SentenceTransformerEmbedder
            return SentenceTransformerEmbedder(s)

    def _load_default_store(self, s: Settings) -> VectorStore:
        if s.store_backend == "chroma":
            from ragmine.core.store_chroma import ChromaStore
            return ChromaStore(s)
        else:
            from ragmine.core.store_lance import LanceStore
            return LanceStore(s)

    def _load_default_chunker(self, s: Settings) -> Chunker:
        from ragmine.ingest.chunker import RecursiveChunker
        return RecursiveChunker(s)

    def _load_default_parser(self, s: Settings) -> Parser:
        from ragmine.ingest.parser import SmartParser
        return SmartParser(s)

    def _load_default_llm(self, s: Settings) -> LLMClient:
        from ragmine.generate.llm import OllamaLLM
        return OllamaLLM(s)

    def _load_default_reranker(self, s: Settings) -> Reranker:
        from ragmine.retrieve.rerank import CrossEncoderReranker
        return CrossEncoderReranker(s)


# Global registry
registry = Registry()
