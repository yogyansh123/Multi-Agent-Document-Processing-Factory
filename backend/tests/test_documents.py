"""
tests/test_documents.py
========================
Tests for the document ingestion API.

All tests use in-memory SQLite + a temp storage directory (via conftest).
No external services are required.

Coverage:
1.  Upload a valid PDF
2.  Upload a valid PNG
3.  Reject unsupported file type
4.  Reject oversized file
5.  Get document by ID
6.  Get nonexistent document → 404
7.  List documents
8.  Pagination
9.  Delete document
10. Processing history is created on upload
11. Health endpoint still works
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SMALL_PDF = b"%PDF-1.4 test pdf content"
SMALL_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _pdf_file(name: str = "invoice.pdf") -> dict:
    return {"file": (name, io.BytesIO(SMALL_PDF), "application/pdf")}


def _png_file(name: str = "receipt.png") -> dict:
    return {"file": (name, io.BytesIO(SMALL_PNG), "image/png")}


# ---------------------------------------------------------------------------
# 1. Upload valid PDF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_valid_pdf(async_client: AsyncClient) -> None:
    """POST /api/v1/documents should accept a PDF and return 201."""
    response = await async_client.post(
        "/api/v1/documents",
        files=_pdf_file("invoice_001.pdf"),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["original_filename"] == "invoice_001.pdf"
    assert data["file_type"] == "pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["status"] == "UPLOADED"
    assert data["document_type"] is None
    # Physical path must NOT be in response
    assert "file_path" not in data
    assert "stored_filename" not in data
    # Must have UUID id
    uuid.UUID(data["id"])


# ---------------------------------------------------------------------------
# 2. Upload valid PNG
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_valid_png(async_client: AsyncClient) -> None:
    """POST /api/v1/documents should accept a PNG and return 201."""
    response = await async_client.post(
        "/api/v1/documents",
        files=_png_file("receipt.png"),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["file_type"] == "png"
    assert data["status"] == "UPLOADED"


# ---------------------------------------------------------------------------
# 3. Reject unsupported file type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(async_client: AsyncClient) -> None:
    """POST /api/v1/documents should reject a .exe file with 400."""
    response = await async_client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 400, response.text
    assert "not supported" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Reject oversized file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_oversized_file(async_client: AsyncClient) -> None:
    """POST /api/v1/documents should reject files exceeding MAX_UPLOAD_SIZE_MB."""
    # Temporarily lower the limit to 1 byte to reliably trigger the check
    from app.core import config as cfg_module

    original_bytes = cfg_module.settings.MAX_UPLOAD_SIZE_BYTES

    # Patch the computed field result
    with patch.object(
        type(cfg_module.settings),
        "MAX_UPLOAD_SIZE_BYTES",
        new_callable=lambda: property(lambda self: 1),
    ):
        response = await async_client.post(
            "/api/v1/documents",
            files=_pdf_file("big.pdf"),
        )

    assert response.status_code == 413, response.text
    assert "exceeds" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Get document by ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_by_id(async_client: AsyncClient) -> None:
    """GET /api/v1/documents/{id} should return the document + history."""
    # Upload first
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files=_pdf_file("contract.pdf"),
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Retrieve
    get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()
    assert data["id"] == doc_id
    assert data["original_filename"] == "contract.pdf"
    assert "processing_history" in data
    assert isinstance(data["processing_history"], list)


# ---------------------------------------------------------------------------
# 6. Get nonexistent document → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_nonexistent_document(async_client: AsyncClient) -> None:
    """GET /api/v1/documents/{unknown_id} should return 404."""
    fake_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404, response.text
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. List documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents(async_client: AsyncClient) -> None:
    """GET /api/v1/documents should return a paginated list."""
    # Upload two documents
    for name in ("doc1.pdf", "doc2.png"):
        files = _pdf_file(name) if name.endswith(".pdf") else _png_file(name)
        resp = await async_client.post("/api/v1/documents", files=files)
        assert resp.status_code == 201

    response = await async_client.get("/api/v1/documents")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "total_pages" in data
    assert data["total"] >= 2
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# 8. Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination(async_client: AsyncClient) -> None:
    """Pagination parameters should control the response correctly."""
    # Upload 3 documents
    for i in range(3):
        resp = await async_client.post(
            "/api/v1/documents",
            files=_pdf_file(f"page_test_{i}.pdf"),
        )
        assert resp.status_code == 201

    # Request page 1 with page_size=2
    response = await async_client.get("/api/v1/documents?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2
    assert data["total"] >= 3
    assert data["total_pages"] >= 2

    # Page 2 should work and return remaining items
    response2 = await async_client.get("/api/v1/documents?page=2&page_size=2")
    assert response2.status_code == 200


# ---------------------------------------------------------------------------
# 9. Delete document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document(async_client: AsyncClient) -> None:
    """DELETE /api/v1/documents/{id} should remove the document."""
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files=_pdf_file("to_delete.pdf"),
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Delete
    del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 204, del_resp.text

    # Verify it's gone
    get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 10. Processing history is created on upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processing_history_created_on_upload(async_client: AsyncClient) -> None:
    """Uploading a document must create at least one ProcessingHistory record."""
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files=_pdf_file("history_test.pdf"),
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200
    history = get_resp.json()["processing_history"]
    assert len(history) >= 1
    first = history[0]
    assert first["stage"] == "UPLOAD"
    assert first["status"] == "COMPLETED"
    assert first["document_id"] == doc_id


# ---------------------------------------------------------------------------
# 11. Health endpoint still works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_still_works(async_client: AsyncClient) -> None:
    """The health endpoint must still return 200 after adding document routes."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# 12. Document Summary Stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_summary_stats(async_client: AsyncClient) -> None:
    """GET /api/v1/documents/stats/summary returns aggregated counts."""
    # Upload a document
    await async_client.post("/api/v1/documents", files=_pdf_file("stats_test.pdf"))

    response = await async_client.get("/api/v1/documents/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert data["total_documents"] >= 1
    assert "processing" in data
    assert "approved" in data
    assert "review_required" in data
    assert "rejected" in data
    assert "failed" in data
    assert "average_confidence" in data
    assert "rag_indexed_count" in data


# ---------------------------------------------------------------------------
# 13. Document List Filtering and Search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents_filtering(async_client: AsyncClient) -> None:
    """GET /api/v1/documents supports search and status filtering."""
    await async_client.post("/api/v1/documents", files=_pdf_file("unique_alpha_search.pdf"))
    await async_client.post("/api/v1/documents", files=_pdf_file("unique_beta_search.pdf"))

    # Search by filename
    search_resp = await async_client.get("/api/v1/documents?search=alpha")
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert any("unique_alpha_search.pdf" in item["original_filename"] for item in items)
    assert not any("unique_beta_search.pdf" in item["original_filename"] for item in items)

    # Filter by status
    status_resp = await async_client.get("/api/v1/documents?status=UPLOADED")
    assert status_resp.status_code == 200
    assert len(status_resp.json()["items"]) >= 2

