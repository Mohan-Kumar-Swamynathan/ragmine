"""
ragmine.core.embedder
~~~~~~~~~~~~~~~~~~~~~
Default embedders. Pluggable — register your own via registry.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ragmine.core.config import Settings


class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers. No API needed."""

    def __init__(self, settings: Settings):
        self._model_name = settings.embedding_model
        self._model = None

    @property
    def _m(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._m.get_sentence_embedding_dimension()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._m.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embeddings]

    def embed_query(self, text: str) -> list[float]:
        return self._m.encode(text, show_progress_bar=False).tolist()

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
