import json
import logging
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field, ValidationError, field_validator

from .rag_pipeline import RagPipeline, RagPipelineResult
from .scraper import NewsArticleScraper

try:
    from ragas import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import llm_factory
    from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness
    try:
        from ragas.metrics.collections import ResponseRelevancy
    except ImportError:
        from ragas.metrics import ResponseRelevancy
except ImportError as exc:  # pragma: no cover - exercised in runtime environments
    raise ImportError(
        "RAGAs is required for evaluation. Install project dependencies before "
        "running the evaluation pipeline."
    ) from exc

from .summary import DEFAULT_ANTHROPIC_MODEL
from langchain_voyageai import VoyageAIEmbeddings

logger = logging.getLogger(__name__)


class EvaluationSample(BaseModel):
    """Validated input sample for RAG evaluation.

    Attributes
        question : str
            User question evaluated against the RAG pipeline.
        reference_answer : str
            Ground-truth answer used by reference-based metrics.
        article_url : str or None
            Source article URL to scrape when `article` is not supplied.
        article : dict or None
            Preloaded serialized article payload.
        sample_id : str or None
            Stable identifier for reporting.
        metadata : dict
            Additional caller-supplied metadata passed through to the report.
    """

    question: str
    reference_answer: str
    article_url: Optional[str] = None
    article: Optional[Dict[str, Any]] = None
    sample_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("question", "reference_answer")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Validate required text fields.

        Parameters
            value : str
                Raw text value supplied to the model field.

        Returns
            str
                Normalized non-empty text.

        Raises
            ValueError
                Raised when the supplied text is empty after trimming.
        """
        value = value.strip()
        if not value:
            raise ValueError("question and reference_answer must be non-empty")
        return value

    @field_validator("article_url")
    @classmethod
    def normalize_article_url(cls, value: Optional[str]) -> Optional[str]:
        """Normalize an optional article URL.

        Parameters
            value : str or None
                Raw article URL supplied to the model field.

        Returns
            str or None
                Trimmed URL value or `None` when empty.
        """
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("article")
    @classmethod
    def validate_article_payload(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate an inline article payload.

        Parameters
            value : dict or None
                Raw article payload supplied to the model field.

        Returns
            dict or None
                Original payload when it contains non-empty article content.

        Raises
            ValueError
                Raised when inline article content is missing or empty.
        """
        if value is None:
            return None
        content = str(value.get("content", "")).strip()
        if not content:
            raise ValueError("article.content must be non-empty when article is provided")
        return value

    def resolved_sample_id(self, index: int) -> str:
        """Return a stable sample identifier for reporting.

        Parameters
            index : int
                Zero-based sample index in the evaluation run.

        Returns
            str
                Existing `sample_id` or a generated fallback identifier.
        """
        if self.sample_id:
            return self.sample_id
        if self.article_url:
            return f"sample-{index + 1}"
        return f"in-memory-{index + 1}"

    def resolve_article(self, scraper: NewsArticleScraper) -> Dict[str, Any]:
        """Resolve the article payload used during evaluation.

        Parameters
            scraper : NewsArticleScraper
                Scraper used when the sample references an `article_url`.

        Returns
            dict
                Serialized article payload ready for retrieval and generation.

        Raises
            ValueError
                Raised when neither `article` nor `article_url` is available.
            Exception
                Propagates scraper errors when the remote article cannot be resolved.
        """
        if self.article:
            return self.article
        if not self.article_url:
            raise ValueError("Each evaluation sample must define article or article_url")

        logger.info("Scraping evaluation article: %s", self.article_url)
        return scraper.scrape_article(self.article_url).model_dump(mode="json")


class EvaluationMetrics(BaseModel):
    """Metric scores reported for a single evaluation unit or summary aggregate.

    Attributes
        context_precision : float
            Reference-based precision of retrieved contexts.
        context_recall : float
            Reference-based recall of retrieved contexts.
        faithfulness : float
            Grounding score for the generated answer relative to retrieved context.
        answer_relevancy : float
            Relevance score for the generated answer relative to the user question.
    """

    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float


