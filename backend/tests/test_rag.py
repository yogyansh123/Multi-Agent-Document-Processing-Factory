"""
tests/test_rag.py
=================
Comprehensive test suite for STEP 9 — RAG + Vector Database Document Intelligence.

Tests cover:
1.  chunking deterministic
2.  chunk overlap
3.  page preservation
4.  empty and whitespace text handling
5.  fake embedding provider determinism
6.  embedding dimension validation
7.  document indexing
8.  indexing idempotency
9.  re-index replacement
10. vector retrieval query construction
11. top-k validation
12. document-type filtering
13. document id filtering
14. context assembly
15. context size limiting
16. grounded prompt construction
17. no-context behavior
18. RAG API query validation
19. RAG API retrieval success
20. source citation formatting
21. rejected document indexing prevention
22. approved document auto-indexing
23. review correction re-indexing
24. index-status endpoint
25. full RAG query pipeline end-to-end
26. manual index endpoint success
27. manual index endpoint not found
"""

import uuid
import datetime
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.enums import DocumentStatus, DocumentType, ReviewDecision, ReviewStatus
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.review import DocumentReview
from app.services.rag.chunking import (
    chunk_text,
    chunk_document_text,
    split_into_pages,
    estimate_token_count,
    TextChunk,
)
from app.services.rag.embeddings import (
    FakeEmbeddingProvider,
    get_embedding_provider,
)
from app.services.rag.ingestion import (
    RagIngestionService,
    DocumentNotEligibleForIndexingError,
    DocumentNotFoundError,
)
from app.services.rag.retrieval import RagRetrievalService, RetrievedChunk
from app.services.rag.context import assemble_rag_context
from app.services.rag.generator import RagGeneratorService, GeneratedRagAnswer
from app.services.confidence_service import ConfidenceService
from app.services.review_service import ReviewService


# ===========================================================================
# 1. Chunking Tests
# ===========================================================================


def test_chunking_deterministic():
    """Verify chunking splits text deterministically into expected chunk sizes."""
    sample_text = (
        "This is paragraph one of the agreement. It outlines the scope of software delivery.\n\n"
        "This is paragraph two. It specifies the financial obligations and payment terms of Net 30.\n\n"
        "This is paragraph three. It describes the intellectual property rights and confidentiality clauses."
    )
    chunks = chunk_text(sample_text, chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.content) > 0
        assert c.token_count is not None
        assert c.token_count > 0


def test_chunk_overlap():
    """Verify consecutive chunks preserve sliding window overlap."""
    words = [f"word{i}" for i in range(100)]
    long_text = " ".join(words)
    chunks = chunk_text(long_text, chunk_size=150, chunk_overlap=40)
    assert len(chunks) > 1

    # Check that adjacent chunks share overlapping words/substrings
    for i in range(len(chunks) - 1):
        tail = chunks[i].content[-30:]
        head = chunks[i + 1].content[:50]
        # At least some tokens in the tail of chunk i must appear in chunk i+1
        tail_words = set(tail.split())
        head_words = set(head.split())
        assert len(tail_words.intersection(head_words)) > 0


