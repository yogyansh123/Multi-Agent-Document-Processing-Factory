"""
tests/test_ocr.py
=================
Comprehensive tests for Step 3: OCR Pipeline.

Coverage includes:
1. OCRResult dataclass and defaults.
2. OCRProvider abstract interface.
3. OCR factory instantiation, caching, and unknown/unimplemented errors.
4. TesseractProvider error handling (file not found, unsupported type).
5. Native DOCX extraction without external Tesseract binary.
6. Trigger OCR endpoint (POST /api/v1/documents/{id}/ocr) success flow.
7. Document model updates after OCR (text, provider, page_count, time, completed_at, status).
8. ProcessingHistory record creation for stage=OCR.
9. Trigger OCR failure flow (status=FAILED, error_message recorded, 422 response).
10. Trigger OCR 404 for nonexistent document.
11. Get extracted text endpoint (GET /api/v1/documents/{id}/text) success.
12. Get extracted text before OCR returns 409 Conflict.
13. Get extracted text 404 for nonexistent document.
14. Reprocessing flow: running OCR again overwrites document fields and appends history.
"""

from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
import docx

from app.api.deps import get_ocr_provider
from app.core.enums import DocumentStatus, ProcessingStage, StageStatus
from app.main import app as fastapi_app
from app.services.ocr.base import OCRError, OCRProvider, OCRResult
from app.services.ocr.factory import get_ocr_provider as factory_get_ocr_provider
from app.services.ocr.tesseract import TesseractProvider
from tests.conftest import MockOCRProvider

# Sample minimal PDF bytes
VALID_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
)


# ---------------------------------------------------------------------------
# 1. Base Abstraction & Dataclass Tests
# ---------------------------------------------------------------------------

def test_ocr_result_dataclass():
    """Verify OCRResult stores text and metadata correctly."""
    result = OCRResult(
        text="Extracted Invoice Text",
        provider="mock",
        page_count=3,
        processing_time_ms=150,
        metadata={"confidence": 0.95},
    )
    assert result.text == "Extracted Invoice Text"
    assert result.provider == "mock"
    assert result.page_count == 3
    assert result.processing_time_ms == 150
    assert result.metadata == {"confidence": 0.95}


def test_ocr_provider_cannot_be_instantiated_directly():
    """Verify OCRProvider is an abstract base class."""
    with pytest.raises(TypeError):
        OCRProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. Factory Tests
# ---------------------------------------------------------------------------

def test_factory_returns_tesseract_provider():
    """Factory should return a TesseractProvider when requested."""
    provider = factory_get_ocr_provider("tesseract")
    assert isinstance(provider, TesseractProvider)
    assert provider.provider_name == "tesseract"


def test_factory_unimplemented_provider():
    """Factory raises NotImplementedError for future cloud providers."""
    with pytest.raises(NotImplementedError):
        factory_get_ocr_provider("aws_textract")


def test_factory_unknown_provider():
    """Factory raises ValueError for invalid provider names."""
    with pytest.raises(ValueError, match="Unknown OCR provider"):
        factory_get_ocr_provider("nonexistent_engine")


# ---------------------------------------------------------------------------
# 3. TesseractProvider Unit Tests (No binary required)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tesseract_provider_file_not_found(tmp_path):
    """TesseractProvider raises OCRError if file does not exist."""
    provider = TesseractProvider()
    non_existent = str(tmp_path / "does_not_exist.pdf")
    with pytest.raises(OCRError, match="File not found"):
        await provider.extract_text(non_existent, "pdf")


@pytest.mark.asyncio
async def test_tesseract_provider_unsupported_type(tmp_path):
    """TesseractProvider raises OCRError for unsupported file extensions."""
    test_file = tmp_path / "test.unknown"
    test_file.write_text("hello")
    provider = TesseractProvider()
    with pytest.raises(OCRError, match="Unsupported file type"):
        await provider.extract_text(str(test_file), "unknown")


@pytest.mark.asyncio
async def test_tesseract_provider_docx_native_extraction(tmp_path):
    """TesseractProvider natively extracts paragraphs and tables from DOCX without Tesseract."""
    doc_path = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.add_paragraph("First Invoice Line")
    doc.add_paragraph("Second Invoice Line")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Item"
    table.rows[0].cells[1].text = "Price"
    doc.save(str(doc_path))

    provider = TesseractProvider()
    res = await provider.extract_text(str(doc_path), "docx")
    assert "First Invoice Line" in res.text
    assert "Second Invoice Line" in res.text
    assert "Item | Price" in res.text
    assert res.page_count == 1
    assert res.metadata["extracted_via"] == "native_docx"


# ---------------------------------------------------------------------------
# 4. OCR API Endpoint Tests
# ---------------------------------------------------------------------------

