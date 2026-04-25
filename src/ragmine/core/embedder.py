"""
ragmine.core.embedder
~~~~~~~~~~~~~~~~~~~~~
Default embedders. Pluggable — register your own via registry.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Any

from ragmine.core.config import Settings


class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers. No API needed."""

    def __init__(self, settings: Settings):
        self._model_name = settings.embedding_model
        self._model = None
        self._fallback_dimension = 384

    @property
    def _m(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        try:
            return self._m.get_sentence_embedding_dimension()
        except Exception:
            return self._fallback_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self._m.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            if "fds_to_keep" not in str(e):
                raise
            return [_hash_embed_text(text, self._fallback_dimension) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._m.encode(text, show_progress_bar=False).tolist()
        except Exception as e:
            if "fds_to_keep" not in str(e):
                raise
            return _hash_embed_text(text, self._fallback_dimension)

    async def aembed_texts(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_texts, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


class OllamaEmbedder:
    """Embeddings via Ollama API. Fully local, privacy-first."""

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url
        self._model = settings.embedding_model
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            vec = self.embed_query("hello")
            self._dimension = len(vec)
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        import httpx
        resp = httpx.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def aembed_texts(self, texts: list[str]) -> list[list[float]]:
        async def embed_one(t: str) -> list[float]:
            import httpx
            resp = await httpx.AsyncClient().post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": t},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]

        results = await asyncio.gather(*[embed_one(t) for t in texts])
        return list(results)

    async def aembed_query(self, text: str) -> list[float]:
        import httpx
        client = httpx.AsyncClient()
        resp = await client.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=60,
        )
        await client.aclose()
        resp.raise_for_status()
        return resp.json()["embedding"]


def _hash_embed_text(text: str, dim: int) -> list[float]:
    """Deterministic fallback embedding when model inference is unavailable."""
    if dim <= 0:
        return []
    if not text:
        return [0.0] * dim

    vec = [0.0] * dim
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = -1.0 if digest[4] & 1 else 1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]