class EvaluationDiagnostics(BaseModel):
    """Diagnostics reported alongside metric scores.

    Attributes
        total_elapsed_ms : float
            End-to-end latency in milliseconds.
        retrieval_elapsed_ms : float
            Retrieval latency in milliseconds.
        generation_elapsed_ms : float or None
            Generation latency in milliseconds when answer generation occurred.
        total_chunks : int
            Total number of chunks available before ranking.
        returned_chunks : int
            Number of chunks returned after ranking.
        requested_k : int
            Number of chunks requested by the evaluator.
        similarity_max : float or None
            Highest similarity score in the retrieved set.
        similarity_min : float or None
            Lowest similarity score in the retrieved set.
        similarity_mean : float or None
            Mean similarity score in the retrieved set.
        used_fallback_answer : bool
            Indicates whether the pipeline answered with the no-context fallback.
    """

    total_elapsed_ms: float
    retrieval_elapsed_ms: float
    generation_elapsed_ms: Optional[float] = None
    total_chunks: int
    returned_chunks: int
    requested_k: int
    similarity_max: Optional[float] = None
    similarity_min: Optional[float] = None
    similarity_mean: Optional[float] = None
    used_fallback_answer: bool


class SampleEvaluationResult(BaseModel):
    """Per-sample evaluation report.

    Attributes
        sample_id : str
            Stable sample identifier.
        question : str
            User question evaluated by the pipeline.
        reference_answer : str
            Ground-truth answer used for scoring.
        answer : str
            Generated pipeline answer.
        contexts : list of str
            Retrieved contexts used during evaluation.
        metrics : EvaluationMetrics
            Metric scores for the sample.
        diagnostics : EvaluationDiagnostics
            Retrieval and latency diagnostics for the sample.
        metadata : dict
            Caller-supplied metadata copied from the input sample.
    """

    sample_id: str
    question: str
    reference_answer: str
    answer: str
    contexts: List[str]
    metrics: EvaluationMetrics
    diagnostics: EvaluationDiagnostics
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationSummary(BaseModel):
    """Aggregate statistics across all evaluated samples.

    Attributes
        sample_count : int
            Number of evaluated samples.
        averages : EvaluationMetrics
            Mean value for each reported metric.
        average_total_latency_ms : float
            Mean end-to-end latency in milliseconds.
        average_retrieval_latency_ms : float
            Mean retrieval latency in milliseconds.
        average_generation_latency_ms : float
            Mean generation latency in milliseconds.
    """

    sample_count: int
    averages: EvaluationMetrics
    average_total_latency_ms: float
    average_retrieval_latency_ms: float
    average_generation_latency_ms: float


class EvaluationReport(BaseModel):
    """Complete evaluation report.

    Attributes
        summary : EvaluationSummary
            Aggregate metrics and latency statistics.
        samples : list of SampleEvaluationResult
            Per-sample evaluation details.
    """

    summary: EvaluationSummary
    samples: List[SampleEvaluationResult]