async def _upload_document(client: AsyncClient, filename: str = "invoice.pdf") -> str:
    """Helper to upload a document and return its ID."""
    response = await client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_trigger_ocr_success(async_client: AsyncClient, mock_ocr: MockOCRProvider):
    """POST /documents/{id}/ocr triggers OCR and transitions status to OCR_COMPLETED."""
    doc_id = await _upload_document(async_client)

    response = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == doc_id
    assert data["status"] == DocumentStatus.OCR_COMPLETED.value
    assert data["ocr_provider"] == "mock_ocr"
    assert "INVOICE #INV-2026-001" in data["text_preview"]
    assert data["page_count"] == 1
    assert data["processing_time_ms"] == 42
    assert "ocr_completed_at" in data
    assert mock_ocr.call_count == 1


@pytest.mark.asyncio
async def test_trigger_ocr_updates_document_fields_and_history(async_client: AsyncClient):
    """Verify document GET reflects updated status and processing history."""
    doc_id = await _upload_document(async_client)
    ocr_resp = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert ocr_resp.status_code == 200

    # Fetch document with history
    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()

    assert doc_data["status"] == DocumentStatus.OCR_COMPLETED.value
    assert doc_data["ocr_provider"] == "mock_ocr"
    assert doc_data["ocr_page_count"] == 1
    assert doc_data["ocr_processing_time_ms"] == 42
    assert doc_data["ocr_completed_at"] is not None

    # Check history stages: UPLOAD then OCR
    history = doc_data["processing_history"]
    stages = [h["stage"] for h in history]
    assert ProcessingStage.UPLOAD.value in stages
    assert ProcessingStage.OCR.value in stages

    ocr_hist = [h for h in history if h["stage"] == ProcessingStage.OCR.value][0]
    assert ocr_hist["status"] == StageStatus.COMPLETED.value
    assert "OCR completed successfully" in ocr_hist["message"]
    assert ocr_hist["completed_at"] is not None


@pytest.mark.asyncio
async def test_trigger_ocr_failure_flow(async_client: AsyncClient):
    """When OCR provider fails, document transitions to FAILED and returns 422."""
    doc_id = await _upload_document(async_client)

    # Override OCR provider with failing mock
    failing_ocr = MockOCRProvider(should_fail=True)
    fastapi_app.dependency_overrides[get_ocr_provider] = lambda: failing_ocr

    try:
        response = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
        assert response.status_code == 422
        assert "Simulated OCR failure" in response.json()["detail"]

        # Document status should be FAILED
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["status"] == DocumentStatus.FAILED.value
        assert "Simulated OCR failure" in (doc_data["error_message"] or "")

        # History should record stage=OCR as FAILED
        ocr_hist = [h for h in doc_data["processing_history"] if h["stage"] == ProcessingStage.OCR.value][0]
        assert ocr_hist["status"] == StageStatus.FAILED.value
        assert "Simulated OCR failure" in (ocr_hist["message"] or "")
    finally:
        fastapi_app.dependency_overrides.pop(get_ocr_provider, None)


@pytest.mark.asyncio
async def test_trigger_ocr_nonexistent_document(async_client: AsyncClient):
    """POST /documents/{id}/ocr for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.post(f"/api/v1/documents/{fake_id}/ocr")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 5. Extracted Text Retrieval Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_text_success(async_client: AsyncClient):
    """GET /documents/{id}/text returns full text once OCR is completed."""
    doc_id = await _upload_document(async_client)
    await async_client.post(f"/api/v1/documents/{doc_id}/ocr")

    response = await async_client.get(f"/api/v1/documents/{doc_id}/text")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["status"] == DocumentStatus.OCR_COMPLETED.value
    assert data["ocr_provider"] == "mock_ocr"
    assert "INVOICE #INV-2026-001" in data["text"]


@pytest.mark.asyncio
async def test_get_text_before_ocr_conflict_409(async_client: AsyncClient):
    """GET /documents/{id}/text before OCR returns 409 Conflict."""
    doc_id = await _upload_document(async_client)

    response = await async_client.get(f"/api/v1/documents/{doc_id}/text")
    assert response.status_code == 409
    assert "OCR must be completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_text_nonexistent_document_404(async_client: AsyncClient):
    """GET /documents/{id}/text for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/documents/{fake_id}/text")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. Reprocessing Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_reprocessing_updates_fields_and_appends_history(
    async_client: AsyncClient,
    mock_ocr: MockOCRProvider,
):
    """Triggering OCR a second time overwrites fields and appends another history record."""
    doc_id = await _upload_document(async_client)

    # First run
    resp1 = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert resp1.status_code == 200

    # Modify mock return text for rerun
    mock_ocr.text = "UPDATED INVOICE #INV-2026-999"
    mock_ocr.page_count = 5

    # Second run (reprocessing)
    resp2 = await async_client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["page_count"] == 5
    assert "UPDATED INVOICE" in data2["text_preview"]

    # Verify document in DB has updated text
    text_resp = await async_client.get(f"/api/v1/documents/{doc_id}/text")
    assert text_resp.status_code == 200
    assert "UPDATED INVOICE" in text_resp.json()["text"]

    # Verify history contains two OCR records
    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    history = doc_resp.json()["processing_history"]
    ocr_records = [h for h in history if h["stage"] == ProcessingStage.OCR.value]
    assert len(ocr_records) == 2
    assert ocr_records[0]["status"] == StageStatus.COMPLETED.value
    assert ocr_records[1]["status"] == StageStatus.COMPLETED.value
