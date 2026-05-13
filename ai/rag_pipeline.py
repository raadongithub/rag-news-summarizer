"""End-to-end RAG orchestration with retrieval and grounded generation."""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .embeddings import VoyageEmbeddingService
from .milvus_store import MilvusChunkStore
from .retriever import ContextRetriever
from .summary import DEFAULT_ANTHROPIC_MODEL, SummaryGenerator

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the article to answer your question."
)


class RetrievedPassage(BaseModel):
    """Normalized retrieved passage returned by the ranking stage.

    Attributes
    ----------
    text : str
        Retrieved article chunk content.
    similarity_score : float
        Final semantic score assigned during reranking.
    rank : int
        One-based ranking position in the final retrieval result set.
    metadata : dict of str to Any
        Retrieval metadata persisted with the chunk.
    base_similarity_score : float or None
        Original vector-search score returned by Milvus before reranking.
    """

    text: str
    similarity_score: float
    rank: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    base_similarity_score: Optional[float] = None


class RetrievalDiagnostics(BaseModel):
    """Operational metadata captured for the retrieval stage.

    Attributes
    ----------
    url : str
        Article URL associated with the retrieval request.
    title : str
        Article title associated with the retrieval request.
    total_chunks : int
        Total number of chunks produced before ranking.
    retrieval_method : str
        Retrieval implementation identifier.
    chunk_size : int
        Number of sentences per chunk window.
    chunk_overlap : int
        Number of overlapping sentences between adjacent chunks.
    requested_k : int
        Number of passages requested by the caller.
    returned_k : int
        Number of passages actually returned.
    elapsed_ms : float
        Retrieval latency in milliseconds.
    similarity_max : float or None
        Highest similarity score in the returned set.
    similarity_min : float or None
        Lowest similarity score in the returned set.
    similarity_mean : float or None
        Mean similarity score in the returned set.
    candidate_k : int
        Candidate pool size requested from Milvus before compression.
    compression_enabled : bool
        Whether contextual compression was enabled.
    llm_extraction_enabled : bool
        Whether LLM-based extraction ran during retrieval.
    inserted_chunks : int
        Number of newly inserted chunks during ingestion.
    ingested_chunks : int
        Total chunks seen for the article during ingestion.
    """

    url: str = ""
    title: str = ""
    total_chunks: int = 0
    retrieval_method: str = ""
    chunk_size: int = 0
    chunk_overlap: int = 0
    requested_k: int = 0
    returned_k: int = 0
    elapsed_ms: float = 0.0
    similarity_max: Optional[float] = None
    similarity_min: Optional[float] = None
    similarity_mean: Optional[float] = None
    candidate_k: int = 0
    compression_enabled: bool = False
    llm_extraction_enabled: bool = False
    inserted_chunks: int = 0
    ingested_chunks: int = 0


class GenerationDiagnostics(BaseModel):
    """Operational metadata captured for the generation stage.

    Attributes
    ----------
    model : str
        Model identifier used for answer generation.
    elapsed_ms : float
        Generation latency in milliseconds.
    """

    model: str = DEFAULT_ANTHROPIC_MODEL
    elapsed_ms: float = 0.0


class RagPipelineResult(BaseModel):
    """Structured output from a full RAG question-answer turn.

    Attributes
    ----------
    query : str
        User question processed by the pipeline.
    answer : str
        Final answer returned by the generation stage or fallback path.
    retrieved_passages : list of RetrievedPassage
        Ranked passages used as generation context.
    retrieval : RetrievalDiagnostics
        Retrieval diagnostics captured for the request.
    generation : GenerationDiagnostics or None
        Generation diagnostics when an answer was generated from retrieved context.
    total_elapsed_ms : float
        End-to-end pipeline latency in milliseconds.
    used_fallback_answer : bool
        Indicates whether the pipeline returned the no-context fallback response.
    """

    query: str
    answer: str
    retrieved_passages: List[RetrievedPassage] = Field(default_factory=list)
    retrieval: RetrievalDiagnostics
    generation: Optional[GenerationDiagnostics] = None
    total_elapsed_ms: float = 0.0
    used_fallback_answer: bool = False


