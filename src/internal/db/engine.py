"""SQLAlchemy engine, session, and base infrastructure."""

from __future__ import annotations

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

_engine = None


def create_engine_from_env():
    """Create a SQLAlchemy Engine from the DATABASE_URL environment variable.

    Raises:
        ValueError: If DATABASE_URL is not set or is empty.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(url, pool_pre_ping=True, pool_size=5)


def get_engine():
    """Get or create the singleton Engine instance."""
    global _engine
    if _engine is None:
        _engine = create_engine_from_env()
    return _engine


# Eagerly initialise the engine on module load so SessionLocal binds correctly.
_engine = create_engine_from_env()

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

Base = declarative_base()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations.

    Yields a Session. Commits on normal exit, rolls back on exception,
    and always closes the session.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
