"""
ragmine.server.api
~~~~~~~~~~~~~~~~~~~
REST API. Start with: ragmine serve
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    generate: bool = True


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class IngestRequest(BaseModel):
    path: str
    recursive: bool = True
    glob: str = "*"


def create_app():
    app = FastAPI(title="ragmine", version="0.1.0", description="Mine your documents.")
    rm = Ragmine()

    @app.post("/api/query")
    def query(req: QueryRequest):
        if req.generate:
            resp = rm.query(req.question)
            return {
                "answer": resp.answer,
                "sources": [
                    {"source": r.source, "text": r.chunk.text[:300], "score": r.score}
                    for r in resp.sources
                ],
                "latency_ms": resp.latency_ms,
            }
        else:
            results = rm.search(req.question, limit=req.top_k)
            return {
                "results": [
                    {"source": r.source, "text": r.chunk.text[:300], "score": r.score}
                    for r in results
                ]
            }

    @app.post("/api/query/stream")
    async def query_stream(req: QueryRequest):
        if not req.generate:
            return {"error": "Streaming only works with generate=true"}

        s = rm.settings
        full_prompt = _build_prompt(rm, req.question)

        async def event_generator():
            try:
                client = httpx.AsyncClient(base_url=s.ollama_base_url, timeout=120)
                async with client.stream(
                    "POST",
                    "/api/generate",
                    json={
                        "model": s.ollama_model,
                        "prompt": full_prompt,
                        "stream": True,
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data:
                                try:
                                    obj = json.loads(data)
                                    text = obj.get("response", "")
                                    if text:
                                        yield f"data: {json.dumps({'token': text})}\n\n"
                                except Exception:
                                    continue
                await client.aclose()
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/search")
    def search(req: SearchRequest):
        results = rm.search(req.query, limit=req.limit)
        return {
            "results": [
                {"source": r.source, "text": r.chunk.text[:300], "score": r.score}
                for r in results
            ]
        }

    @app.post("/api/ingest")
    def ingest(req: IngestRequest):
        count = rm.ingest(req.path, recursive=req.recursive, glob=req.glob)
        return {"chunks_created": count, "path": req.path}

    @app.post("/api/ingest/connector")
    def ingest_connector(req: IngestRequest):
        if req.path == "metabase":
            from ragmine.connectors.metabase import MetabaseConnector
            connector = MetabaseConnector(
                url=req.glob or "http://localhost:3000",
                api_key=req.recursive or "",
            )
            chunks = connector.fetch_chunks()
            count = rm.ingest_chunks(chunks, source="metabase")
            return {"chunks_created": count, "source": "metabase"}
        return {"error": "Unknown connector"}

    @app.get("/api/sources")
    def sources(limit: int = 100, offset: int = 0):
        return {"sources": rm.store.list_sources(limit=limit, offset=offset)}

    @app.delete("/api/sources/{source:path}")
    def delete_source(source: str):
        count = rm.store.delete_by_source(source)
        return {"deleted": count, "source": source}

    @app.get("/api/status")
    def status():
        return rm.status()

    @app.get("/")
    def root():
        return {"name": "ragmine", "version": "0.1.0", "status": "running"}

    return app


def _build_prompt(rm, question: str) -> str:
    from ragmine.pipeline import RAG_PROMPT, RAG_SYSTEM, _truncate_context
    from pathlib import Path

    results = rm.search(question)
    if not results:
        return RAG_PROMPT.format(context="No relevant documents found.", question=question)

    context_parts = []
    for i, r in enumerate(results, 1):
        source_name = Path(r.source).name if r.source else "unknown"
        context_parts.append(f"[Source {i}: {source_name}]\n{r.chunk.text}")

    context = "\n\n---\n\n".join(context_parts)
    context = _truncate_context(context, question)
    return RAG_PROMPT.format(context=context, question=question)


# Lazy import to avoid circular
from ragmine.pipeline import Ragmine
