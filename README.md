# ragmine ⛏️

**Mine your documents. Local RAG that works.**

Zero-config local RAG with hybrid search, smart chunking, MCP support, and 9 data connectors.
Everything is pluggable — swap any component without touching the rest.

```bash
pip install 'ragmine[all]'
ragmine
```

## Features

- **Simple** — one command to ingest, one command to query
- **Pluggable** — every component is a Protocol. Swap embeddings, stores, chunkers, LLMs freely
- **Hybrid search** — vector + full-text search combined via Reciprocal Rank Fusion
- **Smart chunking** — auto-routes by document type (markdown, code, text, PDF)
- **MCP native** — works as MCP server for Claude, Cursor, Codex, ChatGPT
- **Local-first** — runs fully offline with Ollama. No data leaves your machine
- **Reranking** — optional cross-encoder reranking for precision
- **Async support** — async pipelines for better performance
- **Textual TUI** — OpenCode-like terminal interface with command palette

## Quick Start

```bash
# Install with all batteries
pip install 'ragmine[all]'

# Interactive CLI
ragmine

# Ingest documents
ragmine ingest ./my-project --glob "*.py,*.md"
ragmine ingest ~/Documents/papers

# One-shot query (no LLM needed)
ragmine query "kafka retry logic" --no-generate

# Full RAG
ragmine query "How does the payment service handle failures?"

# Textual TUI (OpenCode-like interface)
ragmine tui
```

## Connectors

Pull data from 9 external sources:

| Connector | Description | Command |
|-----------|-------------|---------|
| `web` | Fetch web pages | `/connect web --url=https://...` |
| `github` | Repos, issues, PRs | `/connect github --repo=owner/repo` |
| `confluence` | Spaces & pages | `/connect confluence --space=KEY` |
| `slack` | Channels & messages | `/connect slack --channel=C012345` |
| `notion` | Pages & databases | `/connect notion --page=id` |
| `database` | SQL schemas & queries | `/connect database --dsn=...` |
| `rss` | RSS/Atom feeds | `/connect rss --feed=https://...` |
| `s3` | S3/GCS bucket files | `/connect s3 --bucket=...` |
| `metabase` | Schemas & questions | `/connect metabase --url=...` |

### Example: Web Connector
```bash
ragmine /connect web --url=https://docs.example.com --url=https://blog.example.com
```

### Example: GitHub Connector
```bash
ragmine /connect github --repo=owner/repo --token=ghp_xxx --include-issues --include-prs
```

### Example: RSS Feed
```bash
ragmine /connect rss --feed=https://hnrss.org/frontpage --days=7
```

## Interactive CLI

The CLI works like opencode — just type to query:

```
 ⛏️  ragmine v0.2.0
   Mine your documents. Local RAG that works.

   ● 127 chunks from 3 sources ready

 Commands:
     /ingest <path>  — add documents       /sources  — list sources
     /status         — show stats          /delete <src> — remove source
     /search <q>    — search only        /clear   — clear screen
     /connect <src> — ingest connector   /help   — show this
     /quit         — exit

 Connectors:
     web, github, confluence, slack, notion, database, rss, s3, metabase

 Shortcuts:
     i <path>    — ingest           s <q>     — search
     q <q>      — query           ?        — help
```

### Help System
```bash
/help           # General help
/help connectors # All available connectors
/help web       # Help for specific connector
```

## Textual TUI

Start the modern TUI with command palette (Ctrl+P):

```bash
ragmine tui
```

Features:
- Command palette with fuzzy search
- Sidebar navigation
- Scrollable message history
- Keyboard shortcuts

```
Ctrl+P  — Command palette
Ctrl+B  — Toggle sidebar
Ctrl+N  — New conversation
Esc     — Cancel/close
```

## Python API

```python
from ragmine import Ragmine

rm = Ragmine()

# Ingest files or directories
rm.ingest("./docs")
rm.ingest("./docs", glob="*.py,*.md")

# Ingest from connectors
from ragmine.connectors.web import WebConnector
connector = WebConnector(urls=["https://example.com"])
chunks = connector.fetch_chunks()
rm.ingest_chunks(chunks, source="web:example.com")

# Upsert (update existing or insert new)
rm.upsert_chunks(chunks, source="web:example.com")

# Search only
results = rm.search("authentication flow")
for r in results:
    print(f"{r.source}: {r.chunk.text[:100]}")

# Full RAG
response = rm.query("How does auth work?")
print(response.answer)
print(response.sources)

# Async pipeline
import asyncio
response = asyncio.run(rm.aquery("How does auth work?"))
```

