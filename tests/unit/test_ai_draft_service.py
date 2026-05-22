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


# ---------------------------------------------------------------------------
# Mock session (no DB needed — customer lookup is the only query)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Mock gateway
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    gateway.chat = AsyncMock(
        return_value=AIResponse(
            reply="This is a draft email body.",
            suggestions=["Send now", "Edit draft"],
            actions=[
                {"type": "navigate", "label": "View Customer", "path": "/customers/1"},
                {"type": "send_email", "label": "Send Draft", "payload": {"draft_id": 1}},
            ],
        )
    )
    return gateway


@pytest.fixture
def ai_draft_service(mock_db_session, mock_gateway):
    return AiDraftService(mock_db_session, gateway=mock_gateway)


# ---------------------------------------------------------------------------
# Fixtures
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
        self, ai_draft_service, mock_db_session, mock_gateway, draft_request
    ):
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        result = await ai_draft_service.generate_draft(draft_request, tenant_id=1)

        assert isinstance(result, DraftResponse)
        assert result.body == "This is a draft email body."
        assert len(result.suggested_actions) == 2
        assert result.suggested_actions[0].label == "View Customer"
        assert result.suggested_actions[0].action_type == "navigate"

    async def test_calls_gateway_chat_with_messages(
        self, ai_draft_service, mock_db_session, mock_gateway, draft_request
    ):
        mock_customer = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        await ai_draft_service.generate_draft(draft_request, tenant_id=1)

        mock_gateway.chat.assert_called_once()
        call_args = mock_gateway.chat.call_args
        messages = call_args[0][0]
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)

    async def test_maps_actions_from_ai_response(self, ai_draft_service, mock_db_session, mock_gateway, draft_request):
        mock_customer = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        result = await ai_draft_service.generate_draft(draft_request, tenant_id=1)

        assert len(result.suggested_actions) == 2
        action = result.suggested_actions[1]
        assert action.label == "Send Draft"
        assert action.action_type == "send_email"
        assert action.payload["payload"] == {"draft_id": 1}

    async def test_works_with_sms_type(self, ai_draft_service, mock_db_session, mock_gateway, sms_draft_request):
        mock_customer = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        result = await ai_draft_service.generate_draft(sms_draft_request, tenant_id=1)
        assert isinstance(result, DraftResponse)
        assert result.body == "This is a draft email body."


# ---------------------------------------------------------------------------
# generate_draft — error paths
# ---------------------------------------------------------------------------


class TestGenerateDraftErrors:
    async def test_raises_not_found_for_missing_customer(self, mock_db_session, mock_gateway, draft_request):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        svc = AiDraftService(mock_db_session, gateway=mock_gateway)

        with pytest.raises(NotFoundException):
            await svc.generate_draft(draft_request, tenant_id=1)

    async def test_raises_validation_exception_when_gateway_returns_empty_reply(
        self, mock_db_session, mock_gateway, draft_request
    ):
        mock_customer = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        empty_gateway = MagicMock()
        empty_gateway.chat = AsyncMock(return_value=AIResponse(reply="", suggestions=None, actions=None))
        svc = AiDraftService(mock_db_session, gateway=empty_gateway)

        with pytest.raises(ValidationException):
            await svc.generate_draft(draft_request, tenant_id=1)

    async def test_raises_validation_exception_when_gateway_returns_whitespace_only(
        self, mock_db_session, mock_gateway, draft_request
    ):
        mock_customer = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer
        mock_db_session.execute.return_value = mock_result

        whitespace_gateway = MagicMock()
        whitespace_gateway.chat = AsyncMock(return_value=AIResponse(reply="   \n\t  ", suggestions=None, actions=None))
        svc = AiDraftService(mock_db_session, gateway=whitespace_gateway)

        with pytest.raises(ValidationException):
            await svc.generate_draft(draft_request, tenant_id=1)


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
