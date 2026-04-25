# ⛏️ ragmine

**Mine your documents. Local RAG that works.**

Zero-config local RAG with hybrid search, smart chunking, MCP support, and 9 data connectors.
Everything is pluggable — swap any component without touching the rest.

```bash
pip install 'ragmine[all]'
ragmine
```

---

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
- **9 Connectors** — import from web, GitHub, Confluence, Slack, Notion, Database, RSS, S3, Metabase

---

## Quick Start

```bash
# Install with all batteries
pip install 'ragmine[all]'

# Interactive CLI
ragmine

# Textual TUI (recommended - like OpenCode)
ragmine tui

# Ingest documents
ragmine ingest ./my-project --glob "*.py,*.md"
ragmine ingest ~/Documents/papers

# One-shot query (no LLM needed for search)
ragmine query "kafka retry logic" --no-generate

# Full RAG with LLM
ragmine query "How does the payment service handle failures?"

# Start API server
ragmine serve

# Start MCP server (for Claude, Cursor)
ragmine mcp
```

---

## End-to-End Guide

### 1) Start with local dev launcher (recommended)

```bash
cd /path/to/ragmine
./run-ragmine-dev.sh tui
```

This avoids global Python/env conflicts and guarantees you run local source.

### 2) Add your first data

```text
/ingest ./docs
/ingest /Users/you/Desktop/resume.pdf
/connect web --url=https://example.com
```

Notes:
- PDF ingest now auto-falls back: `docling` -> `pdfplumber` -> `pypdf`.
- If a file name is given without full path, Ragmine also checks common folders (`Downloads`, `Documents`, `Desktop`).

### 3) Verify the knowledge base

```text
/status
/sources
```

### 4) Ask questions

```text
how does this project work?
what are key highlights from my resume?
```

### 5) Export or iterate

```text
/export
/delete <source>
/clear-all
/ingest <updated-file>
```

---

## Demo GIFs

![TUI Quick Tour](docs/images/tui-quick-tour.gif)
![PDF Ingest Demo](docs/images/pdf-ingest-demo.gif)
![Web Connect Demo](docs/images/web-connect-demo.gif)
![Troubleshooting Demo](docs/images/troubleshooting-demo.gif)

Suggested captures:
- Open TUI, run `/help`, `/status`, `/sources`
- Ingest a PDF and ask a question
- Connect a web URL and query the result
- Fix a model config error and verify recovery

---

## TUI Mode (OpenCode-like Interface)

```bash
ragmine tui
```

### Commands in TUI

```
/help              Show all commands
/ingest <path>     Add documents (e.g., /ingest ./docs)
/connect <name>    Connect data source
/sources           List all sources
/status            Show KB status
/delete <source>   Delete a source
/clear-all         Delete all sources/chunks at once
/clear             Clear chat
/export            Export chat to file
/quit              Exit
```

### Keyboard Shortcuts in TUI

| Key | Action |
|-----|--------|
| `↑` / `↓` | Command history |
| `Tab` | Accept suggestion |
| `Ctrl+A` | Copy all chat to clipboard |
| `Ctrl+L` | Clear screen |
| `Ctrl+K` / `Ctrl+J` | Scroll up / down |
| `Esc` | Quit |

### Auto-Suggestions

Type `/` and press `Tab` to see suggestions:
- `/help`
- `/ingest ./`
- `/connect web --url=`
- `/connect github --repo=`
- `/connect rss --feed=`

---

## Connectors (9 Data Sources)

Pull data from 9 external sources:

```bash
# In TUI
/connect web --url=https://example.com
/connect github --repo=owner/repo --token=ghp_xxx
/connect rss --feed=https://blog.example.com/feed
/connect confluence --space=KEY --url=https://site.atlassian.net --email=you@email.com --api-key=xxx
/connect slack --channel=C0123456789 --token=xoxb-xxx
/connect notion --page=xxx --token=secret_xxx
/connect database --dsn=postgresql://user:pass@localhost/db
/connect s3 --bucket=my-bucket --provider=aws
/connect metabase --url=http://localhost:3000 --api-key=xxx
```

### Web Connector
```bash
/connect web --url=https://python.langchain.com/docs
```
Fetches web pages and converts to searchable chunks.

### GitHub Connector
```bash
/connect github --repo=openai/openai-python --include-issues --include-prs
```
Fetches repos, issues, PRs, and READMEs.

### RSS Connector
```bash
/connect rss --feed=https://hnrss.org/frontpage --days=7
```
Monitors RSS/Atom feeds for new content.

### Database Connector
```bash
/connect database --dsn=sqlite:///data.db
/connect database --dsn=postgresql://user:pass@localhost/db --query="SELECT * FROM users"
```
Ingests SQL schemas and query results.

