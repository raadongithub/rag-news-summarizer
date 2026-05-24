"""Serialization helpers for ORM-backed responses."""

from __future__ import annotations

from typing import Any

from ..models import SessionRecord, User


def serialize_user(user: User) -> dict[str, Any]:
    """Convert a user entity to a response payload.

    Parameters
    ----------
    user : User
        User entity to serialize.

    Returns
    -------
    dict[str, Any]
        Serialized user payload.
    """

    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def serialize_session(record: SessionRecord) -> dict[str, Any]:
    """Convert a session entity to a response payload.

    Parameters
    ----------
    record : SessionRecord
        Session entity to serialize.

    Returns
    -------
    dict[str, Any]
        Serialized session payload.
    """

    return {
        "id": record.id,
        "user_id": record.user_id,
        "url": record.url,
        "article": record.article_json,
        "summary": record.summary,
        "chat_history": record.chat_history_json or [],
        "retrieved_passages": record.retrieved_passages_json,
        "status": record.status,
        "error_message": record.error_message,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
