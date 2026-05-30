"""Unit tests for tenant_context module."""
import pytest

from internal.middleware.tenant_context import clear, get_tenant_id, set_tenant_id


@pytest.fixture(autouse=True)
def _cleanup():
    """Guarantee tenant context is cleared before and after every test."""
    clear()
    yield
    clear()


class TestTenantContext:
    def test_set_and_get_tenant_id(self, tenant_id: int):
        """Setting a tenant_id can be retrieved."""
        set_tenant_id(tenant_id)
        assert get_tenant_id() == tenant_id

    def test_clear_tenant_id(self, tenant_id: int):
        """Clearing removes the stored tenant_id."""
        set_tenant_id(tenant_id)
        clear()
        assert get_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_id_propagates_across_await(self, tenant_id: int):
        """tenant_id is visible inside an awaited helper coroutine."""
        set_tenant_id(tenant_id)

        async def helper():
            return get_tenant_id()

        result = await helper()
        assert result == tenant_id
