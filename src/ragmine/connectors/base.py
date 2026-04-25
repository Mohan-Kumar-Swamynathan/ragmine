"""
ragmine.connectors.base
~~~~~~~~~~~~~~~~~~~~~~~~
Base protocol for connectors. Implement to add new data sources.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ragmine.core.protocols import Chunk


@runtime_checkable
class Connector(Protocol):
    """Pull data from external sources into ragmine."""

    def fetch_chunks(self) -> list[Chunk]:
        """Fetch and return chunks ready for ingestion."""
        ...

    @property
    def name(self) -> str:
        """Connector name for display."""
        ...
