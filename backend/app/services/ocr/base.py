"""
services/ocr/base.py
====================
Abstract OCR provider interface and OCRResult dataclass.

Every OCR backend (Tesseract, AWS Textract, Google Vision, …) must
implement ``OCRProvider``.  The rest of the application imports only
``OCRProvider`` and ``OCRResult`` — never a concrete class.

This makes swapping OCR engines a one-file change in the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRResult:
    """
    Typed result returned by every OCR provider.

    Attributes
    ----------
    text:
        Full extracted text, Unicode, normalised to LF line endings.
        May be empty string if the document contained no readable text.
    provider:
        Lowercase provider name, e.g. ``'tesseract'``, ``'aws_textract'``.
    page_count:
        Number of pages (or images) processed.
    processing_time_ms:
        Wall-clock time for the OCR call in milliseconds.
    metadata:
        Provider-specific supplementary data (confidence scores, bounding
        boxes, language detected, etc.).  Stored as JSON in the database.
        Must be JSON-serialisable.
    """

    text: str
    provider: str
    page_count: int
    processing_time_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


class OCRProvider(ABC):
    """
    Abstract interface all OCR backends must implement.

    Implementations must:
    - Be stateless (safe to call concurrently).
    - Never execute uploaded content.
    - Validate that the supplied path is inside the storage root before use.
    - Return an ``OCRResult`` on success.
    - Raise ``OCRError`` on failure.
    """

    @abstractmethod
    async def extract_text(
        self,
        file_path: str,
        file_type: str,
    ) -> OCRResult:
        """
        Extract text from the file at *file_path*.

        Parameters
        ----------
        file_path:
            Absolute path to the file on disk (resolved by the service layer
            before this call is made).
        file_type:
            Lowercase extension of the file (``'pdf'``, ``'png'``, …) so the
            provider can dispatch without re-inspecting the content.

        Returns
        -------
        OCRResult with the extracted text and processing metadata.

        Raises
        ------
        OCRError:
            Any OCR-level failure (missing binary, corrupt file, timeout, …).
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Machine-readable provider identifier (lowercase, no spaces)."""


class OCRError(Exception):
    """
    Raised when an OCR provider cannot extract text from a document.

    Wraps provider-specific errors so callers never need to handle
    pytesseract, boto3, or google.cloud exceptions directly.
    """

    def __init__(self, message: str, provider: str, cause: Exception | None = None) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(message)
