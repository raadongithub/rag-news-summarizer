"""Pydantic request models for the API."""

from pydantic import BaseModel, Field


class ArticleRequest(BaseModel):
    """URL of a news article to scrape and summarize."""

    url: str


class ChatRequest(BaseModel):
    """A user question to answer against the loaded article."""

    question: str = Field(min_length=1)
