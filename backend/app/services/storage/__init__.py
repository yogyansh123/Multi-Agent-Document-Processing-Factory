"""
services/storage/__init__.py
=============================
File storage provider abstraction.

Exports the abstract base class and factory function.

Usage:
    from app.services.storage import get_storage_provider
    storage = get_storage_provider()
    path = await storage.save(file_bytes, filename)
"""

from app.services.storage.base import StorageProvider, StoredFile
from app.services.storage.factory import get_storage_provider

__all__ = ["StorageProvider", "StoredFile", "get_storage_provider"]
