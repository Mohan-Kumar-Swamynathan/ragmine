"""
ragmine.core.config
~~~~~~~~~~~~~~~~~~~~
All settings in one place. Env vars, YAML, or code.

    RAGMINE_DATA_DIR=~/.ragmine ragmine ingest ./docs
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAGMINE_", env_file=".env", extra="ignore")

    # ── Storage ──
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".ragmine")
    db_name: str = "default"

    # ── Embeddings ──
    embedding_provider: Literal["sentence-transformers", "ollama"] = "sentence-transformers"
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Chunking ──
    chunk_size: int = 512
    chunk_overlap: int = 77  # ~15% of 512

    # ── Retrieval ──
    top_k: int = 5
    top_k_retrieve: int = 50  # candidates before rerank

    # ── Reranker ──
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── LLM ──
    llm_provider: Literal["ollama", "openai-compatible"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""

    # ── Store backend ──
    store_backend: Literal["lancedb", "chroma"] = "lancedb"

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8420

    @property
    def db_path(self) -> Path:
        p = self.data_dir / self.db_name
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton-ish, importable anywhere
_settings: Settings | None = None


def get_settings(**overrides) -> Settings:
    global _settings
    if _settings is None or overrides:
        _settings = Settings(**overrides)
    return _settings
