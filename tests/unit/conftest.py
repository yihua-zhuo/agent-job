"""Shared test fixtures, including dotenv loading and db_session fixture."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env so DATABASE_URL is available in test environment.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@pytest.fixture
def db_session():
    """Provide a transactional-scoped database session.

    Opens a connection, begins a transaction, binds a Session to that
    connection, yields it, then rolls back the transaction on teardown.
    No data is ever committed to the database — zero Supabase pollution.
    """
    from src.internal.db.engine import get_engine, SessionLocal

    eng = get_engine()
    conn = eng.connect()
    conn.begin()
    session = SessionLocal(bind=conn)
    yield session
    session.close()
    conn.rollback()
    conn.close()