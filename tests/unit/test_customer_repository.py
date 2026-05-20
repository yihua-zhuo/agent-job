"""Unit tests for CustomerRepository — all 10 data-access methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from db.repositories.customer import CustomerRepository
from models.customer import CustomerStatus
from pkg.errors.app_exceptions import NotFoundException, ValidationException


def _make_mock_session():
    """Build a minimal mock AsyncSession for CustomerRepository.

    Key invariant: ``session.execute`` is an AsyncMock, so ``await
    session.execute(...)`` returns the mock result object.  Sub-attributes
    that are called synchronously (e.g. ``.scalar_one_or_none()``,
    ``.scalars().all()``, ``.all``) must be plain MagicMock, not AsyncMock.
    """
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()

    # Execute is async so that `await session.execute(...)` returns the mock result.
    # The mock result (returned from .return_value) has synchronous sub-attributes.
    from types import SimpleNamespace
    session.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        scalar_one_or_none=MagicMock(return_value=None),
        scalar=MagicMock(return_value=0),
        all=MagicMock(return_value=[]),
        rowcount=0,
    ))
    return session


def _row(**fields):
    """Build a mock ORM-like object from a fields dict."""
    m = MagicMock()
    for k, v in fields.items():
        setattr(m, k, v)
    return m


class TestCreate:
    """Tests for CustomerRepository.create."""

    @pytest.mark.asyncio
    async def test_create_flushes_and_returns_model(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)

        result = await repo.create({"name": "Alice", "email": "alice@example.com"}, tenant_id=1)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        added = session.add.call_args[0][0]
        assert added.name == "Alice"
        assert added.email == "alice@example.com"
        assert added.tenant_id == 1
        assert added.status == "lead"
        assert added.owner_id == 0
        assert added.tags == []
        # create returns the object (auto-assignment trigger is service-layer concern)
        assert result is added

    @pytest.mark.asyncio
    async def test_create_defaults_for_empty_dict(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)
        await repo.create({}, tenant_id=1)
        added = session.add.call_args[0][0]
        assert added.name == "Customer"
        assert added.email is None
        assert added.status == "lead"
        assert added.owner_id == 0
        assert added.tags == []


class TestGetCustomer:
    """Tests for CustomerRepository.get_customer."""

    @pytest.mark.asyncio
    async def test_returns_customer_when_found(self):
        session = _make_mock_session()
        mock_customer = _row(id=5, tenant_id=1, name="Bob")
        # scalar_one_or_none() is called synchronously — plain mock, not AsyncMock
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_customer)
        repo = CustomerRepository(session)

        result = await repo.get_customer(5, tenant_id=1)

        assert result is mock_customer

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        repo = CustomerRepository(session)

        with pytest.raises(NotFoundException, match="客户"):
            await repo.get_customer(9999, tenant_id=1)


class TestUpdateCustomer:
    """Tests for CustomerRepository.update_customer."""

    @pytest.mark.asyncio
    async def test_updates_allowed_fields_and_flushes(self):
        session = _make_mock_session()
        mock_customer = _row(
            id=1, tenant_id=1, name="Old", email=None, phone=None,
            company=None, status="lead", owner_id=0, tags=[],
            updated_at=None,
        )
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_customer)
        repo = CustomerRepository(session)

        result = await repo.update_customer(1, {"name": "New Name"}, tenant_id=1)

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(mock_customer)
        assert mock_customer.name == "New Name"

    @pytest.mark.asyncio
    async def test_raises_validation_for_invalid_status(self):
        session = _make_mock_session()
        # execute is never called because validation fails first
        repo = CustomerRepository(session)

        with pytest.raises(ValidationException, match="Invalid status"):
            await repo.update_customer(1, {"status": "not_a_real_status"}, tenant_id=1)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_allowed_fields_changed(self):
        session = _make_mock_session()
        mock_customer = _row(id=1, tenant_id=1, name="X", tags=[],
                             status="lead", owner_id=0, email=None, phone=None,
                             company=None, updated_at=None)
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_customer)
        repo = CustomerRepository(session)

        result = await repo.update_customer(1, {"tags": ["vip"]}, tenant_id=1)

        assert result is None
        session.flush.assert_not_called()


class TestDeleteCustomer:
    """Tests for CustomerRepository.delete_customer."""

    @pytest.mark.asyncio
    async def test_deletes_and_returns_id(self):
        session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute.return_value = mock_result
        repo = CustomerRepository(session)

        result = await repo.delete_customer(1, tenant_id=1)

        assert result == {"id": 1}
        session.execute.assert_awaited_once()
        # Must NOT commit — callers own the flush cycle
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_not_found_when_rowcount_zero(self):
        session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result
        repo = CustomerRepository(session)

        with pytest.raises(NotFoundException, match="客户"):
            await repo.delete_customer(9999, tenant_id=1)


class TestCountByStatus:
    """Tests for CustomerRepository.count_by_status."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_customers(self):
        session = _make_mock_session()
        # .all is called synchronously
        session.execute.return_value.all = MagicMock(return_value=[])
        repo = CustomerRepository(session)

        result = await repo.count_by_status(tenant_id=1)

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_correct_counts_per_status(self):
        session = _make_mock_session()
        session.execute.return_value.all = MagicMock(return_value=[
            ("lead", 3),
            ("opportunity", 2),
            ("customer", 1),
        ])
        repo = CustomerRepository(session)

        result = await repo.count_by_status(tenant_id=1)

        assert result[CustomerStatus.LEAD] == 3
        assert result[CustomerStatus.OPPORTUNITY] == 2
        assert result[CustomerStatus.CUSTOMER] == 1

    @pytest.mark.asyncio
    async def test_raises_validation_for_invalid_db_status(self):
        session = _make_mock_session()
        session.execute.return_value.all = MagicMock(return_value=[("unknown_status", 1)])
        repo = CustomerRepository(session)

        with pytest.raises(ValidationException, match="Invalid customer status in DB"):
            await repo.count_by_status(tenant_id=1)


