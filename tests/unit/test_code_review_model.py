"""Unit tests for CodeReviewModel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from db.models.code_review import CodeReviewModel
from tests.unit.conftest import MockState, make_mock_session


@pytest.fixture
def mock_db_session():
    from tests.unit.domain_handlers.code_review import make_code_review_handler

    state = MockState()
    return make_mock_session([make_code_review_handler(state)], state=state)


@pytest.fixture
def code_review_service(mock_db_session):
    return CodeReviewModelTestHelper(mock_db_session)


class CodeReviewModelTestHelper:
    """Minimal test helper that exercises CodeReviewModel.to_dict()."""

    def __init__(self, session):
        self.session = session


class TestCodeReviewModelToDict:
    """Test to_dict() output shape, types, nullability."""

    def test_to_dict_full_record(self, mock_db_session):
        """to_dict() returns all fields including optional ones when set."""
        now = datetime(2026, 5, 22, 14, 0, 0, tzinfo=timezone.utc)  # noqa: UP017
        review = CodeReviewModel(
            tenant_id=1,
            user_id=10,
            language="python",
            review_type="pr_review",
            code_snippet="def foo(): pass",
            score=85,
            summary="LGTM with nits",
            created_at=now,
        )
        d = review.to_dict()
        assert d["id"] is None
        assert d["tenant_id"] == 1
        assert d["user_id"] == 10
        assert d["language"] == "python"
        assert d["review_type"] == "pr_review"
        assert d["code_snippet"] == "def foo(): pass"
        assert d["score"] == 85
        assert d["summary"] == "LGTM with nits"
        assert d["created_at"] == now.isoformat()

    def test_to_dict_optional_fields_null(self, mock_db_session):
        """to_dict() returns None for unset optional fields."""
        review = CodeReviewModel(
            tenant_id=2,
            user_id=20,
        )
        d = review.to_dict()
        assert d["id"] is None
        assert d["tenant_id"] == 2
        assert d["user_id"] == 20
        assert d["language"] is None
        assert d["review_type"] is None
        assert d["code_snippet"] is None
        assert d["score"] is None
        assert d["summary"] is None
        assert d["created_at"] is None

    def test_to_dict_iso_format_for_created_at(self, mock_db_session):
        """created_at is serialized as an ISO 8601 string."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # noqa: UP017
        review = CodeReviewModel(
            tenant_id=1,
            user_id=1,
            created_at=now,
        )
        d = review.to_dict()
        assert d["created_at"] == "2026-01-01T12:00:00+00:00"

    def test_to_dict_no_tenant_leak(self, mock_db_session):
        """to_dict() includes all model fields but no extra keys."""
        review = CodeReviewModel(tenant_id=1, user_id=1)
        d = review.to_dict()
        expected_keys = {
            "id",
            "tenant_id",
            "user_id",
            "language",
            "review_type",
            "code_snippet",
            "score",
            "summary",
            "created_at",
        }
        assert set(d.keys()) == expected_keys
