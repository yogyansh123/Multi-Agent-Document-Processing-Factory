"""
services/storage/base.py
========================
Abstract base class for file storage providers.

All concrete providers (local filesystem, S3, GCS, Azure Blob) must
implement this interface.  The rest of the application only imports
`StorageProvider` — never a concrete class.

This ensures the storage backend can be swapped without touching any
business logic or API layer code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredFile:
    """
    Result returned after successfully saving a file.

    Attributes
    ----------
    stored_filename:
        The name under which the file was saved (may differ from the
        original filename to ensure uniqueness).
    file_path:
        Backend-relative path or object key.  For local storage this is
        relative to the storage root; for S3 it would be the object key.
        NEVER exposed directly to API clients.
    file_size:
        Exact size of the stored file in bytes.
    mime_type:
        MIME type as detected or inferred at save time.
    """

    stored_filename: str
    file_path: str
    file_size: int
    mime_type: str


class StorageProvider(ABC):
    """
    Abstract interface for file storage operations.

    Implementations must be safe against path-traversal attacks and must
    never raise bare exceptions — only StorageError or its subclasses.
    """

    @abstractmethod
    async def save(
        self,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
    ) -> StoredFile:
        """
        Persist the file and return metadata about how it was stored.

        Parameters
        ----------
        file_bytes:
            Raw bytes of the uploaded file.
        original_filename:
            The original name provided by the user (used to derive
            the file extension).
        mime_type:
            MIME type of the file.

        Returns
        -------
        StoredFile with the stored path, generated filename, and size.
        """

    @abstractmethod
    async def delete(self, file_path: str) -> None:
        """
        Remove a previously stored file.

        Parameters
        ----------
        file_path:
            The `file_path` value returned by a previous call to `save`.

        Raises
        ------
        FileNotFoundError if the file does not exist.
        StorageError for any other backend error.
        """

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Return True if the file at file_path exists."""
