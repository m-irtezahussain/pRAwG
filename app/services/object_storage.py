from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, unquote

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.schemas import StoredDocument

OBJECT_PREFIX = "documents/"
STREAM_CHUNK_SIZE = 64 * 1024
MAX_CUSTOM_METADATA_BYTES = 1024


class ObjectStorageError(RuntimeError):
    """A safe-to-display object-storage failure."""


class StoredDocumentNotFoundError(ObjectStorageError):
    pass


@dataclass
class DocumentDownload:
    body: Any
    content_type: str
    filename: str
    size: int

    def chunks(self) -> Iterator[bytes]:
        try:
            while data := self.body.read(STREAM_CHUNK_SIZE):
                yield data
        finally:
            self.body.close()


class ObjectStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.bucket = settings.object_storage_bucket
        self.region = settings.object_storage_region
        self.client = client or boto3.client(
            "s3",
            endpoint_url=str(settings.object_storage_endpoint).rstrip("/"),
            aws_access_key_id=settings.object_storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.object_storage_secret_key.get_secret_value(),
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise ObjectStorageError("Unable to access document storage") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError("Unable to access document storage") from exc

        try:
            create_args: dict[str, Any] = {"Bucket": self.bucket}
            if self.region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            self.client.create_bucket(**create_args)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("Unable to initialize document storage") from exc

    def heartbeat(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("Document storage is unavailable") from exc

    def store_document(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        collection: str,
        chunk_count: int,
        custom_metadata: dict[str, str],
    ) -> str:
        document_id = hashlib.sha256(content).hexdigest()
        encoded_metadata = _encode_custom_metadata(custom_metadata)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._key(document_id),
                Body=content,
                ContentLength=len(content),
                ContentType=content_type,
                ContentDisposition=attachment_disposition(filename),
                Metadata={
                    "filename": quote(filename, safe=""),
                    "collection": quote(collection, safe=""),
                    "chunks": str(chunk_count),
                    "sha256": document_id,
                    "custom-metadata": encoded_metadata,
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError("Unable to store the uploaded document") from exc
        return document_id

    def list_documents(self) -> list[StoredDocument]:
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            items: list[StoredDocument] = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=OBJECT_PREFIX):
                for object_item in page.get("Contents", []):
                    key = str(object_item.get("Key", ""))
                    document_id = key.removeprefix(OBJECT_PREFIX)
                    if len(document_id) != 64:
                        continue
                    head = self.client.head_object(Bucket=self.bucket, Key=key)
                    metadata = head.get("Metadata", {})
                    items.append(
                        StoredDocument(
                            document_id=document_id,
                            filename=unquote(str(metadata.get("filename", "document"))),
                            size=int(head.get("ContentLength", object_item.get("Size", 0))),
                            content_type=str(head.get("ContentType", "application/octet-stream")),
                            collection=unquote(str(metadata.get("collection", "unknown"))),
                            chunks=_non_negative_int(metadata.get("chunks")),
                            uploaded_at=object_item.get("LastModified") or datetime.now(UTC),
                            metadata=_decode_custom_metadata(metadata.get("custom-metadata")),
                        )
                    )
        except (BotoCoreError, ClientError, TypeError, ValueError) as exc:
            raise ObjectStorageError("Unable to list stored documents") from exc
        return sorted(items, key=lambda item: item.uploaded_at, reverse=True)

    def get_document(self, document_id: str) -> DocumentDownload:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(document_id))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise StoredDocumentNotFoundError("Stored document was not found") from exc
            raise ObjectStorageError("Unable to retrieve the stored document") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError("Unable to retrieve the stored document") from exc
        metadata = response.get("Metadata", {})
        return DocumentDownload(
            body=response["Body"],
            content_type=str(response.get("ContentType", "application/octet-stream")),
            filename=unquote(str(metadata.get("filename", "document"))),
            size=int(response.get("ContentLength", 0)),
        )

    @staticmethod
    def _key(document_id: str) -> str:
        return f"{OBJECT_PREFIX}{document_id}"


def attachment_disposition(filename: str) -> str:
    fallback = "".join(character for character in filename if 32 <= ord(character) < 127)
    fallback = fallback.replace('"', "").replace("\\", "_").replace("/", "_") or "document"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _encode_custom_metadata(metadata: dict[str, str]) -> str:
    serialized = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(serialized) > MAX_CUSTOM_METADATA_BYTES:
        raise ObjectStorageError("Custom metadata is too large to store")
    return base64.urlsafe_b64encode(serialized).decode("ascii")


def _decode_custom_metadata(value: Any) -> dict[str, str]:
    if not value:
        return {}
    try:
        payload = json.loads(base64.urlsafe_b64decode(str(value).encode("ascii")))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(item) for key, item in payload.items()}
