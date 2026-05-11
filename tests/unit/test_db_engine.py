"""Unit tests for src.internal.db.engine module."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestEngineCreation:
    """Tests for engine creation and configuration."""

    def test_create_engine_requires_url(self):
        """create_engine_from_env raises ValueError when DATABASE_URL is unset."""
        import internal.db.engine as eng_module

        orig_engine = eng_module._engine
        eng_module._engine = None

        try:
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(ValueError, match="DATABASE_URL"):
                    eng_module.create_engine_from_env()
        finally:
            eng_module._engine = orig_engine

    def test_base_is_declarative(self):
        """Base is a declarative class with a metadata attribute."""
        from internal.db.engine import Base

        assert Base is not None
        assert hasattr(Base, "metadata")
        import sqlalchemy
        assert isinstance(Base.metadata, sqlalchemy.MetaData)
