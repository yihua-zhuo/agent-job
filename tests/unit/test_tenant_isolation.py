"""Unit tests for TenantService and data isolation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.tenant_service import TenantService
from services.data_isolation import (
    DataIsolationError,
    TenantScope,
    require_tenant_id,
    sanitize_tenant_write,
    get_cross_tenant_fields,
    is_cross_tenant_safe,
)


# ─────────────────────────────────────────────────────────────────────────────
#  TenantService — mocked at DB layer
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_service(mock_get_db_session):
    return TenantService(mock_get_db_session)


@pytest.mark.asyncio
class TestTenantService:
    async def test_create_tenant_success(self, tenant_service):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: [
            1, "Acme Corp", "pro", "active",
            '{"max_users": 10}', None, None,
        ][i]
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.create_tenant(
                name="Acme Corp",
                plan="pro",
                admin_email="admin@acme.com",
            )
        assert bool(result) is True
        assert result.data["name"] == "Acme Corp"
        assert result.data["plan"] == "pro"
        assert result.data["status"] == "active"

    async def test_get_tenant_not_found(self, tenant_service):
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.get_tenant(9999)
        assert bool(result) is False
        assert result.status.value == "not_found"

    async def test_get_tenant_success(self, tenant_service):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: [
            42, "Beta Org", "enterprise",
            "active", '{"sso": true}', None, None,
        ][i]
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.get_tenant(42)
        assert bool(result) is True
        assert result.data["name"] == "Beta Org"
        assert result.data["plan"] == "enterprise"

    async def test_update_tenant_not_found(self, tenant_service):
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.update_tenant(9999, name="New Name")
        assert bool(result) is False
        assert result.status.value == "not_found"

    async def test_update_tenant_no_allowed_fields(self, tenant_service):
        """Passing only disallowed fields should return NOT_FOUND (nothing to update)."""
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            # Only 'settings' (allowed) but not passed through kwargs properly
            result = await tenant_service.update_tenant(9999, name="")
        assert bool(result) is False

    async def test_update_tenant_success(self, tenant_service):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: [
            1, "Updated Name", "pro", "active", "{}", None, None,
        ][i]
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.update_tenant(1, name="Updated Name")
        assert bool(result) is True
        assert result.data["name"] == "Updated Name"

    async def test_delete_tenant_not_found(self, tenant_service):
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.delete_tenant(9999)
        assert bool(result) is False
        assert result.status.value == "not_found"

    async def test_delete_tenant_success(self, tenant_service):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: [
            1, "To Delete", "pro", "deleted", "{}", None, None,
        ][i]
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.delete_tenant(1)
        assert bool(result) is True
        assert result.data["tenant_id"] == 1

    async def test_list_tenants_paginated(self, tenant_service):
        """Mock execute returning count and rows sequentially."""
        count_result = MagicMock()
        count_result.fetchone = MagicMock(return_value=(2,))
        rows_result = MagicMock()
        rows_result.fetchall = MagicMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[count_result, rows_result])

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.list_tenants(page=2, page_size=10)
        assert bool(result) is True
        assert result.data.total == 2
        assert result.data.page == 2
        assert result.data.page_size == 10

    async def test_list_tenants_with_status_filter(self, tenant_service):
        mock_count = MagicMock()
        mock_count.fetchone = MagicMock(return_value=(2,))
        mock_rows = MagicMock()
        mock_rows.fetchall = MagicMock(return_value=[])
        mock_result = MagicMock()
        mock_result.__getitem__ = lambda self, i: [mock_count, mock_rows][i]

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.list_tenants(status="active")
        assert bool(result) is True

    async def test_get_tenant_usage(self, tenant_service):
        tenant_result = MagicMock()
        tenant_result.fetchone = MagicMock(return_value=(1,))
        user_count_result = MagicMock()
        user_count_result.fetchone = MagicMock(return_value=(7,))

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[tenant_result, user_count_result])

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.get_tenant_usage(1)
        assert bool(result) is True
        assert result.data["user_count"] == 7
        assert result.data["tenant_id"] == 1

    async def test_get_tenant_usage_not_found(self, tenant_service):
        tenant_result = MagicMock()
        tenant_result.fetchone = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=tenant_result)

        with patch("services.tenant_service.get_db_session", return_value=mock_session):
            result = await tenant_service.get_tenant_usage(9999)
        assert bool(result) is False
        assert result.status.value == "not_found"


# ─────────────────────────────────────────────────────────────────────────────
#  DataIsolation — pure unit tests (no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantScope:
    def test_filter_query_returns_only_matching_tenant(self):
        scope = TenantScope(tenant_id=5)
        records = [
            {"id": 1, "tenant_id": 5, "name": "Record A"},
            {"id": 2, "tenant_id": 99, "name": "Record B"},
            {"id": 3, "tenant_id": 5, "name": "Record C"},
        ]
        filtered = scope.filter_query(records)
        assert len(filtered) == 2
        assert all(r["tenant_id"] == 5 for r in filtered)

    def test_filter_query_empty_list(self):
        scope = TenantScope(tenant_id=1)
        assert scope.filter_query([]) == []

    def test_check_ownership_returns_true_for_matching_tenant(self):
        scope = TenantScope(tenant_id=10)
        assert scope.check_ownership({"tenant_id": 10}) is True

    def test_check_ownership_returns_false_for_different_tenant(self):
        scope = TenantScope(tenant_id=10)
        assert scope.check_ownership({"tenant_id": 99}) is False

    def test_check_ownership_returns_false_for_none(self):
        scope = TenantScope(tenant_id=1)
        assert scope.check_ownership(None) is False

    def test_check_ownership_returns_false_for_missing_tenant_id(self):
        scope = TenantScope(tenant_id=1)
        assert scope.check_ownership({"id": 1}) is False

    def test_tenant_scope_invalid_tenant_id(self):
        with pytest.raises(ValueError, match="positive integer"):
            TenantScope(tenant_id=0)
        with pytest.raises(ValueError, match="positive integer"):
            TenantScope(tenant_id=-5)

    def test_sanitize_tenant_write_injects_tenant_id(self):
        data = {"name": "Hello", "email": "a@b.com"}
        result = sanitize_tenant_write(data, tenant_id=7)
        assert result["tenant_id"] == 7
        assert result["name"] == "Hello"

    def test_sanitize_tenant_write_rejects_cross_tenant(self):
        data = {"name": "Hello", "tenant_id": 99}
        with pytest.raises(DataIsolationError, match="different tenant"):
            sanitize_tenant_write(data, tenant_id=7)

    def test_sanitize_tenant_write_allows_matching_tenant_id(self):
        data = {"name": "Hello", "tenant_id": 7}
        result = sanitize_tenant_write(data, tenant_id=7)
        assert result["tenant_id"] == 7


class TestRequireTenantIdDecorator:
    def test_raises_when_tenant_id_missing(self):
        @require_tenant_id
        def fn(tenant_id):
            return tenant_id

        with pytest.raises(DataIsolationError, match="valid tenant_id"):
            fn(None)

    def test_raises_when_tenant_id_zero(self):
        @require_tenant_id
        def fn(tenant_id):
            return tenant_id

        with pytest.raises(DataIsolationError):
            fn(0)

    def test_raises_when_tenant_id_negative(self):
        @require_tenant_id
        def fn(tenant_id):
            return tenant_id

        with pytest.raises(DataIsolationError):
            fn(-1)

    def test_passes_when_tenant_id_positive(self):
        @require_tenant_id
        def fn(tenant_id):
            return tenant_id * 2

        assert fn(tenant_id=3) == 6

    def test_raises_when_tenant_id_not_int(self):
        @require_tenant_id
        def fn(tenant_id):
            return tenant_id

        with pytest.raises(DataIsolationError):
            fn(tenant_id="abc")


class TestCrossTenantHelpers:
    def test_get_cross_tenant_fields(self):
        fields = get_cross_tenant_fields()
        assert "_system_config" in fields
        assert "_global_settings" in fields

    def test_is_cross_tenant_safe_true_for_allowed_fields(self):
        assert is_cross_tenant_safe("_system_config") is True
        assert is_cross_tenant_safe("_global_settings") is True

    def test_is_cross_tenant_safe_false_for_regular_fields(self):
        assert is_cross_tenant_safe("tenant_id") is False
        assert is_cross_tenant_safe("email") is False
        assert is_cross_tenant_safe("name") is False
