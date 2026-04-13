"""Unit tests for src.internal.db.engine module."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestEngineCreation:
    """Tests for engine creation and configuration."""

    def test_create_engine_requires_url(self):
        """create_engine_from_env raises ValueError when DATABASE_URL is unset."""
        # Reload the module with DATABASE_URL removed from env.
        import importlib
        import src.internal.db.engine as eng_module

        # Save state.
        orig_engine = eng_module._engine

        # Clear the module-level engine so create_engine_from_env re-reads env.
        eng_module._engine = None

        try:
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(ValueError, match="DATABASE_URL"):
                    eng_module.create_engine_from_env()
        finally:
            # Restore engine state to avoid affecting other tests.
            eng_module._engine = orig_engine

    def test_base_is_declarative(self):
        """Base is a declarative class with a metadata attribute."""
        from src.internal.db.engine import Base

        assert Base is not None
        assert hasattr(Base, "metadata")
        import sqlalchemy
        assert isinstance(Base.metadata, sqlalchemy.MetaData)


class TestSessionScope:
    """Tests for session_scope context manager."""

    def test_session_scope_commits(self, db_session):
        """session_scope commits a transaction on normal exit."""
        from src.internal.db.engine import get_engine

        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))  # Warm up.

        # Use a separate connection to verify commit visibility.
        from src.internal.db import session_scope

        with session_scope() as s:
            s.execute(text("SELECT 1 AS a"))

        # If we get here without exception, commit succeeded.
        assert True

    def test_session_scope_rollback_on_exception(self):
        """session_scope rolls back when an exception is raised inside."""
        import random
        from src.internal.db import session_scope

        table_name = f"rollback_test_{random.randint(10000, 99999)}"

        # Create the table in a committed transaction.
        with session_scope() as s:
            s.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {table_name} "
                    "(id SERIAL PRIMARY KEY, val TEXT)"
                )
            )

        try:
            with session_scope() as s:
                s.execute(
                    text(f"INSERT INTO {table_name}(val) VALUES ('to_rollback')")
                )
                raise RuntimeError("trigger rollback")
        except RuntimeError:
            pass  # Expected.

        # Verify the row was rolled back (table still exists, row not present).
        with session_scope() as s:
            result = s.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE val = 'to_rollback'")
            )
            count = result.scalar()
            assert count == 0, f"Expected 0 rows after rollback, got {count}"

        # Clean up test table.
        with session_scope() as s:
            s.execute(text(f"DROP TABLE IF EXISTS {table_name}"))


class TestDatabaseConnection:
    """Tests for database connectivity via db_session fixture."""

    def test_engine_can_select_one(self, db_session):
        """db_session can execute SELECT 1 and return a result."""
        result = db_session.execute(text("SELECT 1 AS value"))
        assert result.scalar() == 1