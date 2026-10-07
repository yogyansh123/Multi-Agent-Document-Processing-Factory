"""
main.py
=======
FastAPI application factory.

This module creates and configures the FastAPI application instance.
It is the entry point for uvicorn:

    uvicorn app.main:app --reload

Architecture notes:
- Business logic lives in services/, agents/, workflows/ — NOT here.
- Route handlers live in api/v1/endpoints/ — NOT here.
- This file wires together the configuration, routers, middleware, and
  application lifecycle (startup / shutdown) events.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

# ---------------------------------------------------------------------------
# Logging — configure before anything else so startup logs are captured
# ---------------------------------------------------------------------------
configure_logging(
    log_level=settings.LOG_LEVEL,
    json_logs=(settings.APP_ENV == "production"),
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.

    Startup:
    - Log configuration summary
    - (Future) verify database connection
    - (Future) initialise Redis connection pool
    - (Future) register Temporal worker

    Shutdown:
    - (Future) gracefully close database engine
    - (Future) close Redis connection pool
    """
    # ---- Startup -----------------------------------------------------------
    logger.info(
        "app.startup",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
    )

    # Initialise database tables if needed (safe idempotent create_all with checkfirst=True)
    try:
        from app.db.init_db import init_db
        await init_db()
    except Exception as exc:
        logger.warning(
            "db.init.failed",
            error=str(exc),
            message="Starting without database — document endpoints will fail.",
        )

    yield

    # ---- Shutdown ----------------------------------------------------------
    logger.info("app.shutdown", name=settings.APP_NAME)

    # Close the async engine connection pool
    from app.db.session import get_async_engine
    await get_async_engine().dispose()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns
    -------
    A fully configured FastAPI application.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered document intelligence platform. "
            "Processes invoices, receipts, purchase orders, contracts, "
            "and general business documents using a multi-agent pipeline."
        ),
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ---- CORS --------------------------------------------------------------
    cors_kwargs: dict[str, Any] = {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if getattr(settings, "CORS_ORIGIN_REGEX", None):
        cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX

    application.add_middleware(
        CORSMiddleware,
        **cors_kwargs,
    )

    # ---- Root health check (mounted at / level for load balancers) ---------
    application.include_router(health_router)

    # ---- API v1 routes -----------------------------------------------------
    application.include_router(api_router, prefix="/api/v1")

    return application


# Create the application instance used by uvicorn
app = create_application()
