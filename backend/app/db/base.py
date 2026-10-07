"""
db/base.py
==========
SQLAlchemy declarative base for all ORM models.

All models must inherit from `Base`.  This module also exports `metadata`
for use in Alembic migrations.

Usage:
    from app.db.base import Base

    class Document(Base):
        __tablename__ = "documents"
        ...
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models.

    Provides common timestamp columns (created_at, updated_at) that every
    table should have for observability and audit purposes.
    """

    # Subclasses can define __tablename__ and columns normally.
    # The two timestamp columns below are inherited automatically.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="UTC timestamp of record creation.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="UTC timestamp of last record update.",
    )
