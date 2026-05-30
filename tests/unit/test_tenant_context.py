"""Unit tests for tenant_context module."""
import asyncio

import pytest

from internal.middleware.tenant_context import (
    clear,
    get_tenant_id,
    require_tenant_id,
    set_tenant_id,
)
from pkg.errors.app_exceptions import UnauthorizedException


# NOTE: this fixture is not safe for parallel test execution (e.g. pytest-xdist).
# The clear() in yield can race with another test's set_tenant_id if tests run
# concurrently in the same process. Mark this file serial to prevent parallel
# execution; use a unique-key-per-test scoping strategy if parallel execution
# is needed.
@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Ensure every test starts and ends with a clean tenant context."""
    clear()
    yield
    clear()


# Serialize this file to prevent race conditions in parallel execution.
# Tenant context is process-global via contextvars; concurrent tests can
# interfere via the autouse fixture above.
@pytest.mark.serial
class TestTenantContext:
    def test_set_and_get_tenant_id(self):
        """Setting a tenant_id can be retrieved."""
        set_tenant_id(42)
        assert get_tenant_id() == 42

    def test_set_and_get_tenant_id_zero_boundary(self):
        """tenant_id of 0 is a valid value and is retrievable."""
        set_tenant_id(0)
        assert get_tenant_id() == 0

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

    async def test_tenant_id_propagates_via_create_task(self):
        """tenant_id is copied into a task created via asyncio.create_task()."""
        set_tenant_id(13)

        async def task_body():
            return get_tenant_id()

        task = asyncio.create_task(task_body())
        result = await task
        assert result == 13

    async def test_no_tenant_id_in_task_created_before_set(self):
        """A task created before set_tenant_id must NOT see tenant_id."""
        async def task_body():
            return get_tenant_id()

        task = asyncio.create_task(task_body())
        result = await task
        assert result is None

    def test_clear_returns_none_not_stale_value(self):
        """After clear(), get_tenant_id returns None — not a stale tenant_id.

        Ensures isolation across request boundaries (rule 126).
        """
        set_tenant_id(99)
        clear()
        assert get_tenant_id() is None

    def test_require_tenant_id_returns_value(self):
        """require_tenant_id returns the value when set."""
        set_tenant_id(42)
        assert require_tenant_id() == 42

    def test_require_tenant_id_raises_when_unset(self):
        """require_tenant_id raises UnauthorizedException when context is unset."""
        with pytest.raises(UnauthorizedException):
            require_tenant_id()
