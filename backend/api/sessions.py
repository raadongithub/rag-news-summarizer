"""Session, article, summarize, and chat endpoints."""

from fastapi import APIRouter, HTTPException, Request

from ..schema.requests import ArticleRequest, ChatRequest
from ..services import SessionService

router = APIRouter()
session_service = SessionService()


@router.post("/sessions", status_code=201)
def new_session() -> dict:
    """Create a new session."""
    return session_service.create_session()


@router.get("/sessions/{session_id}")
def load_session(session_id: str) -> dict:
    """Load an existing session by ID."""
    try:
        return session_service.get_session(session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/history")
def session_history(session_id: str) -> dict:
    """Return the chat history for a session."""
    try:
        return session_service.get_history(session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/article")
async def load_article(session_id: str, req: ArticleRequest, request: Request) -> dict:
    """Scrape and index an article for a session."""
    runtime = getattr(request.app.state, "runtime", None)
    try:
        return await session_service.load_article(
            session_id,
            req.url,
            context_retriever=getattr(runtime, "context_retriever", None),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/sessions/{session_id}/summarize")
async def summarize_article(session_id: str) -> dict:
    """Generate an article summary for a session."""
    try:
        return await session_service.summarize_article(session_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="No article loaded in this session")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest, request: Request) -> dict:
    """Answer a question against the session's article."""
    runtime = getattr(request.app.state, "runtime", None)
    try:
        return await session_service.answer_question(
            session_id,
            req.question,
            chunk_store=getattr(runtime, "chunk_store", None),
            embeddings=getattr(runtime, "embeddings", None),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="No article loaded in this session")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
