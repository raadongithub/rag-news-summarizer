"""Normalized chat ORM models (3NF)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from ..db.base import Base, TimestampMixin


class ChatMessage(Base, TimestampMixin):
    """A single chat turn (user or assistant) stored in normalized form."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)

    session = relationship("SessionRecord", back_populates="chat_messages")
    critique: Mapped["MessageCritique | None"] = relationship(
        "MessageCritique", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )
    passages: Mapped[list["MessagePassage"]] = relationship(
        "MessagePassage", back_populates="message", order_by="MessagePassage.rank", cascade="all, delete-orphan"
    )


class MessageCritique(Base):
    """Self-critique metadata for an assistant chat message (1:1 with ChatMessage)."""

    __tablename__ = "message_critiques"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_faithful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    faithfulness_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    relevance_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    message = relationship("ChatMessage", back_populates="critique")


class MessagePassage(Base):
    """A retrieved passage associated with an assistant chat message."""

    __tablename__ = "message_passages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    base_similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    article_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message = relationship("ChatMessage", back_populates="passages")
