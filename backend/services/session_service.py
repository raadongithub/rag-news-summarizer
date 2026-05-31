"""Session service: ties together article loading, summarization, and chat."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import AppConfig, get_settings
from ..core.exceptions import NotFoundError, ValidationError
from ..models import User
from ..repositories import SessionRepository
from .article_service import ArticleService
from .chat_service import ChatService
from .serializers import serialize_session, serialize_session_list_item

logger = logging.getLogger(__name__)


class SessionService:
    """Handle session lifecycle, summaries, and chat turns for a user."""

    def __init__(
        self,
        db_session: Session,
        settings: AppConfig | None = None,
        article_service: ArticleService | None = None,
        chat_service: ChatService | None = None,
        session_repository: SessionRepository | None = None,
    ) -> None:
        """Initialize the session service.

        Parameters
        ----------
        db_session : Session
            Active SQLAlchemy session.
        settings : AppConfig | None, optional
            Optional settings override.
        article_service : ArticleService | None, optional
            Optional article service override.
        chat_service : ChatService | None, optional
            Optional chat service override.
        session_repository : SessionRepository | None, optional
            Optional repository override.
        """

        self.db_session = db_session
        self.settings = settings or get_settings()
        self.article_service = article_service or ArticleService(self.settings)
        self.chat_service = chat_service or ChatService(self.settings)
        self.session_repository = session_repository or SessionRepository(db_session)

    def list_sessions(self, user: User, limit: int = 20) -> list[dict[str, Any]]:
        """Return compact summaries of recent sessions for a user.

        Parameters
        ----------
        user : User
            Owning user entity.
        limit : int, optional
            Maximum number of sessions to return.

        Returns
        -------
        list[dict[str, Any]]
            List of compact session list-item payloads ordered by most
            recently updated first.
        """

        records = self.session_repository.list_for_user(user.id, limit=limit)
        return [serialize_session_list_item(r) for r in records]

    def create_session(self, user: User) -> dict[str, Any]:
        """Create and persist a new session for a user.

        Parameters
        ----------
        user : User
            Owning user entity.

        Returns
        -------
        dict[str, Any]
            Serialized session payload.
        """

        record = self.session_repository.create(user_id=user.id)
        self.db_session.commit()
        self.db_session.refresh(record)
        return serialize_session(record)

    def get_session(self, session_id: str, user: User) -> dict[str, Any]:
        """Return a user-owned session by ID.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.

        Returns
        -------
        dict[str, Any]
            Serialized session payload.
        """

        record = self.session_repository.get_for_user(session_id, user.id)
        if record is None:
            raise NotFoundError("Session not found")
        return serialize_session(record)

    def get_history(self, session_id: str, user: User) -> dict[str, list[dict[str, Any]]]:
        """Return the chat history list for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            Wrapped chat history payload.
        """

        session = self.get_session(session_id, user)
        return {"chat_history": session.get("chat_history", [])}

    def _require_record(self, session_id: str, user: User):
        """Return a session record or raise when missing.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.

        Returns
        -------
        SessionRecord
            Persisted session record.
        """

        record = self.session_repository.get_for_user(session_id, user.id)
        if record is None:
            raise NotFoundError("Session not found")
        return record

    def _save(self, record) -> dict[str, Any]:
        """Commit and serialize a session record.

        Parameters
        ----------
        record : SessionRecord
            Session record to commit.

        Returns
        -------
        dict[str, Any]
            Serialized session payload.
        """

        self.db_session.commit()
        self.db_session.refresh(record)
        return serialize_session(record)

    async def load_article(
        self,
        session_id: str,
        user: User,
        url: str,
        *,
        context_retriever: Any = None,
    ) -> dict[str, Any]:
        """Scrape a URL, store the article, and optionally index it in Milvus.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.
        url : str
            Article URL to scrape.
        context_retriever : Any, optional
            Shared retriever used for vector ingestion.

        Returns
        -------
        dict[str, Any]
            Serialized session payload after article ingestion.
        """

        record = self._require_record(session_id, user)
        self.session_repository.update(record, status="processing", error_message=None)
        self.db_session.commit()

        try:
            logger.info("Scraping article: %s", url)
            article = await asyncio.to_thread(self.article_service.scrape_article, url)
            article_dict = article.model_dump(mode="json")

            self.session_repository.update(
                record,
                url=url,
                article=article_dict,
                summary=None,
                chat_history=[],
                retrieved_passages=None,
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
            return self._save(record)
        except Exception as exc:
            logger.error("Scraping failed: %s", exc)
            self.session_repository.update(record, status="error", error_message=str(exc))
            self.db_session.commit()
            raise

    async def summarize_article(self, session_id: str, user: User) -> dict[str, Any]:
        """Generate a summary for the article loaded in a session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.

        Returns
        -------
        dict[str, Any]
            Serialized session payload after summary generation.
        """

        record = self._require_record(session_id, user)
        if not record.article_json:
            raise ValidationError("No article loaded in this session")

        self.session_repository.update(record, status="processing", error_message=None)
        self.db_session.commit()

        try:
            logger.info("Generating full article summary")
            summary = await asyncio.to_thread(
                self.article_service.generate_summary,
                record.article_json["content"],
            )
            self.session_repository.update(record, summary=summary, status="idle")
            logger.info("Summary generation complete")
            return self._save(record)
        except Exception as exc:
            logger.error("Summary generation failed: %s", exc)
            self.session_repository.update(record, status="error", error_message=str(exc))
            self.db_session.commit()
            raise

    async def answer_question(
        self,
        session_id: str,
        user: User,
        question: str,
        *,
        chunk_store: Any = None,
        embeddings: Any = None,
    ) -> dict[str, Any]:
        """Answer a user question against the article loaded in a session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user : User
            Owning user entity.
        question : str
            User question to answer.
        chunk_store : Any, optional
            Shared chunk store.
        embeddings : Any, optional
            Shared embeddings service.

        Returns
        -------
        dict[str, Any]
            Answer payload for the API response.
        """

        record = self._require_record(session_id, user)
        if not record.article_json:
            raise ValidationError("No article loaded in this session")

        history: list[dict[str, Any]] = list(record.chat_history_json or [])
        history.append(
            {"role": "user", "content": question, "critique": None, "passages": []}
        )
        self.session_repository.update(
            record,
            chat_history=history,
            status="processing",
            error_message=None,
        )
        self.db_session.commit()

        try:
            pipeline_result = await self.chat_service.answer_question(
                article=record.article_json,
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

            answer = pipeline_result.answer
            critique = None
            if not pipeline_result.used_fallback_answer:
                logger.info("Running self-critique")
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
            self.session_repository.update(
                record,
                chat_history=history,
                retrieved_passages=passages,
                status="idle",
                error_message=None,
            )
            self.db_session.commit()
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
            self.session_repository.update(
                record,
                chat_history=history,
                status="error",
                error_message=str(exc),
            )
            self.db_session.commit()
            raise
