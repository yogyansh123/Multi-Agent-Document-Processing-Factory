"""
tests/test_e2e_integration.py
==============================
End-to-End Integration Validation Suite for STEP 13.

Verifies the complete document processing factory lifecycle:
1. Document Upload (multipart/form-data)
2. OCR Processing (text extraction & page tracking)
3. Document Classification (invoice recognition & signal detection)
4. Structured Information Extraction (schema adherence)
5. Business Rule Validation (arithmetic checks & issue reporting)
6. Confidence Scoring & Routing (AUTO_APPROVE vs REVIEW_REQUIRED)
7. Human-in-the-Loop Review (claim, correct, revalidate, approve)
8. RAG Ingestion & Vector Indexing (chunking, embeddings, pgvector storage)
9. Grounded RAG Query & Traceable Citations (with insufficiency fallback)
10. Operational Analytics Aggregation (summary KPIs, throughput, stage latency)
11. Safe Error Handling & Edge Cases
"""

import io
import uuid
import datetime
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.activities.document_activities import (
    classify_document_activity,
    extract_fields_activity,
    run_ocr_activity,
    score_confidence_activity,
    set_activity_providers,
    validate_document_activity,
)
from app.activities.schemas import DocumentActivityInput
from app.agents.classification.schemas import DocumentClassification
from app.agents.extraction.schemas import ContactInfo, InvoiceExtraction, InvoiceLineItem
from app.core.enums import DocumentStatus, DocumentType, ReviewDecision, ReviewStatus
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.review import DocumentReview
from app.services.rag.embeddings import FakeEmbeddingProvider
from app.services.storage.local import LocalStorageProvider
from tests.conftest import FakeLLMProvider, MockOCRProvider


INVOICE_TEXT = """
========================================
ACME SUPPLIES LTD. - TAX INVOICE
========================================
Invoice Number: INV-2026-999
Invoice Date: 2026-03-15
Due Date: 2026-04-15
Currency: USD

Vendor: Acme Supplies Ltd., 100 Industrial Way, Tech City
Customer: Global Document Corp, 500 Enterprise Ave, Metropolis

Line Items:
1. High-Performance Processing Unit - Qty: 2 @ $500.00 = $1,000.00
2. Cloud Storage License - Qty: 1 @ $250.00 = $250.00

Subtotal: $1,250.00
Tax (10%): $125.00
Total Amount Due: $1,375.00

Payment Terms: Net 30 Days.
Thank you for your business!
"""


