"""
ragmine.connectors.github
~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetch GitHub repos, issues, PRs, and READMEs.

    from ragmine.connectors.github import GitHubConnector
    connector = GitHubConnector(token="ghp_xxx")
    connector.add_repo("owner/repo")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect github --repo=owner/repo --token=ghp_xxx
    ragmine /connect github --repo=owner/repo --include-issues --include-prs
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import httpx

from ragmine.core.protocols import Chunk


@dataclass
class GitHubRepo:
    owner: str
    name: str
    include_readme: bool = True
    include_issues: bool = True
    include_prs: bool = True
    include_topics: bool = True
    max_items: int = 50


@dataclass
class GitHubConfig:
    token: str = ""
    base_url: str = "https://api.github.com"
    per_page: int = 100


class GitHubConnector:
    """Fetch GitHub repositories, issues, PRs, and READMEs."""

    def __init__(
        self,
        token: str = "",
        base_url: str = "https://api.github.com",
        per_page: int = 100,
    ):
        self._config = GitHubConfig(token=token, base_url=base_url, per_page=per_page)
        self._repos: list[GitHubRepo] = []
        self._client = httpx.Client(timeout=30)

    @property
    def name(self) -> str:
        return "github"

    def add_repo(
        self,
        repo: str,
        include_readme: bool = True,
        include_issues: bool = True,
        include_prs: bool = True,
        include_topics: bool = True,
    ) -> None:
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo}. Expected 'owner/name'")
        self._repos.append(GitHubRepo(
            owner=parts[0],
            name=parts[1],
            include_readme=include_readme,
            include_issues=include_issues,
            include_prs=include_prs,
            include_topics=include_topics,
        ))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        return headers

    def _get(self, path: str, params: dict | None = None) -> list | dict:
        url = f"{self._config.base_url}{path}"
        resp = self._client.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for repo in self._repos:
            if repo.include_readme:
                chunks.extend(self._fetch_readme(repo))
            if repo.include_issues:
                chunks.extend(self._fetch_issues(repo))
            if repo.include_prs:
                chunks.extend(self._fetch_prs(repo))
            if repo.include_topics:
                chunks.extend(self._fetch_topics(repo))
        return chunks

    def _fetch_readme(self, repo: GitHubRepo) -> list[Chunk]:
        chunks = []
        try:
            data = self._get(f"/repos/{repo.owner}/{repo.name}")
            text_parts = [
                f"# {data.get('full_name', '')}",
                f"Description: {data.get('description', 'N/A')}",
                f"Stars: {data.get('stargazers_count', 0)}",
                f"Language: {data.get('language', 'N/A')}",
                f"Topics: {', '.join(data.get('topics', []))}",
                f"License: {data.get('license', {}).get('name', 'N/A')}",
            ]
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text="\n".join(text_parts),
                source=f"github://{repo.owner}/{repo.name}/info",
                source_type="github-repo",
                metadata={"owner": repo.owner, "repo": repo.name, "type": "info"},
            ))

            readme = self._get(f"/repos/{repo.owner}/{repo.name}/readme")
            content = readme.get("content", "")
            if content:
                import base64
                decoded = base64.b64decode(content).decode("utf-8", errors="replace")
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=decoded,
                    source=f"github://{repo.owner}/{repo.name}/README.md",
                    source_type="github-readme",
                    metadata={"owner": repo.owner, "repo": repo.name, "type": "readme"},
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching README for {repo.owner}/{repo.name}: {e}]",
                source=f"github://{repo.owner}/{repo.name}/README.md",
                source_type="github-readme",
                metadata={"owner": repo.owner, "repo": repo.name, "error": str(e)},
            ))
        return chunks

    def _fetch_issues(self, repo: GitHubRepo) -> list[Chunk]:
        chunks = []
        try:
            issues = self._get(
                f"/repos/{repo.owner}/{repo.name}/issues",
                params={"state": "all", "per_page": min(repo.max_items, self._config.per_page)},
            )
            for issue in issues:
                if "pull_request" in issue:
                    continue
                labels = [l.get("name", "") for l in issue.get("labels", [])]
                text = f"""Issue: {issue.get('title', '')}
Number: #{issue.get('number', '')}
State: {issue.get('state', '')}
Labels: {', '.join(labels) if labels else 'None'}
Author: {issue.get('user', {}).get('login', 'unknown')}
Created: {issue.get('created_at', '')}

Body:
{issue.get('body', 'No description')}

