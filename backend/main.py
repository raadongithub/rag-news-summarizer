"""FastAPI application for article ingestion, summarization, and RAG chat."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import create_session, get_session, init_db, update_session

# ai/ is on sys.path via PYTHONPATH=/app when run as `uvicorn backend.main:app`
from ai.embeddings import VoyageEmbeddingService
from ai.milvus_store import MilvusChunkStore
from ai.rag_pipeline import RagPipeline
from ai.retriever import ContextRetriever
from ai.scraper import NewsArticleScraper
from ai.summary import ArticleSummarizer, SelfCritique

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage backend startup and shutdown resources.

    Parameters
    ----------
    app : FastAPI
        Application instance receiving shared resource state.

    Yields
    ------
    None
        Control is yielded to the FastAPI runtime.
    """
    init_db()
    app.state.startup_complete = False
    app.state.embeddings = None
    app.state.chunk_store = None
    app.state.context_retriever = None

    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set - summarization will fail.")
    if not VOYAGE_API_KEY:
        logger.warning("VOYAGE_API_KEY is not set - chat retrieval will fail.")
    else:
        embeddings = VoyageEmbeddingService(api_key=VOYAGE_API_KEY)
        chunk_store = MilvusChunkStore(embeddings=embeddings)
        try:
            await chunk_store.initialize()
            app.state.embeddings = embeddings
            app.state.chunk_store = chunk_store
            app.state.context_retriever = ContextRetriever(
                voyage_api_key=VOYAGE_API_KEY,
                anthropic_api_key=ANTHROPIC_API_KEY,
                embeddings=embeddings,
                chunk_store=chunk_store,
            )
            logger.info("Milvus vector store initialized")
        except Exception as exc:  # pragma: no cover - exercised in runtime environments
            logger.error("Milvus initialization failed: %s", exc)

    app.state.startup_complete = True
    try:
        yield
    finally:
        chunk_store = getattr(app.state, "chunk_store", None)
        if chunk_store is not None:
            await chunk_store.close()


app = FastAPI(title="News Summarizer API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Return backend readiness information.

    Returns
    -------
    dict
        Readiness payload containing service and startup state.
    """
    return {
        "status": "ok",
        "service": "backend",
        "startup_complete": bool(getattr(app.state, "startup_complete", False)),
        "milvus_ready": bool(getattr(app.state, "chunk_store", None)),
    }


@app.post("/sessions", status_code=201)
def new_session() -> dict:
    """Create a new session record.

    Returns
    -------
    dict
        Newly created session payload.
    """
    return create_session()


@app.get("/sessions/{session_id}")
def load_session(session_id: str) -> dict:
    """Load an existing session.

    Parameters
    ----------
    session_id : str
        Session identifier to retrieve.

    Returns
    -------
    dict
        Session payload when found.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str) -> dict:
    """Load chat history for an existing session.

    Parameters
    ----------
    session_id : str
        Session identifier to retrieve.

    Returns
    -------
    dict
        Object containing the chat history list.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"chat_history": session.get("chat_history", [])}


class ArticleRequest(BaseModel):
    """Request model for article loading.

    Attributes
    ----------
    url : str
        Article URL to scrape and attach to a session.
    """

    url: str


@app.post("/sessions/{session_id}/article")
async def load_article(session_id: str, req: ArticleRequest) -> dict:
    """Scrape, store, and index an article for an existing session.

    Parameters
    ----------
    session_id : str
        Session identifier to update.
    req : ArticleRequest
        Request payload containing the target article URL.

    Returns
    -------
    dict
        Updated session payload.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session(session_id, status="processing", error_message=None)

    try:
        logger.info("Scraping article: %s", req.url)
        scraper = NewsArticleScraper()
        article = await asyncio.to_thread(scraper.scrape_article, req.url)
        article_dict = article.model_dump(mode="json")

        update_session(
            session_id,
            url=req.url,
            article=article_dict,
            summary=None,
            chat_history=[],
            status="idle",
            error_message=None,
        )

        context_retriever = getattr(app.state, "context_retriever", None)
        if context_retriever is not None:
            try:
                ingestion_stats = await context_retriever.ingest_article(
                    article_dict,
                    chunk_size=3,
                    chunk_overlap=1,
                )
                logger.info(
                    "Article indexed in Milvus: inserted=%d deleted=%d total=%d",
                    ingestion_stats["inserted"],
                    ingestion_stats["deleted"],
                    ingestion_stats["total"],
                )
            except Exception as exc:  # pragma: no cover - exercised in runtime environments
                logger.warning("Deferred article indexing failed for %s: %s", req.url, exc)

        logger.info("Scraping complete: %s", article.title)
        return get_session(session_id)

    except Exception as exc:
        logger.error("Scraping failed: %s", exc)
        update_session(session_id, status="error", error_message=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/sessions/{session_id}/summarize")
async def summarize_article(session_id: str) -> dict:
    """Generate a full-article summary for an existing session.

    Parameters
    ----------
    session_id : str
        Session identifier to summarize.

    Returns
    -------
    dict
        Updated session payload containing the generated summary.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("article"):
        raise HTTPException(status_code=400, detail="No article loaded in this session")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured - summarization is unavailable",
        )

    update_session(session_id, status="processing", error_message=None)

    try:
        logger.info("Generating full article summary")
        summarizer = ArticleSummarizer(anthropic_api_key=ANTHROPIC_API_KEY)
        summary = await asyncio.to_thread(
            summarizer.generate,
            session["article"]["content"],
        )
        update_session(session_id, summary=summary, status="idle")
        logger.info("Summary generation complete")
        return get_session(session_id)

    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        update_session(session_id, status="error", error_message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


class ChatRequest(BaseModel):
    """Request model for question answering.

    Attributes
    ----------
    question : str
        Non-empty user question asked against the loaded article.
    """

    question: str = Field(min_length=1)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest) -> dict:
    """Answer a user question against the session article.

    Parameters
    ----------
    session_id : str
        Session identifier to update.
    req : ChatRequest
        Request payload containing the user question.

    Returns
    -------
    dict
        Chat result payload containing the answer, critique, and passages.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("article"):
        raise HTTPException(status_code=400, detail="No article loaded in this session")
    if not VOYAGE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="VOYAGE_API_KEY is not configured - chat is unavailable",
        )
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured - chat is unavailable",
        )

    history: list[dict[str, Any]] = list(session.get("chat_history", []))
    history.append(
        {"role": "user", "content": req.question, "critique": None, "passages": []}
    )
    update_session(
        session_id,
        chat_history=history,
        status="processing",
        error_message=None,
    )

    try:
        pipeline = RagPipeline(
            voyage_api_key=VOYAGE_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
            chunk_store=getattr(app.state, "chunk_store", None),
            embeddings=getattr(app.state, "embeddings", None),
        )
        pipeline_result = await pipeline.answer_question_async(
            article=session["article"],
            query=req.question,
            k=3,
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
            ctx = "\n---\n".join(p["text"] for p in passages)
            critique = await asyncio.to_thread(
                SelfCritique(anthropic_api_key=ANTHROPIC_API_KEY).evaluate,
                req.question,
                ctx,
                answer,
            )
            critique = critique.model_dump()

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
        raise HTTPException(status_code=500, detail=str(exc))