class E2ELLMProvider(FakeLLMProvider):
    """Handles both classification and extraction schemas properly without collision."""

    def __init__(self, extraction_override: object = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.custom_extraction = extraction_override

    async def generate_structured(
        self,
        prompt: str,
        schema: type,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ):
        if schema == DocumentClassification:
            return DocumentClassification(
                document_type=self.default_type,
                confidence=self.confidence,
                reasoning=self.reasoning,
                signals=self.signals,
            )
        if self.custom_extraction is not None and issubclass(schema, (InvoiceExtraction, object)):
            return self.custom_extraction
        return await super().generate_structured(
            prompt, schema, system_prompt=system_prompt, temperature=temperature
        )


@pytest.mark.asyncio
async def test_complete_e2e_auto_approval_pipeline(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tmp_storage_dir: str,
):
    """
    Validates the happy path:
    Upload -> OCR -> Classification -> Extraction -> Validation -> Auto Approval -> RAG Index -> RAG Query -> Analytics
    """
    storage = LocalStorageProvider(storage_root=tmp_storage_dir)
    ocr_mock = MockOCRProvider(text=INVOICE_TEXT, page_count=1)

    invoice_data = InvoiceExtraction(
        invoice_number="INV-2026-999",
        invoice_date="2026-03-15",
        due_date="2026-04-15",
        vendor=ContactInfo(name="Acme Supplies Ltd."),
        customer=ContactInfo(name="Global Document Corp"),
        line_items=[
            InvoiceLineItem(description="High-Performance Processing Unit", quantity=2, unit_price=500.0, amount=1000.0),
            InvoiceLineItem(description="Cloud Storage License", quantity=1, unit_price=250.0, amount=250.0),
        ],
        subtotal=1250.0,
        tax=125.0,
        total=1375.0,
        currency="USD",
    )
    llm_mock = E2ELLMProvider(
        default_type=DocumentType.INVOICE,
        confidence=0.96,
        extraction_override=invoice_data,
    )
    set_activity_providers(storage=storage, ocr=ocr_mock, llm=llm_mock)

    # 1. Upload Document
    pdf_bytes = b"%PDF-1.4 sample invoice content"
    files = {"file": ("inv_2026_999.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_res = await async_client.post("/api/v1/documents", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Activity Pipeline: OCR
    act_input = DocumentActivityInput(document_id=doc_id)
    ocr_out = await run_ocr_activity(act_input)
    assert ocr_out.status == "COMPLETED"
    assert ocr_out.stage == "OCR"

    # 3. Activity Pipeline: Classification
    class_out = await classify_document_activity(act_input)
    assert class_out.status == "COMPLETED"
    assert class_out.data.get("document_type") == "INVOICE"

    # 4. Activity Pipeline: Extraction
    extract_out = await extract_fields_activity(act_input)
    assert extract_out.status == "COMPLETED"
    assert extract_out.data.get("document_type") == "INVOICE"

    # 5. Activity Pipeline: Validation
    val_out = await validate_document_activity(act_input)
    assert val_out.status == "COMPLETED"
    assert val_out.data.get("is_valid") is True

    # 6. Activity Pipeline: Confidence Scoring & Auto-Approval
    conf_out = await score_confidence_activity(act_input)
    assert conf_out.status == "COMPLETED"
    assert conf_out.data.get("recommendation") == "AUTO_APPROVE"
    assert conf_out.data.get("status") == "APPROVED"

    # Refresh document state
    doc_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_res.status_code == 200
    doc_json = doc_res.json()
    assert doc_json["status"] == "APPROVED"
    assert doc_json["overall_confidence"] >= 0.85
    assert doc_json["rag_indexed"] is True
    assert doc_json["extracted_data"]["invoice_number"] == "INV-2026-999"

    # 7. Verify RAG Indexing
    chunks_query = select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    chunks = (await db_session.execute(chunks_query)).scalars().all()
    assert len(chunks) >= 1
    assert chunks[0].embedding is not None

    # 8. Verify RAG Query (Grounded Answer)
    rag_query_res = await async_client.post(
        "/api/v1/rag/query",
        json={
            "query": "What is the total amount due for invoice INV-2026-999?",
            "top_k": 5,
        },
    )
    assert rag_query_res.status_code == 200
    rag_data = rag_query_res.json()
    assert rag_data["query"] == "What is the total amount due for invoice INV-2026-999?"
    assert len(rag_data["sources"]) > 0
    assert rag_data["sources"][0]["document_id"] == doc_id
    assert rag_data["sources"][0]["filename"] == "inv_2026_999.pdf"

    # 9. Verify RAG Insufficiency Response
    empty_rag_res = await async_client.post(
        "/api/v1/rag/query",
        json={
            "query": "What is the secret passphrase for Project Antigravity?",
            "document_type": "CONTRACT",  # Filters out the INVOICE document
        },
    )
    assert empty_rag_res.status_code == 200
    assert "I could not find sufficient evidence" in empty_rag_res.json()["answer"]

    # 10. Verify Analytics Telemetry
    summary_res = await async_client.get("/api/v1/analytics/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_documents"] >= 1
    assert summary["approved_documents"] >= 1
    assert summary["rag_indexed_documents"] >= 1

    stages_res = await async_client.get("/api/v1/analytics/stages")
    assert stages_res.status_code == 200
    stages = stages_res.json()["stages"]
    stage_names = [s["stage"] for s in stages]
    assert "OCR" in stage_names
    assert "CLASSIFICATION" in stage_names
    assert "EXTRACTION" in stage_names
    assert "VALIDATION" in stage_names
    assert "CONFIDENCE_SCORING" in stage_names


@pytest.mark.asyncio
async def test_complete_e2e_human_review_pipeline(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tmp_storage_dir: str,
):
    """
    Validates human-in-the-loop review path:
    Upload -> Pipeline with Arithmetic Error -> REVIEW_REQUIRED -> Review Queue -> Claim -> Correct -> Approve -> RAG Indexing
    """
    storage = LocalStorageProvider(storage_root=tmp_storage_dir)
    ocr_mock = MockOCRProvider(text="Sample PO text", page_count=1)

    # Extraction with deliberate arithmetic error to trigger REVIEW_REQUIRED
    invalid_invoice = InvoiceExtraction(
        invoice_number="INV-ERR-001",
        invoice_date="2026-03-01",
        vendor=ContactInfo(name="Mismatched Supplies"),
        subtotal=100.0,
        tax=0.0,
        total=500.0,  # subtotal(100) + tax(0) != total(500) -> validation failure
        currency="USD",
        line_items=[
            InvoiceLineItem(description="Item A", quantity=2, unit_price=50.0, amount=100.0)
        ],
    )
    llm_mock = E2ELLMProvider(
        default_type=DocumentType.INVOICE,
        confidence=0.70,
        extraction_override=invalid_invoice,
    )
    set_activity_providers(storage=storage, ocr=ocr_mock, llm=llm_mock)

    # 1. Upload
    pdf_bytes = b"%PDF-1.4 error invoice"
    files = {"file": ("inv_err_001.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_res = await async_client.post("/api/v1/documents", files=files)
    doc_id = upload_res.json()["id"]

    # 2. Run activities
    act_input = DocumentActivityInput(document_id=doc_id)
    await run_ocr_activity(act_input)
    await classify_document_activity(act_input)
    await extract_fields_activity(act_input)
    await validate_document_activity(act_input)
    conf_res = await score_confidence_activity(act_input)
    assert conf_res.data.get("recommendation") == "REVIEW_REQUIRED"

    # 3. Check Review Queue
    queue_res = await async_client.get("/api/v1/review/queue")
    assert queue_res.status_code == 200
    queue = queue_res.json()["items"]
    matching_review = next((r for r in queue if str(r["document_id"]) == doc_id), None)
    assert matching_review is not None
    review_id = matching_review["review_id"]
    assert matching_review["status"] == "PENDING"

    # 4. Claim / Start Review
    start_res = await async_client.post(
        f"/api/v1/review/{review_id}/start",
        json={"reviewer_name": "auditor_alice"},
    )
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_REVIEW"

    # 5. Submit Correction (fix arithmetic total to 100.0)
    corrected_data = invalid_invoice.model_dump(mode="json")
    corrected_data["total"] = 100.0
    corrected_data["total_amount"] = 100.0

    correct_res = await async_client.post(
        f"/api/v1/review/{review_id}/correct",
        json={
            "corrected_data": corrected_data,
            "reason": "Fixed invoice total arithmetic error",
            "reviewer_name": "auditor_alice",
        },
    )
    assert correct_res.status_code == 200
    correct_json = correct_res.json()
    assert correct_json["status"] == "COMPLETED"
    assert correct_json["decision"] == "CORRECTED"
    assert correct_json["document_status"] == "APPROVED"

    # 6. Verify Document Status is now APPROVED & RAG indexed
    doc_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_res.status_code == 200
    assert doc_res.json()["status"] == "APPROVED"
    assert doc_res.json()["rag_indexed"] is True

    # 7. Verify Review Metrics in Analytics
    rev_analytics = await async_client.get("/api/v1/analytics/reviews")
    assert rev_analytics.status_code == 200
    rev_data = rev_analytics.json()
    assert rev_data["completed_reviews"] >= 1
    assert rev_data["corrected_reviews"] >= 1


@pytest.mark.asyncio
async def test_e2e_error_handling_and_edge_cases(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Validates robust error handling across the entire stack:
    1. Querying nonexistent document returns 404
    2. Invalid date range on analytics returns 400
    3. Triggering review actions on invalid states returns 400/404
    4. RAG query with no relevant documents returns deterministic insufficiency message
    5. Starting workflow on nonexistent document returns 404
    """
    fake_id = str(uuid.uuid4())

    # 1. Nonexistent document lookup
    doc_res = await async_client.get(f"/api/v1/documents/{fake_id}")
    assert doc_res.status_code == 404
    assert "not found" in doc_res.json()["detail"].lower()

    # 2. Nonexistent workflow trigger
    wf_res = await async_client.post(f"/api/v1/documents/{fake_id}/process")
    assert wf_res.status_code == 404

    # 3. Invalid date range on analytics (start > end)
    analytics_res = await async_client.get(
        "/api/v1/analytics/summary?start_date=2026-12-31T00:00:00&end_date=2026-01-01T00:00:00"
    )
    assert analytics_res.status_code == 400
    assert "start_date cannot be after end_date" in analytics_res.json()["detail"]

    # 4. Review action on nonexistent review
    rev_action_res = await async_client.post(f"/api/v1/review/{fake_id}/start")
    assert rev_action_res.status_code == 404

    # 5. RAG query on empty vector database
    rag_empty_res = await async_client.post(
        "/api/v1/rag/query",
        json={"query": "What is the vendor tax identification number?"},
    )
    assert rag_empty_res.status_code == 200
    assert "I could not find sufficient evidence" in rag_empty_res.json()["answer"]


