"""
services/ocr
============
OCR abstraction layer for the Multi-Agent Document Processing Factory.

Public API:
- ``OCRProvider``: Abstract base class for all OCR engines.
- ``OCRResult``: Dataclass returned by extract_text().
- ``OCRError``: Base exception raised on OCR processing errors.
- ``TesseractProvider``: Tesseract + PyMuPDF implementation.
- ``get_ocr_provider``: Factory function to retrieve configured OCRProvider.
"""

from app.services.ocr.base import OCRError, OCRProvider, OCRResult
from app.services.ocr.factory import get_ocr_provider
from app.services.ocr.tesseract import TesseractProvider

__all__ = [
    "OCRError",
    "OCRProvider",
    "OCRResult",
    "TesseractProvider",
    "get_ocr_provider",
]
