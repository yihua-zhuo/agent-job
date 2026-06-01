"""Unit tests for ChatService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pkg.errors.app_exceptions import ValidationException
from services.chat_service import ChatService


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockRow:
    def __init__(self, mapping):
        self._mapping = mapping

    def __getitem__(self, key):
        return self._mapping[key]

    def __contains__(self, key):
        return key in self._mapping

    def keys(self):
        return self._mapping.keys()

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def to_dict(self):
        return self._mapping


class MockResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        class _Scalars:
            def all(self):
                return self._rows

            def first(self):
                return self._rows[0] if self._rows else None

        s = _Scalars()
        s._rows = self._rows
        return s


def _make_opportunity_row(tenant_id=1, opp_id=1, name="Opportunity A", customer_id=1, created_at=None):
    return MockRow({
        "id": opp_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "name": name,
        "stage": "qualification",
        "amount": "1000.00",
        "probability": 20,
        "expected_close_date": None,
        "owner_id": 1,
        "pipeline_id": 1,
        "created_at": created_at,
        "updated_at": None,
    })


def _make_ticket_row(tenant_id=1, ticket_id=1, subject="Issue A", description="Desc", status="open", created_at=None):
    return MockRow({
        "id": ticket_id,
        "tenant_id": tenant_id,
        "subject": subject,
        "description": description,
        "status": status,
        "priority": "medium",
        "channel": "email",
        "customer_id": 1,
        "assigned_to": None,
        "sla_level": "standard",
        "resolved_at": None,
        "first_response_at": None,
        "response_deadline": None,
        "created_at": created_at,
        "updated_at": None,
    })


def _make_customer_row(tenant_id=1, customer_id=1, name="Customer A", email="a@test.com", created_at=None):
    return MockRow({
        "id": customer_id,
        "tenant_id": tenant_id,
        "name": name,
        "email": email,
        "phone": "123",
        "company": "Acme",
        "status": "lead",
        "owner_id": 1,
        "tags": [],
        "assigned_at": None,
        "recycle_count": 0,
        "recycle_history": [],
        "created_at": created_at,
        "updated_at": None,
    })


def _extract_tenant_id(params: dict) -> int:
    """Extract tenant_id from compiled SQL params dict (handles SQLAlchemy name variants)."""
    return params.get("tenant_id") or params.get("tenant_id_1") or 0


def _make_customer_handler(tenant_filter_rows=None):
    """Return a handler for customer SELECT queries."""

    def handler(sql_text, params):
        if "select" in sql_text and "from customers" in sql_text and "where id" not in sql_text:
            tenant_id = _extract_tenant_id(params)
            rows = []
            # Seeded rows override default fixtures.
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = tenant_filter_rows[tenant_id]
            else:
                rows = [
                    _make_customer_row(tenant_id=tenant_id, customer_id=1, name="Customer A", email="a@test.com"),
                    _make_customer_row(tenant_id=tenant_id, customer_id=2, name="Customer B", email="b@test.com"),
                ]
            return MockResult(rows)
        return None

    return handler


def _make_opportunity_handler(tenant_filter_rows=None):
    """Return a handler for opportunity SELECT queries."""

    def handler(sql_text, params):
        if "select" in sql_text and "from opportunities" in sql_text:
            tenant_id = _extract_tenant_id(params)
            rows = []
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = tenant_filter_rows[tenant_id]
            else:
                rows = [
                    _make_opportunity_row(tenant_id=tenant_id, opp_id=1, name="Opportunity A", customer_id=1),
                    _make_opportunity_row(tenant_id=tenant_id, opp_id=2, name="Opportunity B", customer_id=2),
                ]
            return MockResult(rows)
        return None

    return handler


def _make_ticket_handler(tenant_filter_rows=None):
    """Return a handler for ticket SELECT queries."""

    def handler(sql_text, params):
        if "select" in sql_text and "from tickets" in sql_text:
            tenant_id = _extract_tenant_id(params)
            rows = []
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = tenant_filter_rows[tenant_id]
            else:
                rows = [
                    _make_ticket_row(tenant_id=tenant_id, ticket_id=1, subject="Issue A", description="Desc A", status="open"),
                    _make_ticket_row(tenant_id=tenant_id, ticket_id=2, subject="Issue B", description="Desc B", status="resolved"),
                ]
            return MockResult(rows)
        return None

    return handler


def make_chat_mock_session(tenant_filter_rows=None):
    """Build a mock AsyncSession for ChatService tests."""
    session = MagicMock()

    async def _execute(sql, params=None):
        from sqlalchemy.sql.elements import ClauseElement
        from sqlalchemy.exc import CompileError

        sql_text = str(sql).lower().strip()
        bound_params = {}

        # Extract params from compiled SQLAlchemy expression
        try:
            if isinstance(sql, ClauseElement):
                compiled_params = getattr(sql.compile(), "params", {}) or {}
                bound_params.update(compiled_params)
        except (TypeError, AttributeError, RuntimeError, CompileError):
            pass

        # Caller-supplied params override compiled params
        bound_params.update(params or {})

        return (
            _make_customer_handler(tenant_filter_rows)(sql_text, bound_params) or
            _make_opportunity_handler(tenant_filter_rows)(sql_text, bound_params) or
            _make_ticket_handler(tenant_filter_rows)(sql_text, bound_params) or
            MockResult([])
        )

    session.execute = AsyncMock(side_effect=_execute)
    return session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Default mock session with no seeded rows."""
    return make_chat_mock_session()


