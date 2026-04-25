"""
ragmine.core.store_lance
~~~~~~~~~~~~~~~~~~~~~~~~~
LanceDB backend — embedded, zero-config, hybrid search.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from ragmine.core.config import Settings
from ragmine.core.protocols import Chunk, SearchFilter, SearchResult


TABLE_NAME = "chunks"


class LanceStore:
    """LanceDB vector store with vector + FTS hybrid search."""

    def __init__(self, settings: Settings):
        import lancedb

        self._db = lancedb.connect(str(settings.db_path / "lance.db"))
        self._table = None

    def _get_table(self):
        if self._table is None:
            try:
                self._table = self._db.open_table(TABLE_NAME)
            except Exception:
                self._table = None
        return self._table

    def _ensure_table(self, dim: int):
        if self._get_table() is None:
            import pyarrow as pa

            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("source", pa.string()),
                pa.field("source_type", pa.string()),
                pa.field("chunk_index", pa.int32()),
                pa.field("parent_id", pa.string()),
                pa.field("metadata_json", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
            ])
            self._table = self._db.create_table(TABLE_NAME, schema=schema)

    def create_fts_index(self):
        """Create FTS index for full-text search."""
        table = self._get_table()
        if table is None:
            return False

        try:
            from lancedb.fts import create_fts_index
            create_fts_index(table, "text")
            return True
        except Exception:
            return False

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0

        dim = len(chunks[0].embedding) if chunks[0].embedding else 384
        self._ensure_table(dim)

        data = []
        for c in chunks:
            if c.embedding is None:
                continue
            data.append({
                "id": c.id or str(uuid.uuid4()),
                "text": c.text,
                "source": c.source,
                "source_type": c.source_type,
                "chunk_index": c.chunk_index,
                "parent_id": c.parent_id or "",
                "metadata_json": json.dumps(c.metadata),
                "vector": c.embedding,
            })

        if data:
            self._get_table().add(data)

        return len(data)

    def update_chunks(self, chunks: list[Chunk]) -> int:
        """Upsert chunks (insert or update existing)."""
        if not chunks:
            return 0

        table = self._get_table()
        if table is None:
            return self.add_chunks(chunks)

        deleted = 0
        for c in chunks:
            if c.source:
                deleted += table.delete(f"source = '{c.source}'")

        return deleted + self.add_chunks(chunks)

    def vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]:
        table = self._get_table()
        if table is None:
            return []

        query = table.search(embedding).limit(limit)

        if filter:
            where_parts = []
            if filter.source:
                where_parts.append(f"source = '{filter.source}'")
            if filter.source_type:
                where_parts.append(f"source_type = '{filter.source_type}'")
            if where_parts:
                query = query.where(" AND ".join(where_parts))

        try:
            results = query.to_list()
        except Exception:
            results = []

        return [self._row_to_result(r) for r in results]

    def fts_search(self, query: str, limit: int = 10) -> list[SearchResult]:
        table = self._get_table()
        if table is None:
            return []

        try:
            results = table.search(query, query_type="fts").limit(limit).to_list()
            return [self._row_to_result(r, score_key="_score") for r in results]
        except Exception:
            return []

    def delete_by_source(self, source: str) -> int:
        table = self._get_table()
        if table is None:
            return 0
        before = table.count_rows()
        table.delete(f"source = '{source}'")
        after = table.count_rows()
        return before - after

    def list_sources(self, limit: int = 100, offset: int = 0) -> list[str]:
        table = self._get_table()
        if table is None:
            return []
        df = table.to_pandas()
        if len(df) > 0:
            sources = sorted(df["source"].unique().tolist())
            return sources[offset:offset + limit]
        return []

    def count(self) -> int:
        table = self._get_table()
        return table.count_rows() if table else 0

    def _row_to_result(self, row: dict, score_key: str = "_distance") -> SearchResult:
        meta = {}
        try:
            meta = json.loads(row.get("metadata_json", "{}"))
        except Exception:
            pass

        chunk = Chunk(
            id=row.get("id", ""),
            text=row.get("text", ""),
            source=row.get("source", ""),
            source_type=row.get("source_type", "text"),
            chunk_index=row.get("chunk_index", 0),
            parent_id=row.get("parent_id") or None,
            metadata=meta,
        )

        raw = row.get(score_key, 0.0)
        score = 1.0 / (1.0 + raw) if score_key == "_distance" else raw

        return SearchResult(chunk=chunk, score=score)
