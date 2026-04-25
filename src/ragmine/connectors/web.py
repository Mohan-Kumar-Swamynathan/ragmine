"""
ragmine.connectors.web
~~~~~~~~~~~~~~~~~~~~~~
Fetch and parse web pages into chunks.

    from ragmine.connectors.web import WebConnector
    connector = WebConnector(urls=["https://docs.example.com", "https://blog.example.com"])
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect web --url=https://example.com
    ragmine /connect web --url=https://example.com --url=https://example.org
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterator

import httpx

from ragmine.core.protocols import Chunk


def _html_to_markdown(html: str, base_url: str = "") -> str:
    try:
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.baseurl = base_url
        return h.handle(html)
    except ImportError:
        pass

    try:
        from trafilatura import extract

        return extract(html, url=base_url) or _strip_html_basic(html)
    except ImportError:
        pass

    return _strip_html_basic(html)


def _strip_html_basic(html: str) -> str:
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
            self.ignore_depth = 0
            self.ignore_tags = {"script", "style", "nav", "header", "footer"}

        def handle_starttag(self, tag, attrs):
            if tag in self.ignore_tags:
                self.ignore_depth += 1

        def handle_endtag(self, tag):
            if tag in self.ignore_tags:
                self.ignore_depth = max(0, self.ignore_depth - 1)

        def handle_data(self, data):
            if self.ignore_depth == 0:
                stripped = data.strip()
                if stripped:
                    self.parts.append(stripped)

    extractor = TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    return "\n\n".join(extractor.parts)


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            newline = chunk.rfind("\n")
            if newline > chunk_size // 2:
                chunk = chunk[:newline]
                end = start + len(chunk)

        chunks.append(chunk.strip())
        start = end - overlap
        if start < 0:
            start = 0

    return chunks


@dataclass
class WebPage:
    url: str
    title: str
    text: str
    description: str = ""


class WebConnector:
    """Fetch web pages and convert to chunks."""

    def __init__(
        self,
        urls: list[str] | None = None,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        timeout: int = 30,
    ):
        self._urls = urls or []
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    @property
    def name(self) -> str:
        return "web"

    def add_url(self, url: str) -> None:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url.count("://") > 1:
            raise ValueError(f"Invalid URL: {url}")
        self._urls.append(url)

    def fetch_pages(self) -> Iterator[WebPage]:
        for url in self._urls:
            yield self._fetch_page(url)

    def _fetch_page(self, url: str) -> WebPage:
        if "://" in url[10:] if len(url) > 10 else "://" in url:
            return WebPage(url=url, title="", text="[Error: Invalid URL format]")

        try:
            resp = self._client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; RagmineBot/1.0)"
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return WebPage(
                    url=url,
                    title="",
                    text=f"[Binary content: {content_type}]",
                )

            html = resp.text
            title = self._extract_title(html)
            description = self._extract_description(html)
            markdown = _html_to_markdown(html, base_url=url)

            return WebPage(
                url=url,
                title=title or url,
                text=markdown,
                description=description or "",
            )

        except httpx.TimeoutException:
            return WebPage(url=url, title="", text=f"[Timeout fetching: {url}]")
        except httpx.HTTPStatusError as e:
            return WebPage(url=url, title="", text=f"[HTTP {e.response.status_code}: {url}]")
        except Exception as e:
            return WebPage(url=url, title="", text=f"[Error fetching: {url} - {e}]")

    def _extract_title(self, html: str) -> str:
        import re
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_description(self, html: str) -> str:
        import re
        patterns = [
            r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
            r'<meta[^>]+content="([^"]+)"[^>]+name="description"',
            r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for page in self.fetch_pages():
            text_chunks = _chunk_text(page.text, self._chunk_size, self._chunk_overlap)

            for i, text in enumerate(text_chunks):
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=page.url,
                    source_type="web",
                    metadata={
                        "url": page.url,
                        "title": page.title,
                        "description": page.description,
                        "chunk_index": i,
                        "total_chunks": len(text_chunks),
                    },
                ))

        return chunks


class WebConnectorCLI:
    """CLI helper for web connector."""

    @staticmethod
    def parse_args(args: str) -> WebConnector:
        urls: list[str] = []
        chunk_size = 2000
        chunk_overlap = 200

        for part in args.split():
            if part.startswith("--url="):
                urls.append(part.split("=", 1)[1])
            elif part.startswith("--size="):
                try:
                    chunk_size = int(part.split("=", 1)[1])
                except ValueError:
                    pass
            elif part.startswith("--overlap="):
                try:
                    chunk_overlap = int(part.split("=", 1)[1])
                except ValueError:
                    pass

        if not urls:
            raise ValueError("No URLs provided. Use --url=https://example.com")

        connector = WebConnector(
            urls=urls,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return connector

    @staticmethod
    def help_text() -> str:
        return """web — Fetch web pages and convert to chunks

Usage:
  /connect web --url=https://example.com
  /connect web --url=https://example.com --url=https://docs.example.com

Options:
  --url=<url>           URL to fetch (can be repeated)
  --size=<n>            Chunk size (default: 2000)
  --overlap=<n>         Chunk overlap (default: 200)

Example:
  /connect web --url=https://python.langchain.com/docs --size=1000

Note: Requires httpx and html2text or trafilatura for best results.
  pip install 'ragmine[connector-web]'
"""