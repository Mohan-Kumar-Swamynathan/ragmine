"""
ragmine.connectors.slack
~~~~~~~~~~~~~~~~~~~~~~~~
Fetch Slack channels and messages.

    from ragmine.connectors.slack import SlackConnector
    connector = SlackConnector(token="xoxb-xxx")
    connector.add_channel("C0123456789")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect slack --token=xoxb-xxx --channel=C0123456789
    ragmine /connect slack --token=xoxb-xxx --workspace=myworkspace --days=30
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import httpx

from ragmine.core.protocols import Chunk


class SlackConnector:
    """Fetch Slack channels, messages, and threads."""

    def __init__(
        self,
        token: str,
        max_messages: int = 500,
        days_back: int = 30,
    ):
        self._token = token
        self._max_messages = max_messages
        self._days_back = days_back
        self._channels: list[str] = []
        self._client = httpx.Client(timeout=60)

    @property
    def name(self) -> str:
        return "slack"

    def add_channel(self, channel_id: str) -> None:
        self._channels.append(channel_id)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, data: dict) -> dict:
        url = f"https://slack.com/api{endpoint}"
        resp = self._client.post(url, headers=self._headers(), json=data)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok"):
            raise Exception(f"Slack API error: {result.get('error', 'Unknown')}")
        return result

    def _get_channel_name(self, channel_id: str) -> str:
        try:
            result = self._post("/conversations.info", {"channel": channel_id})
            return result.get("channel", {}).get("name", channel_id)
        except Exception:
            return channel_id

    def _get_messages(self, channel_id: str) -> list[dict]:
        oldest = (datetime.now() - timedelta(days=self._days_back)).timestamp()
        messages = []
        cursor = None

        while len(messages) < self._max_messages:
            data = {
                "channel": channel_id,
                "oldest": str(oldest),
                "limit": min(200, self._max_messages - len(messages)),
            }
            if cursor:
                data["cursor"] = cursor

            result = self._post("/conversations.history", data)
            messages.extend(result.get("messages", []))
            cursor = result.get("response_metadata", {}).get("next_cursor")

            if not cursor:
                break

        return messages

    def _format_message(self, msg: dict, channel_name: str) -> str:
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        ts = msg.get("ts", "")
        thread_ts = msg.get("thread_ts", "")
        is_thread = thread_ts and thread_ts != ts

        dt = datetime.fromtimestamp(float(ts)) if ts else None
        time_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""

        parts = [
            f"[{channel_name}] {time_str}",
            f"User: {user}",
        ]
        if is_thread:
            parts.append(f"Thread reply to: {thread_ts}")
        parts.append(f"Message:\n{text}")

        return "\n".join(parts)

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for channel_id in self._channels:
            chunks.extend(self._fetch_channel(channel_id))
        return chunks

    def _fetch_channel(self, channel_id: str) -> list[Chunk]:
        chunks = []
        channel_name = self._get_channel_name(channel_id)

        try:
            messages = self._get_messages(channel_id)

            for msg in messages:
                if msg.get("subtype") in {"bot_message", "channel_join", "channel_leave"}:
                    continue

                text = self._format_message(msg, channel_name)
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"slack://channel/{channel_id}/{msg.get('ts', '')}",
                    source_type="slack-message",
                    metadata={
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "user": msg.get("user", ""),
                        "timestamp": msg.get("ts", ""),
                    },
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching channel {channel_name} ({channel_id}): {e}]",
                source=f"slack://channel/{channel_id}",
                source_type="slack-message",
                metadata={"channel_id": channel_id, "error": str(e)},
            ))
        return chunks


class SlackConnectorCLI:
    """CLI helper for Slack connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[SlackConnector, str]:
        token = ""
        channels: list[str] = []
        days = 30

        for part in args.split():
            if part.startswith("--token="):
                token = part.split("=", 1)[1]
            elif part.startswith("--channel="):
                channels.append(part.split("=", 1)[1])
            elif part.startswith("--days="):
                try:
                    days = int(part.split("=", 1)[1])
                except ValueError:
                    pass

        if not token:
            raise ValueError("No token provided. Use --token=xoxb-xxx")

        connector = SlackConnector(token=token, days_back=days)
        for channel in channels:
            connector.add_channel(channel)

        source = f"slack://{','.join(channels)}" if channels else "slack://"
        return connector, source

    @staticmethod
    def help_text() -> str:
        return """slack — Fetch Slack channels and messages

Usage:
  /connect slack --token=xoxb-xxx --channel=C0123456789
  /connect slack --token=xoxb-xxx --channel=C0123456789 --channel=C9876543210 --days=7

Options:
  --token=<token>       Slack Bot or User OAuth token
  --channel=<id>       Channel ID to fetch (can be repeated)
  --days=<n>           Days of history to fetch (default: 30)

Example:
  /connect slack --token=xoxb-xxx --channel=C0123456789 --days=7

Note: Requires a Slack token with channels:history scope.
  pip install 'ragmine[connector-slack]'
"""