"""Alembic migration helpers."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from ..core.config import get_settings


def get_alembic_config() -> Config:
    """Build an Alembic configuration bound to the active database URL.

    Returns
    -------
    Config
        Alembic configuration object.
    """

    settings = get_settings()
    config = Config(str(settings.project_root / "alembic.ini"))
    config.set_main_option("script_location", str(settings.project_root / "db_migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def run_migrations() -> None:
    """Apply all pending Alembic migrations.

    Returns
    -------
    None
        The database is updated in place.
    """

    command.upgrade(get_alembic_config(), "head")
