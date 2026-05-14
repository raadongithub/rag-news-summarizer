"""Shared backend dependencies: embeddings, vector store, and retriever."""

import logging
from dataclasses import dataclass

from ..ai.embeddings import VoyageEmbeddingService
from ..ai.milvus_store import MilvusChunkStore
from ..ai.retriever import ContextRetriever
from ..core.config import AppConfig, get_settings

logger = logging.getLogger(__name__)


@dataclass
class BackendRuntime:
    """Holds shared resources created once at startup and reused per request."""

    embeddings: VoyageEmbeddingService | None = None
    chunk_store: MilvusChunkStore | None = None
    context_retriever: ContextRetriever | None = None


async def initialize_runtime(settings: AppConfig | None = None) -> BackendRuntime:
    """Connect to Milvus and build the shared runtime (called once on startup)."""
    resolved_settings = settings or get_settings()
    runtime = BackendRuntime()

    if not resolved_settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY is not set - summarization will fail.")
    if not resolved_settings.voyage_api_key:
        logger.warning("VOYAGE_API_KEY is not set - chat retrieval will fail.")
        return runtime

    embeddings = VoyageEmbeddingService(api_key=resolved_settings.voyage_api_key)
    chunk_store = MilvusChunkStore(embeddings=embeddings)
    await chunk_store.initialize()

    runtime.embeddings = embeddings
    runtime.chunk_store = chunk_store
    runtime.context_retriever = ContextRetriever(
        voyage_api_key=resolved_settings.voyage_api_key,
        anthropic_api_key=resolved_settings.anthropic_api_key,
        embeddings=embeddings,
        chunk_store=chunk_store,
    )
    return runtime


async def close_runtime(runtime: BackendRuntime | None) -> None:
    """Gracefully close the Milvus connection on shutdown."""
    if runtime is None or runtime.chunk_store is None:
        return
    await runtime.chunk_store.close()
