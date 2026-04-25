"""
tests/test_connectors.py
~~~~~~~~~~~~~~~~~~~~~~~~
Tests for connectors.
"""

import pytest
from ragmine.core.protocols import Chunk


class TestWebConnector:
    """Tests for WebConnector."""

    def test_web_connector_init(self):
        from ragmine.connectors.web import WebConnector

        connector = WebConnector(urls=["https://example.com"])
        assert connector.name == "web"
        assert len(connector._urls) == 1

    def test_web_connector_add_url(self):
        from ragmine.connectors.web import WebConnector

        connector = WebConnector()
        connector.add_url("https://example.com")
        connector.add_url("https://example.org")
        assert len(connector._urls) == 2

    def test_web_connector_chunk_text(self):
        from ragmine.connectors.web import _chunk_text

        text = "A" * 3000
        chunks = _chunk_text(text, chunk_size=1000, overlap=100)
        assert len(chunks) > 1

    def test_web_connector_html_to_markdown_fallback(self):
        from ragmine.connectors.web import _strip_html_basic

        html = "<html><body><p>Hello World</p></body></html>"
        text = _strip_html_basic(html)
        assert "Hello World" in text


class TestGitHubConnector:
    """Tests for GitHubConnector."""

    def test_github_connector_init(self):
        from ragmine.connectors.github import GitHubConnector

        connector = GitHubConnector(token="test-token")
        assert connector.name == "github"

    def test_github_connector_add_repo(self):
        from ragmine.connectors.github import GitHubConnector

        connector = GitHubConnector()
        connector.add_repo("owner/repo")
        assert len(connector._repos) == 1
        assert connector._repos[0].owner == "owner"
        assert connector._repos[0].name == "repo"

    def test_github_connector_invalid_repo(self):
        from ragmine.connectors.github import GitHubConnector

        connector = GitHubConnector()
        with pytest.raises(ValueError):
            connector.add_repo("invalid-repo")


class TestConfluenceConnector:
    """Tests for ConfluenceConnector."""

    def test_confluence_connector_init(self):
        from ragmine.connectors.confluence import ConfluenceConnector

        connector = ConfluenceConnector(
            url="https://example.atlassian.net",
            email="test@example.com",
            api_key="xxx",
        )
        assert connector.name == "confluence"

    def test_confluence_connector_add_space(self):
        from ragmine.connectors.confluence import ConfluenceConnector

        connector = ConfluenceConnector(url="https://example.atlassian.net")
        connector.add_space("SPACEKEY")
        assert len(connector._spaces) == 1


class TestSlackConnector:
    """Tests for SlackConnector."""

    def test_slack_connector_init(self):
        from ragmine.connectors.slack import SlackConnector

        connector = SlackConnector(token="xoxb-test")
        assert connector.name == "slack"

    def test_slack_connector_add_channel(self):
        from ragmine.connectors.slack import SlackConnector

        connector = SlackConnector(token="xoxb-test")
        connector.add_channel("C0123456789")
        assert len(connector._channels) == 1


class TestNotionConnector:
    """Tests for NotionConnector."""

    def test_notion_connector_init(self):
        from ragmine.connectors.notion import NotionConnector

        connector = NotionConnector(token="secret-test")
        assert connector.name == "notion"

    def test_notion_connector_add_page_database(self):
        from ragmine.connectors.notion import NotionConnector

        connector = NotionConnector(token="secret-test")
        connector.add_page("page-id")
        connector.add_database("db-id")
        assert len(connector._pages) == 1
        assert len(connector._databases) == 1


class TestDatabaseConnector:
    """Tests for DatabaseConnector."""

    def test_database_connector_init(self):
        from ragmine.connectors.database import DatabaseConnector

        connector = DatabaseConnector(dsn="sqlite:///:memory:")
        assert connector.name == "database"


class TestRSSConnector:
    """Tests for RSSConnector."""

    def test_rss_connector_init(self):
        from ragmine.connectors.rss import RSSConnector

        connector = RSSConnector(feeds=["https://example.com/feed"])
        assert connector.name == "rss"

    def test_rss_connector_add_feed(self):
        from ragmine.connectors.rss import RSSConnector

        connector = RSSConnector()
        connector.add_feed("https://example.com/feed")
        connector.add_feed("https://example.org/rss")
        assert len(connector._feeds) == 2


class TestS3Connector:
    """Tests for S3Connector."""

    def test_s3_connector_init(self):
        from ragmine.connectors.s3 import S3Connector

        connector = S3Connector(provider="aws", bucket="test-bucket")
        assert connector.name == "s3"

    def test_s3_connector_add_prefix(self):
        from ragmine.connectors.s3 import S3Connector

        connector = S3Connector(provider="aws", bucket="test-bucket")
        connector.add_prefix("docs/")
        connector.add_prefix("data/")
        assert len(connector._prefixes) == 2


class TestConnectorRegistry:
    """Tests for connector registry."""

    def test_list_connectors(self):
        from ragmine.connectors import list_connectors

        connectors = list_connectors()
        assert "web" in connectors
        assert "github" in connectors
        assert "slack" in connectors
        assert "notion" in connectors
        assert "database" in connectors
        assert "rss" in connectors
        assert "s3" in connectors

    def test_get_connector_help(self):
        from ragmine.connectors import get_connector_help

        help_text = get_connector_help("web")
        assert "web" in help_text
        assert "--url" in help_text

        help_text = get_connector_help("github")
        assert "github" in help_text
        assert "--repo" in help_text


class TestConnectorCLI:
    """Tests for connector CLI helpers."""

    def test_web_connector_cli_parse(self):
        from ragmine.connectors.web import WebConnectorCLI

        connector = WebConnectorCLI.parse_args("--url=https://example.com --url=https://example.org")
        assert len(connector._urls) == 2

    def test_web_connector_cli_help(self):
        from ragmine.connectors.web import WebConnectorCLI

        help_text = WebConnectorCLI.help_text()
        assert "web" in help_text
        assert "--url=" in help_text

    def test_github_connector_cli_parse(self):
        from ragmine.connectors.github import GitHubConnectorCLI

        connector, source = GitHubConnectorCLI.parse_args("--repo=owner/repo --repo=owner/repo2 --token=xxx")
        assert len(connector._repos) == 2

    def test_rss_connector_cli_parse(self):
        from ragmine.connectors.rss import RSSConnectorCLI

        connector = RSSConnectorCLI.parse_args("--feed=https://example.com/feed --days=7")
        assert len(connector._feeds) == 1
        assert connector._days_back == 7


class TestMetabaseConnector:
    """Tests for MetabaseConnector."""

    def test_metabase_connector_init(self):
        from ragmine.connectors.metabase import MetabaseConnector

        connector = MetabaseConnector(
            url="http://localhost:3000",
            api_key="test-key",
        )
        assert connector.name == "metabase"