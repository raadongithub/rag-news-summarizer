"""User persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User


class UserQueries:
    """Repository for user persistence operations."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the repository."""

        self.db_session = db_session

    def create(self, *, email: str, password_hash: str) -> User:
        """Create and persist a user."""

        user = User(email=email, password_hash=password_hash)
        self.db_session.add(user)
        self.db_session.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        """Return a user by email."""

        statement = select(User).where(User.email == email)
        return self.db_session.execute(statement).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> User | None:
        """Return a user by identifier."""

        statement = select(User).where(User.id == user_id)
        return self.db_session.execute(statement).scalar_one_or_none()
