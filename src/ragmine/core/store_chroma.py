"""
ragmine.core.store_chroma
~~~~~~~~~~~~~~~~~~~~~~~~
ChromaDB backend — another vector store option.
"""

from __future__ import annotations

import uuid
from typing import Any

from ragmine.core.config import Settings
from ragmine.core.protocols import Chunk, SearchFilter, SearchResult


class ChromaStore:
    """ChromaDB vector store with collection-based storage."""

    def __init__(self, settings: Settings):
        import chromadb

        self._client = chromadb.PersistentClient(
            path=str(settings.db_path / "chroma.db")
        )
        self._collection = None
        self._dim = 384

    def _get_collection(self, dim: int = 384):
        if self._collection is None:
            try:
                self._collection = self._client.get_collection("ragmine")
            except Exception:
                self._collection = self._client.create_collection(
                    "ragmine",
                    metadata={"hnsw:space": f"l2_{dim}"}
                )
            self._dim = dim
        return self._collection

    def _ensure_collection(self, dim: int):
        self._get_collection(dim)

    def create_fts_index(self):
        """Chroma doesn't have native FTS, returns False."""
        return False

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0

        dim = len(chunks[0].embedding) if chunks[0].embedding else self._dim
        self._ensure_collection(dim)

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for c in chunks:
            if c.embedding is None:
                continue
            ids.append(c.id or str(uuid.uuid4()))
            embeddings.append(c.embedding)
            documents.append(c.text)
            metadatas.append({
                "source": c.source,
                "source_type": c.source_type,
                "chunk_index": c.chunk_index,
            })

        if ids:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        return len(ids)

    def update_chunks(self, chunks: list[Chunk]) -> int:
        """Upsert chunks (insert or update existing)."""
        if not chunks:
            return 0

        deleted = 0
        for c in chunks:
            if c.source:
                deleted += self.delete_by_source(c.source)

        return deleted + self.add_chunks(chunks)

    def vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]:
        if self._collection is None:
            return []

        where = {}
        if filter:
            if filter.source:
                where["source"] = filter.source
            if filter.source_type:
                where["source_type"] = filter.source_type

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=where if where else None,
        )

        return self._results_to_search_results(results)

    def fts_search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return self.vector_search(
            self._get_dummy_embedding(limit),
            limit=limit
        )

    def _get_dummy_embedding(self, dim: int = 384) -> list[float]:
        return [0.0] * dim

    def delete_by_source(self, source: str) -> int:
        if self._collection is None:
            return 0

        try:
            results = self._collection.get(where={"source": source})
            if results and results["ids"]:
                self._collection.delete(ids=results["ids"])
                return len(results["ids"])
        except Exception:
            pass
        return 0

    def list_sources(self, limit: int = 100, offset: int = 0) -> list[str]:
        if self._collection is None:
            return []

        try:
            results = self._collection.get()
            if results and results["metadatas"]:
                sources = []
                seen = set()
                for meta in results["metadatas"]:
                    if "source" in meta and meta["source"] not in seen:
                        sources.append(meta["source"])
                        seen.add(meta["source"])
                return sorted(sources)[offset:offset + limit]
        except Exception:
            pass
        return []

    def count(self) -> int:
        if self._collection is None:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def _results_to_search_results(self, results: dict) -> list[SearchResult]:
        search_results = []

        if not results or not results.get("ids"):
            return []

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            chunk = Chunk(
                id=doc_id,
                text=documents[i] if i < len(documents) else "",
                source=meta.get("source", ""),
                source_type=meta.get("source_type", "text"),
                chunk_index=meta.get("chunk_index", 0),
            )

            dist = distances[i] if i < len(distances) else 0.0
            score = 1.0 / (1.0 + dist)

            search_results.append(SearchResult(chunk=chunk, score=score))

        return search_results