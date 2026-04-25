"""
ragmine.retrieve.rerank
~~~~~~~~~~~~~~~~~~~~~~~~
Cross-encoder reranker. Optional — enable via RAGMINE_RERANK_ENABLED=true.
"""

from __future__ import annotations

from ragmine.core.config import Settings
from ragmine.core.protocols import SearchResult


class CrossEncoderReranker:
    """Reranks results using a cross-encoder model. Runs on CPU."""

    def __init__(self, settings: Settings):
        self._model_name = settings.rerank_model
        self._model = None

    @property
    def _m(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        if not results:
            return []

        pairs = [(query, r.chunk.text) for r in results]
        scores = self._m.predict(pairs)

        for result, score in zip(results, scores):
            result.score = float(score)

        reranked = sorted(results, key=lambda r: r.score, reverse=True)
        return reranked[:top_k]


class NoopReranker:
    """Pass-through reranker. Just truncates to top_k."""

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        return results[:top_k]