---
Comments: {issue.get('comments', 0)}
URL: {issue.get('html_url', '')}"""
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"github://{repo.owner}/{repo.name}/issues/{issue.get('number', '')}",
                    source_type="github-issue",
                    metadata={
                        "owner": repo.owner,
                        "repo": repo.name,
                        "number": issue.get("number"),
                        "state": issue.get("state"),
                        "labels": labels,
                    },
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching issues for {repo.owner}/{repo.name}: {e}]",
                source=f"github://{repo.owner}/{repo.name}/issues",
                source_type="github-issue",
                metadata={"owner": repo.owner, "repo": repo.name, "error": str(e)},
            ))
        return chunks

    def _fetch_prs(self, repo: GitHubRepo) -> list[Chunk]:
        chunks = []
        try:
            prs = self._get(
                f"/repos/{repo.owner}/{repo.name}/pulls",
                params={"state": "all", "per_page": min(repo.max_items, self._config.per_page)},
            )
            for pr in prs:
                labels = [l.get("name", "") for l in pr.get("labels", [])]
                text = f"""Pull Request: {pr.get('title', '')}
Number: #{pr.get('number', '')}
State: {pr.get('state', '')}
Labels: {', '.join(labels) if labels else 'None'}
Author: {pr.get('user', {}).get('login', 'unknown')}
Created: {pr.get('created_at', '')}

Description:
{pr.get('body', 'No description')}

---
Files changed: {pr.get('changed_files', 0)}
Additions: {pr.get('additions', 0)} / Deletions: {pr.get('deletions', 0)}
URL: {pr.get('html_url', '')}"""
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"github://{repo.owner}/{repo.name}/pull/{pr.get('number', '')}",
                    source_type="github-pr",
                    metadata={
                        "owner": repo.owner,
                        "repo": repo.name,
                        "number": pr.get("number"),
                        "state": pr.get("state"),
                        "labels": labels,
                    },
                ))
        except Exception as e:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=f"[Error fetching PRs for {repo.owner}/{repo.name}: {e}]",
                source=f"github://{repo.owner}/{repo.name}/pulls",
                source_type="github-pr",
                metadata={"owner": repo.owner, "repo": repo.name, "error": str(e)},
            ))
        return chunks

    def _fetch_topics(self, repo: GitHubRepo) -> list[Chunk]:
        chunks = []
        try:
            data = self._get(f"/repos/{repo.owner}/{repo.name}/topics")
            topic_names = data.get("names", [])
            if topic_names:
                text = f"Repository Topics for {repo.owner}/{repo.name}:\n" + "\n".join(f"- {t}" for t in topic_names)
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"github://{repo.owner}/{repo.name}/topics",
                    source_type="github-topic",
                    metadata={"owner": repo.owner, "repo": repo.name, "topics": topic_names},
                ))
        except Exception:
            pass
        return chunks


class GitHubConnectorCLI:
    """CLI helper for GitHub connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[GitHubConnector, str]:
        token = ""
        repos: list[str] = []
        include_issues = True
        include_prs = True
        include_readme = True

        for part in args.split():
            if part.startswith("--token="):
                token = part.split("=", 1)[1]
            elif part.startswith("--repo="):
                repos.append(part.split("=", 1)[1])
            elif part == "--no-issues":
                include_issues = False
            elif part == "--no-prs":
                include_prs = False
            elif part == "--no-readme":
                include_readme = False

        if not repos:
            raise ValueError("No repos provided. Use --repo=owner/name")

        connector = GitHubConnector(token=token)
        for repo in repos:
            connector.add_repo(
                repo,
                include_readme=include_readme,
                include_issues=include_issues,
                include_prs=include_prs,
            )

        return connector, f"github://{','.join(repos)}"

    @staticmethod
    def help_text() -> str:
        return """github — Fetch GitHub repos, issues, and PRs

Usage:
  /connect github --repo=owner/repo --token=ghp_xxx
  /connect github --repo=owner/repo --repo=owner/repo2

Options:
  --repo=<owner/name>    Repository to fetch (can be repeated)
  --token=<token>       GitHub Personal Access Token (optional for public repos)
  --no-issues           Skip fetching issues
  --no-prs              Skip fetching pull requests
  --no-readme           Skip fetching README

Example:
  /connect github --repo=ragmine/ragmine --repo=owner/project --include-issues

Note: Requires a GitHub token for higher rate limits.
  pip install 'ragmine[connector-github]'
"""