def test_page_preservation():
    """Verify multi-page markers preserve page numbers in metadata."""
    paginated_text = (
        "--- Page 1 ---\n"
        "Invoice Number: INV-2026-001\n"
        "Vendor: Acme Corporation\n\n"
        "--- Page 2 ---\n"
        "Line Items: 10 Widgets at $150.00 each.\n"
        "Total Amount Due: $1,500.00\n\n"
        "--- Page 3 ---\n"
        "Terms and Conditions: Payment due within 30 days of delivery."
    )
    pages = split_into_pages(paginated_text)
    assert len(pages) == 3
    assert pages[0][0] == 1
    assert "INV-2026-001" in pages[0][1]
    assert pages[1][0] == 2
    assert "Widgets" in pages[1][1]
    assert pages[2][0] == 3

    chunks = chunk_document_text(paginated_text)
    assert len(chunks) >= 3
    page_numbers = {c.page_number for c in chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert 3 in page_numbers


def test_empty_and_whitespace_text_handling():
    """Verify empty or pure whitespace texts result in empty chunk list."""
    assert chunk_text("") == []
    assert chunk_text("   \n\t  \r  ") == []
    assert chunk_document_text("") == []
    assert chunk_document_text("   \n\n   ") == []


# ===========================================================================
# 2. Embedding Provider Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_fake_embedding_provider_deterministic():
    """Verify FakeEmbeddingProvider produces deterministic, normalized unit vectors."""
    provider = FakeEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    vec1 = await provider.embed_text("Contract termination clause")
    vec2 = await provider.embed_text("Contract termination clause")
    vec3 = await provider.embed_text("Invoice total payment")

    assert len(vec1) == settings.EMBEDDING_DIMENSION
    assert vec1 == vec2  # Exactly deterministic
    assert vec1 != vec3  # Different text produces distinct vector


@pytest.mark.asyncio
async def test_embedding_dimension_validation():
    """Verify embedding vectors conform strictly to settings.EMBEDDING_DIMENSION."""
    provider = FakeEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    batch = await provider.embed_documents([
        "Invoice INV-100",
        "Purchase Order PO-200",
        "Master Services Agreement",
    ])
    assert len(batch) == 3
    for v in batch:
        assert len(v) == settings.EMBEDDING_DIMENSION
        # Check unit norm: sqrt(sum(v_i^2)) ~= 1.0
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 1e-4


# ===========================================================================
# 3. Ingestion & Indexing Service Tests
# ===========================================================================


@pytest_asyncio.fixture
async def approved_invoice_doc(db_session: AsyncSession) -> Document:
    """Fixture providing an APPROVED document ready for vector indexing."""
    doc = Document(
        id=uuid.uuid4(),
        original_filename="invoice_acme.pdf",
        stored_filename="stored_invoice.pdf",
        file_path="/tmp/fake_invoice.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=1024,
        document_type=DocumentType.INVOICE.value,
        status=DocumentStatus.APPROVED.value,
        ocr_text=(
            "--- Page 1 ---\n"
            "ACME CORP INVOICE\n"
            "Invoice Number: INV-2026-999\n"
            "Total Amount: $4,500.00\n"
            "Due Date: 2026-03-31\n\n"
            "--- Page 2 ---\n"
            "Line Item 1: Cloud Architecture Consulting - $3,000.00\n"
            "Line Item 2: Security Assessment - $1,500.00\n"
            "Payment Terms: Net 30"
        ),
        ocr_page_count=2,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_document_indexing(db_session: AsyncSession, approved_invoice_doc: Document):
    """Verify RagIngestionService indexes an approved document and persists chunks."""
    service = RagIngestionService(db=db_session)
    result = await service.index_document(approved_invoice_doc.id)

    assert result.document_id == approved_invoice_doc.id
    assert result.chunks_created >= 2
    assert result.status == "INDEXED"

    # Verify chunks in database
    stmt = select(DocumentChunk).where(DocumentChunk.document_id == approved_invoice_doc.id)
    chunks_res = await db_session.execute(stmt)
    chunks = chunks_res.scalars().all()
    assert len(chunks) == result.chunks_created
    for chk in chunks:
        assert chk.embedding is not None
        assert len(chk.embedding) == settings.EMBEDDING_DIMENSION
        assert chk.page_number in (1, 2)


@pytest.mark.asyncio
async def test_indexing_idempotency(db_session: AsyncSession, approved_invoice_doc: Document):
    """Verify indexing an already-indexed document does not duplicate chunks."""
    service = RagIngestionService(db=db_session)
    res1 = await service.index_document(approved_invoice_doc.id)
    res2 = await service.index_document(approved_invoice_doc.id)

    assert res1.chunks_created == res2.chunks_created

    count_stmt = select(func.count(DocumentChunk.id)).where(
        DocumentChunk.document_id == approved_invoice_doc.id
    )
    count_res = await db_session.execute(count_stmt)
    assert count_res.scalar() == res1.chunks_created


@pytest.mark.asyncio
async def test_reindex_replacement(db_session: AsyncSession, approved_invoice_doc: Document):
    """Verify re-indexing with modified OCR text replaces previous chunks cleanly."""
    service = RagIngestionService(db=db_session)
    await service.index_document(approved_invoice_doc.id)

    # Update OCR text
    approved_invoice_doc.ocr_text = "Updated single line OCR text for Acme."
    await db_session.commit()

    res = await service.index_document(approved_invoice_doc.id)
    assert res.chunks_created == 1

    chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == approved_invoice_doc.id)
    chunks = (await db_session.execute(chunks_stmt)).scalars().all()
    assert len(chunks) == 1
    assert "Updated single line" in chunks[0].content


@pytest.mark.asyncio
async def test_rejected_document_indexing_prevention(db_session: AsyncSession):
    """Verify indexing a REJECTED document is blocked."""
    doc = Document(
        id=uuid.uuid4(),
        original_filename="rejected_doc.pdf",
        stored_filename="stored_rej.pdf",
        file_path="/tmp/fake_rej.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        status=DocumentStatus.REJECTED.value,
        ocr_text="Some text here",
    )
    db_session.add(doc)
    await db_session.commit()

    service = RagIngestionService(db=db_session)
    with pytest.raises(DocumentNotEligibleForIndexingError):
        await service.index_document(doc.id)


# ===========================================================================
# 4. Retrieval & Filtering Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_vector_retrieval_query_construction(
    db_session: AsyncSession, approved_invoice_doc: Document
):
    """Verify semantic retrieval retrieves and orders chunks by similarity."""
    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(approved_invoice_doc.id)

    retrieval = RagRetrievalService(db=db_session)
    results = await retrieval.retrieve(query="What is the total amount?", top_k=3)

    assert len(results) > 0
    assert isinstance(results[0], RetrievedChunk)
    assert results[0].document_id == approved_invoice_doc.id
    assert results[0].similarity_score > 0.0
    # Top chunk should mention Total Amount or financial lines
    assert any("Total Amount" in r.content or "Consulting" in r.content for r in results)


