"""
services/ocr/factory.py
=======================
Factory for instantiating OCR providers.

Decouples caller from the concrete provider class.  Swapping OCR backends
in production requires only setting the OCR_PROVIDER environment variable.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.ocr.base import OCRProvider
from app.services.ocr.tesseract import TesseractProvider


@lru_cache(maxsize=4)
def get_ocr_provider(provider_name: str | None = None) -> OCRProvider:
    """
    Return a cached singleton OCRProvider instance for the given provider name.

    If *provider_name* is None, uses ``settings.OCR_PROVIDER``.
    """
    name = (provider_name or settings.OCR_PROVIDER).lower()

    if name == "tesseract":
        return TesseractProvider()
    elif name in {"aws_textract", "google_vision", "azure_form_recognizer", "unstructured"}:
        raise NotImplementedError(
            f"OCR provider '{name}' is planned for a future step and not yet implemented."
        )
    else:
        raise ValueError(f"Unknown OCR provider: '{name}'")
