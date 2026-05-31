"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import AppConfig, get_settings

_ENGINE = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def get_engine(settings: AppConfig | None = None):
    """Return the shared SQLAlchemy engine."""

    global _ENGINE
    if _ENGINE is None:
        resolved_settings = settings or get_settings()
        _ENGINE = create_engine(
            resolved_settings.database_url,
            pool_pre_ping=True,
        )
    return _ENGINE


def get_session_factory(settings: AppConfig | None = None) -> sessionmaker[Session]:
    """Return the shared SQLAlchemy session factory."""

    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(settings),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _SESSION_FACTORY


def get_db_session() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
