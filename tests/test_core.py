"""Tests for ragmine core components."""

import pytest

from ragmine.core.protocols import Chunk, ParsedDocument, SearchResult, SearchFilter
from ragmine.core.config import Settings
from ragmine.ingest.chunker import RecursiveChunker
from ragmine.ingest.parser import SmartParser
from ragmine.pipeline import _truncate_context, _count_tokens


# ── Chunker Tests ──


class TestRecursiveChunker:
    def setup_method(self):
        self.chunker = RecursiveChunker(Settings(chunk_size=100, chunk_overlap=15))

    def test_basic_chunking(self):
        doc = ParsedDocument(text="Hello world. " * 50, source="test.txt")
        chunks = self.chunker.chunk(doc)
        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_empty_doc(self):
        doc = ParsedDocument(text="", source="empty.txt")
        chunks = self.chunker.chunk(doc)
        assert chunks == []

    def test_small_doc_single_chunk(self):
        doc = ParsedDocument(text="Short text.", source="small.txt")
        chunks = self.chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."

    def test_markdown_splitting(self):
        md = "# Header 1\nContent one.\n\n## Header 2\nContent two."
        doc = ParsedDocument(text=md, source="doc.md", source_type="text")
        chunks = self.chunker.chunk(doc)
        assert len(chunks) >= 1

    def test_code_splitting(self):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n\nclass Baz:\n    pass"
        doc = ParsedDocument(text=code, source="app.py", source_type="code")
        chunks = self.chunker.chunk(doc)
        assert len(chunks) >= 1

    def test_chunk_has_source(self):
        doc = ParsedDocument(text="Some text content here.", source="/path/to/file.txt")
        chunks = self.chunker.chunk(doc)
        assert all(c.source == "/path/to/file.txt" for c in chunks)

    def test_chunk_has_id(self):
        doc = ParsedDocument(text="Content.", source="test.txt")
        chunks = self.chunker.chunk(doc)
        assert all(c.id for c in chunks)
        # IDs should be unique
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))


# ── Parser Tests ──


class TestSmartParser:
    def setup_method(self):
        self.parser = SmartParser()

    def test_supports_text_files(self):
        assert self.parser.supports("readme.md")
        assert self.parser.supports("notes.txt")
        assert self.parser.supports("config.yaml")

    def test_supports_code_files(self):
        assert self.parser.supports("app.py")
        assert self.parser.supports("Main.java")
        assert self.parser.supports("index.ts")

    def test_supports_doc_files(self):
        assert self.parser.supports("report.pdf")
        assert self.parser.supports("proposal.docx")
        assert self.parser.supports("page.html")

    def test_parse_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello ragmine!")
        doc = self.parser.parse(str(f))
        assert doc.text == "Hello ragmine!"
        assert doc.source_type == "text"

    def test_parse_code_file(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("def hello():\n    return 'world'")
        doc = self.parser.parse(str(f))
        assert "def hello" in doc.text
        assert doc.source_type == "code"

    def test_parse_markdown(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome content here.")
        doc = self.parser.parse(str(f))
        assert "Title" in doc.text
        assert "content" in doc.text


# ── Data Model Tests ──


class TestDataModels:
    def test_chunk_defaults(self):
        c = Chunk(id="1", text="hello", source="test.txt")
        assert c.source_type == "text"
        assert c.chunk_index == 0
        assert c.metadata == {}
        assert c.embedding is None

    def test_search_result(self):
        c = Chunk(id="1", text="hello", source="test.txt")
        r = SearchResult(chunk=c, score=0.95)
        assert r.score == 0.95
        assert r.source == "test.txt"


# ── Config Tests ──


class TestConfig:
    def test_defaults(self):
        s = Settings()
        assert s.chunk_size == 512
        assert s.chunk_overlap == 77
        assert s.store_backend == "lancedb"
        assert s.embedding_model == "all-MiniLM-L6-v2"
        assert s.top_k == 5

    def test_override(self):
        s = Settings(chunk_size=256, top_k=10)
        assert s.chunk_size == 256
        assert s.top_k == 10

    def test_db_path(self, tmp_path):
        s = Settings(data_dir=tmp_path, db_name="test")
        assert s.db_path == tmp_path / "test"
        assert s.db_path.exists()


# ── Context Truncation Tests ──


class TestContextTruncation:
    def test_count_tokens(self):
        text = "a " * 1000
        tokens = _count_tokens(text)
        assert tokens == 500

    def test_truncation_needed(self):
        short = "short"
        long = "a " * 20000
        result = _truncate_context(long, short)
        assert len(result) < len(long)

    def test_no_truncation_needed(self):
        short = "a " * 100
        result = _truncate_context(short, "question")
        assert result == short


# ── Search Filter Tests ──


class TestSearchFilter:
    def test_filter_creation(self):
        f = SearchFilter(source="test.txt")
        assert f.source == "test.txt"
        assert f.source_type is None

    def test_filter_with_metadata(self):
        f = SearchFilter(source="test.txt", metadata={"key": "value"})
        assert f.source == "test.txt"
        assert f.metadata == {"key": "value"}
