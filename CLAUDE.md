# CLAUDE.md — Ragmine

## What is this?
Ragmine is a local-first RAG server. Simple to use, everything is pluggable.

## Architecture: Protocols + Defaults
Every component is a Python Protocol. Users can swap any piece.
- `Embedder` protocol → default: SentenceTransformer
- `VectorStore` protocol → default: LanceDB
- `Chunker` protocol → default: RecursiveChunker
- `Parser` protocol → default: TextParser (Docling optional)
- `LLMClient` protocol → default: Ollama via httpx
- `Reranker` protocol → default: CrossEncoder (optional)

## Tech Stack
- Python 3.11+, managed with uv
- Config: Pydantic Settings
- CLI: Click + Rich
- API: FastAPI (optional)
- MCP: mcp[cli] FastMCP (optional)

## Code Style
- Type hints everywhere
- Protocols for interfaces, not ABCs
- Async where I/O bound
- Small modules (<200 lines)
- No unnecessary abstractions

## Key Paths
- src/ragmine/core/protocols.py — ALL interfaces live here
- src/ragmine/core/config.py — settings
- src/ragmine/core/registry.py — plugin registry
- src/ragmine/ingest/ — parsing + chunking
- src/ragmine/retrieve/ — search + rerank
- src/ragmine/generate/ — LLM interaction
- src/ragmine/server/ — API + MCP
- src/ragmine/connectors/ — Metabase, GitHub, etc.
