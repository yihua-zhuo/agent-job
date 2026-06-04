"""Unit tests for src/dependencies/rbac.py — @require_permission decorator."""

import pytest

from dependencies.rbac import require_permission
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import ForbiddenException


class TestRequirePermission:
    def test_require_permission_returns_callable(self):
        """require_permission returns a callable usable as FastAPI.Depends."""
        result = require_permission("customer", "read")
        assert callable(result)

    @pytest.mark.asyncio
    async def test_permission_allowed_returns_ctx(self):
        """Admin role grants customer:read — returns AuthContext without raising."""
        ctx = AuthContext(user_id=1, tenant_id=1, roles=["admin"])
        guard = require_permission("customer", "read")
        result = await guard(ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_permission_denied_raises_forbidden(self):
        """Viewer lacks customer:delete — raises ForbiddenException."""
        ctx = AuthContext(user_id=2, tenant_id=1, roles=["viewer"])
        guard = require_permission("customer", "delete")
        with pytest.raises(ForbiddenException) as exc_info:
            await guard(ctx=ctx)
        assert "权限不足" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_roles_raises_forbidden(self):
        """Empty roles list — raises ForbiddenException."""
        ctx = AuthContext(user_id=3, tenant_id=1, roles=[])
        guard = require_permission("customer", "read")
        with pytest.raises(ForbiddenException) as exc_info:
            await guard(ctx=ctx)
        assert "权限不足" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_multiple_roles_one_has_permission(self):
        """Viewer+admin — admin has permission, so access is granted."""
        ctx = AuthContext(user_id=4, tenant_id=1, roles=["viewer", "admin"])
        guard = require_permission("customer", "read")
        result = await guard(ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_viewer_opportunity_read_allowed(self):
        """Viewer has opportunity:read — allowed."""
        ctx = AuthContext(user_id=5, tenant_id=None, roles=["viewer"])
        guard = require_permission("opportunity", "read")
        result = await guard(ctx=ctx)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_owner_can_do_anything(self):
        """Owner has wildcard — allowed for any resource:action."""
        ctx = AuthContext(user_id=6, tenant_id=1, roles=["owner"])
        guard = require_permission("anything", "whatsoever")
        result = await guard(ctx=ctx)
        assert result is ctx