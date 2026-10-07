"""
models/__init__.py
==================
ORM model registry.

Import all models here so that SQLAlchemy's `Base.metadata` is aware of
every table when `create_all()` or Alembic's `autogenerate` runs.

Usage:
    # In db/init_db.py:
    from app.models import *  # noqa — ensures all models are registered
    await Base.metadata.create_all(engine)
"""

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.processing_history import ProcessingHistory
from app.models.review import DocumentReview

__all__ = ["Document", "ProcessingHistory", "DocumentReview", "DocumentChunk"]

