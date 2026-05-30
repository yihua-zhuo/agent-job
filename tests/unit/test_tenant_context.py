"""Unit tests for tenant_context module."""

import pytest

from internal.middleware.tenant_context import clear, get_tenant_id, set_tenant_id


class TestTenantContext:
    def test_set_and_get_tenant_id(self):
        """Setting a tenant_id can be retrieved."""
        clear()
        set_tenant_id(42)
        assert get_tenant_id() == 42
        clear()

    def test_clear_tenant_id(self):
        """Clearing removes the stored tenant_id."""
        set_tenant_id(99)
        clear()
        assert get_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_id_propagates_across_await(self):
        """tenant_id is visible inside an awaited helper coroutine."""
        clear()
        set_tenant_id(7)

        async def helper():
            return get_tenant_id()

        result = await helper()
        assert result == 7
        clear()
