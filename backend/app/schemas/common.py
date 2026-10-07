"""
schemas/common.py
=================
Shared Pydantic schema components used across multiple resources.

Includes:
- PaginatedResponse: generic paginated list wrapper
- ErrorDetail: structured error detail for 4xx/5xx responses
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response envelope.

    Used for any list endpoint that supports page/page_size pagination.

    Example JSON:
        {
            "items": [...],
            "page": 1,
            "page_size": 20,
            "total": 50,
            "total_pages": 3
        }
    """

    items: list[T] = Field(description="The page of results.")
    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, description="Number of items per page.")
    total: int = Field(ge=0, description="Total number of items across all pages.")
    total_pages: int = Field(ge=0, description="Total number of pages.")

    model_config = {"from_attributes": True}


class ErrorDetail(BaseModel):
    """Standard error response body."""

    detail: str = Field(description="Human-readable error message.")
    code: str | None = Field(default=None, description="Machine-readable error code.")
