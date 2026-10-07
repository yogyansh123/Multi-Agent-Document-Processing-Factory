"""
services/rag/retrieval.py
=========================
Semantic similarity retrieval service with hybrid metadata filtering.

Features:
- pgvector cosine distance similarity search on PostgreSQL
- Exact in-memory cosine similarity fallback for SQLite test environments
- Hybrid filtering by document_type and document_id
- Automatic exclusion of non-approved and rejected documents
- Normalized similarity scoring (0.0 to 1.0)
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.core.logging import get_logger
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.rag.embeddings import EmbeddingProvider, get_embedding_provider

logger = get_logger("app.services.rag.retrieval")


@dataclass
class RetrievedChunk:
    """Represents a matched chunk returned by semantic retrieval."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    document_type: str | None
    page_number: int | None
    chunk_index: int
    content: str
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def to_float_vector(emb: Any) -> list[float]:
    """Coerce various vector representations (list, tuple, ndarray, string) to list[float]."""
    if emb is None:
        return []
    if isinstance(emb, (list, tuple)):
        return [float(x) for x in emb]
    if hasattr(emb, "tolist"):
        return [float(x) for x in emb.tolist()]
    if isinstance(emb, str):
        cleaned = emb.strip("[]() \t\n")
        if not cleaned:
            return []
        try:
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
        except ValueError:
            return []
    return []


def calculate_cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    """Compute cosine similarity between two float vectors (0.0 to 1.0)."""
    a = to_float_vector(vec_a)
    b = to_float_vector(vec_b)
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    sim = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, round(sim, 4)))



class RagRetrievalService:
    """
    Executes semantic similarity search over document chunks with metadata filtering.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        document_type: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> list[RetrievedChunk]:
        """
        Execute semantic retrieval for a natural-language query.

        Args:
            query: The user query string
            top_k: Number of most relevant chunks to return (1..RAG_TOP_K_MAX)
            document_type: Optional filter (e.g. INVOICE, CONTRACT)
            document_id: Optional filter for a specific document
        """
        if not query or not query.strip():
            return []

        limit = min(
            settings.RAG_TOP_K_MAX,
            max(1, top_k if top_k is not None else settings.RAG_TOP_K_DEFAULT),
        )

        # 1. Generate query embedding
        query_embedding = await self.embedding_provider.embed_text(query.strip())

        # 2. Build base query with document join
        # Ensure only APPROVED documents are retrieved (rejected and unapproved are excluded)
        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == DocumentStatus.APPROVED.value)
            .options(selectinload(DocumentChunk.document))
        )

        # 3. Apply hybrid metadata filters
        if document_type:
            stmt = stmt.where(Document.document_type == document_type.strip().upper())

        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        bind = self.db.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        # 4. PostgreSQL path with pgvector cosine distance
        if dialect_name == "postgresql":
            try:
                # pgvector cosine distance operator <=>
                pg_stmt = stmt.order_by(
                    DocumentChunk.embedding.cosine_distance(query_embedding)
                ).limit(limit)
                result = await self.db.execute(pg_stmt)
                chunks = result.scalars().all()

                retrieved: list[RetrievedChunk] = []
                for chunk in chunks:
                    chunk_vec = list(chunk.embedding) if chunk.embedding is not None else []
                    sim = calculate_cosine_similarity(query_embedding, chunk_vec)
                    doc = chunk.document
                    retrieved.append(
                        RetrievedChunk(
                            chunk_id=chunk.id,
                            document_id=chunk.document_id,
                            filename=doc.original_filename if doc else "unknown",
                            document_type=doc.document_type if doc else None,
                            page_number=chunk.page_number,
                            chunk_index=chunk.chunk_index,
                            content=chunk.content,
                            similarity_score=sim,
                            metadata=chunk.chunk_metadata or {},
                        )
                    )
                return retrieved
            except Exception as exc:
                logger.warning("pgvector_query_fallback", error=str(exc))

        # 5. In-memory cosine similarity fallback (SQLite testing / dialect fallback)
        res = await self.db.execute(stmt)
        all_candidate_chunks = res.scalars().all()

        scored_chunks: list[tuple[float, DocumentChunk]] = []
        for chk in all_candidate_chunks:
            if chk.embedding is None:
                continue
            score = calculate_cosine_similarity(query_embedding, chk.embedding)
            scored_chunks.append((score, chk))

        # Sort descending by similarity score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored_chunks[:limit]

        results: list[RetrievedChunk] = []
        for score, chk in top_candidates:
            doc = chk.document
            results.append(
                RetrievedChunk(
                    chunk_id=chk.id,
                    document_id=chk.document_id,
                    filename=doc.original_filename if doc else "unknown",
                    document_type=doc.document_type if doc else None,
                    page_number=chk.page_number,
                    chunk_index=chk.chunk_index,
                    content=chk.content,
                    similarity_score=score,
                    metadata=chk.chunk_metadata or {},
                )
            )

        logger.info(
            "rag_retrieval_completed",
            query_length=len(query),
            returned_count=len(results),
            top_score=results[0].similarity_score if results else 0.0,
        )

        return results
