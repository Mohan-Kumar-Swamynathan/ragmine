"""
ragmine.pipeline
~~~~~~~~~~~~~~~~~
The main pipeline. Ingest docs, query them, get answers.

    from ragmine import Ragmine

    rm = Ragmine()
    rm.ingest("./docs")
    answer = rm.query("How does auth work?")
"""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from ragmine.core.config import Settings, get_settings
from ragmine.core.protocols import Chunk, RAGResponse, SearchResult
from ragmine.core.registry import registry
from ragmine.retrieve.search import HybridSearcher

console = Console()

RAG_SYSTEM = "You are a helpful assistant. Answer based on the provided context. Cite sources."

MAX_CONTEXT_TOKENS = 8000


def _count_tokens(text: str) -> int:
    return len(text) // 4


def _truncate_context(context: str, question: str) -> str:
    tokens = _count_tokens(context)
    if tokens <= MAX_CONTEXT_TOKENS:
        return context

    allowed = MAX_CONTEXT_TOKENS - _count_tokens(question) - 100
    return context[: allowed * 4]


RAG_PROMPT = """Use the following context to answer the question.
If the context doesn't contain the answer, say "I don't have enough information."

Context:
{context}

Question: {question}

Answer:"""


class Ragmine:
    """The main API. Simple to use, everything pluggable underneath."""

    def __init__(self, settings: Settings | None = None, **overrides):
        self.settings = settings or get_settings(**overrides)
        self._searcher: HybridSearcher | None = None

    @property
    def store(self):
        return registry.get_store(settings=self.settings)

    @property
    def embedder(self):
        return registry.get_embedder(settings=self.settings)

    @property
    def chunker(self):
        return registry.get_chunker(settings=self.settings)

    @property
    def parser(self):
        return registry.get_parser(settings=self.settings)

    @property
    def llm(self):
        return registry.get_llm(settings=self.settings)

    @property
    def searcher(self) -> HybridSearcher:
        if self._searcher is None:
            self._searcher = HybridSearcher(self.store, self.embedder)
        return self._searcher

    # ── Ingest ──

    def ingest(self, path: str, recursive: bool = True, glob: str = "*") -> int:
        """Ingest a file or directory. Returns number of chunks created."""
        p = Path(path)
        total = 0

        if p.is_file():
            total += self._ingest_file(p)
        elif p.is_dir():
            patterns = glob.split(",") if "," in glob else [glob]
            for pattern in patterns:
                for f in sorted(p.rglob(pattern.strip()) if recursive else p.glob(pattern.strip())):
                    if f.is_file() and self.parser.supports(str(f)):
                        total += self._ingest_file(f)
        else:
            console.print(f"[red]Path not found: {path}[/red]")

        return total

    def ingest_chunks(self, chunks: list[Chunk], source: str) -> int:
        """Ingest chunks directly (from connector or other source)."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_texts(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        count = self.store.add_chunks(chunks)
        return count

    def upsert_chunks(self, chunks: list[Chunk], source: str) -> int:
        """Upsert chunks (update existing or insert new)."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_texts(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        count = self.store.update_chunks(chunks)
        return count

    def _ingest_file(self, file_path: Path) -> int:
        """Parse → chunk → embed → store a single file."""
        source = str(file_path)

        # Remove old chunks for this file (re-ingest = replace)
        self.store.delete_by_source(source)

        # Parse
        doc = self.parser.parse(source)
        if not doc.text.strip():
            return 0

        # Chunk
        chunks = self.chunker.chunk(doc)
        if not chunks:
            return 0

        # Embed
        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_texts(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        # Store
        count = self.store.add_chunks(chunks)
        return count

    # ── Search ──

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        """Search without LLM generation."""
        k = limit or self.settings.top_k_retrieve
        results = self.searcher.search(query, limit=k)

        # Optional rerank
        reranker = registry.get_reranker(settings=self.settings)
        if reranker:
            results = reranker.rerank(query, results, top_k=self.settings.top_k)
        else:
            results = results[: self.settings.top_k]

        return results

    # ── Query (search + generate) ──

    def query(self, question: str) -> RAGResponse:
        """Full RAG: search → rerank → generate answer."""
        start = time.time()

        results = self.search(question)

        if not results:
            return RAGResponse(
                answer="No relevant documents found. Try ingesting some documents first.",
                sources=[], query=question,
                latency_ms=(time.time() - start) * 1000,
            )

        # Build context with truncation
        context_parts = []
        for i, r in enumerate(results, 1):
            source_name = Path(r.source).name if r.source else "unknown"
            context_parts.append(f"[Source {i}: {source_name}]\n{r.chunk.text}")

        context = "\n\n---\n\n".join(context_parts)
        context = _truncate_context(context, question)
        prompt = RAG_PROMPT.format(context=context, question=question)

        # Generate
        answer = self.llm.generate(prompt, system=RAG_SYSTEM)

        return RAGResponse(
            answer=answer,
            sources=results,
            query=question,
            latency_ms=(time.time() - start) * 1000,
        )

    async def aquery(self, question: str) -> RAGResponse:
        """Async full RAG pipeline."""
        start = time.time()

        k = self.settings.top_k_retrieve
        embedding = await self.embedder.aembed_query(question)
        vec_results = self.store.vector_search(embedding, limit=k)
        fts_results = self.store.fts_search(question, limit=k)

        from ragmine.retrieve.search import rrf_fuse
        if fts_results:
            results = rrf_fuse(vec_results, fts_results)[:k]
        else:
            results = vec_results[:k]

        reranker = registry.get_reranker(settings=self.settings)
        if reranker:
            results = reranker.rerank(question, results, top_k=self.settings.top_k)
        else:
            results = results[: self.settings.top_k]

        if not results:
            return RAGResponse(
                answer="No relevant documents found. Try ingesting some documents first.",
                sources=[], query=question,
                latency_ms=(time.time() - start) * 1000,
            )

        context_parts = []
        for i, r in enumerate(results, 1):
            source_name = Path(r.source).name if r.source else "unknown"
            context_parts.append(f"[Source {i}: {source_name}]\n{r.chunk.text}")

        context = "\n\n---\n\n".join(context_parts)
        context = _truncate_context(context, question)
        prompt = RAG_PROMPT.format(context=context, question=question)

        answer = await self.llm.agenerate(prompt, system=RAG_SYSTEM)

        return RAGResponse(
            answer=answer,
            sources=results,
            query=question,
            latency_ms=(time.time() - start) * 1000,
        )

    # ── Status ──

    def status(self) -> dict:
        return {
            "total_chunks": self.store.count(),
            "total_sources": len(self.store.list_sources()),
            "store_backend": self.settings.store_backend,
            "embedding_model": self.settings.embedding_model,
            "llm_model": self.settings.ollama_model,
            "data_dir": str(self.settings.data_dir),
        }
