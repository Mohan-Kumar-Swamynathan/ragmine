"""
ragmine.ingest.chunker
~~~~~~~~~~~~~~~~~~~~~~~
Splits documents into chunks. Auto-routes by doc type.
"""

from __future__ import annotations

import uuid

from ragmine.core.config import Settings
from ragmine.core.protocols import Chunk, ParsedDocument


class RecursiveChunker:
    """Recursive character splitting — the proven default.

    Based on benchmarks: 512 tokens, 15% overlap beats semantic chunking
    for most real-world RAG workloads (Vectara NAACL 2025).
    """

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.chunk_size = s.chunk_size
        self.chunk_overlap = s.chunk_overlap

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        if not doc.text.strip():
            return []

        # Route to best strategy
        if doc.source_type == "code":
            raw_chunks = self._split_code(doc.text)
        elif doc.source.endswith(".md"):
            raw_chunks = self._split_markdown(doc.text)
        else:
            raw_chunks = self._split_recursive(doc.text)

        chunks = []
        for i, text in enumerate(raw_chunks):
            if not text.strip():
                continue
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=text.strip(),
                source=doc.source,
                source_type=doc.source_type,
                chunk_index=i,
                metadata={**doc.metadata, "chunk_method": "recursive"},
            ))

        return chunks

    def _split_recursive(self, text: str) -> list[str]:
        """Split by paragraph → sentence → word boundaries."""
        separators = ["\n\n", "\n", ". ", " "]
        return self._do_split(text, separators, self.chunk_size, self.chunk_overlap)

    def _split_markdown(self, text: str) -> list[str]:
        """Split on markdown headers first, then recurse."""
        sections = []
        current = []
        current_header = ""

        for line in text.split("\n"):
            if line.startswith("#"):
                if current:
                    content = "\n".join(current)
                    if content.strip():
                        # Prefix with header for context
                        prefixed = f"{current_header}\n{content}" if current_header else content
                        sections.append(prefixed)
                current = []
                current_header = line
            else:
                current.append(line)

        if current:
            content = "\n".join(current)
            if content.strip():
                prefixed = f"{current_header}\n{content}" if current_header else content
                sections.append(prefixed)

        # If sections are still too large, split them further
        result = []
        for section in sections:
            if len(section) > self.chunk_size * 4:  # rough char estimate
                result.extend(self._split_recursive(section))
            else:
                result.append(section)

        return result

    def _split_code(self, text: str) -> list[str]:
        """Split on function/class boundaries."""
        separators = ["\nclass ", "\ndef ", "\nasync def ", "\n\n", "\n"]
        return self._do_split(text, separators, self.chunk_size, self.chunk_overlap)

    def _do_split(
        self, text: str, separators: list[str], max_size: int, overlap: int
    ) -> list[str]:
        """Core recursive splitting algorithm."""
        # Try each separator, finest to coarsest
        for sep in separators:
            parts = text.split(sep)
            if len(parts) > 1:
                return self._merge_parts(parts, sep, max_size, overlap)

        # No separator worked — just split by character
        chunks = []
        for i in range(0, len(text), max_size - overlap):
            chunk = text[i : i + max_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def _merge_parts(
        self, parts: list[str], sep: str, max_size: int, overlap: int
    ) -> list[str]:
        """Merge small parts together, respecting max_size."""
        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part

            if len(candidate) > max_size * 4 and current:
                chunks.append(current.strip())
                # Overlap: keep tail of previous chunk
                tail = current[-overlap:] if overlap > 0 else ""
                current = tail + sep + part if tail else part
            else:
                current = candidate

        if current.strip():
            chunks.append(current.strip())

        return chunks
