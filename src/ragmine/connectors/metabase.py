"""
ragmine.connectors.metabase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pull Metabase metadata into ragmine.

    ragmine ingest --source metabase --url http://localhost:3000 --api-key mb_xxx

Or via Python:

    from ragmine.connectors.metabase import MetabaseConnector
    connector = MetabaseConnector(url="http://localhost:3000", api_key="mb_xxx")
    chunks = connector.fetch_chunks()
"""

from __future__ import annotations

import json
import uuid

import httpx

from ragmine.core.protocols import Chunk


class MetabaseConnector:
    """Ingests Metabase schemas, saved questions, and dashboards."""

    def __init__(self, url: str, api_key: str):
        self._url = url.rstrip("/")
        self._headers = {"x-api-key": api_key}
        self._client = httpx.Client(base_url=self._url, headers=self._headers, timeout=30)

    @property
    def name(self) -> str:
        return "metabase"

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunks.extend(self._fetch_schemas())
        chunks.extend(self._fetch_questions())
        chunks.extend(self._fetch_dashboards())
        return chunks

    def _fetch_schemas(self) -> list[Chunk]:
        """Fetch database schemas — tables, columns, types."""
        chunks = []
        try:
            databases = self._get("/api/database/")
            if isinstance(databases, dict):
                databases = databases.get("data", [])

            for db in databases:
                db_id = db.get("id")
                db_name = db.get("name", "unknown")
                try:
                    meta = self._get(f"/api/database/{db_id}/metadata")
                    for table in meta.get("tables", []):
                        text = self._format_table(db_name, table)
                        chunks.append(Chunk(
                            id=str(uuid.uuid4()),
                            text=text,
                            source=f"metabase://schema/{db_name}/{table.get('name', '')}",
                            source_type="metabase-schema",
                            metadata={"db": db_name, "table": table.get("name", "")},
                        ))
                except Exception:
                    continue
        except Exception:
            pass
        return chunks

    def _fetch_questions(self) -> list[Chunk]:
        """Fetch saved questions — name, description, SQL."""
        chunks = []
        try:
            cards = self._get("/api/card/")
            for card in cards:
                text = self._format_question(card)
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"metabase://question/{card.get('id', '')}",
                    source_type="metabase-question",
                    metadata={
                        "question_id": card.get("id"),
                        "name": card.get("name", ""),
                        "display": card.get("display", ""),
                    },
                ))
        except Exception:
            pass
        return chunks

    def _fetch_dashboards(self) -> list[Chunk]:
        """Fetch dashboards — title, description, cards list."""
        chunks = []
        try:
            dashboards = self._get("/api/dashboard/")
            for dash in dashboards:
                dash_id = dash.get("id")
                try:
                    detail = self._get(f"/api/dashboard/{dash_id}")
                    text = self._format_dashboard(detail)
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        text=text,
                        source=f"metabase://dashboard/{dash_id}",
                        source_type="metabase-dashboard",
                        metadata={
                            "dashboard_id": dash_id,
                            "name": detail.get("name", ""),
                        },
                    ))
                except Exception:
                    continue
        except Exception:
            pass
        return chunks

    # ── Formatters ──

    def _format_table(self, db_name: str, table: dict) -> str:
        cols = []
        for f in table.get("fields", []):
            desc = f.get("description", "")
            dtype = f.get("database_type", f.get("base_type", ""))
            cols.append(f"  - {f.get('name', '')} ({dtype}){': ' + desc if desc else ''}")

        return (
            f"Database: {db_name}\n"
            f"Table: {table.get('name', '')}\n"
            f"Description: {table.get('description', 'N/A')}\n"
            f"Columns:\n" + "\n".join(cols)
        )

    def _format_question(self, card: dict) -> str:
        query = card.get("dataset_query", {})
        sql = query.get("native", {}).get("query", "")
        query_type = "SQL" if sql else "Visual Query Builder"

        return (
            f"Saved Question: {card.get('name', '')}\n"
            f"Description: {card.get('description', 'N/A')}\n"
            f"Visualization: {card.get('display', 'table')}\n"
            f"Query Type: {query_type}\n"
            + (f"SQL:\n{sql}" if sql else "")
        )

    def _format_dashboard(self, dash: dict) -> str:
        cards = dash.get("dashcards", dash.get("ordered_cards", []))
        card_names = []
        for dc in cards:
            card = dc.get("card", {})
            if card and card.get("name"):
                card_names.append(f"  - {card['name']}")

        return (
            f"Dashboard: {dash.get('name', '')}\n"
            f"Description: {dash.get('description', 'N/A')}\n"
            f"Questions on this dashboard:\n" + "\n".join(card_names)
        )

    # ── HTTP ──

    def _get(self, path: str) -> dict | list:
        resp = self._client.get(path)
        resp.raise_for_status()
        return resp.json()
