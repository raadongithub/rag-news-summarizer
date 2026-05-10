import logging
from time import perf_counter
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .retriever import ContextRetriever
from .summary import DEFAULT_ANTHROPIC_MODEL, SummaryGenerator

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the article to answer your question."
)


class RetrievedPassage(BaseModel):
    text: str
    similarity_score: float
    rank: int


class RetrievalDiagnostics(BaseModel):
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


class GenerationDiagnostics(BaseModel):
    model: str = DEFAULT_ANTHROPIC_MODEL
    elapsed_ms: float = 0.0


class RagPipelineResult(BaseModel):
    query: str
    answer: str
    retrieved_passages: List[RetrievedPassage] = Field(default_factory=list)
    retrieval: RetrievalDiagnostics
    generation: Optional[GenerationDiagnostics] = None
    total_elapsed_ms: float = 0.0
    used_fallback_answer: bool = False


class RagPipeline:
    """Run retrieval and answer generation while capturing diagnostics."""

    def __init__(
        self,
        voyage_api_key: str,
        anthropic_api_key: Optional[str] = None,
    ) -> None:
        self.retriever = ContextRetriever(voyage_api_key=voyage_api_key)
        self.generator = SummaryGenerator(anthropic_api_key=anthropic_api_key)

    def answer_question(
        self,
        article: Dict,
        query: str,
        *,
        k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> RagPipelineResult:
        """Answer a question from an article using the current RAG stack."""
        total_started = perf_counter()

        retrieval_started = perf_counter()
        retrieval_payload = self.retriever.retrieve(
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
        answer = self.generator.generate(
            query=query,
            retrieved_passages=[passage.model_dump() for passage in passages],
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

    @staticmethod
    def _build_retrieval_diagnostics(
        *,
        metadata: Dict,
        passages: List[RetrievedPassage],
        requested_k: int,
        chunk_size: int,
        chunk_overlap: int,
        elapsed_ms: float,
    ) -> RetrievalDiagnostics:
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
        )
