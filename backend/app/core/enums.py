"""
core/enums.py
=============
Application-wide enum definitions.

All enums are defined here once and imported everywhere they are needed.
Never duplicate status/type constants in other modules.

Usage:
    from app.core.enums import DocumentStatus, ProcessingStage
"""

from __future__ import annotations

import enum


class DocumentStatus(str, enum.Enum):
    """
    Lifecycle states for a document moving through the processing pipeline.

    The value of each member is a string so it can be stored directly
    in PostgreSQL varchar/text columns and serialised in JSON responses
    without extra conversion.

    Transition diagram:
        UPLOADED → PROCESSING → OCR_COMPLETED → CLASSIFIED → EXTRACTED
               → VALIDATED → REVIEW_REQUIRED → APPROVED
        Any stage → FAILED
    """

    UPLOADED = "UPLOADED"
    """Document has been received and stored. Processing not yet started."""

    PROCESSING = "PROCESSING"
    """Temporal workflow has been initiated and is actively running."""

    OCR_COMPLETED = "OCR_COMPLETED"
    """OCR text extraction has finished successfully."""

    CLASSIFIED = "CLASSIFIED"
    """Document type has been determined by the classification agent."""

    EXTRACTED = "EXTRACTED"
    """Structured fields have been extracted by the extraction agent."""

    VALIDATED = "VALIDATED"
    """Business rules validation has been applied."""

    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    """Confidence score is below threshold; document awaits human review."""

    APPROVED = "APPROVED"
    """Document has been approved (automatically or by a human reviewer)."""

    REJECTED = "REJECTED"
    """Document has been rejected by a human reviewer."""

    FAILED = "FAILED"
    """Unrecoverable error occurred during processing."""


class ProcessingStage(str, enum.Enum):
    """
    Processing stage identifiers used in ProcessingHistory records.

    Each stage maps to one Temporal activity in the future workflow.
    Records are append-only — a new record is created per retry attempt.
    """

    UPLOAD = "UPLOAD"
    """Initial upload and storage of the raw file."""

    OCR = "OCR"
    """Optical character recognition / text extraction."""

    CLASSIFICATION = "CLASSIFICATION"
    """Document type classification (Invoice, Receipt, PO, Contract, General)."""

    EXTRACTION = "EXTRACTION"
    """Structured field extraction via LLM."""

    VALIDATION = "VALIDATION"
    """Business rule validation of extracted data."""

    CONFIDENCE_SCORING = "CONFIDENCE_SCORING"
    """Per-field and document-level confidence scoring."""

    REVIEW_ROUTING = "REVIEW_ROUTING"
    """Routing to human review queue or auto-approval."""

    APPROVAL = "APPROVAL"
    """Final approval action (automated or human)."""

    HUMAN_REVIEW = "HUMAN_REVIEW"
    """Human-in-the-loop review action (start, approve, reject, correct)."""


class StageStatus(str, enum.Enum):
    """Status of a single processing history record."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DocumentType(str, enum.Enum):
    """
    Supported document classifications recognized by the Classification Agent.
    """

    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    CONTRACT = "CONTRACT"
    OTHER = "OTHER"


class ValidationSeverity(str, enum.Enum):
    """Severity levels for validation issues."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ConfidenceRecommendation(str, enum.Enum):
    """Recommendation produced by confidence scoring."""

    AUTO_APPROVE = "AUTO_APPROVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReviewStatus(str, enum.Enum):
    """Lifecycle status of a human review item."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"


class ReviewDecision(str, enum.Enum):
    """Decision made by the human reviewer."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CORRECTED = "CORRECTED"


