"""
ragmine.connectors.confluence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetch Confluence spaces and pages.

    from ragmine.connectors.confluence import ConfluenceConnector
    connector = ConfluenceConnector(url="https://yoursite.atlassian.net", email="you@example.com", api_key="xxx")
    connector.add_space("SPACEKEY")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect confluence --url=https://yoursite.atlassian.net --email=you@example.com --api-key=xxx --space=SPACEKEY
"""

from __future__ import annotations

import uuid

import httpx

from ragmine.core.protocols import Chunk


class ConfluenceConnector:
    """Fetch Confluence spaces, pages, and their content."""

    def __init__(
        self,
        url: str,
        email: str = "",
        api_key: str = "",
        max_pages: int = 100,
    ):
        self._url = url.rstrip("/")
        self._email = email
        self._api_key = api_key
        self._max_pages = max_pages
        self._spaces: list[str] = []
        self._client = httpx.Client(timeout=60)

    @property
    def name(self) -> str:
        return "confluence"

    def add_space(self, space_key: str) -> None:
        self._spaces.append(space_key)

    def _auth(self) -> tuple[str, str]:
        return (self._email, self._api_key)

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self._url}/wiki/rest/api{path}"
        resp = self._client.get(url, auth=self._auth(), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _get_page_html(self, page_id: str) -> str:
        url = f"{self._url}/wiki/rest/api/content/{page_id}/body/html"
        resp = self._client.get(url, auth=self._auth(), headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("value", "")

    def _html_to_text(self, html: str) -> str:
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: list[str] = []
                self.skip_tags = {"script", "style", "nav"}
                self.depth = 0

            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    self.depth += 1

            def handle_endtag(self, tag):
                if tag in self.skip_tags:
                    self.depth = max(0, self.depth - 1)

            def handle_data(self, data):
                if self.depth == 0:
                    stripped = data.strip()
                    if stripped:
                        self.parts.append(stripped)

        extractor = TextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            pass
        return "\n\n".join(extractor.parts)

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for space in self._spaces:
            chunks.extend(self._fetch_space_pages(space))
        return chunks

    def _fetch_space_pages(self, space_key: str) -> list[Chunk]:
        chunks = []
        try:
            pages = self._get(
                f"/space/{space_key}/content",
                params={"limit": min(self._max_pages, 100), "expand": "body.storage,version"},
            )
            results = pages.get("results", []) if isinstance(pages, dict) else pages

            for page in results:
                page_chunks = self._fetch_page(page, space_key)
                chunks.extend(page_chunks)
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching space {space_key}: {e}]",
                source=f"confluence://space/{space_key}",
                source_type="confluence-space",
                metadata={"space": space_key, "error": str(e)},
            ))
        return chunks

    def _fetch_page(self, page: dict, space_key: str) -> list[Chunk]:
        chunks = []
        page_id = page.get("id", "")
        title = page.get("title", "")
        version = page.get("version", {}).get("number", "")

        try:
            html = self._get_page_html(page_id)
            text = self._html_to_text(html)

            if text:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=f"# {title}\n\n{text}",
                    source=f"confluence://page/{page_id}",
                    source_type="confluence-page",
                    metadata={
                        "page_id": page_id,
                        "title": title,
                        "space": space_key,
                        "version": version,
                    },
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching page {title} ({page_id}): {e}]",
                source=f"confluence://page/{page_id}",
                source_type="confluence-page",
                metadata={"page_id": page_id, "title": title, "error": str(e)},
            ))
        return chunks


class ConfluenceConnectorCLI:
    """CLI helper for Confluence connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[ConfluenceConnector, str]:
        url = ""
        email = ""
        api_key = ""
        spaces: list[str] = []

        for part in args.split():
            if part.startswith("--url="):
                url = part.split("=", 1)[1]
            elif part.startswith("--email="):
                email = part.split("=", 1)[1]
            elif part.startswith("--api-key="):
                api_key = part.split("=", 1)[1]
            elif part.startswith("--space="):
                spaces.append(part.split("=", 1)[1])

        if not url:
            raise ValueError("No URL provided. Use --url=https://yoursite.atlassian.net")
        if not email or not api_key:
            raise ValueError("Email and API key required. Use --email=you@example.com --api-key=xxx")

        connector = ConfluenceConnector(url=url, email=email, api_key=api_key)
        for space in spaces:
            connector.add_space(space)

        source = f"confluence://{','.join(spaces)}" if spaces else "confluence://"
        return connector, source

    @staticmethod
    def help_text() -> str:
        return """confluence — Fetch Confluence spaces and pages

Usage:
  /connect confluence --url=https://yoursite.atlassian.net --email=you@example.com --api-key=xxx --space=SPACEKEY

Options:
  --url=<url>            Confluence base URL
  --email=<email>       Your Atlassian email
  --api-key=<key>       Atlassian API token (generate at https://id.atlassian.com/manage-profile/security/api-tokens)
  --space=<key>         Space key to fetch (can be repeated)

Example:
  /connect confluence --url=https://yoursite.atlassian.net --email=me@company.com --api-key=xxx --space=DOCS --space=TEAM

Note: Requires Atlassian API token.
  pip install 'ragmine[connector-confluence]'
"""