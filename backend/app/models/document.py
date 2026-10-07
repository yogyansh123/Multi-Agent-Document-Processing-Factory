"""
models/document.py
==================
SQLAlchemy ORM model for the Document entity.

A Document represents one uploaded file moving through the processing pipeline.
It holds file metadata, current status, and links to processing history.

This module ONLY defines the data structure.
Business logic lives in app/services/document.py.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DocumentStatus
from app.db.base import Base


class Document(Base):
    """
    Represents a single document uploaded by the user.

    The document moves through well-defined status transitions as it is
    processed by the multi-agent pipeline.  Every status change should be
    accompanied by a ProcessingHistory record.

    Relationships:
        processing_history: list of ProcessingHistory records (one per stage
            attempt).  Append-only; never deleted or updated.
    """

    __tablename__ = "documents"

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Globally unique document identifier.",
    )

    # -------------------------------------------------------------------------
    # File metadata
    # -------------------------------------------------------------------------
    original_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="The filename as provided by the uploader.",
    )

    stored_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="The filename used to store the file on the storage backend.",
    )

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Relative path to the stored file within the storage backend.",
    )

    file_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Lowercase file extension (e.g. 'pdf', 'png', 'jpg').",
    )

    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="MIME type detected at upload time (e.g. 'application/pdf').",
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="File size in bytes.",
    )

    # -------------------------------------------------------------------------
    # Classification result (filled by Classification Agent)
    # -------------------------------------------------------------------------
    document_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc=(
            "Detected document category. "
            "Null until classification completes. "
            "E.g. 'INVOICE', 'RECEIPT', 'PURCHASE_ORDER', 'CONTRACT', 'OTHER'."
        ),
    )

    classification_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Confidence score for classification (0.0 to 1.0).",
    )

    classification_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Concise explanation of why the document was classified this way.",
    )

    classification_signals: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Key textual or structural signals identified during classification.",
    )

    classified_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when classification was completed.",
    )

    # -------------------------------------------------------------------------
    # Extraction results (filled by Information Extraction Agent)
    # -------------------------------------------------------------------------
    extracted_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Structured extracted data validated against document-type-specific schema.",
    )

    extraction_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Version of the extraction prompt and schema applied.",
    )

    extracted_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when information extraction was completed.",
    )

    # -------------------------------------------------------------------------
    # Validation results (filled by Validation Agent)
    # -------------------------------------------------------------------------
    validation_result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Detailed validation result including issues, rules checked, and validity.",
    )

    validation_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Calculated validation score (0.0 to 1.0).",
    )

    validated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when validation was completed.",
    )

    # -------------------------------------------------------------------------
    # Confidence scoring results (filled by Confidence Scoring)
    # -------------------------------------------------------------------------
    overall_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Overall weighted confidence score (0.0 to 1.0).",
    )

    extraction_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Extraction completeness / confidence score (0.0 to 1.0).",
    )

    validation_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Validation confidence component (0.0 to 1.0).",
    )

    confidence_recommendation: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Decision recommendation: 'AUTO_APPROVE' or 'REVIEW_REQUIRED'.",
    )

    confidence_factors: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Transparent factor breakdown of confidence scoring components.",
    )

    confidence_calculated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when confidence scoring was calculated.",
    )

    # -------------------------------------------------------------------------
    # Processing status
    # -------------------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DocumentStatus.UPLOADED.value,
        doc="Current processing status. See DocumentStatus enum.",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable error message if status is FAILED.",
    )

    # -------------------------------------------------------------------------
    # OCR results (filled by OCR pipeline — all nullable until OCR completes)
    # -------------------------------------------------------------------------
    ocr_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Full extracted text from OCR or direct text extraction.",
    )

    ocr_provider: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="OCR provider name used (e.g. 'tesseract', 'aws_textract').",
    )

    ocr_page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of pages processed by OCR.",
    )

    ocr_processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Wall-clock time for OCR in milliseconds.",
    )

    ocr_completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when OCR last completed (successfully or failed).",
    )

    ocr_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Provider-specific OCR metadata stored as JSON (e.g. confidence scores per page).",
    )

    # -------------------------------------------------------------------------
    # RAG Vector Search & Indexing (Step 9)
    # -------------------------------------------------------------------------
    rag_indexed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether document text and embeddings have been indexed into vector database.",
    )

    rag_indexed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when document was last indexed into vector database.",
    )

    rag_chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of text chunks indexed for this document.",
    )

    rag_embedding_model: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Embedding model identifier used for generating chunk vectors.",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    processing_history: Mapped[list["ProcessingHistory"]] = relationship(  # type: ignore[name-defined]
        "ProcessingHistory",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ProcessingHistory.created_at",
        lazy="select",
    )

    reviews: Mapped[list["DocumentReview"]] = relationship(  # type: ignore[name-defined]
        "DocumentReview",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentReview.created_at.desc()",
        lazy="select",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(  # type: ignore[name-defined]
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
        lazy="select",
    )


    def __repr__(self) -> str:
        return (
            f"<Document id={self.id!s} "
            f"filename={self.original_filename!r} "
            f"status={self.status!r}>"
        )
