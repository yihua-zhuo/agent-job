"""Unit tests for src/services/ai_draft_service.py — AiDraftService business logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from internal.ai_gateway import AIResponse
from models.ai_draft import (
    DraftContext,
    DraftRequest,
    DraftResponse,
    DraftType,
    SuggestedAction,
    TemplateType,
    ToneType,
)
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.ai_draft_service import AiDraftService
from tests.unit.conftest import MockResult, MockRow


# ---------------------------------------------------------------------------
# Mock session — use handler pattern from conftest + direct execute patching
# ---------------------------------------------------------------------------


class MockCustomerRow(MockRow):
    """A mock row representing a customer record."""

    def __init__(self, customer_id: int, tenant_id: int, name: str = "Test Customer"):
        super().__init__({
            "id": customer_id,
            "tenant_id": tenant_id,
            "name": name,
            "email": "test@example.com",
            "phone": "123",
            "company": "Acme",
            "status": "active",
            "owner_id": 1,
            "tags": "[]",
            "created_at": None,
            "updated_at": None,
        })


def make_mock_db_session(known_customer: tuple[int, int] | None = None):
    """Build a mock session that returns a customer or empty result."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.refresh = AsyncMock()
    if known_customer is not None:
        customer_id, tenant_id = known_customer
        session.execute.return_value = MockResult([MockCustomerRow(customer_id, tenant_id)])
    else:
        session.execute.return_value = MockResult([])
    return session


@pytest.fixture
def mock_db_session():
    """Mock session that returns a valid customer (id=1, tenant_id=1) for happy-path tests."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.refresh = MagicMock()
    session.execute.return_value = MockResult([MockCustomerRow(customer_id=1, tenant_id=1)])
    return session


# ---------------------------------------------------------------------------
# Stub gateways (match AIChatGateway interface)
# ---------------------------------------------------------------------------


class StubAIChatGateway:
    """Stub gateway returning a deterministic reply and actions."""

    def __init__(self, reply="This is a draft email body.", actions=None):
        self.reply = reply
        self.actions = actions or [
            {"type": "navigate", "label": "View Customer", "path": "/customers/1"},
            {"type": "send_email", "label": "Send Draft", "payload": {"draft_id": 1}},
        ]

    async def chat(self, messages):
        return AIResponse(
            reply=self.reply,
            suggestions=["Send now", "Edit draft"],
            actions=self.actions,
        )


class EmptyAIChatGateway:
    """Stub gateway that returns an empty reply."""

    async def chat(self, messages):
        return AIResponse(reply="", suggestions=None, actions=None)


class SpyAIChatGateway:
    """Spy gateway that records messages and delegates to StubAIChatGateway."""

    def __init__(self):
        self.last_messages = None
        self._inner = StubAIChatGateway()

    async def chat(self, messages):
        self.last_messages = messages
        return await self._inner.chat(messages)


@pytest.fixture
def ai_draft_service(mock_db_session):
    return AiDraftService(mock_db_session, gateway=StubAIChatGateway())


# ---------------------------------------------------------------------------
# Request fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def draft_context():
    return DraftContext(customer_id=1, opportunity_id=None, template_type=TemplateType.EMAIL)


@pytest.fixture
def draft_request(draft_context):
    return DraftRequest(
        type=DraftType.EMAIL,
        subject="Follow-up on our conversation",
        tone=ToneType.PROFESSIONAL,
        context=draft_context,
    )


@pytest.fixture
def sms_draft_request():
    return DraftRequest(
        type=DraftType.SMS,
        subject=None,
        tone=ToneType.FRIENDLY,
        context=DraftContext(customer_id=1, opportunity_id=5, template_type=TemplateType.SMS),
    )


# ---------------------------------------------------------------------------
# generate_draft — happy path
# ---------------------------------------------------------------------------


class TestGenerateDraft:
    async def test_returns_draft_response_with_non_empty_body(
        self, mock_db_session, draft_request
    ):
        svc = AiDraftService(mock_db_session, gateway=StubAIChatGateway())
        result = await svc.generate_draft(draft_request, tenant_id=1)

        assert isinstance(result, DraftResponse)
        assert result.body == "This is a draft email body."
        assert len(result.suggested_actions) == 2
        assert result.suggested_actions[0].label == "View Customer"
        assert result.suggested_actions[0].action_type == "navigate"

    async def test_calls_gateway_chat_with_messages(self, mock_db_session, draft_request):
        spy_gateway = SpyAIChatGateway()
        svc = AiDraftService(mock_db_session, gateway=spy_gateway)
        await svc.generate_draft(draft_request, tenant_id=1)

        assert spy_gateway.last_messages is not None
        messages = spy_gateway.last_messages
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        assert "email" in user_msg.lower()
        assert "professional" in user_msg.lower()
        assert "1" in user_msg  # customer_id

    async def test_maps_actions_from_ai_response(self, mock_db_session, draft_request):
        svc = AiDraftService(mock_db_session, gateway=StubAIChatGateway())
        result = await svc.generate_draft(draft_request, tenant_id=1)

        assert len(result.suggested_actions) == 2
        action = result.suggested_actions[1]
        assert action.label == "Send Draft"
        assert action.action_type == "send_email"
        assert action.payload == {"type": "send_email", "label": "Send Draft", "payload": {"draft_id": 1}}

    async def test_works_with_sms_type(self, mock_db_session, sms_draft_request):
        svc = AiDraftService(mock_db_session, gateway=StubAIChatGateway())
        result = await svc.generate_draft(sms_draft_request, tenant_id=1)
        assert isinstance(result, DraftResponse)
        assert result.body == "This is a draft email body."


# ---------------------------------------------------------------------------
# generate_draft — error paths
# ---------------------------------------------------------------------------


class TestGenerateDraftErrors:
    async def test_raises_not_found_for_missing_customer(self):
        """Customer lookup returns None → NotFoundException."""
        session = MagicMock()
        session.execute = AsyncMock(return_value=MockResult([]))
        session.add = MagicMock()
        session.flush = MagicMock()
        session.refresh = MagicMock()
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Test",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=999, template_type=TemplateType.EMAIL),
        )
        svc = AiDraftService(session, gateway=StubAIChatGateway())
        with pytest.raises(NotFoundException):
            await svc.generate_draft(request, tenant_id=1)

    async def test_raises_validation_exception_when_gateway_returns_empty_reply(
        self, mock_db_session, draft_request
    ):
        """Valid customer but gateway returns empty reply → ValidationException."""
        svc = AiDraftService(mock_db_session, gateway=EmptyAIChatGateway())
        with pytest.raises(ValidationException):
            await svc.generate_draft(draft_request, tenant_id=1)

    async def test_raises_validation_exception_when_gateway_returns_whitespace_only(
        self, mock_db_session, draft_request
    ):
        """Gateway returns whitespace-only reply → ValidationException."""
        svc = AiDraftService(mock_db_session, gateway=StubAIChatGateway(reply="   \n\t  "))
        with pytest.raises(ValidationException):
            await svc.generate_draft(draft_request, tenant_id=1)

    async def test_cross_tenant_isolation(self):
        """Tenant A cannot access tenant B's customer — NotFoundException raised."""
        customer_row = MockCustomerRow(customer_id=1, tenant_id=1)
        found_result = MockResult([customer_row])
        not_found_result = MockResult([])

        def execute_side_effect(sql, params=None):
            # When tenant_id in params is 1 → return customer; any other tenant → not found
            tenant_id_in_params = (params or {}).get("tenant_id") or (params or {}).get("tenant_id_1")
            if tenant_id_in_params == 1:
                return found_result
            return not_found_result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=execute_side_effect)
        session.add = MagicMock()
        session.flush = MagicMock()
        session.refresh = MagicMock()
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Cross-tenant test",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=1, template_type=TemplateType.EMAIL),
        )
        svc = AiDraftService(session, gateway=StubAIChatGateway())
        with pytest.raises(NotFoundException):
            await svc.generate_draft(request, tenant_id=999)


