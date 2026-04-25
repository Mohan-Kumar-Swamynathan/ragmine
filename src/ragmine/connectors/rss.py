"""
ragmine.connectors.rss
~~~~~~~~~~~~~~~~~~~~~~
Fetch RSS/Atom feeds and convert to chunks.

    from ragmine.connectors.rss import RSSConnector
    connector = RSSConnector(feeds=["https://blog.example.com/feed", "https://news.example.com/rss"])
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect rss --feed=https://blog.example.com/feed
    ragmine /connect rss --feed=https://blog.example.com/feed --feed=https://news.example.com/rss --days=7
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Iterator

import httpx

from ragmine.core.protocols import Chunk


class RSSConnector:
    """Fetch RSS/Atom feeds."""

    def __init__(
        self,
        feeds: list[str] | None = None,
        max_items_per_feed: int = 50,
        days_back: int = 30,
        include_content: bool = True,
    ):
        self._feeds = feeds or []
        self._max_items_per_feed = max_items_per_feed
        self._days_back = days_back
        self._include_content = include_content
        self._client = httpx.Client(timeout=30)

    @property
    def name(self) -> str:
        return "rss"

    def add_feed(self, url: str) -> None:
        self._feeds.append(url)

    def fetch_items(self) -> Iterator[dict]:
        for feed_url in self._feeds:
            yield from self._fetch_feed(feed_url)

    def _fetch_feed(self, feed_url: str) -> list[dict]:
        items = []
        try:
            import feedparser
            resp = self._client.get(feed_url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

            cutoff = datetime.now() - timedelta(days=self._days_back)
            for entry in feed.entries[:self._max_items_per_feed]:
                published = entry.get("published_parsed")
                if published:
                    pub_date = datetime(*published[:6])
                    if pub_date < cutoff:
                        continue

                item = {
                    "feed_url": feed_url,
                    "feed_title": feed.feed.get("title", feed_url),
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                    "content": entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "",
                    "author": entry.get("author", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                }
                items.append(item)
        except ImportError:
            items.append({
                "feed_url": feed_url,
                "error": "feedparser required. pip install 'ragmine[connector-rss]'",
            })
        except Exception as e:
            items.append({
                "feed_url": feed_url,
                "error": str(e),
            })
        return items

    def fetch_chunks(self) -> list[Chunk]:
        chunks = []
        for item in self.fetch_items():
            if "error" in item:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=f"[Error fetching {item['feed_url']}: {item['error']}]",
                    source=f"rss://{item['feed_url']}",
                    source_type="rss-feed",
                    metadata={"feed_url": item["feed_url"], "error": item["error"]},
                ))
                continue

            text_parts = [
                f"# {item['title']}",
                f"Source: {item['feed_title']}",
                f"Link: {item['link']}",
                f"Published: {item['published']}",
                f"Author: {item['author']}",
            ]

            if item["tags"]:
                text_parts.append(f"Tags: {', '.join(item['tags'])}")

            text_parts.append("\n## Summary")
            text_parts.append(item["summary"])

            if self._include_content and item["content"]:
                text_parts.append("\n## Content")
                text_parts.append(item["content"])

            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text="\n".join(text_parts),
                source=f"rss://{item['feed_url']}/{item['link']}",
                source_type="rss-entry",
                metadata={
                    "feed_url": item["feed_url"],
                    "feed_title": item["feed_title"],
                    "title": item["title"],
                    "link": item["link"],
                    "published": item["published"],
                    "tags": item["tags"],
                },
            ))
        return chunks


class RSSConnectorCLI:
    """CLI helper for RSS connector."""

    @staticmethod
    def parse_args(args: str) -> RSSConnector:
        feeds: list[str] = []
        days = 30
        include_content = True

        for part in args.split():
            if part.startswith("--feed="):
                feeds.append(part.split("=", 1)[1])
            elif part.startswith("--days="):
                try:
                    days = int(part.split("=", 1)[1])
                except ValueError:
                    pass
            elif part == "--no-content":
                include_content = False

        if not feeds:
            raise ValueError("No feeds provided. Use --feed=https://example.com/feed")

        return RSSConnector(
            feeds=feeds,
            days_back=days,
            include_content=include_content,
        )

    @staticmethod
    def help_text() -> str:
        return """rss — Fetch RSS/Atom feeds

Usage:
  /connect rss --feed=https://blog.example.com/feed
  /connect rss --feed=https://blog.example.com/feed --days=7

Options:
  --feed=<url>           RSS/Atom feed URL (can be repeated)
  --days=<n>             Days of history to fetch (default: 30)
  --no-content           Skip fetching full article content

Example:
  /connect rss --feed=https://hnrss.org/frontpage --feed=https://lobste.rs/rss --days=7

Note: Requires feedparser.
  pip install 'ragmine[connector-rss]'
"""