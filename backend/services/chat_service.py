"""Chat service: builds the RAG pipeline and runs Q&A with self-critique."""

from typing import Any

from ..ai.embeddings import VoyageEmbeddingService
from ..ai.milvus_store import MilvusChunkStore
from ..ai.rag_pipeline import RagPipeline, RagPipelineResult
from ..ai.retriever import ContextRetriever
from ..ai.summary import Critique, SelfCritique
from ..core.config import AppConfig, get_settings


class ChatService:
    """Coordinate retrieval, grounded answer generation, and self-critique."""

    def __init__(self, settings: AppConfig | None = None) -> None:
        self.settings = settings or get_settings()

    def create_context_retriever(
        self,
        *,
        chunk_store: MilvusChunkStore | None = None,
        embeddings: VoyageEmbeddingService | None = None,
    ) -> ContextRetriever:
        """Build a ContextRetriever wired to the shared chunk store."""
        if not self.settings.voyage_api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY is not configured - chat retrieval is unavailable"
            )
        return ContextRetriever(
            voyage_api_key=self.settings.voyage_api_key,
            anthropic_api_key=self.settings.anthropic_api_key,
            chunk_store=chunk_store,
            embeddings=embeddings,
        )

    def create_pipeline(
        self,
        *,
        chunk_store: MilvusChunkStore | None = None,
        embeddings: VoyageEmbeddingService | None = None,
    ) -> RagPipeline:
        """Build a RagPipeline wired to the shared chunk store."""
        if not self.settings.voyage_api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY is not configured - chat is unavailable"
            )
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured - chat is unavailable"
            )
        return RagPipeline(
            voyage_api_key=self.settings.voyage_api_key,
            anthropic_api_key=self.settings.anthropic_api_key,
            chunk_store=chunk_store,
            embeddings=embeddings,
        )

    async def answer_question(
        self,
        article: dict[str, Any],
        query: str,
        *,
        chunk_store: MilvusChunkStore | None = None,
        embeddings: VoyageEmbeddingService | None = None,
        k: int | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> RagPipelineResult:
        """Run the RAG pipeline and return the answer with retrieval diagnostics."""
        resolved_k = self.settings.default_top_k if k is None else k
        resolved_chunk_size = (
            self.settings.default_chunk_size if chunk_size is None else chunk_size
        )
        resolved_chunk_overlap = (
            self.settings.default_chunk_overlap
            if chunk_overlap is None
            else chunk_overlap
        )
        pipeline = self.create_pipeline(chunk_store=chunk_store, embeddings=embeddings)
        return await pipeline.answer_question_async(
            article=article,
            query=query,
            k=resolved_k,
            chunk_size=resolved_chunk_size,
            chunk_overlap=resolved_chunk_overlap,
        )

    def evaluate_answer(self, query: str, context: str, summary: str) -> Critique:
        """Score the generated answer for faithfulness and relevance."""
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured - critique is unavailable"
            )
        critique = SelfCritique(anthropic_api_key=self.settings.anthropic_api_key)
        return critique.evaluate(query=query, context=context, summary=summary)
