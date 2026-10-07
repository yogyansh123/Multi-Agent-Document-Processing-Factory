"""
services/storage/local.py
==========================
Local filesystem storage provider.

Stores files in a configurable directory on the local filesystem.
Suitable for development and single-server deployments.

Security:
- Generates a UUID-based stored filename to prevent filename collisions
  and path-traversal attacks.
- Never uses the user-supplied filename as the stored filename.
- Resolves paths relative to the configured storage root; refuses to
  write outside the root.
- Creates the storage directory tree automatically if it does not exist.

To swap to a cloud provider, implement StorageProvider and update the
factory.  No other code needs to change.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.storage.base import StorageProvider, StoredFile

logger = get_logger(__name__)

# MIME type → extension mapping for safe extension derivation
_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def _safe_extension(original_filename: str, mime_type: str) -> str:
    """
    Return a safe, lowercase file extension.

    Priority:
    1. Extension derived from MIME type (most reliable).
    2. Extension from the original filename.
    3. Falls back to 'bin' if neither is available.
    """
    mime_ext = _MIME_TO_EXT.get(mime_type.lower())
    if mime_ext:
        return mime_ext

    suffix = Path(original_filename).suffix.lstrip(".").lower()
    return suffix if suffix else "bin"


class LocalStorageProvider(StorageProvider):
    """
    Stores files on the local filesystem under `settings.STORAGE_PATH`.

    Directory layout:
        <STORAGE_PATH>/
            <uuid>.<ext>   (flat structure for simplicity at this stage)

    The stored filename is always a UUID to guarantee uniqueness and to
    prevent any information from the original filename leaking into the path.
    """

    def __init__(self, storage_root: str | None = None) -> None:
        root = storage_root or settings.STORAGE_PATH
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """Absolute path to the storage root directory."""
        return self._root

    def _ensure_root(self) -> None:
        """Create the storage root directory if it does not exist."""
        self._root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, stored_filename: str) -> Path:
        """
        Resolve the stored filename relative to the storage root.

        Raises ValueError if the resolved path escapes the root
        (path-traversal protection).
        """
        target = (self._root / stored_filename).resolve()
        if not str(target).startswith(str(self._root)):
            raise ValueError(
                f"Path traversal detected: {stored_filename!r} resolves outside storage root."
            )
        return target

    async def save(
        self,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
    ) -> StoredFile:
        """
        Write file_bytes to disk and return a StoredFile descriptor.

        The stored filename is generated as `<uuid4>.<ext>` — the caller's
        original filename is preserved only in the database metadata, never
        in the path itself.
        """
        ext = _safe_extension(original_filename, mime_type)
        stored_filename = f"{uuid.uuid4().hex}.{ext}"

        self._ensure_root()
        target_path = self._safe_path(stored_filename)

        # Write using asyncio thread-pool so we don't block the event loop
        await asyncio.to_thread(target_path.write_bytes, file_bytes)

        # Relative path stored in DB (relative to storage root)
        relative_path = stored_filename

        logger.info(
            "storage.save.complete",
            stored_filename=stored_filename,
            original_filename=original_filename,
            size_bytes=len(file_bytes),
        )

        return StoredFile(
            stored_filename=stored_filename,
            file_path=relative_path,
            file_size=len(file_bytes),
            mime_type=mime_type,
        )

    async def delete(self, file_path: str) -> None:
        """Remove the file at the given relative path from the storage root."""
        target = self._safe_path(file_path)

        if not await asyncio.to_thread(target.exists):
            raise FileNotFoundError(
                f"File not found in storage: {file_path!r}"
            )

        await asyncio.to_thread(target.unlink)
        logger.info("storage.delete.complete", file_path=file_path)

    async def exists(self, file_path: str) -> bool:
        """Return True if the file at the given relative path exists."""
        try:
            target = self._safe_path(file_path)
        except ValueError:
            return False
        return await asyncio.to_thread(target.exists)
