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
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature

    def generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": self._max_tokens,
                "temperature": self._temperature,
            },
        }
        if system:
            payload["system"] = system

        data = self._generate_once(payload)
        answer = data.get("response", "")

        # Auto-continue once if Ollama stopped due to output length limit.
        if data.get("done_reason") == "length":
            ctx = data.get("context")
            if ctx:
                cont_payload = {
                    "model": self._model,
                    "prompt": "Continue from where you stopped. Do not repeat previous text.",
                    "stream": False,
                    "context": ctx,
                    "options": {
                        "num_predict": max(128, self._max_tokens // 2),
                        "temperature": self._temperature,
                    },
                }
                if system:
                    cont_payload["system"] = system
                cont_data = self._generate_once(cont_payload)
                answer += cont_data.get("response", "")

        return answer

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": self._max_tokens,
                "temperature": self._temperature,
            },
        }
        if system:
            payload["system"] = system

        data = await self._agenerate_once(payload)
        answer = data.get("response", "")

        if data.get("done_reason") == "length":
            ctx = data.get("context")
            if ctx:
                cont_payload = {
                    "model": self._model,
                    "prompt": "Continue from where you stopped. Do not repeat previous text.",
                    "stream": False,
                    "context": ctx,
                    "options": {
                        "num_predict": max(128, self._max_tokens // 2),
                        "temperature": self._temperature,
                    },
                }
                if system:
                    cont_payload["system"] = system
                cont_data = await self._agenerate_once(cont_payload)
                answer += cont_data.get("response", "")

        return answer

    def _generate_once(self, payload: dict) -> dict:
        resp = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    async def _agenerate_once(self, payload: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()


class OpenAICompatibleLLM:
    """Any OpenAI-compatible API (vLLM, LiteLLM, OpenRouter, etc.)."""

    def __init__(self, settings: Settings):
        self._base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = httpx.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": messages,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": self._max_tokens,
                    "temperature": self._temperature,
                },
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
