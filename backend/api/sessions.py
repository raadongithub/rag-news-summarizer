"""Session, article, summarize, and chat endpoints."""

from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import User
from ..schema import (
    ArticleRequest,
    ChatAnswerResponse,
    ChatRequest,
    SessionHistoryResponse,
    SessionListItemResponse,
    SessionResponse,
)
from ..services import SessionService
from .dependencies import get_current_user

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _tokenize_for_streaming(answer: str) -> list[str]:
    """Split a final answer into whitespace-preserving token chunks."""

    chunks = re.findall(r"\S+\s*", answer)
    return chunks if chunks else [answer]


@router.get("", response_model=list[SessionListItemResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[dict]:
    """Return compact summaries of the authenticated user's recent sessions."""

    return SessionService(db_session).list_sessions(current_user)


@router.post("", response_model=SessionResponse, status_code=201)
def new_session(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Create a new session."""

    return SessionService(db_session).create_session(current_user)


@router.get("/{session_id}", response_model=SessionResponse)
def load_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Load an existing session by ID."""

    return SessionService(db_session).get_session(session_id, current_user)


@router.get("/{session_id}/history", response_model=SessionHistoryResponse)
def session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Return the chat history for a session."""

    return SessionService(db_session).get_history(session_id, current_user)


@router.post("/{session_id}/article", response_model=SessionResponse)
async def load_article(
    session_id: str,
    payload: ArticleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Scrape and index an article for a session."""

    runtime = getattr(request.app.state, "runtime", None)
    return await SessionService(db_session).load_article(
        session_id,
        current_user,
        str(payload.url),
        context_retriever=getattr(runtime, "context_retriever", None),
    )


@router.post("/{session_id}/summarize", response_model=SessionResponse)
async def summarize_article(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Generate an article summary for a session."""

    return await SessionService(db_session).summarize_article(session_id, current_user)


@router.post("/{session_id}/chat", response_model=ChatAnswerResponse)
async def chat(
    session_id: str,
    payload: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    """Answer a question against the session's article."""

    runtime = getattr(request.app.state, "runtime", None)
    return await SessionService(db_session).answer_question(
        session_id,
        current_user,
        payload.question,
        chunk_store=getattr(runtime, "chunk_store", None),
        embeddings=getattr(runtime, "embeddings", None),
    )


@router.post("/{session_id}/chat/stream")
async def chat_stream(
    session_id: str,
    payload: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Stream a chat answer as incremental token chunks.

    Summary generation remains strictly non-streaming and is handled by the
    summarize endpoint. This route is only for chat token streaming."""

    runtime = getattr(request.app.state, "runtime", None)

    async def stream_events():
        """Yield NDJSON events for incremental chat rendering."""

        try:
            result = await SessionService(db_session).answer_question(
                session_id,
                current_user,
                payload.question,
                chunk_store=getattr(runtime, "chunk_store", None),
                embeddings=getattr(runtime, "embeddings", None),
            )

            answer = str(result.get("answer", ""))
            for token in _tokenize_for_streaming(answer):
                yield json.dumps({"type": "token", "token": token}) + "\n"
                await asyncio.sleep(0)

            yield (
                json.dumps(
                    {
                        "type": "done",
                        "answer": answer,
                        "critique": result.get("critique"),
                        "passages": result.get("passages", []),
                    }
                )
                + "\n"
            )
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"

    return StreamingResponse(stream_events(), media_type="application/x-ndjson")
