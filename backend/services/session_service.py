"""Session service: ties together article loading, summarization, and chat."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import AppConfig, get_settings
from ..core.exceptions import NotFoundError, ValidationError
from ..models import User
from ..models.chat import ChatMessage, MessageCritique, MessagePassage
from ..queries import SessionQueries
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
        session_repository: SessionQueries | None = None,
    ) -> None:
        """Initialize the session service."""

        self.db_session = db_session
        self.settings = settings or get_settings()
        self.article_service = article_service or ArticleService(self.settings)
        self.chat_service = chat_service or ChatService(self.settings)
        self.session_repository = session_repository or SessionQueries(db_session)

    def list_sessions(self, user: User, limit: int = 20) -> list[dict[str, Any]]:
        """Return compact summaries of recent sessions for a user."""

        records = self.session_repository.list_for_user(user.id, limit=limit)
        return [serialize_session_list_item(r) for r in records]

    def create_session(self, user: User) -> dict[str, Any]:
        """Create and persist a new session for a user."""

        record = self.session_repository.create(user_id=user.id)
        self.db_session.commit()
        self.db_session.refresh(record)
        return serialize_session(record)

    def get_session(self, session_id: str, user: User) -> dict[str, Any]:
        """Return a user-owned session by ID."""

        record = self.session_repository.get_for_user(session_id, user.id)
        if record is None:
            raise NotFoundError("Session not found")
        return serialize_session(record)

    def get_history(self, session_id: str, user: User) -> dict[str, list[dict[str, Any]]]:
        """Return the chat history list for a session."""

        session = self.get_session(session_id, user)
        return {"chat_history": session.get("chat_history", [])}

    def _require_record(self, session_id: str, user: User):
        """Return a session record or raise when missing."""

        record = self.session_repository.get_for_user(session_id, user.id)
        if record is None:
            raise NotFoundError("Session not found")
        return record

    def _save(self, record) -> dict[str, Any]:
        """Commit and serialize a session record."""

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
        """Scrape a URL, store the article, and optionally index it in Milvus."""

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
        """Generate a summary for the article loaded in a session."""

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
        """Answer a user question against the article loaded in a session."""

        record = self._require_record(session_id, user)
        if not record.article_json:
            raise ValidationError("No article loaded in this session")

        history: list[dict[str, Any]] = list(record.chat_history_json or [])
        message_id = str(uuid.uuid4())
        user_message_index = len(history)
        history.append(
            {"role": "user", "content": question, "critique": None, "passages": [], "message_id": message_id}
        )
        self.session_repository.update(
            record,
            chat_history=history,
            status="processing",
            error_message=None,
        )
        self.db_session.commit()

        logger.info(
            "%s",
            json.dumps({
                "event": "query_sent",
                "session_id": session_id,
                "message_id": message_id,
                "message_index": user_message_index,
                "query": question,
            }),
        )
        query_start = time.monotonic()

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
                "message_id": message_id,
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

            # Persist to normalized tables (3NF)
            user_msg_row = ChatMessage(
                id=message_id,
                session_id=session_id,
                role="user",
                content=question,
                message_index=user_message_index,
            )
            self.db_session.add(user_msg_row)
            assistant_msg_id = str(uuid.uuid4())
            assistant_msg_row = ChatMessage(
                id=assistant_msg_id,
                session_id=session_id,
                role="assistant",
                content=answer,
                message_index=user_message_index + 1,
            )
            self.db_session.add(assistant_msg_row)
            if critique:
                self.db_session.add(MessageCritique(
                    message_id=assistant_msg_id,
                    is_faithful=critique.get("is_faithful", False),
                    faithfulness_explanation=critique.get("faithfulness_explanation", ""),
                    is_relevant=critique.get("is_relevant", False),
                    relevance_explanation=critique.get("relevance_explanation", ""),
                    confidence_score=critique.get("confidence_score", 0.0),
                ))
            for passage in passages:
                meta = passage.get("metadata") or {}
                self.db_session.add(MessagePassage(
                    message_id=assistant_msg_id,
                    rank=passage.get("rank", 0),
                    text=passage.get("text", ""),
                    similarity_score=passage.get("similarity_score", 0.0),
                    base_similarity_score=meta.get("base_similarity_score"),
                    chunk_id=str(meta.get("chunk_id", "") or "")[:128] or None,
                    article_url=meta.get("article_url"),
                    title=meta.get("title"),
                    chunk_index=meta.get("chunk_index"),
                ))
            self.db_session.commit()

            elapsed_ms = round((time.monotonic() - query_start) * 1000, 1)
            logger.info(
                "%s",
                json.dumps({
                    "event": "response_received",
                    "session_id": session_id,
                    "message_id": message_id,
                    "message_index": user_message_index + 1,
                    "answer": answer,
                    "passages_count": len(passages),
                    "retrieved_chunks": [
                        {"rank": p.get("rank"), "text": p.get("text", "")[:120], "similarity_score": p.get("similarity_score")}
                        for p in passages
                    ],
                    "critique": critique,
                    "elapsed_ms": elapsed_ms,
                }),
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
            self.session_repository.update(
                record,
                chat_history=history,
                status="error",
                error_message=str(exc),
            )
            self.db_session.commit()
            raise
