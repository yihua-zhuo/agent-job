"""Integration tests for CodeReviewModel ORM class.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_code_review_integration.py -v

Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import pytest

from db.models.code_review import CodeReviewModel


@pytest.mark.integration
class TestCodeReviewModelIntegration:
    """Full CodeReviewModel lifecycle via the real DB."""

    async def test_insert_and_select_roundtrip(self, db_schema, tenant_id, async_session):
        """Insert a record and retrieve it by ID — all fields match."""
        review = CodeReviewModel(
            tenant_id=tenant_id,
            user_id=99,
            language="python",
            review_type="pr_review",
            code_snippet="def hello():\n    print('world')",
            score=90,
            summary="Clean and well-structured",
        )
        async_session.add(review)
        await async_session.flush()

        result = await async_session.get(CodeReviewModel, review.id)
        assert result is not None
        assert result.id == review.id
        assert result.tenant_id == tenant_id
        assert result.user_id == 99
        assert result.language == "python"
        assert result.review_type == "pr_review"
        assert result.code_snippet == "def hello():\n    print('world')"
        assert result.score == 90
        assert result.summary == "Clean and well-structured"
        assert result.created_at is not None

    async def test_insert_with_null_optional_fields(self, db_schema, tenant_id, async_session):
        """Only required fields (tenant_id, user_id) are needed — rest are nullable."""
        review = CodeReviewModel(tenant_id=tenant_id, user_id=1)
        async_session.add(review)
        await async_session.flush()

        result = await async_session.get(CodeReviewModel, review.id)
        assert result is not None
        assert result.id == review.id
        assert result.tenant_id == tenant_id
        assert result.user_id == 1
        assert result.language is None
        assert result.review_type is None
        assert result.code_snippet is None
        assert result.score is None
        assert result.summary is None

    async def test_to_dict_returns_all_fields(self, db_schema, tenant_id, async_session):
        """to_dict() produces a complete, serialisable dict."""
        from datetime import datetime, timezone

        now = datetime(2026, 5, 22, 14, 0, 0, tzinfo=timezone.utc)  # noqa: UP017
        review = CodeReviewModel(
            tenant_id=tenant_id,
            user_id=77,
            language="go",
            review_type="security_audit",
            code_snippet="func main() {}",
            score=72,
            summary="Minor issues found",
            created_at=now,
        )
        async_session.add(review)
        await async_session.flush()

        d = review.to_dict()
        assert d["id"] == review.id
        assert d["tenant_id"] == tenant_id
        assert d["user_id"] == 77
        assert d["language"] == "go"
        assert d["review_type"] == "security_audit"
        assert d["code_snippet"] == "func main() {}"
        assert d["score"] == 72
        assert d["summary"] == "Minor issues found"
        assert "created_at" in d
        assert d["created_at"] is not None

    async def test_multi_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Records are not visible across tenant boundaries."""
        review_a = CodeReviewModel(
            tenant_id=tenant_id,
            user_id=1,
            language="rust",
            review_type="style",
            code_snippet="// todo",
            score=60,
            summary="Needs improvement",
        )
        review_b = CodeReviewModel(
            tenant_id=tenant_id_2,
            user_id=2,
            language="typescript",
            review_type="style",
            code_snippet="// todo",
            score=80,
            summary="Good work",
        )
        async_session.add(review_a)
        async_session.add(review_b)
        await async_session.flush()

        from sqlalchemy import select

        result = await async_session.execute(
            select(CodeReviewModel).where(CodeReviewModel.tenant_id == tenant_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].id == review_a.id
        assert rows[0].tenant_id == tenant_id

        result_2 = await async_session.execute(
            select(CodeReviewModel).where(CodeReviewModel.tenant_id == tenant_id_2)
        )
        rows_2 = result_2.scalars().all()
        assert len(rows_2) == 1
        assert rows_2[0].id == review_b.id
        assert rows_2[0].tenant_id == tenant_id_2