### S3 Connector
```bash
/connect s3 --bucket=docs --prefix=projects/ --provider=aws
/connect s3 --bucket=files --provider=gcs --credentials-file=./creds.json
```
Fetches files from S3 or Google Cloud Storage.

---

## Python API

### Basic Usage

```python
from ragmine import Ragmine

rm = Ragmine()

# Ingest files
rm.ingest("./docs")
rm.ingest("./src", glob="*.py,*.md")

# Ingest from connectors
from ragmine.connectors.web import WebConnector
connector = WebConnector(urls=["https://example.com"])
chunks = connector.fetch_chunks()
rm.ingest_chunks(chunks, source="web:example.com")

# Search only
results = rm.search("authentication flow")
for r in results:
    print(f"{r.source}: {r.chunk.text[:100]}...")

# Full RAG with LLM
response = rm.query("How does auth work?")
print(response.answer)

# Async
import asyncio
response = asyncio.run(rm.aquery("How does auth work?"))
```

### Pluggable Components

```python
from ragmine import Ragmine, registry

# Use custom embedder
class MyEmbedder:
    def embed_texts(self, texts): ...
    def embed_query(self, text): ...

registry.register_embedder("my-embedder", MyEmbedder)
rm = Ragmine(embedding_provider="my-embedder")
```

---

## Configuration

All settings via environment variables (`RAGMINE_` prefix) or `.env` file:

```bash
# Storage
RAGMINE_DATA_DIR=~/.ragmine
RAGMINE_DB_NAME=default
RAGMINE_STORE_BACKEND=lancedb  # or: chroma

# Embeddings (recommended: sentence-transformers)
RAGMINE_EMBEDDING_PROVIDER=sentence-transformers  # or: ollama
RAGMINE_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Chunking
RAGMINE_CHUNK_SIZE=512
RAGMINE_CHUNK_OVERLAP=77

# Retrieval
RAGMINE_TOP_K=5
RAGMINE_TOP_K_RETRIEVE=50

# Reranker
RAGMINE_RERANK_ENABLED=true
RAGMINE_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# LLM (Ollama or OpenAI-compatible)
RAGMINE_LLM_PROVIDER=ollama  # or: openai-compatible
RAGMINE_OLLAMA_BASE_URL=http://localhost:11434
RAGMINE_OLLAMA_MODEL=qwen3:8b
RAGMINE_LLM_MAX_TOKENS=512
RAGMINE_LLM_TEMPERATURE=0.2

# Server
RAGMINE_HOST=0.0.0.0
RAGMINE_PORT=8420
```

### Recommended Setup for macOS

Add to `~/.zshrc`:
```bash
export RAGMINE_EMBEDDING_PROVIDER=sentence-transformers
export RAGMINE_EMBEDDING_MODEL=all-MiniLM-L6-v2
export RAGMINE_STORE_BACKEND=lancedb
export RAGMINE_DATA_DIR=~/.ragmine
```

---

## MCP Server (Claude, Cursor, Codex)

Add to your MCP config (`~/.config/claude/claude_desktop_config.json` or similar):

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

---

## REST API

```bash
# Start server
ragmine serve

# Query with streaming
curl -N -X POST http://localhost:8420/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "How does auth work?", "generate": true}'

# Search only
curl -X POST http://localhost:8420/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 5}'
```

---

## Architecture

```
ragmine/
├── core/
│   ├── protocols.py    # All interfaces (Embedder, VectorStore, Chunker, etc.)
│   ├── config.py       # Settings
│   ├── registry.py     # Component registry
│   ├── embedder.py     # SentenceTransformer, Ollama
│   ├── store_lance.py  # LanceDB backend
│   └── store_chroma.py # ChromaDB backend
├── ingest/
│   ├── parser.py       # SmartParser (auto-routes by file type)
│   └── chunker.py      # RecursiveChunker (markdown, code, text)
├── retrieve/
│   ├── search.py       # HybridSearcher (RRF fusion)
│   └── rerank.py       # CrossEncoderReranker
├── generate/
│   └── llm.py          # OllamaLLM, OpenAICompatibleLLM
├── connectors/
│   ├── web.py          # Web/URL connector
│   ├── github.py       # GitHub connector
│   ├── confluence.py   # Confluence connector
│   ├── slack.py        # Slack connector
│   ├── notion.py       # Notion connector
│   ├── database.py     # SQL connector
│   ├── rss.py          # RSS feed connector
│   ├── s3.py           # S3/GCS connector
│   └── metabase.py     # Metabase connector
├── tui/
│   ├── app.py          # Textual TUI application
│   ├── screens/        # Chat, Sources, Settings screens
│   └── widgets/        # Sidebar, Command Palette, Status Bar
├── server/
│   ├── api.py          # FastAPI REST
│   └── mcp_server.py   # MCP server
├── pipeline.py          # Ragmine main class
└── cli.py              # Interactive CLI + Rich
```

