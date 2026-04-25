"""
ragmine.connectors
~~~~~~~~~~~~~~~~~~
All available connectors for ingesting external data sources.

Usage:
    from ragmine.connectors import CONNECTORS, get_connector_help

    # List all available connectors
    for name in CONNECTORS:
        print(f"  {name}: {get_connector_help(name)}")

    # Get a connector instance
    connector = CONNECTORS["web"].create(token="...")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class ConnectorInfo:
    name: str
    description: str
    help_text: str
    create: Callable[[], object]


CONNECTOR_REGISTRY: dict[str, ConnectorInfo] = {}


def _register_connectors():
    global CONNECTOR_REGISTRY

    try:
        from ragmine.connectors.web import WebConnector, WebConnectorCLI
        CONNECTOR_REGISTRY["web"] = ConnectorInfo(
            name="web",
            description="Fetch web pages and convert to chunks",
            help_text=WebConnectorCLI.help_text(),
            create=lambda: WebConnector(),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.github import GitHubConnector, GitHubConnectorCLI
        CONNECTOR_REGISTRY["github"] = ConnectorInfo(
            name="github",
            description="Fetch GitHub repos, issues, and PRs",
            help_text=GitHubConnectorCLI.help_text(),
            create=lambda: GitHubConnector(),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.confluence import ConfluenceConnector, ConfluenceConnectorCLI
        CONNECTOR_REGISTRY["confluence"] = ConnectorInfo(
            name="confluence",
            description="Fetch Confluence spaces and pages",
            help_text=ConfluenceConnectorCLI.help_text(),
            create=lambda: ConfluenceConnector(url=""),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.slack import SlackConnector, SlackConnectorCLI
        CONNECTOR_REGISTRY["slack"] = ConnectorInfo(
            name="slack",
            description="Fetch Slack channels and messages",
            help_text=SlackConnectorCLI.help_text(),
            create=lambda: SlackConnector(token=""),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.notion import NotionConnector, NotionConnectorCLI
        CONNECTOR_REGISTRY["notion"] = ConnectorInfo(
            name="notion",
            description="Fetch Notion pages and databases",
            help_text=NotionConnectorCLI.help_text(),
            create=lambda: NotionConnector(token=""),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.database import DatabaseConnector, DatabaseConnectorCLI
        CONNECTOR_REGISTRY["database"] = ConnectorInfo(
            name="database",
            description="Fetch database schemas and query results",
            help_text=DatabaseConnectorCLI.help_text(),
            create=lambda: DatabaseConnector(),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.rss import RSSConnector, RSSConnectorCLI
        CONNECTOR_REGISTRY["rss"] = ConnectorInfo(
            name="rss",
            description="Fetch RSS/Atom feeds",
            help_text=RSSConnectorCLI.help_text(),
            create=lambda: RSSConnector(),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.s3 import S3Connector, S3ConnectorCLI
        CONNECTOR_REGISTRY["s3"] = ConnectorInfo(
            name="s3",
            description="Fetch files from S3 or GCS buckets",
            help_text=S3ConnectorCLI.help_text(),
            create=lambda: S3Connector(),
        )
    except ImportError:
        pass

    try:
        from ragmine.connectors.metabase import MetabaseConnector
        CONNECTOR_REGISTRY["metabase"] = ConnectorInfo(
            name="metabase",
            description="Pull Metabase schemas, questions, and dashboards",
            help_text="""metabase — Pull Metabase metadata

Usage:
  /connect metabase --url=http://localhost:3000 --api-key=xxx

Options:
  --url=<url>           Metabase URL
  --api-key=<key>       Metabase API key

Note: pip install 'ragmine[connector-metabase]'
""",
            create=lambda: MetabaseConnector(url="", api_key=""),
        )
    except ImportError:
        pass


_register_connectors()


def get_connector(name: str) -> ConnectorInfo | None:
    return CONNECTOR_REGISTRY.get(name.lower())


def get_connector_help(name: str) -> str:
    info = get_connector(name)
    return info.help_text if info else f"Unknown connector: {name}"


def list_connectors() -> list[str]:
    return list(CONNECTOR_REGISTRY.keys())


def get_all_help() -> str:
    lines = ["Available Connectors:", ""]
    for name, info in CONNECTOR_REGISTRY.items():
        lines.append(f"  [cyan]{name}[/cyan] — {info.description}")
    lines.append("")
    lines.append("Usage: /connect <name> [options]")
    lines.append("Help:  /help connectors")
    lines.append("       /help <connector-name>")
    return "\n".join(lines)


CONNECTORS = CONNECTOR_REGISTRY

__all__ = [
    "CONNECTORS",
    "ConnectorInfo",
    "get_connector",
    "get_connector_help",
    "list_connectors",
    "get_all_help",
]