"""
models/document_chunk.py
========================
SQLAlchemy model for document chunks and vector embeddings (pgvector).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.config import settings
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentChunk(Base):
    """
    Represents a segmented text chunk from a processed document,
    its dense vector embedding, and source positioning metadata.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique chunk identifier.",
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to the parent document.",
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Zero-based sequence index of the chunk within the document.",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Raw textual content of the chunk.",
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="1-based page number where this chunk originated, if available.",
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Approximate number of tokens in the chunk.",
    )

    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
        doc="Dense semantic vector embedding.",
    )

    # Column name is 'metadata' in DB, mapped to chunk_metadata attribute to avoid conflict with Base.metadata
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        doc="Arbitrary chunk metadata (filename, doc type, character range, etc.).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp when chunk was created.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp when chunk was last updated.",
    )

    # Relationship back to parent document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        Index("ix_document_chunks_doc_chunk", "document_id", "chunk_index", unique=True),
    )


    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id!s} "
            f"document_id={self.document_id!s} "
            f"chunk_index={self.chunk_index} "
            f"page={self.page_number}>"
        )
