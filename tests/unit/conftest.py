"""Shared test fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env so DATABASE_URL is available in test environment.
_dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_dotenv_path)

# Silence SQLAlchemy 2.0 warnings during tests
import warnings

warnings.filterwarnings("ignore", category=warnings.SQLAlchemyWarning)

# Ensure project root is on sys.path so "src" imports resolve
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


@pytest.fixture
def tenant_id() -> int:
    """Return a fixed test tenant ID."""
    return 1


@pytest.fixture
def tenant_id_2() -> int:
    """Return a second fixed test tenant ID."""
    return 2
