from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers.documents import router
from app.schemas import StoredDocument
from app.services.object_storage import (
    DocumentDownload,
    ObjectStorage,
    attachment_disposition,
)


class FakePaginator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages

    def paginate(self, **_: Any) -> list[dict[str, Any]]:
        return self.pages


class FakeS3Client:
    def __init__(self) -> None:
        self.put: dict[str, Any] | None = None

    def head_bucket(self, **_: Any) -> None:
        return None

    def put_object(self, **kwargs: Any) -> None:
        self.put = kwargs

    def get_paginator(self, _: str) -> FakePaginator:
        return FakePaginator(
            [
                {
                    "Contents": [
                        {
                            "Key": "documents/" + "a" * 64,
                            "Size": 5,
                            "LastModified": datetime(2026, 1, 2, tzinfo=UTC),
                        }
                    ]
                }
            ]
        )

    def head_object(self, **_: Any) -> dict[str, Any]:
        return {
            "ContentLength": 5,
            "ContentType": "text/plain; charset=utf-8",
            "Metadata": {
                "filename": "notes.txt",
                "collection": "research-notes",
                "chunks": "2",
                "custom-metadata": "eyJhdXRob3IiOiJBZGEifQ==",
            },
        }


def test_stores_document_under_content_hash() -> None:
    client = FakeS3Client()
    storage = ObjectStorage(Settings(), client=client)

    document_id = storage.store_document(
        "../../notes.txt",
        b"hello",
        "text/plain",
        "research-notes",
        2,
        {"author": "Ada"},
    )

    assert client.put is not None
    assert client.put["Key"] == f"documents/{document_id}"
    assert "notes.txt" not in client.put["Key"]
    assert client.put["Metadata"]["sha256"] == document_id
    assert client.put["Metadata"]["custom-metadata"] == "eyJhdXRob3IiOiJBZGEifQ=="


def test_lists_stored_document_metadata() -> None:
    storage = ObjectStorage(Settings(), client=FakeS3Client())

    documents = storage.list_documents()

    assert documents[0].filename == "notes.txt"
    assert documents[0].collection == "research-notes"
    assert documents[0].chunks == 2
    assert documents[0].metadata == {"author": "Ada"}


def test_attachment_header_strips_control_characters() -> None:
    header = attachment_disposition('report\r\nX-Bad: value".pdf')

    assert "\r" not in header
    assert "\n" not in header
    assert "filename*=UTF-8''" in header


class FakeRag:
    settings = SimpleNamespace(max_upload_mb=25, chunk_size=1200, chunk_overlap=200)

    def ingest(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        assert filename == "renamed-notes.txt"
        assert content_type.startswith("text/plain")
        assert chunks == ["hello world"]
        assert metadata == {"author": "Ada", "project": "Analytical Engine"}
        return "a" * 64

    def list_documents(self) -> list[StoredDocument]:
        return [
            StoredDocument(
                document_id="a" * 64,
                filename="notes.txt",
                size=11,
                content_type="text/plain; charset=utf-8",
                collection="research-notes",
                chunks=1,
                uploaded_at=datetime(2026, 1, 2, tzinfo=UTC),
                metadata={"author": "Ada"},
            )
        ]

    def get_document(self, document_id: str) -> DocumentDownload:
        assert document_id == "a" * 64
        return DocumentDownload(BytesIO(b"hello world"), "text/plain; charset=utf-8", "notes.txt", 11)


def _client() -> TestClient:
    api = FastAPI()
    api.include_router(router)
    api.state.rag = FakeRag()
    return TestClient(api)


def test_document_routes_store_list_and_download() -> None:
    client = _client()

    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={
            "filename": "renamed-notes.txt",
            "metadata": '{"author":"Ada","project":"Analytical Engine"}',
        },
    )
    listed = client.get("/api/v1/documents")
    downloaded = client.get(f"/api/v1/documents/{'a' * 64}/content")

    assert uploaded.status_code == 201
    assert uploaded.json()["stored"] is True
    assert uploaded.json()["filename"] == "renamed-notes.txt"
    assert uploaded.json()["metadata"] == {"author": "Ada", "project": "Analytical Engine"}
    assert listed.json()["documents"][0]["filename"] == "notes.txt"
    assert downloaded.content == b"hello world"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["content-disposition"].startswith("attachment")


def test_document_route_rejects_reserved_metadata_key() -> None:
    response = _client().post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={"metadata": '{"filename":"override"}'},
    )

    assert response.status_code == 422


def test_document_route_rejects_changed_extension() -> None:
    response = _client().post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={"filename": "notes.pdf"},
    )

    assert response.status_code == 422


def test_document_route_rejects_case_insensitive_duplicate_metadata_keys() -> None:
    response = _client().post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={"metadata": '{"Author":"Ada","author":"Grace"}'},
    )

    assert response.status_code == 422
