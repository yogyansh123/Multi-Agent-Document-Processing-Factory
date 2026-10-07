"""
models/processing_history.py
=============================
SQLAlchemy ORM model for ProcessingHistory.

Every time a document transitions through a processing stage, one
ProcessingHistory record is appended.  Records are never updated or deleted
(except via cascade when the parent Document is deleted).

This model is the audit trail and observability backbone of the platform.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingHistory(Base):
    """
    Immutable record of a single processing stage attempt for a document.

    A document may have multiple ProcessingHistory rows for the same stage
    if retries occur.  The stage and status columns store string values from
    the ProcessingStage and StageStatus enums respectively.

    Relationships:
        document: the parent Document.
    """

    __tablename__ = "processing_history"

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for this history record.",
    )

    # -------------------------------------------------------------------------
    # Foreign key
    # -------------------------------------------------------------------------
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="References the document this history record belongs to.",
    )

    # -------------------------------------------------------------------------
    # Stage information
    # -------------------------------------------------------------------------
    stage: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Processing stage name. See ProcessingStage enum.",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Status of this stage attempt. See StageStatus enum.",
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable message about this stage (progress notes, etc.).",
    )

    error_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed error information if the stage failed (sanitised, no secrets).",
    )

    # -------------------------------------------------------------------------
    # Timing
    # -------------------------------------------------------------------------
    started_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this stage began execution.",
    )

    completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when this stage finished (success or failure).",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    document: Mapped["Document"] = relationship(  # type: ignore[name-defined]
        "Document",
        back_populates="processing_history",
    )

    def __repr__(self) -> str:
        return (
            f"<ProcessingHistory id={self.id!s} "
            f"document_id={self.document_id!s} "
            f"stage={self.stage!r} "
            f"status={self.status!r}>"
        )