### Filtered Search

```python
from ragmine.core.protocols import SearchFilter

results = rm.store.vector_search(
    embedding,
    limit=10,
    filter=SearchFilter(source_type="code")
)
```

## MCP Server (Claude, Cursor, Codex)

```json
{
  "mcpServers": {
    "ragmine": {
      "command": "ragmine",
      "args": ["mcp"]
    }
  }
}
```

Now your AI assistant can search your knowledge base automatically.

## REST API

```bash
# Start server
ragmine serve

# Query with streaming
curl -N -X POST http://localhost:8420/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "How does auth work?", "generate": true}'
```

## Pluggable Architecture

Every component is a `Protocol`. Register your own:

```python
from ragmine import Ragmine, registry, Embedder

class MyEmbedder:
    @property
    def dimension(self) -> int:
        return 768

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        # Your custom embedding logic
        ...

    def embed_query(self, text: str) -> list[float]:
        ...

registry.register_embedder("my-embedder", MyEmbedder)
rm = Ragmine(embedding_provider="my-embedder")
```

Same pattern works for: `VectorStore`, `Chunker`, `Parser`, `LLMClient`, `Reranker`

## Configuration

All settings via environment variables (prefix `RAGMINE_`) or `.env` file:

```bash
# Storage
RAGMINE_DATA_DIR=~/.ragmine
RAGMINE_DB_NAME=default
RAGMINE_STORE_BACKEND=lancedb  # or: chroma

# Embeddings
RAGMINE_EMBEDDING_PROVIDER=sentence-transformers  # or: ollama
RAGMINE_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Chunking
RAGMINE_CHUNK_SIZE=512
RAGMINE_CHUNK_OVERLAP=77

# Retrieval
RAGMINE_TOP_K=5
RAGMINE_TOP_K_RETRIVEVE=50

# Reranker
RAGMINE_RERANK_ENABLED=true
RAGMINE_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# LLM
RAGMINE_LLM_PROVIDER=ollama  # or: openai-compatible
RAGMINE_OLLAMA_BASE_URL=http://localhost:11434
RAGMINE_OLLAMA_MODEL=qwen3:8b

# Server
RAGMINE_HOST=0.0.0.0
RAGMINE_PORT=8420
```

## Architecture

```
ragmine/
├── core/
│   ├── protocols.py    # All interfaces (Embedder, VectorStore, Chunker, etc.)
│   ├── config.py    # Settings
│   ├── registry.py  # Component registry
│   ├── embedder.py  # SentenceTransformer, Ollama
│   ├── store_lance.py # LanceDB backend
│   └── store_chroma.py # ChromaDB backend
├── ingest/
│   ├── parser.py   # SmartParser (auto-routes by file type)
│   └── chunker.py  # RecursiveChunker (markdown, code, text)
├── retrieve/
│   ├── search.py   # HybridSearcher (RRF fusion)
│   └── rerank.py   # CrossEncoderReranker
├── generate/
│   └── llm.py      # OllamaLLM, OpenAICompatibleLLM
├── connectors/
│   ├── __init__.py  # Connector registry
│   ├── base.py      # Connector protocol
│   ├── web.py       # Web/URL connector
│   ├── github.py    # GitHub connector
│   ├── confluence.py # Confluence connector
│   ├── slack.py     # Slack connector
│   ├── notion.py    # Notion connector
│   ├── database.py  # SQL connector
│   ├── rss.py       # RSS feed connector
│   ├── s3.py        # S3/GCS connector
│   └── metabase.py  # Metabase connector
├── tui/
│   ├── app.py        # Main Textual app
│   ├── screens/      # Chat, Sources, Settings screens
│   └── widgets/      # Sidebar, Command Palette, Status Bar
├── server/
│   ├── api.py        # FastAPI REST
│   └── mcp_server.py # MCP server
├── pipeline.py       # Ragmine main class
└── cli.py            # Interactive CLI + Rich
```

## License

MIT