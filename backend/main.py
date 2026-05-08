import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import create_session, get_session, init_db, update_session

# ai/ is on sys.path via PYTHONPATH=/app when run as `uvicorn backend.main:app`
from ai.retriever import ContextRetriever
from ai.scraper import NewsArticleScraper
from ai.summary import ArticleSummarizer, SelfCritique, SummaryGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

app = FastAPI(title="News Summarizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set – summarization will fail.")
    if not VOYAGE_API_KEY:
        logger.warning("VOYAGE_API_KEY is not set – chat retrieval will fail.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@app.post("/sessions", status_code=201)
def new_session() -> dict:
    return create_session()


@app.get("/sessions/{session_id}")
def load_session(session_id: str) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"chat_history": session.get("chat_history", [])}


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------


class ArticleRequest(BaseModel):
    url: str


@app.post("/sessions/{session_id}/article")
def load_article(session_id: str, req: ArticleRequest) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session(session_id, status="processing", error_message=None)

    try:
        logger.info("Scraping article: %s", req.url)
        scraper = NewsArticleScraper()
        article = scraper.scrape_article(req.url)
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
        logger.info("Scraping complete: %s", article.title)
        return get_session(session_id)

    except Exception as exc:
        logger.error("Scraping failed: %s", exc)
        update_session(session_id, status="error", error_message=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------


@app.post("/sessions/{session_id}/summarize")
def summarize_article(session_id: str) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("article"):
        raise HTTPException(status_code=400, detail="No article loaded in this session")

    update_session(session_id, status="processing", error_message=None)

    try:
        logger.info("Generating full article summary")
        summarizer = ArticleSummarizer(anthropic_api_key=ANTHROPIC_API_KEY)
        summary = summarizer.generate(session["article"]["content"])
        update_session(session_id, summary=summary, status="idle")
        logger.info("Summary generation complete")
        return get_session(session_id)

    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        update_session(session_id, status="error", error_message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str


@app.post("/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.get("article"):
        raise HTTPException(status_code=400, detail="No article loaded in this session")
    if not VOYAGE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="VOYAGE_API_KEY is not configured – chat is unavailable",
        )

    # Persist user message immediately so the session isn't empty on failure
    history: list = list(session.get("chat_history", []))
    history.append(
        {"role": "user", "content": req.question, "critique": None, "passages": []}
    )
    update_session(session_id, chat_history=history, status="processing", error_message=None)

    try:
        logger.info("Retrieving passages for: %s", req.question)
        retriever = ContextRetriever(voyage_api_key=VOYAGE_API_KEY)
        results = retriever.retrieve(
            scraped_data=session["article"], query=req.question, k=3
        )
        passages = results.get("retrieved_passages", [])

        if not passages:
            answer = "I could not find relevant information in the article to answer your question."
            critique = None
        else:
            logger.info("Generating answer")
            answer = SummaryGenerator(anthropic_api_key=ANTHROPIC_API_KEY).generate(
                req.question, passages
            )

            logger.info("Running self-critique")
            ctx = "\n---\n".join(p["text"] for p in passages)
            critique = SelfCritique(anthropic_api_key=ANTHROPIC_API_KEY).evaluate(
                req.question, ctx, answer
            ).model_dump()

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
        # Record error but keep the user message in history
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
