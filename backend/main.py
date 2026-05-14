"""FastAPI application entry point.

Startup/shutdown lifecycle is handled here. All routes live in backend/api/.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .services import close_runtime, initialize_runtime
from .database import init_db
from .api import health_router, sessions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup; clean up on shutdown."""
    init_db()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sessions_router)