# ---------------------------------------------------------------------------
# DraftRequest — validation
# ---------------------------------------------------------------------------


class TestDraftRequestValidation:
    async def test_raises_validation_exception_when_email_missing_subject(self, draft_context):
        with pytest.raises(ValidationException):
            DraftRequest(
                type=DraftType.EMAIL,
                subject=None,
                tone=ToneType.PROFESSIONAL,
                context=draft_context,
            )

    async def test_raises_validation_exception_when_email_has_blank_subject(self, draft_context):
        """Empty or whitespace-only subjects must also be rejected for EMAIL type."""
        with pytest.raises(ValidationException):
            DraftRequest(
                type=DraftType.EMAIL,
                subject="   ",
                tone=ToneType.PROFESSIONAL,
                context=draft_context,
            )

    async def test_sms_draft_allows_missing_subject(self, draft_context):
        request = DraftRequest(
            type=DraftType.SMS,
            subject=None,
            tone=ToneType.FRIENDLY,
            context=draft_context,
        )
        assert request.type == DraftType.SMS

    async def test_email_draft_with_subject_succeeds(self, draft_context):
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Hello",
            tone=ToneType.PROFESSIONAL,
            context=draft_context,
        )
        assert request.subject == "Hello"


# ---------------------------------------------------------------------------
# DraftResponse — to_dict
# ---------------------------------------------------------------------------


class TestDraftResponse:
    async def test_to_dict_returns_model_dump(self):
        action = SuggestedAction(label="Send", action_type="send", payload={"id": 1})
        response = DraftResponse(body="Hello world", suggested_actions=[action])
        d = response.to_dict()
        assert d["body"] == "Hello world"
        assert len(d["suggested_actions"]) == 1
        assert d["suggested_actions"][0]["label"] == "Send"