class TestSearchCustomers:
    """Tests for CustomerRepository.search_customers."""

    @pytest.mark.asyncio
    async def test_empty_keyword_returns_empty_list(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)

        result = await repo.search_customers("", tenant_id=1)

        assert result == []
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_escapes_wildcards_and_queries(self):
        session = _make_mock_session()
        session.execute.return_value.scalars.return_value.all = MagicMock(return_value=[])
        repo = CustomerRepository(session)

        await repo.search_customers(r"100%_fit\\", tenant_id=1)

        session.execute.assert_awaited_once()
        stmt = session.execute.await_args.args[0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)
        assert r"100\%\_fit\\" in sql
        assert "ESCAPE" in sql

    @pytest.mark.asyncio
    async def test_returns_results(self):
        session = _make_mock_session()
        mock_customer = _row(id=1, tenant_id=1, name="Alice", email="alice@example.com")
        session.execute.return_value.scalars.return_value.all = MagicMock(return_value=[mock_customer])
        repo = CustomerRepository(session)

        result = await repo.search_customers("alice", tenant_id=1)

        assert len(result) == 1
        assert result[0] is mock_customer


class TestAddTag:
    """Tests for CustomerRepository.add_tag."""

    @pytest.mark.asyncio
    async def test_adds_new_tag_and_flushes(self):
        session = _make_mock_session()
        mock_customer = _row(id=1, tenant_id=1, tags=["existing"], updated_at=None)
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_customer)
        repo = CustomerRepository(session)

        result = await repo.add_tag(1, "vip", tenant_id=1)

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()
        assert "vip" in mock_customer.tags
        assert "existing" in mock_customer.tags

    @pytest.mark.asyncio
    async def test_raises_not_found_when_customer_missing(self):
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        repo = CustomerRepository(session)

        with pytest.raises(NotFoundException, match="客户"):
            await repo.add_tag(9999, "vip", tenant_id=1)


class TestRemoveTag:
    """Tests for CustomerRepository.remove_tag."""

    @pytest.mark.asyncio
    async def test_removes_tag_and_flushes(self):
        session = _make_mock_session()
        mock_customer = _row(id=1, tenant_id=1, tags=["vip", "enterprise"], updated_at=None)
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_customer)
        repo = CustomerRepository(session)

        result = await repo.remove_tag(1, "vip", tenant_id=1)

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()
        assert "vip" not in mock_customer.tags
        assert "enterprise" in mock_customer.tags

    @pytest.mark.asyncio
    async def test_raises_not_found_when_customer_missing(self):
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        repo = CustomerRepository(session)

        with pytest.raises(NotFoundException, match="客户"):
            await repo.remove_tag(9999, "vip", tenant_id=1)


class TestBulkImport:
    """Tests for CustomerRepository.bulk_import."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)

        result = await repo.bulk_import([], tenant_id=1)

        assert result == 0
        session.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_all_and_flushes(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)

        customers = [
            {"name": "A", "email": "a@test.com"},
            {"name": "B", "email": "b@test.com"},
        ]
        result = await repo.bulk_import(customers, tenant_id=1)

        assert result == 2
        session.add_all.assert_called_once()
        added = session.add_all.call_args[0][0]
        assert len(added) == 2
        assert added[0].name == "A"
        assert added[1].name == "B"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_defaults_for_missing_fields(self):
        session = _make_mock_session()
        repo = CustomerRepository(session)

        await repo.bulk_import([{"name": "C"}], tenant_id=1)

        added = session.add_all.call_args[0][0]
        assert added[0].email is None
        assert added[0].status == "lead"
        assert added[0].owner_id == 0
        assert added[0].tags == []