"""
schemas/rag.py
==============
Pydantic schemas for RAG query, document indexing, and status endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RagQueryRequest(BaseModel):
    """Request payload for RAG semantic search and answer generation."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or search query.",
        examples=["What is the total invoice amount for Acme Corp in 2026?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of most relevant chunks to retrieve (1 to 20).",
    )
    document_type: str | None = Field(
        default=None,
        description="Optional filter by document type (e.g. INVOICE, CONTRACT, RECEIPT).",
    )
    document_id: uuid.UUID | None = Field(
        default=None,
        description="Optional filter restricting search to a specific document.",
    )


class RagSourceCitation(BaseModel):
    """Source provenance citation for a retrieved chunk."""
    model_config = ConfigDict(from_attributes=True)

    source_number: int = Field(..., description="1-based citation index e.g. [Source 1].")
    document_id: uuid.UUID = Field(..., description="ID of originating document.")
    filename: str = Field(..., description="Original filename of source document.")
    document_type: str | None = Field(default=None, description="Document classification type.")
    page_number: int | None = Field(default=None, description="Page number where content appears.")
    chunk_id: uuid.UUID = Field(..., description="ID of document chunk.")
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0).")
    excerpt: str = Field(..., description="Snippet of source content.")
    is_cited: bool = Field(default=True, description="Whether this source is directly cited in the answer.")


class RagQueryResponse(BaseModel):
    """Consolidated response containing answer, sources, and generation metadata."""
    model_config = ConfigDict(from_attributes=True)

    query: str
    answer: str
    sources: list[RagSourceCitation]
    retrieved_count: int
    generation_metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIndexResponse(BaseModel):
    """Response returned upon manually indexing a document."""
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    chunks_created: int
    status: str
    indexed_at: datetime


class DocumentIndexStatusResponse(BaseModel):
    """Response indicating vector indexing status for a document."""
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    indexed: bool
    chunk_count: int
    indexed_at: datetime | None = None
    embedding_model: str | None = None
