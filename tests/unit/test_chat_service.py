"""Unit tests for ChatService."""

from __future__ import annotations

import pytest

from pkg.errors.app_exceptions import ValidationException
from services.chat_service import ChatService
from tests.unit.conftest import MockResult, MockState, make_mock_session

# ---------------------------------------------------------------------------
# ORM-like mock objects — used in place of MockRow so that r.to_dict()
# (called by chat_service on scalars) returns a dict rather than crashing.
# ---------------------------------------------------------------------------


class _MockChatEntity(dict):
    """Dict subclass that quacks like an ORM model for ChatService tests.

    .to_dict() returns a plain dict (copy of stored fields), matching what
    CustomerModel / OpportunityModel / TicketModel return.
    """

    __slots__ = ()

    def to_dict(self) -> dict:
        return dict(self)


class _MockCustomer(_MockChatEntity):
    pass


class _MockOpportunity(_MockChatEntity):
    pass


class _MockTicket(_MockChatEntity):
    pass


# ---------------------------------------------------------------------------
# Row factories — produce dicts accepted by the ORM-like mock classes above
# ---------------------------------------------------------------------------


def _opportunity_dict(
    tenant_id: int = 1,
    opp_id: int = 1,
    name: str = "Opportunity A",
    customer_id: int = 1,
) -> dict:
    # NOTE: _opportunity_dict uses field 'name' to match OpportunityModel.
    # The opportunity_handler in tests/unit/domain_handlers/sales.py uses
    # 'title' instead — a field-name mismatch with the ORM model.
    return {
        "id": opp_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "name": name,  # aligns with OpportunityModel.name
        "stage": "qualification",
        "amount": "1000.00",
        "probability": 20,
        "expected_close_date": None,
        "owner_id": 1,
        "pipeline_id": 1,
        "created_at": None,
        "updated_at": None,
    }


def _ticket_dict(
    tenant_id: int = 1,
    ticket_id: int = 1,
    subject: str = "Issue A",
    description: str = "Desc",
    status: str = "open",
) -> dict:
    return {
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
        "created_at": None,
        "updated_at": None,
    }


def _customer_dict(
    tenant_id: int = 1,
    customer_id: int = 1,
    name: str = "Customer A",
    email: str = "a@test.com",
) -> dict:
    return {
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
        "created_at": None,
        "updated_at": None,
    }


# ---------------------------------------------------------------------------
# Custom handlers — table-name pattern matching with bound-parameter inspection
# ---------------------------------------------------------------------------


def _make_chat_handler(tenant_filter_rows=None):
    """Return a handler that routes customer/opportunity/ticket SELECTs by table name.

    Uses table-name detection (not exact SQL text matching) to keep routing stable
    across minor ORM query-form changes. Falls back to default fixtures when no
    tenant-specific seed data is provided.

    Bound-param naming contract: ORM may emit tenant_id as "tenant_id",
    "tenant_id_1", or "tenant_id_2" depending on how many aliases are in the
    query. _get_tenant_id checks all three; if all are None it silently falls
    back to tenant 1 — print a warning to catch naming mismatches in dev.
    """

    def _get_tenant_id(params):
        """Extract tenant_id from params, handling ORM-generated numbered variants."""
        val = params.get("tenant_id") or params.get("tenant_id_1") or params.get("tenant_id_2")
        if val is None:
            # Warn early when tenant_id binding fails — most likely cause is
            # SQLAlchemy emitting a differently-named bind (e.g. "p_tenant_id").
            import warnings
            warnings.warn(f"[chat_service test] tenant_id is None in params {list(params.keys())}")
        return val or 1

    def handler(sql_text, params):
        if "from customers" in sql_text:
            tenant_id = _get_tenant_id(params)
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = [_MockCustomer(r) for r in tenant_filter_rows[tenant_id].get("customers", [])]
            else:
                rows = [
                    _MockCustomer(_customer_dict(tenant_id=tenant_id, customer_id=1, name="Customer A", email="a@test.com")),
                    _MockCustomer(_customer_dict(tenant_id=tenant_id, customer_id=2, name="Customer B", email="b@test.com")),
                ]
            return MockResult(rows)

        if "from opportunities" in sql_text:
            tenant_id = _get_tenant_id(params)
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = [_MockOpportunity(r) for r in tenant_filter_rows[tenant_id].get("opportunities", [])]
            else:
                rows = [
                    _MockOpportunity(_opportunity_dict(tenant_id=tenant_id, opp_id=1, name="Opportunity A", customer_id=1)),
                    _MockOpportunity(_opportunity_dict(tenant_id=tenant_id, opp_id=2, name="Opportunity B", customer_id=2)),
                ]
            return MockResult(rows)

        if "from tickets" in sql_text:
            tenant_id = _get_tenant_id(params)
            if tenant_filter_rows and tenant_id in tenant_filter_rows:
                rows = [_MockTicket(r) for r in tenant_filter_rows[tenant_id].get("tickets", [])]
            else:
                rows = [
                    _MockTicket(_ticket_dict(tenant_id=tenant_id, ticket_id=1, subject="Issue A", status="open")),
                    _MockTicket(_ticket_dict(tenant_id=tenant_id, ticket_id=2, subject="Issue B", status="resolved")),
                ]
            # Respect status filter from params — params["status_1"] (ORM-qualified)
            # is present when a status condition is in the WHERE clause.
            if params.get("status") or params.get("status_1"):
                status_filter = params.get("status") or params.get("status_1")
                rows = [r for r in rows if r["status"] == status_filter]
            return MockResult(rows)

        return None

    return handler


