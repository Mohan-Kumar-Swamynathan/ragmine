"""
ragmine.connectors.notion
~~~~~~~~~~~~~~~~~~~~~~~~~
Fetch Notion pages and databases.

    from ragmine.connectors.notion import NotionConnector
    connector = NotionConnector(token="secret_xxx")
    connector.add_page("page-id-1")
    connector.add_database("database-id-1")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect notion --token=secret_xxx --page=page-id-1 --database=database-id-2
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from ragmine.core.protocols import Chunk


class NotionConnector:
    """Fetch Notion pages and databases."""

    def __init__(
        self,
        token: str,
        max_pages: int = 100,
    ):
        self._token = token
        self._max_pages = max_pages
        self._pages: list[str] = []
        self._databases: list[str] = []
        self._client = httpx.Client(timeout=60)

    @property
    def name(self) -> str:
        return "notion"

    def add_page(self, page_id: str) -> None:
        self._pages.append(page_id)

    def add_database(self, database_id: str) -> None:
        self._databases.append(database_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def _get(self, path: str) -> dict:
        url = f"https://api.notion.com/v1{path}"
        resp = self._client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        url = f"https://api.notion.com/v1{path}"
        resp = self._client.post(url, headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    def _block_to_text(self, block: dict) -> str:
        block_type = block.get("type", "")
        content = block.get(block_type, {})

        if block_type == "paragraph":
            return self._rich_text(content.get("rich_text", []))
        elif block_type == "heading_1":
            return f"# {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "heading_2":
            return f"## {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "heading_3":
            return f"### {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "bulleted_list_item":
            return f"- {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "numbered_list_item":
            return f"1. {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "code":
            lang = content.get("language", "")
            code = self._rich_text(content.get("rich_text", []))
            return f"```{lang}\n{code}\n```"
        elif block_type == "quote":
            return f"> {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "callout":
            icon = content.get("icon", {}).get("emoji", "💡")
            return f"{icon} {self._rich_text(content.get('rich_text', []))}"
        elif block_type == "table":
            return "[Table content]"
        else:
            return ""

    def _rich_text(self, rich_text: list[dict]) -> str:
        result = []
        for t in rich_text:
            text = t.get("text", {})
            content = text.get("content", "") if isinstance(text, dict) else t.get("plain_text", "")
            link = text.get("link", {}).get("url", "") if isinstance(text, dict) else ""
            if link:
                result.append(f"[{content}]({link})")
            else:
                result.append(content)
        return "".join(result)

    def _property_to_text(self, prop: dict, name: str) -> str:
        prop_type = prop.get("type", "")
        if prop_type == "title":
            return self._rich_text(prop.get("title", []))
        elif prop_type == "rich_text":
            return self._rich_text(prop.get("rich_text", []))
        elif prop_type == "number":
            return str(prop.get("number", ""))
        elif prop_type == "select":
            select = prop.get("select", {})
            return select.get("name", "") if select else ""
        elif prop_type == "multi_select":
            return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
        elif prop_type == "date":
            date = prop.get("date", {})
            return date.get("start", "") if date else ""
        elif prop_type == "checkbox":
            return "Yes" if prop.get("checkbox") else "No"
        elif prop_type == "url":
            return prop.get("url", "")
        elif prop_type == "email":
            return prop.get("email", "")
        elif prop_type == "phone_number":
            return prop.get("phone_number", "")
        elif prop_type == "created_time":
            return prop.get("created_time", "")
        elif prop_type == "last_edited_time":
            return prop.get("last_edited_time", "")
        else:
            return f"[{prop_type}]"

    def _fetch_page_blocks(self, page_id: str) -> str:
        blocks = []
        cursor = None

        while len(blocks) < 1000:
            params = {"page_id": page_id, "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            result = self._post("/blocks/{}/children".format(page_id), params)
            blocks.extend(result.get("results", []))
            cursor = result.get("next_cursor")

            if not cursor:
                break

        return "\n\n".join(self._block_to_text(b) for b in blocks if b.get("has_children") or self._block_to_text(b).strip())

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for page_id in self._pages:
            chunks.extend(self._fetch_page(page_id))
        for db_id in self._databases:
            chunks.extend(self._fetch_database(db_id))
        return chunks

    def _fetch_page(self, page_id: str) -> list[Chunk]:
        chunks = []
        try:
            page = self._get(f"/pages/{page_id}")
            title = "Untitled"
            for prop_name, prop in page.get("properties", {}).items():
                if prop.get("type") == "title":
                    title = self._rich_text(prop.get("title", []))
                    break

            text = self._fetch_page_blocks(page_id)
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"# {title}\n\n{text}",
                source=f"notion://page/{page_id}",
                source_type="notion-page",
                metadata={
                    "page_id": page_id,
                    "title": title,
                    "url": page.get("url", ""),
                },
            ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching page {page_id}: {e}]",
                source=f"notion://page/{page_id}",
                source_type="notion-page",
                metadata={"page_id": page_id, "error": str(e)},
            ))
        return chunks

    def _fetch_database(self, database_id: str) -> list[Chunk]:
        chunks = []
        try:
            db = self._get(f"/databases/{database_id}")
            title = self._rich_text(db.get("title", [])) or "Untitled Database"
            properties = db.get("properties", {})

            schema_text = f"# Database: {title}\n\nSchema:\n"
            for prop_name, prop in properties.items():
                prop_type = prop.get("type", "")
                schema_text += f"- {prop_name}: {prop_type}\n"

            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=schema_text,
                source=f"notion://database/{database_id}",
                source_type="notion-database",
                metadata={
                    "database_id": database_id,
                    "title": title,
                },
            ))

            query = self._post(f"/databases/{database_id}/query", {"page_size": min(self._max_pages, 100)})
            results = query.get("results", [])

            for page in results:
                page_id = page.get("id", "")
                props = page.get("properties", {})

                row_text = f"\n## Entry\n"
                for prop_name, prop in props.items():
                    row_text += f"{prop_name}: {self._property_to_text(prop, prop_name)}\n"

                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=row_text,
                    source=f"notion://database/{database_id}/entry/{page_id}",
                    source_type="notion-entry",
                    metadata={
                        "database_id": database_id,
                        "page_id": page_id,
                    },
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching database {database_id}: {e}]",
                source=f"notion://database/{database_id}",
                source_type="notion-database",
                metadata={"database_id": database_id, "error": str(e)},
            ))
        return chunks


class NotionConnectorCLI:
    """CLI helper for Notion connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[NotionConnector, str]:
        token = ""
        pages: list[str] = []
        databases: list[str] = []

        for part in args.split():
            if part.startswith("--token="):
                token = part.split("=", 1)[1]
            elif part.startswith("--page="):
                pages.append(part.split("=", 1)[1])
            elif part.startswith("--database="):
                databases.append(part.split("=", 1)[1])

        if not token:
            raise ValueError("No token provided. Use --token=secret_xxx")

        connector = NotionConnector(token=token)
        for page in pages:
            connector.add_page(page)
        for db in databases:
            connector.add_database(db)

        source = f"notion://{len(pages)}pages,{len(databases)}databases"
        return connector, source

    @staticmethod
    def help_text() -> str:
        return """notion — Fetch Notion pages and databases

Usage:
  /connect notion --token=secret_xxx --page=page-id-1 --database=database-id-1

Options:
  --token=<token>       Notion integration token
  --page=<id>           Page ID to fetch (can be repeated)
  --database=<id>       Database ID to fetch (can be repeated)

Example:
  /connect notion --token=secret_xxx --page=xxx --database=yyy

Note: Requires a Notion integration with read access to the pages/databases.
  pip install 'ragmine[connector-notion]'
"""