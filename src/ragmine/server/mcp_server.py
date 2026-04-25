"""
ragmine.server.mcp_server
~~~~~~~~~~~~~~~~~~~~~~~~~~~
MCP server — plug ragmine into any AI assistant.

Add to Claude Desktop config:
    {
      "mcpServers": {
        "ragmine": {
          "command": "ragmine",
          "args": ["mcp"]
        }
      }
    }
"""

from __future__ import annotations


def run_mcp():
    from mcp.server.fastmcp import FastMCP

    from ragmine.pipeline import Ragmine

    mcp = FastMCP("ragmine")
    rm = Ragmine()

    @mcp.tool()
    def query_knowledge(question: str, top_k: int = 5) -> str:
        """Search the knowledge base and get an AI-generated answer with sources."""
        response = rm.query(question)
        parts = [response.answer, "", "Sources:"]
        for i, r in enumerate(response.sources, 1):
            parts.append(f"  {i}. {r.source} (score: {r.score:.3f})")
        return "\n".join(parts)

    @mcp.tool()
    def search_documents(query: str, limit: int = 10) -> str:
        """Semantic search without LLM generation. Returns relevant chunks."""
        results = rm.search(query, limit=limit)
        if not results:
            return "No results found."

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.source} (score: {r.score:.3f})")
            parts.append(r.chunk.text[:500])
            parts.append("")
        return "\n".join(parts)

    @mcp.tool()
    def ingest_file(file_path: str) -> str:
        """Add a document to the knowledge base."""
        count = rm.ingest(file_path)
        return f"Ingested {count} chunks from {file_path}"

    @mcp.tool()
    def ingest_directory(dir_path: str, glob_pattern: str = "*") -> str:
        """Add all documents from a directory to the knowledge base."""
        count = rm.ingest(dir_path, recursive=True, glob=glob_pattern)
        return f"Ingested {count} chunks from {dir_path}"

    @mcp.tool()
    def list_sources() -> str:
        """List all documents in the knowledge base."""
        sources = rm.store.list_sources()
        if not sources:
            return "Knowledge base is empty."
        return "\n".join(f"• {s}" for s in sources)

    @mcp.tool()
    def delete_source(source: str) -> str:
        """Remove a document from the knowledge base."""
        count = rm.store.delete_by_source(source)
        return f"Deleted {count} chunks from {source}"

    @mcp.tool()
    def kb_status() -> str:
        """Show knowledge base statistics."""
        s = rm.status()
        return "\n".join(f"{k}: {v}" for k, v in s.items())

    mcp.run()
