"""Session service: ties together article loading, summarization, and chat."""

import asyncio
import logging
from typing import Any

from ..database import create_session, get_session, update_session
from ..core.config import AppConfig, get_settings

from .article_service import ArticleService
from .chat_service import ChatService

logger = logging.getLogger(__name__)


class SessionService:
    """Handle session lifecycle — article loading, summaries, and chat turns."""

    def __init__(
        self,
        settings: AppConfig | None = None,
        article_service: ArticleService | None = None,
        chat_service: ChatService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.article_service = article_service or ArticleService(self.settings)
        self.chat_service = chat_service or ChatService(self.settings)

    def create_session(self) -> dict[str, Any]:
        """Create and persist a new session record."""
        return create_session()

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Return a session by ID, or raise LookupError if not found."""
        session = get_session(session_id)
        if not session:
            raise LookupError("Session not found")
        return session

    def get_history(self, session_id: str) -> dict[str, list[dict[str, Any]]]:
        """Return the chat history list for a session."""
        session = self.get_session(session_id)
        return {"chat_history": session.get("chat_history", [])}

    async def load_article(
        self,
        session_id: str,
        url: str,
        *,
        context_retriever: Any = None,
    ) -> dict[str, Any]:
        """Scrape a URL, store the article, and optionally index it in Milvus."""
        self.get_session(session_id)
        update_session(session_id, status="processing", error_message=None)

        try:
            logger.info("Scraping article: %s", url)
            article = await asyncio.to_thread(self.article_service.scrape_article, url)
            article_dict = article.model_dump(mode="json")

            update_session(
                session_id,
                url=url,
                article=article_dict,
                summary=None,
                chat_history=[],
                status="idle",
                error_message=None,
            )

            if context_retriever is not None:
                try:
                    ingestion_stats = await context_retriever.ingest_article(
                        article_dict,
                        chunk_size=self.settings.default_chunk_size,
                        chunk_overlap=self.settings.default_chunk_overlap,
                    )
                    logger.info(
                        "Article indexed in Milvus: inserted=%d deleted=%d total=%d",
                        ingestion_stats["inserted"],
                        ingestion_stats["deleted"],
                        ingestion_stats["total"],
                    )
                except Exception as exc:  # pragma: no cover
                    logger.warning("Deferred article indexing failed for %s: %s", url, exc)

            logger.info("Scraping complete: %s", article.title)
            return self.get_session(session_id)
        except Exception as exc:
            logger.error("Scraping failed: %s", exc)
            update_session(session_id, status="error", error_message=str(exc))
            raise

    async def summarize_article(self, session_id: str) -> dict[str, Any]:
        """Generate a summary for the article loaded in a session."""
        session = self.get_session(session_id)
        if not session.get("article"):
            raise ValueError("No article loaded in this session")

        update_session(session_id, status="processing", error_message=None)

        try:
            logger.info("Generating full article summary")
            summary = await asyncio.to_thread(
                self.article_service.generate_summary,
                session["article"]["content"],
            )
            update_session(session_id, summary=summary, status="idle")
            logger.info("Summary generation complete")
            return self.get_session(session_id)
        except Exception as exc:
            logger.error("Summary generation failed: %s", exc)
            update_session(session_id, status="error", error_message=str(exc))
            raise

    async def answer_question(
        self,
        session_id: str,
        question: str,
        *,
        chunk_store: Any = None,
        embeddings: Any = None,
    ) -> dict[str, Any]:
        """Answer a user question against the article loaded in a session."""
        session = self.get_session(session_id)
        if not session.get("article"):
            raise ValueError("No article loaded in this session")

        history: list[dict[str, Any]] = list(session.get("chat_history", []))
        history.append(
            {"role": "user", "content": question, "critique": None, "passages": []}
        )
        update_session(
            session_id,
            chat_history=history,
            status="processing",
            error_message=None,
        )

        try:
            pipeline_result = await self.chat_service.answer_question(
                article=session["article"],
                query=question,
                chunk_store=chunk_store,
                embeddings=embeddings,
                k=self.settings.default_top_k,
                chunk_size=self.settings.default_chunk_size,
                chunk_overlap=self.settings.default_chunk_overlap,
            )
            passages = [
                passage.model_dump() for passage in pipeline_result.retrieved_passages
            ]
            logger.info(
                "RAG pipeline completed in %.1fms (retrieval %.1fms, returned %d/%d chunks, candidate_k=%d, inserted=%d)",
                pipeline_result.total_elapsed_ms,
                pipeline_result.retrieval.elapsed_ms,
                pipeline_result.retrieval.returned_k,
                pipeline_result.retrieval.total_chunks,
                pipeline_result.retrieval.candidate_k,
                pipeline_result.retrieval.inserted_chunks,
            )

            if pipeline_result.used_fallback_answer:
                answer = pipeline_result.answer
                critique = None
            else:
                logger.info("Running self-critique")
                answer = pipeline_result.answer
                context = "\n---\n".join(passage["text"] for passage in passages)
                critique_result = await asyncio.to_thread(
                    self.chat_service.evaluate_answer,
                    question,
                    context,
                    answer,
                )
                critique = critique_result.model_dump()

            assistant_message = {
                "role": "assistant",
                "content": answer,
                "critique": critique,
                "passages": passages,
            }
            history.append(assistant_message)
            update_session(
                session_id,
                chat_history=history,
                retrieved_passages=passages,
                status="idle",
                error_message=None,
            )
            logger.info("Chat turn complete")
            return {"answer": answer, "critique": critique, "passages": passages}
        except Exception as exc:
            logger.error("Chat failed: %s", exc)
            history.append(
                {
                    "role": "assistant",
                    "content": "Sorry, I encountered an error processing your question.",
                    "critique": None,
                    "passages": [],
                }
            )
            update_session(
                session_id,
                chat_history=history,
                status="error",
                error_message=str(exc),
            )
            raise
