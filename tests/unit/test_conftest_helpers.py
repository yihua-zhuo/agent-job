"""Tests for the test infrastructure helpers added in tests/unit/conftest.py."""
import pytest
from sqlalchemy.exc import MultipleResultsFound

from tests.unit.conftest import MockRow, MockResult


# ---------------------------------------------------------------------------
# MockRow
# ---------------------------------------------------------------------------

class TestMockRow:
    def test_getitem_returns_value(self):
        row = MockRow({"id": 42, "name": "Alice"})
        assert row["id"] == 42
        assert row["name"] == "Alice"

    def test_get_with_default(self):
        row = MockRow({"id": 1})
        assert row.get("missing", 99) == 99

    def test_get_existing_key(self):
        row = MockRow({"id": 5})
        assert row.get("id") == 5

    def test_contains(self):
        row = MockRow({"id": 1})
        assert "id" in row
        assert "missing" not in row

    def test_keys(self):
        row = MockRow({"id": 1, "name": "Bob"})
        assert set(row.keys()) == {"id", "name"}

    def test_mapping_attribute(self):
        d = {"id": 7, "status": "lead"}
        row = MockRow(d)
        assert row._mapping == d

    def test_repr(self):
        row = MockRow({"id": 1})
        assert "MockRow" in repr(row)


# ---------------------------------------------------------------------------
# MockResult — fetchone / fetchall
# ---------------------------------------------------------------------------

class TestMockResultFetchMethods:
    def test_fetchone_returns_first_row(self):
        row = MockRow({"id": 1})
        result = MockResult([row])
        assert result.fetchone() is row

    def test_fetchone_returns_none_when_empty(self):
        result = MockResult([])
        assert result.fetchone() is None

    def test_fetchall_returns_all_rows(self):
        rows = [MockRow({"id": i}) for i in range(3)]
        result = MockResult(rows)
        assert result.fetchall() == rows

    def test_fetchall_empty(self):
        result = MockResult([])
        assert result.fetchall() == []

    def test_default_empty_rows(self):
        result = MockResult()
        assert result.fetchall() == []


# ---------------------------------------------------------------------------
# MockResult — mappings().one_or_none()  (the newly added method)
# ---------------------------------------------------------------------------

class TestMockResultMappings:
    """Tests for the new MockResult.mappings() method added in conftest.py."""

    def test_one_or_none_returns_none_when_empty(self):
        result = MockResult([])
        assert result.mappings().one_or_none() is None

    def test_one_or_none_returns_single_row(self):
        row = MockRow({"id": 1})
        result = MockResult([row])
        assert result.mappings().one_or_none() is row

    def test_one_or_none_raises_when_multiple_rows(self):
        rows = [MockRow({"id": 1}), MockRow({"id": 2})]
        result = MockResult(rows)
        with pytest.raises(MultipleResultsFound):
            result.mappings().one_or_none()

    def test_mappings_all_returns_all_rows(self):
        rows = [MockRow({"id": i}) for i in range(4)]
        result = MockResult(rows)
        assert result.mappings().all() == rows

    def test_mappings_all_empty(self):
        result = MockResult([])
        assert result.mappings().all() == []

    def test_one_or_none_with_exactly_three_rows_raises(self):
        """Boundary: 3 rows still raises MultipleResultsFound."""
        rows = [MockRow({"id": i}) for i in range(3)]
        result = MockResult(rows)
        with pytest.raises(MultipleResultsFound):
            result.mappings().one_or_none()


# ---------------------------------------------------------------------------
# MockResult — scalars / scalar methods
# ---------------------------------------------------------------------------

class TestMockResultScalars:
    def test_scalar_returns_first_row(self):
        result = MockResult([42])
        assert result.scalar() == 42

    def test_scalar_returns_none_when_empty(self):
        result = MockResult([])
        assert result.scalar() is None

    def test_scalar_one_or_none_returns_none_when_empty(self):
        result = MockResult([])
        assert result.scalar_one_or_none() is None

    def test_scalar_one_or_none_returns_value(self):
        result = MockResult([99])
        assert result.scalar_one_or_none() == 99

    def test_scalar_one_returns_value(self):
        result = MockResult([7])
        assert result.scalar_one() == 7

    def test_iter(self):
        rows = [MockRow({"id": i}) for i in range(3)]
        result = MockResult(rows)
        assert list(result) == rows


# ---------------------------------------------------------------------------
# _make_mock_session — key SQL routing behaviours
# ---------------------------------------------------------------------------

class TestMakeMockSession:
    """Tests for the session mock's SQL dispatch logic updated in this PR."""

    def test_insert_customers_returns_row(self):
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text

        session = _make_mock_session()
        sql = text("INSERT INTO customers (...) RETURNING *")
        result = session.execute(sql, {"tenant_id": 5, "name": "Test"})
        # execute is AsyncMock, get the return value synchronously
        import asyncio
        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)
        assert result is not None

    def test_select_from_customers_where_id_returns_single_row_for_id_1(self):
        """New SQL-matching logic: 'from customers where id' returns row only for id=1."""
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("SELECT * FROM customers WHERE id = :id")

        coro = session.execute(sql, {"id": 1})
        result = asyncio.get_event_loop().run_until_complete(coro)
        row = result.mappings().one_or_none()
        assert row is not None
        assert row["id"] == 1

    def test_select_from_customers_where_id_returns_empty_for_id_9999(self):
        """New SQL-matching logic: non-fixture IDs return empty result."""
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("SELECT * FROM customers WHERE id = :id")

        coro = session.execute(sql, {"id": 9999})
        result = asyncio.get_event_loop().run_until_complete(coro)
        row = result.mappings().one_or_none()
        assert row is None

    def test_select_all_customers_returns_two_rows(self):
        """New logic: SELECT without WHERE id returns list of 2 fixture rows."""
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("SELECT * FROM customers WHERE tenant_id = :tenant_id LIMIT 20 OFFSET 0")

        coro = session.execute(sql, {"tenant_id": 1})
        result = asyncio.get_event_loop().run_until_complete(coro)
        rows = result.fetchall()
        assert len(rows) == 2

    def test_delete_customers_returns_row(self):
        """New logic: DELETE FROM customers returns a row with id."""
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("DELETE FROM customers WHERE id = :id RETURNING id")

        coro = session.execute(sql, {"id": 1})
        result = asyncio.get_event_loop().run_until_complete(coro)
        row = result.mappings().one_or_none()
        assert row is not None
        assert row["id"] == 1

    def test_count_query_returns_scalar(self):
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("SELECT count(*) FROM customers WHERE tenant_id = :tenant_id")

        coro = session.execute(sql, {"tenant_id": 1})
        result = asyncio.get_event_loop().run_until_complete(coro)
        assert result.scalar() == 3

    def test_unknown_sql_returns_empty(self):
        """Default case: unrecognised SQL returns empty MockResult."""
        from tests.unit.conftest import _make_mock_session
        from sqlalchemy import text
        import asyncio

        session = _make_mock_session()
        sql = text("SELECT * FROM unknown_table WHERE x = :x")

        coro = session.execute(sql, {"x": 1})
        result = asyncio.get_event_loop().run_until_complete(coro)
        assert result.fetchall() == []