def make_chat_mock_session(tenant_filter_rows=None):
    """Build a mock AsyncSession using table-name routing.

    Routes queries by table name ("from customers", "from opportunities", "from tickets")
    using bound-parameter inspection rather than fragile SQL text matching.
    """
    state = MockState()
    state.opaque["tenant_filter_rows"] = tenant_filter_rows
    return make_mock_session([_make_chat_handler(tenant_filter_rows)], state=state)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Default mock session with no seeded rows."""
    return make_chat_mock_session()


@pytest.fixture
def tenant_filter_rows():
    """Seeded rows per tenant for all three entity types."""
    return {
        1: {
            "customers": [
                _customer_dict(tenant_id=1, customer_id=10, name="Alpha", email="alpha@test.com"),
                _customer_dict(tenant_id=1, customer_id=11, name="Beta", email="beta@test.com"),
            ],
            "opportunities": [
                _opportunity_dict(tenant_id=1, opp_id=10, name="Opp Alpha", customer_id=10),
                _opportunity_dict(tenant_id=1, opp_id=11, name="Opp Beta", customer_id=11),
            ],
            "tickets": [
                _ticket_dict(tenant_id=1, ticket_id=10, subject="Ticket Alpha", status="open"),
                _ticket_dict(tenant_id=1, ticket_id=11, subject="Ticket Beta", status="resolved"),
            ],
        },
        2: {
            "customers": [
                _customer_dict(tenant_id=2, customer_id=20, name="Gamma", email="gamma@test.com"),
            ],
            "opportunities": [
                _opportunity_dict(tenant_id=2, opp_id=20, name="Opp Gamma", customer_id=20),
            ],
            "tickets": [
                _ticket_dict(tenant_id=2, ticket_id=20, subject="Ticket Gamma", status="open"),
            ],
        },
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
    async def test_ticket_query_only_ticket_word(self, mock_db_session):
        """Test that 'ticket' alone classifies as ticket_query (not customer_lookup).

        The customer_lookup regex checks 'customer'/'customers' only, so 'ticket'
        alone hits the ticket_query pattern without needing the keyword fallback.
        """
        svc = ChatService(mock_db_session)
        assert await svc.classify_intent("open my ticket") == "ticket_query"

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
    async def test_keyword_fallback_tie_uses_first_intent(self, mock_db_session):
        svc = ChatService(mock_db_session)
        # No regex match; keyword fallback triggered. "customer" and "deals" are both
        # 8 chars — tie-break goes to whichever intent appears first in iteration order
        # (customer_lookup before sales_summary), per documented iteration-order rule.
        result = await svc.classify_intent("there is a customer and deals discussion")
        assert result == "customer_lookup"


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
    async def test_has_expected_keys(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_customers(tenant_id=1)
        for r in result:
            assert isinstance(r, dict)
            assert "name" in r
            assert "email" in r
            assert "tenant_id" in r

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, seeded_session):
        svc = ChatService(seeded_session)
        result_1 = await svc.query_customers(tenant_id=1)
        result_2 = await svc.query_customers(tenant_id=2)
        names_1 = {r["name"] for r in result_1}
        names_2 = {r["name"] for r in result_2}
        assert "Alpha" in names_1
        assert "Gamma" in names_2
        assert names_1 != names_2

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_customers(tenant_id=1, keyword="Alpha")
        assert isinstance(result, list)
        names = {r["name"] for r in result}
        assert "Alpha" in names, f"keyword='Alpha' should match customer 'Alpha', got names={names}"

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
    async def test_has_expected_keys(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_opportunities(tenant_id=1)
        for r in result:
            assert isinstance(r, dict)
            assert "name" in r
            assert "stage" in r
            assert "tenant_id" in r

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_opportunities(tenant_id=1, keyword="Alpha")
        assert isinstance(result, list)
        names = {r["name"] for r in result}
        assert "Opp Alpha" in names, f"keyword='Alpha' should match 'Opp Alpha', got names={names}"

    @pytest.mark.asyncio
    async def test_numeric_keyword_matches_customer_id(self, mock_db_session):
        """Numeric keyword '1' matches opportunities with customer_id=1 by id or name."""
        svc = ChatService(mock_db_session)
        result = await svc.query_opportunities(tenant_id=1, keyword="1")
        assert isinstance(result, list)
        # Default mock rows: (opp_id=1, customer_id=1) and (opp_id=2, customer_id=2)
        # Numeric '1' should match the opportunity with customer_id=1 (and any by name)
        assert len(result) >= 2, "numeric keyword should match at least 2 opportunities"
        customer_ids = {r["customer_id"] for r in result}
        assert 1 in customer_ids

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, seeded_session):
        svc = ChatService(seeded_session)
        result_1 = await svc.query_opportunities(tenant_id=1)
        result_2 = await svc.query_opportunities(tenant_id=2)
        names_1 = {r["name"] for r in result_1}
        names_2 = {r["name"] for r in result_2}
        assert "Opp Alpha" in names_1
        assert "Opp Gamma" in names_2
        assert names_1 != names_2

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
    async def test_has_expected_keys(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1)
        for r in result:
            assert isinstance(r, dict)
            assert "subject" in r
            assert "status" in r
            assert "tenant_id" in r

    @pytest.mark.asyncio
    async def test_with_keyword(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1, keyword="Alpha")
        assert isinstance(result, list)
        subjects = {r["subject"] for r in result}
        assert "Ticket Alpha" in subjects, f"keyword='Alpha' should match 'Ticket Alpha', got subjects={subjects}"

    @pytest.mark.asyncio
    async def test_status_filter(self, seeded_session):
        svc = ChatService(seeded_session)
        result = await svc.query_tickets(tenant_id=1, status="open")
        assert isinstance(result, list)
        statuses = {r["status"] for r in result}
        assert "open" in statuses, f"status='open' filter should include 'open' tickets, got statuses={statuses}"
        assert "resolved" not in statuses, f"status='open' filter should exclude 'resolved' tickets, got statuses={statuses}"

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, seeded_session):
        svc = ChatService(seeded_session)
        result_1 = await svc.query_tickets(tenant_id=1)
        result_2 = await svc.query_tickets(tenant_id=2)
        subjects_1 = {r["subject"] for r in result_1}
        subjects_2 = {r["subject"] for r in result_2}
        assert "Ticket Alpha" in subjects_1
        assert "Ticket Gamma" in subjects_2
        assert subjects_1 != subjects_2

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
        assert {"intent", "query_results", "error"} <= set(result.keys())