@pytest.mark.asyncio
async def test_top_k_limiting(db_session: AsyncSession, approved_invoice_doc: Document):
    """Verify top_k bounds retrieval count."""
    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(approved_invoice_doc.id)

    retrieval = RagRetrievalService(db=db_session)
    results_1 = await retrieval.retrieve(query="Acme consulting invoice", top_k=1)
    assert len(results_1) == 1


@pytest.mark.asyncio
async def test_retrieval_document_type_filtering(db_session: AsyncSession):
    """Verify hybrid filtering by document_type excludes other document types."""
    # 1. Create Invoice
    doc_inv = Document(
        id=uuid.uuid4(),
        original_filename="invoice_alpha.pdf",
        stored_filename="alpha.pdf",
        file_path="/tmp/alpha.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.INVOICE.value,
        status=DocumentStatus.APPROVED.value,
        ocr_text="Invoice Alpha: Total $1000",
    )
    # 2. Create Contract
    doc_cnt = Document(
        id=uuid.uuid4(),
        original_filename="contract_beta.pdf",
        stored_filename="beta.pdf",
        file_path="/tmp/beta.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.CONTRACT.value,
        status=DocumentStatus.APPROVED.value,
        ocr_text="Contract Beta: Master Agreement 2026",
    )
    db_session.add_all([doc_inv, doc_cnt])
    await db_session.commit()

    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(doc_inv.id)
    await ingestion.index_document(doc_cnt.id)

    retrieval = RagRetrievalService(db=db_session)
    # Search for contracts only
    results = await retrieval.retrieve(query="Agreement", top_k=5, document_type="CONTRACT")
    assert len(results) > 0
    for r in results:
        assert r.document_type == "CONTRACT"
        assert r.document_id == doc_cnt.id


@pytest.mark.asyncio
async def test_retrieval_document_id_filtering(db_session: AsyncSession):
    """Verify hybrid filtering by document_id restricts search strictly to that document."""
    doc1 = Document(
        id=uuid.uuid4(),
        original_filename="doc1.pdf",
        stored_filename="doc1.pdf",
        file_path="/tmp/doc1.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.OTHER.value,
        status=DocumentStatus.APPROVED.value,
        ocr_text="Specific secret alpha details",
    )
    doc2 = Document(
        id=uuid.uuid4(),
        original_filename="doc2.pdf",
        stored_filename="doc2.pdf",
        file_path="/tmp/doc2.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.OTHER.value,
        status=DocumentStatus.APPROVED.value,
        ocr_text="Specific secret beta details",
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(doc1.id)
    await ingestion.index_document(doc2.id)

    retrieval = RagRetrievalService(db=db_session)
    results = await retrieval.retrieve(query="secret", top_k=5, document_id=doc1.id)
    assert len(results) == 1
    assert results[0].document_id == doc1.id


# ===========================================================================
# 5. Context Assembly & Grounded Generation Tests
# ===========================================================================


def test_context_assembly():
    """Verify assemble_rag_context formats chunks with [Source N] markers."""
    chunk1 = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        content="First paragraph describing terms.",
        page_number=1,
        similarity_score=0.92,
        filename="contract.pdf",
        document_type="CONTRACT",
    )
    chunk2 = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=1,
        content="Second paragraph describing payments.",
        page_number=2,
        similarity_score=0.85,
        filename="contract.pdf",
        document_type="CONTRACT",
    )
    context_text, citations = assemble_rag_context([chunk1, chunk2])

    assert "[Source 1]" in context_text
    assert "Document: contract.pdf" in context_text
    assert "Page: 1" in context_text
    assert "[Source 2]" in context_text
    assert len(citations) == 2
    assert citations[0]["source_number"] == 1
    assert citations[1]["source_number"] == 2


