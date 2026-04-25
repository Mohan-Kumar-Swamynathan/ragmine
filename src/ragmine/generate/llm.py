"""
ragmine.generate.llm
~~~~~~~~~~~~~~~~~~~~~
LLM clients. Ollama by default, any OpenAI-compatible API as fallback.
"""

from __future__ import annotations

import asyncio

import httpx

from ragmine.core.config import Settings


class OllamaLLM:
    """Ollama LLM — fully local, no API keys."""

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model

    def generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        resp = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        client = httpx.AsyncClient()
        resp = await client.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        await client.aclose()
        resp.raise_for_status()
        return resp.json().get("response", "")


class OpenAICompatibleLLM:
    """Any OpenAI-compatible API (vLLM, LiteLLM, OpenRouter, etc.)."""

    def __init__(self, settings: Settings):
        self._base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = httpx.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = httpx.AsyncClient()
        resp = await client.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages},
            timeout=120,
        )
        await client.aclose()
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
