"""
tests/test_classification.py
============================
Comprehensive tests for Step 4: LangGraph Document Classification Agent.

Test coverage:
1. DocumentClassification schema validation (valid types, invalid types, confidence bounds).
2. LLM Provider abstraction & factory (OpenAI, unsupported, unknown).
3. OpenAILLMProvider error on missing API key.
4. Standalone LangGraph execution without database dependency.
5. Standalone LangGraph error short-circuit on empty text.
6. Trigger classification endpoint (POST /api/v1/documents/{id}/classify) success flow.
7. Document model persistence of classification fields.
8. ProcessingHistory record creation for stage=CLASSIFICATION.
9. Classification before OCR completion returns 409 Conflict.
10. Classification failure flow (LLM error -> status=FAILED, history recorded, 422 response).
11. Classification 404 for nonexistent document.
12. Get classification endpoint (GET /api/v1/documents/{id}/classification) success.
13. Get classification before classify returns 409 Conflict.
14. Get classification 404 for nonexistent document.
15. Reclassification flow (overwriting fields, appending fresh history record).
16. Health check passes without OPENAI_API_KEY.
"""

from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.agents.classification.graph import create_classification_graph
from app.agents.classification.schemas import DocumentClassification
from app.api.deps import get_llm_provider
from app.core.enums import DocumentStatus, DocumentType, ProcessingStage, StageStatus
from app.main import app as fastapi_app
from app.services.llm.base import LLMConfigurationError
from app.services.llm.factory import get_llm_provider as factory_get_llm_provider
from app.services.llm.ollama import OllamaLLMProvider
from app.services.llm.openai import OpenAILLMProvider
from tests.conftest import FakeLLMProvider

VALID_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
)


# ---------------------------------------------------------------------------
# 1. Schema Validation Tests
# ---------------------------------------------------------------------------

def test_document_classification_valid():
    """Valid document types and confidence are accepted."""
    for doc_type in [
        DocumentType.INVOICE,
        DocumentType.RECEIPT,
        DocumentType.PURCHASE_ORDER,
        DocumentType.CONTRACT,
        DocumentType.OTHER,
    ]:
        obj = DocumentClassification(
            document_type=doc_type,
            confidence=0.88,
            reasoning=f"Identified as {doc_type.value}",
            signals=["signal 1", "signal 2"],
        )
        assert obj.document_type == doc_type
        assert obj.confidence == 0.88


def test_document_classification_invalid_type():
    """Invalid document types are rejected."""
    with pytest.raises(ValidationError):
        DocumentClassification(
            document_type="INVALID_TYPE",  # type: ignore[arg-type]
            confidence=0.9,
            reasoning="Invalid type",
        )


def test_document_classification_confidence_bounds():
    """Confidence must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        DocumentClassification(
            document_type=DocumentType.INVOICE,
            confidence=1.5,
            reasoning="Too high",
        )

    with pytest.raises(ValidationError):
        DocumentClassification(
            document_type=DocumentType.INVOICE,
            confidence=-0.1,
            reasoning="Too low",
        )


# ---------------------------------------------------------------------------
# 2. LLM Provider Abstraction & Factory Tests
# ---------------------------------------------------------------------------

def test_llm_factory_returns_openai_provider():
    """Factory returns OpenAILLMProvider when requested."""
    provider = factory_get_llm_provider("openai")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.provider_name == "openai"


def test_llm_factory_returns_ollama_provider():
    """Factory returns OllamaLLMProvider when requested."""
    provider = factory_get_llm_provider("ollama")
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.provider_name == "ollama"


def test_llm_factory_unimplemented_providers():
    """Factory raises NotImplementedError for planned future providers."""
    for name in ["anthropic", "google", "azure_openai"]:
        with pytest.raises(NotImplementedError):
            factory_get_llm_provider(name)


def test_llm_factory_unknown_provider():
    """Factory raises ValueError for unknown provider names."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        factory_get_llm_provider("unsupported_provider")