def test_context_size_limiting():
    """Verify context assembly respects maximum character limits."""
    chunks = [
        RetrievedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=i,
            content="A" * 500,
            page_number=i,
            similarity_score=0.9,
            filename=f"doc_{i}.pdf",
            document_type="OTHER",
        )
        for i in range(10)
    ]
    max_chars = 1200
    context_text, citations = assemble_rag_context(chunks, max_chars=max_chars)
    assert len(context_text) <= max_chars + 100
    assert len(citations) < 10


@pytest.mark.asyncio
async def test_no_context_behavior(fake_llm):
    """Verify generator returns insufficiency notice when context is empty."""
    generator = RagGeneratorService(llm_provider=fake_llm)
    res = await generator.generate_answer(
        query="What is the total?",
        context="",
        citations=[],
    )
    assert "could not find sufficient evidence" in res.answer.lower()
    assert res.generation_metadata["has_sufficient_evidence"] is False
    assert len(res.sources) == 0


@pytest.mark.asyncio
async def test_grounded_generation_with_citations(fake_llm):
    """Verify generator returns answer citing sources."""
    generator = RagGeneratorService(llm_provider=fake_llm)
    context = "[Source 1]\nDocument: inv.pdf\nPage: 1\nContent:\nTotal amount is $1,650.00"
    citations = [{
        "source_number": 1,
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "filename": "inv.pdf",
        "document_type": "INVOICE",
        "page_number": 1,
        "similarity_score": 0.95,
        "excerpt": "Total amount is $1,650.00",
    }]
    res = await generator.generate_answer(
        query="What is the invoice amount?",
        context=context,
        citations=citations,
    )
    assert len(res.answer) > 0
    assert res.generation_metadata["has_sufficient_evidence"] is True
    assert len(res.sources) == 1
    assert res.sources[0]["is_cited"] is True