@pytest.fixture
def tenant_filter_rows():
    """Seeded rows per tenant."""
    return {
        1: [
            _make_customer_row(tenant_id=1, customer_id=10, name="Alpha", email="alpha@test.com"),
            _make_customer_row(tenant_id=1, customer_id=11, name="Beta", email="beta@test.com"),
        ],
        2: [
            _make_customer_row(tenant_id=2, customer_id=20, name="Gamma", email="gamma@test.com"),
        ],
    }


@pytest.fixture
def seeded_session(tenant_filter_rows):
    return make_chat_mock_session(tenant_filter_rows)


# ---------------------------------------------------------------------------
# classify_intent tests
# ---------------------------------------------------------------------------

class TestClassifyIntent:
    """Tests for classify_intent()."""

    @pytest.mark.asyncio
    async def test_customer_lookup_regex(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("show me that customer") == "customer_lookup"

    @pytest.mark.asyncio
    async def test_ticket_query_regex(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("I have a ticket about billing") == "ticket_query"

    @pytest.mark.asyncio
    async def test_sales_summary_regex_deal(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("how many deals closed this month") == "sales_summary"

    @pytest.mark.asyncio
    async def test_sales_summary_regex_revenue(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("revenue is up this quarter") == "sales_summary"

    @pytest.mark.asyncio
    async def test_sales_summary_regex_pipeline(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("check the pipeline status") == "sales_summary"

    @pytest.mark.asyncio
    async def test_sales_summary_regex_opportunity(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("new opportunity for enterprise") == "sales_summary"

    @pytest.mark.asyncio
    async def test_sales_summary_regex_forecast(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("quarterly forecast looks strong") == "sales_summary"

    @pytest.mark.asyncio
    async def test_general_no_match(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("hello world how are you") == "general"

    @pytest.mark.asyncio
    async def test_general_ignores_noise(self, mock_db_session):
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("please process this request") == "general"

    @pytest.mark.asyncio
    async def test_empty_text_raises(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException) as exc_info:
            await svc.classify_intent("")
        assert "empty" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_raises(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.classify_intent("   ")

    @pytest.mark.asyncio
    async def test_keyword_fallback_longest_wins(self, mock_db_session):
        svc = ChatService(mock_db_session)
        # "deals" is longer than "deal" — should still hit sales_summary via regex
        assert await svc.classify_intent("deals with enterprise clients") == "sales_summary"


# ---------------------------------------------------------------------------
# query_customers tests
# ---------------------------------------------------------------------------

class TestQueryCustomers:
    """Tests for query_customers()."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_customers(tenant_id=1)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, seeded_session):
        svc = ChatService(seeded_session)
        result_1 = await svc.query_customers(tenant_id=1)
        result_2 = await svc.query_customers(tenant_id=2)
        # Tenant 1 seeded with Alpha/Beta, tenant 2 seeded with Gamma
        names_1 = {r["name"] for r in result_1}
        names_2 = {r["name"] for r in result_2}
        assert "Alpha" in names_1
        assert "Gamma" in names_2
        assert names_1 != names_2  # different tenants return different rows

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_customers(tenant_id=1, keyword="Alpha")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_limit_validation_zero(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_customers(tenant_id=1, limit=0)

    @pytest.mark.asyncio
    async def test_limit_validation_negative(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_customers(tenant_id=1, limit=-1)

    @pytest.mark.asyncio
    async def test_limit_validation_exceeds_200(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_customers(tenant_id=1, limit=201)

    @pytest.mark.asyncio
    async def test_limit_boundary_200_ok(self, mock_db_session):
        svc = ChatService(mock_db_session)
        result = await svc.query_customers(tenant_id=1, limit=200)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# query_opportunities tests
# ---------------------------------------------------------------------------

class TestQueryOpportunities:
    """Tests for query_opportunities()."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_opportunities(tenant_id=1)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_opportunities(tenant_id=1, keyword="Opportunity")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_numeric_keyword_matches_customer_id(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_opportunities(tenant_id=1, keyword="1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_limit_validation_zero(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_opportunities(tenant_id=1, limit=0)

    @pytest.mark.asyncio
    async def test_limit_validation_negative(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_opportunities(tenant_id=1, limit=-1)

    @pytest.mark.asyncio
    async def test_limit_validation_exceeds_200(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_opportunities(tenant_id=1, limit=201)


# ---------------------------------------------------------------------------
# query_tickets tests
# ---------------------------------------------------------------------------

class TestQueryTickets:
    """Tests for query_tickets()."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1, keyword="Issue")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_status_filter(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1, status="open")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_limit_validation_zero(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_tickets(tenant_id=1, limit=0)

    @pytest.mark.asyncio
    async def test_limit_validation_negative(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_tickets(tenant_id=1, limit=-1)

    @pytest.mark.asyncio
    async def test_limit_validation_exceeds_200(self, mock_db_session):
        svc = ChatService(mock_db_session)
        with pytest.raises(ValidationException):
            await svc.query_tickets(tenant_id=1, limit=201)


# ---------------------------------------------------------------------------
# handle_message tests
# ---------------------------------------------------------------------------

class TestHandleMessage:
    """Tests for handle_message()."""

    @pytest.mark.asyncio
    async def test_customer_lookup_intent(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("show me that customer", tenant_id=1)
        assert result["intent"] == "customer_lookup"
        assert isinstance(result["query_results"], list)
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_sales_summary_intent(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("how many deals do we have", tenant_id=1)
        assert result["intent"] == "sales_summary"
        assert isinstance(result["query_results"], list)
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_ticket_query_intent(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("I have a ticket about billing", tenant_id=1)
        assert result["intent"] == "ticket_query"
        assert isinstance(result["query_results"], list)
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_general_intent_no_query(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("hello world", tenant_id=1)
        assert result["intent"] == "general"
        assert result["query_results"] is None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_empty_message_returns_general(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("", tenant_id=1)
        assert result["intent"] == "general"
        assert result["query_results"] is None
        assert result["error"] == "empty message"

    @pytest.mark.asyncio
    async def test_whitespace_message_returns_general(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("   ", tenant_id=1)
        assert result["intent"] == "general"
        assert result["query_results"] is None
        assert result["error"] == "empty message"

    @pytest.mark.asyncio
    async def test_result_has_expected_keys(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.handle_message("show me customers", tenant_id=1)
        assert set(result.keys()) == {"intent", "query_results", "error"}
