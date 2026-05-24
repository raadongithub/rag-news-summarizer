"""Session and chat request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ArticleRequest(BaseModel):
    """URL of a news article to scrape and summarize."""

    url: AnyHttpUrl


class ChatRequest(BaseModel):
    """A user question to answer against the loaded article."""

    question: str = Field(min_length=1, max_length=1000)


class CritiqueResponse(BaseModel):
    """Serialized answer critique."""

    is_faithful: bool
    faithfulness_explanation: str
    is_relevant: bool
    relevance_explanation: str
    confidence_score: float


class PassageResponse(BaseModel):
    """Serialized retrieved passage."""

    text: str
    similarity_score: float
    rank: int
    metadata: dict[str, Any] | None = None
    base_similarity_score: float | None = None


class ChatMessageResponse(BaseModel):
    """Serialized chat message."""

    role: Literal["user", "assistant"]
    content: str
    critique: CritiqueResponse | None
    passages: list[PassageResponse]


class ScrapedArticleResponse(BaseModel):
    """Serialized scraped article."""

    url: str
    title: str
    content: str
    authors: list[str]
    publish_date: str | None
    summary: str
    source_domain: str
    word_count: int
    extraction_method: str


class SessionResponse(BaseModel):
    """Serialized persisted session."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    url: str | None
    article: ScrapedArticleResponse | None
    summary: str | None
    chat_history: list[ChatMessageResponse]
    retrieved_passages: list[PassageResponse] | None
    status: Literal["idle", "processing", "error"]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SessionHistoryResponse(BaseModel):
    """Serialized chat history wrapper."""

    chat_history: list[ChatMessageResponse]


class ChatAnswerResponse(BaseModel):
    """Serialized chat answer response."""

    answer: str
    critique: CritiqueResponse | None
    passages: list[PassageResponse]