# ===========================================================================
# 6. HTTP API Endpoints Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_rag_api_query_validation(async_client: AsyncClient):
    """Verify POST /api/v1/rag/query validates inputs properly."""
    # Empty query
    res = await async_client.post("/api/v1/rag/query", json={"query": "", "top_k": 5})
    assert res.status_code == 422

    # Invalid top_k (< 1)
    res = await async_client.post("/api/v1/rag/query", json={"query": "test", "top_k": 0})
    assert res.status_code == 422

    # Invalid top_k (> 20)
    res = await async_client.post("/api/v1/rag/query", json={"query": "test", "top_k": 50})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_rag_api_retrieval_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
    approved_invoice_doc: Document,
):
    """Verify POST /api/v1/rag/query retrieves and answers correctly."""
    # Index the document
    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(approved_invoice_doc.id)

    res = await async_client.post(
        "/api/v1/rag/query",
        json={
            "query": "What are the line items on Acme invoice?",
            "top_k": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "What are the line items on Acme invoice?"
    assert "answer" in data
    assert len(data["sources"]) > 0
    assert data["retrieved_count"] > 0
    first_src = data["sources"][0]
    assert first_src["filename"] == "invoice_acme.pdf"
    assert "similarity_score" in first_src
    assert "excerpt" in first_src


@pytest.mark.asyncio
async def test_manual_index_endpoint_success(
    async_client: AsyncClient,
    approved_invoice_doc: Document,
):
    """Verify POST /api/v1/documents/{document_id}/index successfully indexes document."""
    res = await async_client.post(f"/api/v1/documents/{approved_invoice_doc.id}/index")
    assert res.status_code == 200
    data = res.json()
    assert data["document_id"] == str(approved_invoice_doc.id)
    assert data["status"] == "INDEXED"
    assert data["chunks_created"] >= 2


@pytest.mark.asyncio
async def test_manual_index_endpoint_not_found(async_client: AsyncClient):
    """Verify POST /api/v1/documents/{non_existent_id}/index returns 404."""
    random_id = uuid.uuid4()
    res = await async_client.post(f"/api/v1/documents/{random_id}/index")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_manual_index_endpoint_rejected_blocked(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify POST /api/v1/documents/{id}/index returns 400 for rejected document."""
    doc = Document(
        id=uuid.uuid4(),
        original_filename="rejected.pdf",
        stored_filename="rej.pdf",
        file_path="/tmp/rej.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=200,
        status=DocumentStatus.REJECTED.value,
        ocr_text="Some text",
    )
    db_session.add(doc)
    await db_session.commit()

    res = await async_client.post(f"/api/v1/documents/{doc.id}/index")
    assert res.status_code == 400
    assert "rejected" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_document_index_status_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
    approved_invoice_doc: Document,
):
    """Verify GET /api/v1/documents/{document_id}/index-status returns accurate status."""
    # Before indexing
    res = await async_client.get(f"/api/v1/documents/{approved_invoice_doc.id}/index-status")
    assert res.status_code == 200
    data = res.json()
    assert data["indexed"] is False
    assert data["chunk_count"] == 0

    # Index document
    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(approved_invoice_doc.id)

    # After indexing
    res2 = await async_client.get(f"/api/v1/documents/{approved_invoice_doc.id}/index-status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["indexed"] is True
    assert data2["chunk_count"] >= 2
    assert data2["indexed_at"] is not None
    assert data2["embedding_model"] is not None


# ===========================================================================
# 7. Workflow & Review Integration Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_review_approval_auto_indexes(db_session: AsyncSession):
    """Verify human review approval automatically indexes the document."""
    doc = Document(
        id=uuid.uuid4(),
        original_filename="needs_review.pdf",
        stored_filename="nr.pdf",
        file_path="/tmp/nr.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.INVOICE.value,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        confidence_recommendation="REVIEW_REQUIRED",
        ocr_text="Invoice 555 for Acme Corp Total $550",
    )
    db_session.add(doc)
    await db_session.commit()

    review_service = ReviewService(db=db_session)
    review = await review_service.create_review(doc.id)

    # Approve review
    await review_service.approve_review(
        review_id=review.id,
        reason="Looks correct",
        reviewer_name="Auditor Bob",
    )

    # Verify document is marked indexed
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value
    assert doc.rag_indexed is True
    assert doc.rag_chunk_count is not None
    assert doc.rag_chunk_count >= 1


@pytest.mark.asyncio
async def test_review_correction_reindexes(db_session: AsyncSession):
    """Verify review correction with valid data approves and indexes document."""
    doc = Document(
        id=uuid.uuid4(),
        original_filename="correct_me.pdf",
        stored_filename="cm.pdf",
        file_path="/tmp/cm.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size=500,
        document_type=DocumentType.INVOICE.value,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        confidence_recommendation="REVIEW_REQUIRED",
        ocr_text="Invoice INV-CORRECT Total $1000",
    )
    db_session.add(doc)
    await db_session.commit()

    review_service = ReviewService(db=db_session)
    review = await review_service.create_review(doc.id)

    # Apply correction
    corrected_data = {
        "invoice_number": "INV-CORRECT-1",
        "vendor": {"name": "Acme Inc", "address": "123 Main St"},
        "invoice_date": "2026-01-01",
        "due_date": "2026-02-01",
        "currency": "USD",
        "subtotal": 1000.0,
        "tax": 100.0,
        "tax_amount": 100.0,
        "total": 1100.0,
        "total_amount": 1100.0,
        "payment_terms": "Net 30",
        "line_items": [
            {"description": "Item 1", "quantity": 1, "unit_price": 1000.0, "amount": 1000.0, "total_amount": 1000.0}
        ],
    }
    await review_service.correct_review(
        review_id=review.id,
        corrected_data=corrected_data,
        reason="Fixed amounts",
        reviewer_name="Auditor Alice",
    )

    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.APPROVED.value
    assert doc.rag_indexed is True
    assert doc.rag_chunk_count is not None
    assert doc.rag_chunk_count >= 1


@pytest.mark.asyncio
async def test_review_rejection_removes_from_rag(
    db_session: AsyncSession, approved_invoice_doc: Document
):
    """Verify rejecting a previously approved review purges its vector chunks."""
    # First index it
    ingestion = RagIngestionService(db=db_session)
    await ingestion.index_document(approved_invoice_doc.id)

    # Now create and reject review
    review = DocumentReview(
        id=uuid.uuid4(),
        document_id=approved_invoice_doc.id,
        status=ReviewStatus.PENDING.value,
    )
    db_session.add(review)
    await db_session.commit()

    review_service = ReviewService(db=db_session)
    await review_service.reject_review(
        review_id=review.id,
        reason="Fraudulent invoice",
        reviewer_name="Security Analyst",
    )

    await db_session.refresh(approved_invoice_doc)
    assert approved_invoice_doc.status == DocumentStatus.REJECTED.value
    assert approved_invoice_doc.rag_indexed is False
    assert approved_invoice_doc.rag_chunk_count == 0

    # Ensure no chunks remain
    chunks_stmt = select(func.count(DocumentChunk.id)).where(
        DocumentChunk.document_id == approved_invoice_doc.id
    )
    cnt = (await db_session.execute(chunks_stmt)).scalar()
    assert cnt == 0
