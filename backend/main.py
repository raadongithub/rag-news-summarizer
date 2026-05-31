"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import auth_router, health_router, sessions_router
from .core.config import get_settings
from .core.exceptions import ApiError
from .database import run_migrations
from .services import close_runtime, initialize_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup and clean up on shutdown."""

    run_migrations()
    app.state.startup_complete = False
    app.state.runtime = None

    try:
        app.state.runtime = await initialize_runtime(settings)
        if app.state.runtime.chunk_store is not None:
            logger.info("Milvus vector store initialized")
    except Exception as exc:  # pragma: no cover
        logger.error("Milvus initialization failed: %s", exc)

    app.state.startup_complete = True
    try:
        yield
    finally:
        await close_runtime(getattr(app.state, "runtime", None))


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """Return structured JSON responses for domain errors."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return structured JSON responses for request validation failures."""

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "error_code": "request_validation_failed",
            "errors": exc.errors(),
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(sessions_router)
