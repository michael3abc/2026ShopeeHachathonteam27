"""Synchronous SQLAlchemy session construction for Provider Protocols."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://return_agent:return_agent@localhost:5432/return_agent"
)


def database_url() -> str:
    """Return the explicit deployment URL or the local Compose default."""

    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_database_engine(url: str | None = None) -> Engine:
    """Create an engine without opening a database connection eagerly."""

    return create_engine(url or database_url(), pool_pre_ping=True)


def create_session_factory(url: str | None = None) -> sessionmaker[Session]:
    """Create sessions suitable for synchronous provider implementations."""

    return sessionmaker(
        bind=create_database_engine(url),
        expire_on_commit=False,
    )
