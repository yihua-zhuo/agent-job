"""Unit tests for CodeReviewModel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from db.models.code_review import CodeReviewModel


class TestCodeReviewModelInit:
    """Test __init__ field assignment and id state before flush."""

    def test_id_is_none_before_flush(self):
        """id is None on a newly constructed instance before any flush.

        id is None because CodeReviewModel.__init__ does not pre-generate IDs;
        the DB assigns the primary key on INSERT (autoincrement). Until flush,
        the instance has no id assigned.
        """
        review = CodeReviewModel(tenant_id=1, user_id=1)
        assert review.id is None

    def test_required_fields_assigned(self):
        """All required fields are correctly assigned on construction."""
        review = CodeReviewModel(tenant_id=42, user_id=99)
        assert review.tenant_id == 42
        assert review.user_id == 99
        assert review.language is None
        assert review.review_type is None
        assert review.code_snippet is None
        assert review.score is None
        assert review.summary is None
        assert review.created_at is None
        assert review.updated_at is None


class TestCodeReviewModelToDict:
    """Test to_dict() output shape, types, nullability."""

    def test_to_dict_full_record(self):
        """to_dict() returns all fields including optional ones when set."""
        now = datetime(2026, 5, 22, 14, 0, 0, tzinfo=timezone.utc)
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

    def test_to_dict_optional_fields_null(self):
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

    def test_to_dict_iso_format_for_created_at(self):
        """created_at is serialized as an ISO 8601 string."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        review = CodeReviewModel(
            tenant_id=1,
            user_id=1,
            created_at=now,
        )
        d = review.to_dict()
        assert d["created_at"] == "2026-01-01T12:00:00+00:00"

    def test_to_dict_no_extra_keys(self):
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
            "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_long_string_values(self):
        """to_dict() handles very long strings without truncation or errors."""
        long_snippet = "def " + "x" * 10000  # 10k+ char string
        review = CodeReviewModel(
            tenant_id=1,
            user_id=1,
            code_snippet=long_snippet,
            summary="x" * 5000,
        )
        d = review.to_dict()
        assert d["code_snippet"] == long_snippet
        assert d["summary"] == "x" * 5000

    def test_to_dict_empty_string_values(self):
        """to_dict() handles empty strings for text fields."""
        review = CodeReviewModel(
            tenant_id=1,
            user_id=1,
            language="",
            code_snippet="",
            summary="",
        )
        d = review.to_dict()
        assert d["language"] == ""
        assert d["code_snippet"] == ""
        assert d["summary"] == ""

    def test_to_dict_minimal_required_fields(self):
        """to_dict() works with only required fields (tenant_id, user_id)."""
        review = CodeReviewModel(tenant_id=1, user_id=1)
        d = review.to_dict()
        assert d["tenant_id"] == 1
        assert d["user_id"] == 1
        # All optional fields should be None
        for key in ("id", "language", "review_type", "code_snippet", "score", "summary", "created_at", "updated_at"):
            assert d[key] is None, f"expected {key} to be None, got {d[key]}"

    def test_score_range_validation(self):
        """Score values outside 0-100 raise ValueError."""
        for invalid in (-1, 999):
            with pytest.raises(ValueError, match="score must be between 0 and 100"):
                CodeReviewModel(tenant_id=1, user_id=1, score=invalid)

    def test_score_serialization_valid_range(self):
        """to_dict() returns the score unchanged for valid 0-100 values."""
        for score in (0, 50, 100):
            review = CodeReviewModel(tenant_id=1, user_id=1, score=score)
            d = review.to_dict()
            assert d["score"] == score, f"expected score={score}, got {d['score']}"

