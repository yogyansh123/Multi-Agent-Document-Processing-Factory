"""
services/storage/factory.py
============================
Storage provider factory.

Returns the configured storage provider based on STORAGE_BACKEND setting.
Using a factory keeps concrete providers out of business-logic code.

Usage:
    from app.services.storage import get_storage_provider
    storage = get_storage_provider()
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageProvider


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    """
    Return the configured storage provider singleton.

    The provider is selected based on `settings.STORAGE_BACKEND`:
    - "local"      → LocalStorageProvider  (default)
    - "s3"         → (future) S3StorageProvider
    - "gcs"        → (future) GCSStorageProvider
    - "azure_blob" → (future) AzureBlobStorageProvider

    The result is cached via lru_cache so only one provider instance
    is created per process.
    """
    backend = settings.STORAGE_BACKEND

    if backend == "local":
        from app.services.storage.local import LocalStorageProvider
        return LocalStorageProvider()

    # Future backends — raise early rather than silently using a wrong provider
    raise NotImplementedError(
        f"Storage backend {backend!r} is not yet implemented. "
        "Supported backends: 'local'. "
        "Set STORAGE_BACKEND=local in your .env file."
    )
