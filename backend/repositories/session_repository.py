"""Session persistence operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SessionRecord

_DEFAULT_SESSION_LIST_LIMIT = 20


class SessionRepository:
    """Repository for session persistence operations."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the repository.

        Parameters
        ----------
        db_session : Session
            Active SQLAlchemy session.
        """

        self.db_session = db_session

    def create(self, *, user_id: str) -> SessionRecord:
        """Create and persist a new session.

        Parameters
        ----------
        user_id : str
            Owning user identifier.

        Returns
        -------
        SessionRecord
            Newly created session record.
        """

        record = SessionRecord(
            user_id=user_id,
            chat_history_json=[],
            status="idle",
        )
        self.db_session.add(record)
        self.db_session.flush()
        return record

    def get_for_user(self, session_id: str, user_id: str) -> SessionRecord | None:
        """Return a session owned by a given user.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user_id : str
            Owning user identifier.

        Returns
        -------
        SessionRecord | None
            Matching session when present.
        """

        statement = select(SessionRecord).where(
            SessionRecord.id == session_id,
            SessionRecord.user_id == user_id,
        )
        return self.db_session.execute(statement).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: str,
        limit: int = _DEFAULT_SESSION_LIST_LIMIT,
    ) -> list[SessionRecord]:
        """Return the most recent sessions owned by a user.

        Parameters
        ----------
        user_id : str
            Owning user identifier.
        limit : int, optional
            Maximum number of records to return.

        Returns
        -------
        list[SessionRecord]
            Sessions ordered by updated_at descending.
        """

        statement = (
            select(SessionRecord)
            .where(SessionRecord.user_id == user_id)
            .order_by(SessionRecord.updated_at.desc())
            .limit(limit)
        )
        return list(self.db_session.execute(statement).scalars().all())

    def update(self, record: SessionRecord, **fields: Any) -> SessionRecord:
        """Update mutable session fields in place.

        Parameters
        ----------
        record : SessionRecord
            Session record to mutate.
        **fields : Any
            Fields to update.

        Returns
        -------
        SessionRecord
            Updated session record.
        """

        for key, value in fields.items():
            if key == "article":
                record.article_json = value
            elif key == "chat_history":
                record.chat_history_json = value
            elif key == "retrieved_passages":
                record.retrieved_passages_json = value
            else:
                setattr(record, key, value)
        self.db_session.add(record)
        self.db_session.flush()
        return record
