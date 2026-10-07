"""
models/review.py
================
SQLAlchemy ORM model for the DocumentReview entity.

Represents a human-in-the-loop review item for a document requiring human
inspection, decision (approval/rejection), or field correction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ReviewStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentReview(Base):
    """
    Tracks a human review session for a document.

    Maintains snapshots of the original AI extraction alongside reviewer
    modifications, decision rationale, and review state.
    """

    __tablename__ = "document_reviews"

    # -------------------------------------------------------------------------
    # Primary key & Foreign key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Globally unique review identifier.",
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the reviewed Document.",
    )

    # -------------------------------------------------------------------------
    # Status & Reviewer Identity
    # -------------------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ReviewStatus.PENDING.value,
        index=True,
        doc="Review status: PENDING, IN_REVIEW, COMPLETED.",
    )

    reviewer_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="Optional reviewer identifier (for future authentication).",
    )

    reviewer_name: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        doc="Optional human-readable reviewer name.",
    )

    decision: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Final decision: APPROVED, REJECTED, CORRECTED.",
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional rationale for approval, rejection, or corrections.",
    )

    # -------------------------------------------------------------------------
    # Audit Snapshots
    # -------------------------------------------------------------------------
    original_extracted_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Snapshot of AI-generated extracted data prior to human modifications.",
    )

    reviewed_extracted_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Human-corrected extracted data (if decision is CORRECTED).",
    )

    validation_result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Snapshot of validation issues and score when sent to review.",
    )

    confidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Snapshot of overall confidence and factor weights when sent to review.",
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the review decision was finalized.",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="reviews",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentReview id={self.id!s} "
            f"document_id={self.document_id!s} "
            f"status={self.status!r} "
            f"decision={self.decision!r}>"
        )
