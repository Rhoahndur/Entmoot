"""
Main FastAPI application instance.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entmoot import __version__
from entmoot.api.error_handlers import register_error_handlers
from entmoot.api.middleware import (
    LoggingContextMiddleware,
    RequestCorrelationMiddleware,
)
from entmoot.api.projects import router as projects_router
from entmoot.api.upload import router as upload_router
from entmoot.core.cleanup import cleanup_service
from entmoot.core.config import settings
from entmoot.core.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown events:
    - Startup: Configure logging and start the cleanup service
    - Shutdown: Stop the cleanup service gracefully
    """
    # Startup
    # Configure logging
    log_file = None
    if settings.environment == "production":
        log_file = Path(settings.uploads_dir) / "logs" / "entmoot.log"

    setup_logging(
        log_level="DEBUG" if settings.environment == "development" else "INFO",
        log_file=log_file,
        json_logs=(settings.environment == "production"),
        enable_console=True,
    )
    logger.info(f"Starting Entmoot API v{__version__} in {settings.environment} mode")

    # Start cleanup service
    await cleanup_service.start()

    yield

    # Shutdown
    logger.info("Shutting down Entmoot API")
    await cleanup_service.stop()


app = FastAPI(
    title="Entmoot API",
    description="AI-driven site layout automation for real estate due diligence",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware (order matters - add in reverse order of execution)
app.add_middleware(LoggingContextMiddleware)
app.add_middleware(RequestCorrelationMiddleware)

# Register error handlers
register_error_handlers(app)

# Include routers
app.include_router(upload_router, prefix=settings.api_v1_prefix)
app.include_router(projects_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint returning API information.

    Returns:
        dict[str, str]: API information including name and version.
    """
    return {
        "name": "Entmoot API",
        "version": __version__,
        "description": "AI-driven site layout automation",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        dict[str, str]: Health status.
    """
    return {"status": "healthy"}