---

## Installation

### Quick Install (Recommended)

```bash
# Full install with everything
pip install 'ragmine[all]'

# Core + TUI (minimal for most use cases)
pip install 'ragmine[tui]'

# Core + all connectors
pip install 'ragmine[connector-web,connector-github,connector-confluence,connector-slack,connector-notion,connector-database,connector-rss,connector-s3]'
```

### Using pipx (Isolated Python Environment)

```bash
# Install with pipx
pipx install ragmine

# Add all dependencies
pipx inject ragmine 'ragmine[all]'

# Or just TUI deps
pipx inject ragmine textual lancedb pyarrow sentence-transformers

# Run
ragmine tui
```

### Development Install

```bash
# Clone and install
git clone https://github.com/yourrepo/ragmine.git
cd ragmine
pip install -e '.[all]'
```

### Individual Connector Extras

```bash
pip install 'ragmine[connector-web]'       # httpx, html2text
pip install 'ragmine[connector-github]'     # httpx
pip install 'ragmine[connector-confluence]' # httpx
pip install 'ragmine[connector-slack]'     # httpx
pip install 'ragmine[connector-notion]'     # notion-client
pip install 'ragmine[connector-database]'   # sqlalchemy
pip install 'ragmine[connector-rss]'        # feedparser
pip install 'ragmine[connector-s3]'        # boto3 or google-cloud-storage
pip install 'ragmine[connector-metabase]'  # httpx
```

### Server & MCP

```bash
pip install 'ragmine[serve]'               # fastapi, uvicorn
pip install 'ragmine[mcp]'                 # mcp[cli]
```

---

## Troubleshooting

### `/connect web` fails with `bad value(s) in fds_to_keep`

This can happen when running with an incompatible Python/runtime combo (common with global installs on macOS).

Use the project-local launcher so you run local code and env:

```bash
cd /path/to/ragmine
pkill -f "ragmine" || true
pkill -f "python.*ragmine" || true
./run-ragmine-dev.sh tui
```

If `run-ragmine-dev.sh` doesn't exist yet:

```bash
#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src ./venv/bin/python -m ragmine.cli "$@"
```

### `All connection attempts failed` during query

This means retrieval worked, but LLM generation endpoint was unreachable.

Check Ollama API:

```bash
curl http://localhost:11434/api/tags
ollama list
```

Make sure your base URL is correct:

```bash
RAGMINE_OLLAMA_BASE_URL=http://localhost:11434
```

### `400 Bad Request` for `/api/generate` (Ollama)

Usually caused by setting a non-chat embedding model as `RAGMINE_OLLAMA_MODEL`.

Correct `.env` split:

```bash
RAGMINE_EMBEDDING_PROVIDER=ollama
RAGMINE_EMBEDDING_MODEL=nomic-embed-text:latest
RAGMINE_OLLAMA_MODEL=llama3.2:latest
```

### `/ingest` PDF fails with `bad value(s) in fds_to_keep`

Cause: `docling` runtime subprocess issue in some environments.

Current behavior:
- Ragmine automatically falls back to `pdfplumber`, then `pypdf`.
- Ingest no longer hard-fails when Docling fails at runtime.

Recommended parser deps:

```bash
pip install pdfplumber pypdf
```

### `/ingest <filename>.pdf` says "Path not found"

Use either:
- absolute path (`/Users/you/Desktop/file.pdf`), or
- run from a folder containing the file.

Ragmine also tries common fallback folders for filename-only input:
- `~/Downloads`
- `~/Documents`
- `~/Desktop`

### Embeddings Error (Ollama)

If you see `404 Not Found for /api/embeddings`:

```bash
# Use sentence-transformers instead
export RAGMINE_EMBEDDING_PROVIDER=sentence-transformers

# OR install Ollama embeddings model
ollama pull nomic-embed-text
```

### First Run

On first run, models will be downloaded:
- `all-MiniLM-L6-v2` (~90MB) - for embeddings
- `qwen3:8b` (if using Ollama) - for LLM

### Test Installation

```bash
./run-ragmine-dev.sh status
./run-ragmine-dev.sh help
./run-ragmine-dev.sh ingest ./src/ragmine --glob "*.py"
./run-ragmine-dev.sh query "test" --no-generate
```

---

## License

MIT