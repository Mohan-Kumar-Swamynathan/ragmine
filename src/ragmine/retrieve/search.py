"""
ragmine.retrieve.search
~~~~~~~~~~~~~~~~~~~~~~~~
Hybrid search: vector + BM25/FTS combined via Reciprocal Rank Fusion.
"""

from __future__ import annotations

from ragmine.core.protocols import Embedder, SearchResult, VectorStore


def rrf_fuse(
    *result_lists: list[SearchResult],
    k: int = 60,
) -> list[SearchResult]:
    """Reciprocal Rank Fusion — combines multiple ranked lists.

    score(doc) = sum(1 / (k + rank)) across all lists it appears in.
    """
    scores: dict[str, float] = {}
    seen: dict[str, SearchResult] = {}

    for results in result_lists:
        for rank, r in enumerate(results):
            doc_id = r.chunk.id
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in seen:
                seen[doc_id] = r

    # Sort by fused score
    ranked_ids = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)

    fused = []
    for doc_id in ranked_ids:
        result = seen[doc_id]
        result.score = scores[doc_id]
        fused.append(result)

    return fused


class HybridSearcher:
    """Runs vector + FTS search and fuses results."""

    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder

    def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        embedding = self.embedder.embed_query(query)

        vec_results = self.store.vector_search(embedding, limit=limit)
        fts_results = self.store.fts_search(query, limit=limit)

        if fts_results:
            return rrf_fuse(vec_results, fts_results)[:limit]
        else:
            return vec_results[:limit]
