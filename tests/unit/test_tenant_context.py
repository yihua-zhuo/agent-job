"""Unit tests for tenant_context module."""
import pytest

from internal.middleware.tenant_context import (
    clear,
    get_tenant_id,
    require_tenant_id,
    set_tenant_id,
)
from pkg.errors.app_exceptions import UnauthorizedException


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Ensure every test starts and ends with a clean tenant context."""
    clear()
    yield
    clear()


class TestTenantContext:
    def test_set_and_get_tenant_id(self):
        """Setting a tenant_id can be retrieved."""
        set_tenant_id(42)
        assert get_tenant_id() == 42

    def test_clear_tenant_id(self):
        """Clearing removes the stored tenant_id."""
        set_tenant_id(99)
        clear()
        assert get_tenant_id() is None

    async def test_tenant_id_propagates_across_await(self):
        """tenant_id is visible inside an awaited helper coroutine."""
        set_tenant_id(7)

        async def helper():
            return get_tenant_id()

        result = await helper()
        assert result == 7

    def test_require_tenant_id_returns_value(self):
        """require_tenant_id returns the value when set."""
        set_tenant_id(42)
        assert require_tenant_id() == 42

    def test_require_tenant_id_raises_when_unset(self):
        """require_tenant_id raises UnauthorizedException when context is unset."""
        with pytest.raises(UnauthorizedException):
            require_tenant_id()
