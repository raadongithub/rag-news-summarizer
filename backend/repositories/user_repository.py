"""User persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User


class UserRepository:
    """Repository for user persistence operations."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the repository.

        Parameters
        ----------
        db_session : Session
            Active SQLAlchemy session.
        """

        self.db_session = db_session

    def create(self, *, email: str, password_hash: str) -> User:
        """Create and persist a user.

        Parameters
        ----------
        email : str
            User email address.
        password_hash : str
            Encoded password hash.

        Returns
        -------
        User
            Persisted user entity.
        """

        user = User(email=email, password_hash=password_hash)
        self.db_session.add(user)
        self.db_session.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        """Return a user by email.

        Parameters
        ----------
        email : str
            Email address to look up.

        Returns
        -------
        User | None
            Matching user when present.
        """

        statement = select(User).where(User.email == email)
        return self.db_session.execute(statement).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> User | None:
        """Return a user by identifier.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        User | None
            Matching user when present.
        """

        statement = select(User).where(User.id == user_id)
        return self.db_session.execute(statement).scalar_one_or_none()
