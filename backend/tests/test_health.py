"""
tests/test_health.py
====================
Tests for the GET /health endpoint.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(async_client: AsyncClient) -> None:
    """Health endpoint must return HTTP 200."""
    response = await async_client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check_returns_healthy_status(async_client: AsyncClient) -> None:
    """Health endpoint must return {'status': 'healthy'}."""
    response = await async_client.get("/health")
    data = response.json()
    assert data == {"status": "healthy"}


@pytest.mark.asyncio
async def test_health_check_content_type_is_json(async_client: AsyncClient) -> None:
    """Health endpoint must return application/json."""
    response = await async_client.get("/health")
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_api_v1_health_check(async_client: AsyncClient) -> None:
    """Health endpoint is also accessible under /api/v1/health."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