@pytest.mark.asyncio
async def test_openai_provider_raises_when_missing_api_key():
    """OpenAILLMProvider raises LLMConfigurationError if API key is not configured."""
    provider = OpenAILLMProvider(api_key=None)
    provider._api_key = None  # Force empty
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY is not configured"):
        await provider.generate_structured("test", DocumentClassification)


# ---------------------------------------------------------------------------
# 3. Standalone LangGraph Execution Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_classification_graph_success():
    """Classification graph executes successfully in isolation with FakeLLMProvider."""
    fake_llm = FakeLLMProvider(
        default_type=DocumentType.CONTRACT,
        confidence=0.91,
        reasoning="Preamble, recital clauses and signatures found.",
        signals=["Whereas clause", "Agreement between parties", "Signatures"],
    )
    graph = create_classification_graph(llm_provider=fake_llm, db=None)

    initial_state = {
        "document_text": "THIS AGREEMENT is made between Party A and Party B. Whereas...",
    }

    result = await graph.ainvoke(initial_state)

    assert result.get("error") is None
    assert result["document_type"] == DocumentType.CONTRACT.value
    assert result["confidence"] == 0.91
    assert "Whereas clause" in (result["signals"] or [])
    assert fake_llm.call_count == 1


@pytest.mark.asyncio
async def test_standalone_classification_graph_empty_text_error():
    """Classification graph stops with an error if text is empty."""
    fake_llm = FakeLLMProvider()
    graph = create_classification_graph(llm_provider=fake_llm, db=None)

    initial_state = {"document_text": ""}
    result = await graph.ainvoke(initial_state)

    assert result.get("error") is not None
    assert fake_llm.call_count == 0


# ---------------------------------------------------------------------------
# 4. API Endpoint Integration Tests
# ---------------------------------------------------------------------------

async def _upload_and_ocr_document(client: AsyncClient, filename: str = "doc.pdf") -> str:
    """Helper to upload a document and complete OCR."""
    upload_resp = await client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    ocr_resp = await client.post(f"/api/v1/documents/{doc_id}/ocr")
    assert ocr_resp.status_code == 200
    return doc_id


@pytest.mark.asyncio
async def test_classify_document_success(async_client: AsyncClient, fake_llm: FakeLLMProvider):
    """POST /documents/{id}/classify executes agent, transitions to CLASSIFIED, returns schema."""
    doc_id = await _upload_and_ocr_document(async_client)

    response = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == doc_id
    assert data["document_type"] == DocumentType.INVOICE.value
    assert data["confidence"] == 0.95
    assert "invoice number" in data["reasoning"]
    assert "total amount" in data["signals"]
    assert data["status"] == DocumentStatus.CLASSIFIED.value
    assert data["classified_at"] is not None
    assert fake_llm.call_count == 1


@pytest.mark.asyncio
async def test_classify_document_persists_fields_and_history(async_client: AsyncClient):
    """Verify document GET reflects updated classification fields and processing history."""
    doc_id = await _upload_and_ocr_document(async_client)

    classify_resp = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert classify_resp.status_code == 200

    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()

    assert doc_data["status"] == DocumentStatus.CLASSIFIED.value
    assert doc_data["document_type"] == DocumentType.INVOICE.value

    # Verify history has UPLOAD -> OCR -> CLASSIFICATION
    history = doc_data["processing_history"]
    stages = [h["stage"] for h in history]
    assert ProcessingStage.UPLOAD.value in stages
    assert ProcessingStage.OCR.value in stages
    assert ProcessingStage.CLASSIFICATION.value in stages

    class_hist = [h for h in history if h["stage"] == ProcessingStage.CLASSIFICATION.value][0]
    assert class_hist["status"] == StageStatus.COMPLETED.value
    assert "Classified as INVOICE" in class_hist["message"]
    assert class_hist["completed_at"] is not None


