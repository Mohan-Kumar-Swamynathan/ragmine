"""
ragmine.connectors.s3
~~~~~~~~~~~~~~~~~~~~
Fetch files from S3/GCS buckets.

    from ragmine.connectors.s3 import S3Connector
    connector = S3Connector(
        provider="aws",
        bucket="my-bucket",
        access_key="xxx",
        secret_key="xxx",
    )
    connector.add_prefix("docs/")
    chunks = connector.fetch_chunks()

Usage:
    ragmine /connect s3 --provider=aws --bucket=my-bucket --access-key=xxx --secret-key=xxx
    ragmine /connect s3 --provider=gcs --bucket=my-bucket --credentials-file=./creds.json --prefix=docs/
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx

from ragmine.core.protocols import Chunk


SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".rb",
    ".csv", ".log", ".env", ".html", ".xml",
}


class S3Connector:
    """Fetch files from S3 or GCS buckets."""

    def __init__(
        self,
        provider: str = "aws",
        bucket: str = "",
        region: str = "us-east-1",
        access_key: str = "",
        secret_key: str = "",
        credentials_file: str = "",
        prefix: str = "",
    ):
        self._provider = provider.lower()
        self._bucket = bucket
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._credentials_file = credentials_file
        self._prefix = prefix
        self._prefixes: list[str] = []
        self._files: list[str] = []

    @property
    def name(self) -> str:
        return "s3"

    def add_prefix(self, prefix: str) -> None:
        self._prefixes.append(prefix)

    def add_file(self, key: str) -> None:
        self._files.append(key)

    def _get_client(self):
        if self._provider == "aws":
            return self._get_s3_client()
        elif self._provider == "gcs":
            return self._get_gcs_client()
        else:
            raise ValueError(f"Unknown provider: {self._provider}")

    def _get_s3_client(self):
        try:
            import boto3
            client_kwargs = {
                "service_name": "s3",
                "region_name": self._region,
            }
            if self._access_key and self._secret_key:
                client_kwargs["aws_access_key_id"] = self._access_key
                client_kwargs["aws_secret_access_key"] = self._secret_key
            elif self._credentials_file:
                import json
                creds = json.loads(Path(self._credentials_file).read_text())
                client_kwargs["aws_access_key_id"] = creds.get("aws_access_key_id", "")
                client_kwargs["aws_secret_access_key"] = creds.get("aws_secret_access_key", "")
            return boto3.client(**client_kwargs)
        except ImportError:
            raise ImportError("boto3 required. pip install 'ragmine[connector-s3]'")

    def _get_gcs_client(self):
        try:
            from google.cloud import storage
            client_kwargs = {}
            if self._credentials_file:
                client_kwargs["credentials"] = self._credentials_file
            return storage.Client(**client_kwargs)
        except ImportError:
            raise ImportError("google-cloud-storage required. pip install 'ragmine[connector-s3]'")

    def _list_objects(self, prefix: str) -> list[dict]:
        objects = []
        try:
            if self._provider == "aws":
                client = self._get_s3_client()
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        key = obj.get("Key", "")
                        if any(key.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                            objects.append({
                                "key": key,
                                "size": obj.get("Size", 0),
                                "modified": obj.get("LastModified", "").isoformat() if obj.get("LastModified") else "",
                            })
            elif self._provider == "gcs":
                client = self._get_gcs_client()
                bucket = client.bucket(self._bucket)
                blobs = bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    if any(blob.name.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        objects.append({
                            "key": blob.name,
                            "size": blob.size,
                            "modified": blob.time_created.isoformat() if blob.time_created else "",
                        })
        except Exception as e:
            objects.append({"error": str(e)})
        return objects

    def _read_file(self, key: str) -> str:
        try:
            if self._provider == "aws":
                client = self._get_s3_client()
                response = client.get_object(Bucket=self._bucket, Key=key)
                return response["Body"].read().decode("utf-8", errors="replace")
            elif self._provider == "gcs":
                client = self._get_gcs_client()
                bucket = client.bucket(self._bucket)
                blob = bucket.blob(key)
                return blob.download_as_text()
        except Exception as e:
            return f"[Error reading {key}: {e}]"

    def fetch_chunks(self) -> list[Chunk]:
        chunks = []
        prefixes = self._prefixes or [self._prefix] if self._prefix else [""]

        for prefix in prefixes:
            objects = self._list_objects(prefix)

            if not objects:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=f"[No files found in {self._bucket}/{prefix}]",
                    source=f"{self._provider}://{self._bucket}/{prefix}",
                    source_type="s3-bucket",
                    metadata={"bucket": self._bucket, "prefix": prefix},
                ))
                continue

            for obj in objects:
                if "error" in obj:
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        text=f"[Error listing objects: {obj['error']}]",
                        source=f"{self._provider}://{self._bucket}/{prefix}",
                        source_type="s3-bucket",
                        metadata={"error": obj["error"]},
                    ))
                    continue

                key = obj["key"]
                text = self._read_file(key)

                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=text,
                    source=f"{self._provider}://{self._bucket}/{key}",
                    source_type="s3-file",
                    metadata={
                        "bucket": self._bucket,
                        "key": key,
                        "size": obj["size"],
                        "modified": obj["modified"],
                    },
                ))
        return chunks


class S3ConnectorCLI:
    """CLI helper for S3 connector."""

    @staticmethod
    def parse_args(args: str) -> tuple[S3Connector, str]:
        provider = "aws"
        bucket = ""
        region = "us-east-1"
        access_key = ""
        secret_key = ""
        credentials_file = ""
        prefix = ""

        for part in args.split():
            if part.startswith("--provider="):
                provider = part.split("=", 1)[1]
            elif part.startswith("--bucket="):
                bucket = part.split("=", 1)[1]
            elif part.startswith("--region="):
                region = part.split("=", 1)[1]
            elif part.startswith("--access-key="):
                access_key = part.split("=", 1)[1]
            elif part.startswith("--secret-key="):
                secret_key = part.split("=", 1)[1]
            elif part.startswith("--credentials-file="):
                credentials_file = part.split("=", 1)[1]
            elif part.startswith("--prefix="):
                prefix = part.split("=", 1)[1]

        if not bucket:
            raise ValueError("No bucket provided. Use --bucket=my-bucket")

        connector = S3Connector(
            provider=provider,
            bucket=bucket,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            credentials_file=credentials_file,
            prefix=prefix,
        )

        return connector, f"{provider}://{bucket}/{prefix}"

    @staticmethod
    def help_text() -> str:
        return """s3 — Fetch files from S3 or GCS buckets

Usage:
  /connect s3 --provider=aws --bucket=my-bucket --access-key=xxx --secret-key=xxx
  /connect s3 --provider=gcs --bucket=my-bucket --credentials-file=./creds.json --prefix=docs/

Options:
  --provider=<name>           Cloud provider: aws or gcs (default: aws)
  --bucket=<name>             Bucket name
  --region=<region>           AWS region (default: us-east-1)
  --access-key=<key>          AWS access key (or use credentials-file)
  --secret-key=<key>          AWS secret key (or use credentials-file)
  --credentials-file=<path>   Path to credentials JSON file
  --prefix=<path>             Prefix to filter objects

Supported file types: .txt, .md, .json, .yaml, .py, .js, .ts, .go, etc.

Example:
  /connect s3 --bucket=my-docs --prefix=projects/ --credentials-file=~/.aws/credentials

Note: Requires boto3 for AWS or google-cloud-storage for GCS.
  pip install 'ragmine[connector-s3]'
  pip install boto3                          # for AWS
  pip install google-cloud-storage           # for GCS
"""