class RagasEvaluator:
    """Evaluate the current RAG stack with reference-based RAGAs metrics.

    Parameters
        anthropic_api_key : str
            Anthropic API key used by the shared answer generator and RAGAs LLM metrics.
        voyage_api_key : str
            Voyage API key used by retrieval and embedding-backed metrics.
        retrieval_k : int, optional
            Number of passages to retrieve for each sample.
        chunk_size : int, optional
            Number of sentences per retrieval chunk.
        chunk_overlap : int, optional
            Number of overlapping sentences between adjacent retrieval chunks.

    Raises
        ImportError
            Raised when the `ragas` package is unavailable.
        Exception
            Propagates provider initialization errors from Anthropic or Voyage clients.
    """

    def __init__(
        self,
        *,
        anthropic_api_key: str,
        voyage_api_key: str,
        retrieval_k: int = 3,
        chunk_size: int = 3,
        chunk_overlap: int = 1,
    ) -> None:
        self.retrieval_k = retrieval_k
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.scraper = NewsArticleScraper()
        self.pipeline = RagPipeline(
            voyage_api_key=voyage_api_key,
            anthropic_api_key=anthropic_api_key,
        )

        ragas_llm = llm_factory(
            DEFAULT_ANTHROPIC_MODEL,
            provider="anthropic",
            client=AsyncAnthropic(api_key=anthropic_api_key),
            temperature=0.0,
        )
        ragas_llm.model_args.pop("top_p", None)
        embeddings_wrapper = LangchainEmbeddingsWrapper(
            VoyageAIEmbeddings(
                model="voyage-4",
                voyage_api_key=voyage_api_key,
                batch_size=32,
            )
        )

        self.metrics = {
            "context_precision": ContextPrecision(llm=ragas_llm),
            "context_recall": ContextRecall(llm=ragas_llm),
            "faithfulness": Faithfulness(llm=ragas_llm),
            "answer_relevancy": ResponseRelevancy(
                llm=ragas_llm,
                embeddings=embeddings_wrapper,
            ),
        }

    def evaluate_samples(self, samples: List[EvaluationSample]) -> EvaluationReport:
        """Evaluate a validated list of samples against the live RAG stack.

        Parameters
            samples : list of EvaluationSample
                Evaluation samples to score.

        Returns
            EvaluationReport
                Report containing aggregate metrics and per-sample diagnostics.

        Raises
            ValueError
                Raised when the sample list is empty.
            Exception
                Propagates scraping, retrieval, generation, or metric provider errors.
        """
        if not samples:
            raise ValueError("At least one evaluation sample is required")

        results: List[SampleEvaluationResult] = []

        for index, sample in enumerate(samples):
            sample_id = sample.resolved_sample_id(index)
            article = sample.resolve_article(self.scraper)
            logger.info("Evaluating sample %s", sample_id)
            pipeline_result = self.pipeline.answer_question(
                article=article,
                query=sample.question,
                k=self.retrieval_k,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            results.append(
                self._evaluate_single_sample(
                    sample_id=sample_id,
                    sample=sample,
                    pipeline_result=pipeline_result,
                )
            )

        return EvaluationReport(
            summary=self._build_summary(results),
            samples=results,
        )

    def evaluate_file(self, path: str | Path) -> EvaluationReport:
        """Load and evaluate a dataset file.

        Parameters
            path : str or pathlib.Path
                Path to a JSON or JSONL evaluation dataset.

        Returns
            EvaluationReport
                Report containing aggregate metrics and per-sample diagnostics.

        Raises
            FileNotFoundError
                Raised when the dataset file does not exist.
            ValueError
                Raised when the dataset file contents are invalid.
            Exception
                Propagates runtime errors from evaluation dependencies.
        """
        samples = self.load_samples(path)
        return self.evaluate_samples(samples)

    @staticmethod
    def load_samples(path: str | Path) -> List[EvaluationSample]:
        """Load and validate evaluation samples from disk.

        Parameters
            path : str or pathlib.Path
                Path to a JSON or JSONL evaluation dataset.

        Returns
            list of EvaluationSample
                Validated evaluation samples.

        Raises
            FileNotFoundError
                Raised when the dataset file does not exist.
            ValueError
                Raised when the dataset cannot be parsed or validated.
        """
        input_path = Path(path)
        if not input_path.exists():
            raise FileNotFoundError(f"Evaluation dataset not found: {input_path}")

        if input_path.suffix.lower() == ".jsonl":
            raw_items = [
                json.loads(line)
                for line in input_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            raw_items = payload if isinstance(payload, list) else payload.get("samples", [])

        try:
            return [EvaluationSample.model_validate(item) for item in raw_items]
        except ValidationError as exc:
            raise ValueError(f"Invalid evaluation dataset: {exc}") from exc

    def _evaluate_single_sample(
        self,
        *,
        sample_id: str,
        sample: EvaluationSample,
        pipeline_result: RagPipelineResult,
    ) -> SampleEvaluationResult:
        """Evaluate one pipeline result against one reference sample.

        Parameters
            sample_id : str
                Stable identifier used in the report.
            sample : EvaluationSample
                Input sample containing the question and reference answer.
            pipeline_result : RagPipelineResult
                Retrieval and generation output produced by the shared RAG pipeline.

        Returns
            SampleEvaluationResult
                Metric scores and diagnostics for the sample.

        Raises
            Exception
                Propagates metric scoring errors from RAGAs dependencies.
        """
        contexts = [passage.text for passage in pipeline_result.retrieved_passages]
        ragas_sample = SingleTurnSample(
            user_input=sample.question,
            response=pipeline_result.answer,
            reference=sample.reference_answer,
            retrieved_contexts=contexts,
        )
        metric_inputs = {
            "context_precision": {
                "user_input": sample.question,
                "reference": sample.reference_answer,
                "retrieved_contexts": contexts,
            },
            "context_recall": {
                "user_input": sample.question,
                "reference": sample.reference_answer,
                "retrieved_contexts": contexts,
            },
            "faithfulness": {
                "user_input": sample.question,
                "response": pipeline_result.answer,
                "retrieved_contexts": contexts,
            },
        }

        context_precision = 0.0
        context_recall = 0.0
        faithfulness = 0.0

        if contexts:
            context_precision = self._score_metric(
                "context_precision",
                ragas_sample,
                metric_inputs["context_precision"],
            )
            context_recall = self._score_metric(
                "context_recall",
                ragas_sample,
                metric_inputs["context_recall"],
            )
            faithfulness = self._score_metric(
                "faithfulness",
                ragas_sample,
                metric_inputs["faithfulness"],
            )

        metrics = EvaluationMetrics(
            context_precision=context_precision,
            context_recall=context_recall,
            faithfulness=faithfulness,
            answer_relevancy=self._score_metric("answer_relevancy", ragas_sample, {}),
        )

        return SampleEvaluationResult(
            sample_id=sample_id,
            question=sample.question,
            reference_answer=sample.reference_answer,
            answer=pipeline_result.answer,
            contexts=contexts,
            metrics=metrics,
            diagnostics=EvaluationDiagnostics(
                total_elapsed_ms=pipeline_result.total_elapsed_ms,
                retrieval_elapsed_ms=pipeline_result.retrieval.elapsed_ms,
                generation_elapsed_ms=(
                    pipeline_result.generation.elapsed_ms
                    if pipeline_result.generation
                    else None
                ),
                total_chunks=pipeline_result.retrieval.total_chunks,
                returned_chunks=pipeline_result.retrieval.returned_k,
                requested_k=pipeline_result.retrieval.requested_k,
                similarity_max=pipeline_result.retrieval.similarity_max,
                similarity_min=pipeline_result.retrieval.similarity_min,
                similarity_mean=pipeline_result.retrieval.similarity_mean,
                used_fallback_answer=pipeline_result.used_fallback_answer,
            ),
            metadata=sample.metadata,
        )

    def _score_metric(
        self,
        name: str,
        sample: SingleTurnSample,
        inputs: Dict[str, Any],
    ) -> float:
        """Score one metric using the appropriate RAGAs invocation path.

        Parameters
            name : str
                Metric registry key.
            sample : SingleTurnSample
                Standardized RAGAs sample for single-turn metrics.
            inputs : dict
                Keyword arguments for metrics that use direct `score` calls.

        Returns
            float
                Numeric metric score.

        Raises
            KeyError
                Raised when the metric name is not registered.
            Exception
                Propagates runtime errors from the metric implementation.
        """
        metric = self.metrics[name]
        if hasattr(metric, "single_turn_score"):
            result = metric.single_turn_score(sample)
        else:
            result = metric.score(**inputs)
        if hasattr(result, "value"):
            return float(result.value)
        return float(result)

    @staticmethod
    def _build_summary(results: List[SampleEvaluationResult]) -> EvaluationSummary:
        """Build aggregate summary metrics from per-sample results.

        Parameters
            results : list of SampleEvaluationResult
                Completed per-sample evaluation results.

        Returns
            EvaluationSummary
                Aggregate metric and latency summary.
        """
        generation_latencies = [
            result.diagnostics.generation_elapsed_ms
            for result in results
            if result.diagnostics.generation_elapsed_ms is not None
        ]

        return EvaluationSummary(
            sample_count=len(results),
            averages=EvaluationMetrics(
                context_precision=mean(result.metrics.context_precision for result in results),
                context_recall=mean(result.metrics.context_recall for result in results),
                faithfulness=mean(result.metrics.faithfulness for result in results),
                answer_relevancy=mean(result.metrics.answer_relevancy for result in results),
            ),
            average_total_latency_ms=mean(
                result.diagnostics.total_elapsed_ms for result in results
            ),
            average_retrieval_latency_ms=mean(
                result.diagnostics.retrieval_elapsed_ms for result in results
            ),
            average_generation_latency_ms=mean(generation_latencies)
            if generation_latencies
            else 0.0,
        )
