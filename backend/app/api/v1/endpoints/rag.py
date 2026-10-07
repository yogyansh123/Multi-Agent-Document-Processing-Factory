"""
api/v1/endpoints/rag.py
=======================
Endpoints for RAG semantic search, document indexing, and index status.

Endpoints:
- POST /api/v1/rag/query: Query indexed documents using semantic similarity and grounded LLM.
- POST /api/v1/documents/{document_id}/index: Manually trigger vector indexing.
- GET  /api/v1/documents/{document_id}/index-status: Fetch vector indexing status.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.logging import get_logger
from app.schemas.rag import (
    DocumentIndexResponse,
    DocumentIndexStatusResponse,
    RagQueryRequest,
    RagQueryResponse,
    RagSourceCitation,
)
from app.services.rag.context import assemble_rag_context
from app.services.rag.generator import RagGeneratorService
from app.services.rag.ingestion import (
    DocumentNotEligibleForIndexingError,
    DocumentNotFoundError,
    RagIngestionService,
)
from app.services.rag.retrieval import RagRetrievalService

logger = get_logger("app.api.v1.endpoints.rag")

# Router for /rag
rag_router = APIRouter(prefix="/rag", tags=["RAG"])

# Router for /documents sub-routes
document_rag_router = APIRouter(prefix="/documents", tags=["RAG"])


# ---------------------------------------------------------------------------
# RAG Query
# ---------------------------------------------------------------------------


@rag_router.post(
    "/query",
    response_model=RagQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query indexed documents using RAG",
    description="Retrieve relevant chunks using semantic search and generate a grounded answer with source citations.",
)
async def query_rag(
    payload: RagQueryRequest,
    db: DbSession,
) -> RagQueryResponse:
    """Execute grounded RAG query across indexed documents."""
    try:
        retrieval_service = RagRetrievalService(db=db)
        generator = RagGeneratorService()

        # 1. Retrieve top_k semantically similar chunks
        chunks = await retrieval_service.retrieve(
            query=payload.query,
            top_k=payload.top_k,
            document_type=payload.document_type,
            document_id=payload.document_id,
        )

        # 2. Assemble context & source citations
        context, raw_citations = assemble_rag_context(chunks)

        # 3. Generate grounded response with citations
        result = await generator.generate_answer(
            query=payload.query,
            context=context,
            citations=raw_citations,
        )

        # 4. Format citations for response
        citations = [
            RagSourceCitation(
                source_number=c["source_number"],
                document_id=uuid.UUID(str(c["document_id"])),
                filename=c["filename"],
                document_type=c.get("document_type"),
                page_number=c.get("page_number"),
                chunk_id=uuid.UUID(str(c["chunk_id"])),
                similarity_score=round(float(c["similarity_score"]), 4),
                excerpt=c["excerpt"],
                is_cited=c.get("is_cited", True),
            )
            for c in result.sources
        ]

        return RagQueryResponse(
            query=result.query,
            answer=result.answer,
            sources=citations,
            retrieved_count=len(chunks),
            generation_metadata=result.generation_metadata,
        )
    except Exception as exc:
        logger.error(
            "rag_query_failed",
            query=payload.query,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query processing failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Manual Document Indexing
# ---------------------------------------------------------------------------


@document_rag_router.post(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Index document in vector database",
    description="Chunk and generate embeddings for a processed document to make it searchable in RAG.",
)
async def index_document(
    document_id: uuid.UUID,
    db: DbSession,
) -> DocumentIndexResponse:
    """Manually trigger vector indexing for an approved document."""
    service = RagIngestionService(db=db)
    try:
        result = await service.index_document(document_id=document_id)
        return DocumentIndexResponse(
            document_id=result.document_id,
            chunks_created=result.chunks_created,
            status=result.status,
            indexed_at=result.indexed_at,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentNotEligibleForIndexingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "document_indexing_failed",
            document_id=str(document_id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Document Index Status
# ---------------------------------------------------------------------------


@document_rag_router.get(
    "/{document_id}/index-status",
    response_model=DocumentIndexStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document vector indexing status",
    description="Check whether a document is indexed in the vector database and retrieve indexing metadata.",
)
async def get_document_index_status(
    document_id: uuid.UUID,
    db: DbSession,
) -> DocumentIndexStatusResponse:
    """Fetch vector indexing status for a document."""
    service = RagIngestionService(db=db)
    try:
        status_info = await service.get_index_status(document_id=document_id)
        return DocumentIndexStatusResponse(
            document_id=status_info["document_id"],
            indexed=status_info["indexed"],
            chunk_count=status_info["chunk_count"],
            indexed_at=status_info["indexed_at"],
            embedding_model=status_info["embedding_model"],
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "get_index_status_failed",
            document_id=str(document_id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch index status: {exc}",
        ) from exc