@pytest.mark.asyncio
async def test_classify_document_before_ocr_returns_409(async_client: AsyncClient):
    """Attempting classification on an UPLOADED (non-OCR) document returns 409 Conflict."""
    upload_resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("raw.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    response = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert response.status_code == 409
    assert "OCR must be completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_classify_document_failure_flow(async_client: AsyncClient):
    """When LLM provider fails, document transitions to FAILED and API returns 422."""
    doc_id = await _upload_and_ocr_document(async_client)

    failing_llm = FakeLLMProvider(should_fail=True)
    fastapi_app.dependency_overrides[get_llm_provider] = lambda: failing_llm

    try:
        response = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
        assert response.status_code == 422
        assert "Simulated LLM generation error" in response.json()["detail"]

        # Check document status
        doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["status"] == DocumentStatus.FAILED.value
        assert "Simulated LLM generation error" in (doc_data["error_message"] or "")

        # Check history
        class_hist = [
            h for h in doc_data["processing_history"] if h["stage"] == ProcessingStage.CLASSIFICATION.value
        ][0]
        assert class_hist["status"] == StageStatus.FAILED.value
        assert "Simulated LLM generation error" in (class_hist["message"] or "")
    finally:
        fastapi_app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.asyncio
async def test_classify_nonexistent_document_returns_404(async_client: AsyncClient):
    """POST /documents/{id}/classify for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.post(f"/api/v1/documents/{fake_id}/classify")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_classification_success(async_client: AsyncClient):
    """GET /documents/{id}/classification returns classification after completion."""
    doc_id = await _upload_and_ocr_document(async_client)
    await async_client.post(f"/api/v1/documents/{doc_id}/classify")

    response = await async_client.get(f"/api/v1/documents/{doc_id}/classification")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["document_type"] == DocumentType.INVOICE.value
    assert data["status"] == DocumentStatus.CLASSIFIED.value
    assert data["confidence"] == 0.95


@pytest.mark.asyncio
async def test_get_classification_before_classify_returns_409(async_client: AsyncClient):
    """GET /documents/{id}/classification returns 409 Conflict if document not yet classified."""
    doc_id = await _upload_and_ocr_document(async_client)

    response = await async_client.get(f"/api/v1/documents/{doc_id}/classification")
    assert response.status_code == 409
    assert "has not been classified yet" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_classification_nonexistent_document_returns_404(async_client: AsyncClient):
    """GET /documents/{id}/classification for nonexistent document returns 404."""
    fake_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/documents/{fake_id}/classification")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reclassification_flow(async_client: AsyncClient, fake_llm: FakeLLMProvider):
    """Classifying a document a second time overwrites fields and appends new history."""
    doc_id = await _upload_and_ocr_document(async_client)

    # First classification
    resp1 = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert resp1.status_code == 200
    assert resp1.json()["document_type"] == DocumentType.INVOICE.value

    # Change mock LLM output for reclassification
    fake_llm.default_type = DocumentType.PURCHASE_ORDER
    fake_llm.confidence = 0.99
    fake_llm.reasoning = "PO number and shipping delivery terms confirmed."
    fake_llm.signals = ["PO #", "Shipping delivery", "Quantity ordered"]

    # Reclassify
    resp2 = await async_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["document_type"] == DocumentType.PURCHASE_ORDER.value
    assert data2["confidence"] == 0.99

    # Verify document in DB has updated fields
    doc_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    history = doc_resp.json()["processing_history"]
    class_records = [h for h in history if h["stage"] == ProcessingStage.CLASSIFICATION.value]
    assert len(class_records) == 2
    assert class_records[0]["status"] == StageStatus.COMPLETED.value
    assert class_records[1]["status"] == StageStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_health_check_passes_without_openai_key(async_client: AsyncClient):
    """The health check endpoint continues to return 200 regardless of OpenAI configuration."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
