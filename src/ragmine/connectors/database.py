"""
ragmine.connectors.database
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetch database schemas and query results.

    from ragmine.connectors.database import DatabaseConnector
    connector = DatabaseConnector(connection_string="postgresql://user:pass@localhost/db")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect database --dsn=postgresql://user:pass@localhost/db
    ragmine /connect database --dsn=sqlite:///data.db --query="SELECT * FROM users LIMIT 100"
"""

from __future__ import annotations

import uuid

import httpx

from ragmine.core.protocols import Chunk


class DatabaseConnector:
    """Fetch database schemas and query results."""

    def __init__(
        self,
        dsn: str = "",
        query: str = "",
        include_schema: bool = True,
        include_tables: list[str] | None = None,
    ):
        self._dsn = dsn
        self._query = query
        self._include_schema = include_schema
        self._include_tables = include_tables or []
        self._schema = None

    @property
    def name(self) -> str:
        return "database"

    def _get_engine(self):
        try:
            from sqlalchemy import create_engine
            return create_engine(self._dsn)
        except ImportError:
            raise ImportError("sqlalchemy required. pip install 'ragmine[connector-database]'")

    def _fetch_schema(self) -> list[Chunk]:
        chunks = []
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                from sqlalchemy import inspect
                inspector = inspect(conn)

                for table_name in inspector.get_table_names():
                    if self._include_tables and table_name not in self._include_tables:
                        continue

                    columns = inspector.get_columns(table_name)
                    foreign_keys = inspector.get_foreign_keys(table_name)
                    indexes = inspector.get_indexes(table_name)

                    column_lines = []
                    for col in columns:
                        col_type = str(col["type"])
                        nullable = "NULL" if col["nullable"] else "NOT NULL"
                        default = f"DEFAULT {col['default']}" if col["default"] else ""
                        column_lines.append(f"  - {col['name']}: {col_type} {nullable} {default}".strip())

                    fk_lines = []
                    for fk in foreign_keys:
                        fk_lines.append(f"  -> {fk['name']}: {fk['referred_table']}.{fk['referred_columns']}")

                    index_lines = []
                    for idx in indexes:
                        unique = "UNIQUE" if idx["unique"] else ""
                        index_lines.append(f"  - {idx['name']}: {', '.join(idx['column_names'])} {unique}")

                    text_parts = [f"Table: {table_name}"]
                    text_parts.append("Columns:")
                    text_parts.extend(column_lines)

                    if fk_lines:
                        text_parts.append("Foreign Keys:")
                        text_parts.extend(fk_lines)

                    if index_lines:
                        text_parts.append("Indexes:")
                        text_parts.extend(index_lines)

                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        text="\n".join(text_parts),
                        source=f"database://schema/{table_name}",
                        source_type="database-schema",
                        metadata={
                            "table": table_name,
                            "columns": len(columns),
                            "type": "schema",
                        },
                    ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching schema: {e}]",
                source="database://schema",
                source_type="database-schema",
                metadata={"error": str(e)},
            ))
        return chunks

    def _run_query(self) -> list[Chunk]:
        chunks = []
        if not self._query:
            return chunks

        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                result = conn.execute(eval(self._query.replace("conn", "conn")))
                rows = result.fetchall()
                columns = result.keys()

                if not rows:
                    return chunks

                col_widths = {col: len(str(col)) for col in columns}
                for row in rows:
                    for i, val in enumerate(row):
                        if i < len(columns):
                            col_widths[columns[i]] = max(col_widths[columns[i]], len(str(val)[:100]))

                lines = [f"# Query Results: {self._query}\n"]
                header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
                separator = "-+-".join("-" * col_widths[col] for col in columns)
                lines.append(header)
                lines.append(separator)

                for row in rows[:1000]:
                    vals = []
                    for i, val in enumerate(row):
                        if i < len(columns):
                            vals.append(str(val)[:col_widths[columns[i]]].ljust(col_widths[columns[i]]))
                    lines.append(" | ".join(vals))

                if len(rows) > 1000:
                    lines.append(f"\n... ({len(rows)} total rows, showing first 1000)")

                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text="\n".join(lines),
                    source="database://query",
                    source_type="database-query",
                    metadata={"rows": len(rows), "type": "query"},
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error running query: {e}]",
                source="database://query",
                source_type="database-query",
                metadata={"error": str(e)},
            ))
        return chunks

    def fetch_chunks(self) -> list[Chunk]:
        chunks = []
        if self._include_schema:
            chunks.extend(self._fetch_schema())
        if self._query:
            chunks.extend(self._run_query())
        return chunks


class DatabaseConnectorCLI:
    """CLI helper for Database connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[DatabaseConnector, str]:
        dsn = ""
        query = ""
        include_schema = True

        for part in args.split():
            if part.startswith("--dsn="):
                dsn = part.split("=", 1)[1]
            elif part.startswith("--query="):
                query = part.split("=", 1)[1]
            elif part == "--no-schema":
                include_schema = False

        if not dsn:
            raise ValueError("No DSN provided. Use --dsn=postgresql://user:pass@localhost/db")

        connector = DatabaseConnector(
            dsn=dsn,
            query=query,
            include_schema=include_schema,
        )

        return connector, f"database://{dsn.split('@')[-1] if '@' in dsn else dsn}"

    @staticmethod
    def help_text() -> str:
        return """database — Fetch database schemas and query results

Usage:
  /connect database --dsn=postgresql://user:pass@localhost/db
  /connect database --dsn=sqlite:///data.db --query="SELECT * FROM users"
  /connect database --dsn=mysql://user:pass@localhost/db --no-schema

Options:
  --dsn=<connection_string>   Database connection string
  --query=<sql>               SQL query to execute
  --no-schema                 Skip fetching table schemas

Example:
  /connect database --dsn=postgresql://user:pass@localhost/mydb --query="SELECT * FROM products LIMIT 100"

Note: Requires sqlalchemy and appropriate DB driver.
  pip install 'ragmine[connector-database]'
  pip install psycopg2-binary  # for PostgreSQL
  pip install pymysql          # for MySQL
"""