class RagPipeline:
    """Run retrieval and generation while capturing reusable diagnostics.

    Parameters
    ----------
    voyage_api_key : str
        Voyage API key used for embedding and retrieval.
    anthropic_api_key : str or None, optional
        Anthropic API key used for answer generation.
    chunk_store : MilvusChunkStore or None, optional
        Shared Milvus store instance.
    embeddings : VoyageEmbeddingService or None, optional
        Shared embedding service instance.
    """

    def __init__(
        self,
        voyage_api_key: str,
        anthropic_api_key: Optional[str] = None,
        *,
        chunk_store: Optional[MilvusChunkStore] = None,
        embeddings: Optional[VoyageEmbeddingService] = None,
    ) -> None:
        self.retriever = ContextRetriever(
            voyage_api_key=voyage_api_key,
            anthropic_api_key=anthropic_api_key,
            chunk_store=chunk_store,
            embeddings=embeddings,
        )
        self.generator = SummaryGenerator(anthropic_api_key=anthropic_api_key)

    async def answer_question_async(
        self,
        article: Dict[str, Any],
        query: str,
        *,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> RagPipelineResult:
        """Answer a question from an article without blocking the event loop.

        Parameters
        ----------
        article : dict of str to Any
            Serialized article payload containing at least article content.
        query : str
            User question to answer.
        k : int, optional
            Maximum number of ranked passages to return.
        chunk_size : int, optional
            Number of sentences in each retrieval chunk.
        chunk_overlap : int, optional
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        RagPipelineResult
            Structured answer payload with passages, diagnostics, and latency.
        """
        total_started = perf_counter()

        retrieval_started = perf_counter()
        retrieval_payload = await self.retriever.retrieve_async(
            scraped_data=article,
            query=query,
            k=k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        retrieval_elapsed_ms = (perf_counter() - retrieval_started) * 1000

        raw_passages = retrieval_payload.get("retrieved_passages", [])
        passages = [RetrievedPassage.model_validate(passage) for passage in raw_passages]
        retrieval = self._build_retrieval_diagnostics(
            metadata=retrieval_payload.get("metadata", {}),
            passages=passages,
            requested_k=k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            elapsed_ms=retrieval_elapsed_ms,
        )

        if not passages:
            logger.info("No passages retrieved for query '%s'", query)
            return RagPipelineResult(
                query=query,
                answer=NO_CONTEXT_ANSWER,
                retrieved_passages=[],
                retrieval=retrieval,
                generation=None,
                total_elapsed_ms=(perf_counter() - total_started) * 1000,
                used_fallback_answer=True,
            )

        generation_started = perf_counter()
        answer = await asyncio.to_thread(
            self.generator.generate,
            query,
            [passage.model_dump() for passage in passages],
        )
        generation_elapsed_ms = (perf_counter() - generation_started) * 1000

        return RagPipelineResult(
            query=query,
            answer=answer,
            retrieved_passages=passages,
            retrieval=retrieval,
            generation=GenerationDiagnostics(elapsed_ms=generation_elapsed_ms),
            total_elapsed_ms=(perf_counter() - total_started) * 1000,
            used_fallback_answer=False,
        )

    def answer_question(
        self,
        article: Dict[str, Any],
        query: str,
        *,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> RagPipelineResult:
        """Answer a question from an article synchronously.

        Parameters
        ----------
        article : dict of str to Any
            Serialized article payload containing at least article content.
        query : str
            User question to answer.
        k : int, optional
            Maximum number of ranked passages to return.
        chunk_size : int, optional
            Number of sentences in each retrieval chunk.
        chunk_overlap : int, optional
            Number of overlapping sentences between adjacent chunks.

        Returns
        -------
        RagPipelineResult
            Structured answer payload with passages, diagnostics, and latency.
        """
        return asyncio.run(
            self.answer_question_async(
                article=article,
                query=query,
                k=k,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    @staticmethod
    def _build_retrieval_diagnostics(
        *,
        metadata: Dict[str, Any],
        passages: List[RetrievedPassage],
        requested_k: int,
        chunk_size: int,
        chunk_overlap: int,
        elapsed_ms: float,
    ) -> RetrievalDiagnostics:
        """Build normalized retrieval diagnostics from raw retrieval metadata.

        Parameters
        ----------
        metadata : dict of str to Any
            Raw metadata returned by the retriever.
        passages : list of RetrievedPassage
            Ranked passages returned by retrieval.
        requested_k : int
            Number of passages requested by the caller.
        chunk_size : int
            Number of sentences in each retrieval chunk.
        chunk_overlap : int
            Number of overlapping sentences between adjacent chunks.
        elapsed_ms : float
            Measured retrieval latency in milliseconds.

        Returns
        -------
        RetrievalDiagnostics
            Aggregated retrieval diagnostics suitable for logging and evaluation.
        """
        scores = [passage.similarity_score for passage in passages]
        similarity_mean = sum(scores) / len(scores) if scores else None

        return RetrievalDiagnostics(
            url=metadata.get("url", ""),
            title=metadata.get("title", ""),
            total_chunks=metadata.get("total_chunks", 0),
            retrieval_method=metadata.get("retrieval_method", ""),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            requested_k=requested_k,
            returned_k=len(passages),
            elapsed_ms=elapsed_ms,
            similarity_max=max(scores) if scores else None,
            similarity_min=min(scores) if scores else None,
            similarity_mean=similarity_mean,
            candidate_k=metadata.get("candidate_k", 0),
            compression_enabled=bool(metadata.get("compression_enabled", False)),
            llm_extraction_enabled=bool(metadata.get("llm_extraction_enabled", False)),
            inserted_chunks=int(metadata.get("inserted_chunks", 0)),
            ingested_chunks=int(metadata.get("ingested_chunks", 0)),
        )
