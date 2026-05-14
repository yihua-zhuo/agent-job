"""Unit tests for src/services/ai_service.py — AIService business logic."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from internal.ai_gateway import AIResponse
from pkg.errors.app_exceptions import NotFoundException
from services.ai_service import AIService


# ---------------------------------------------------------------------------
# Mock ORM objects
# ---------------------------------------------------------------------------


def _mock_conversation(id=1, tenant_id=1, user_id=99, title="Test"):
    conv = MagicMock()
    conv.id = id
    conv.tenant_id = tenant_id
    conv.user_id = user_id
    conv.title = title
    conv.created_at = datetime.now(UTC)
    conv.updated_at = datetime.now(UTC)
    return conv


def _mock_message(id=1, conversation_id=1, tenant_id=1, role="user", content="Hello"):
    msg = MagicMock()
    msg.id = id
    msg.conversation_id = conversation_id
    msg.tenant_id = tenant_id
    msg.role = role
    msg.content = content
    msg.created_at = datetime.now(UTC)
    return msg


# ---------------------------------------------------------------------------
# Mock gateway
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    gateway.chat = AsyncMock(
        return_value=AIResponse(
            reply="Hello from AI!",
            suggestions=["Show customers", "Show pipeline"],
            actions=[{"type": "navigate", "label": "View Customers", "path": "/customers"}],
        )
    )
    return gateway


# ---------------------------------------------------------------------------
# Mock session
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def ai_service(mock_session, mock_gateway):
    return AIService(mock_session, gateway=mock_gateway)


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:
    async def test_creates_conversation_record(self, ai_service):
        conv = _mock_conversation(id=1, title="Test Chat")

        with patch.object(ai_service, "create_conversation", autospec=True) as mock_method:
            mock_method.return_value = conv
            result = await ai_service.create_conversation(
                tenant_id=1, user_id=99, title="Test Chat"
            )
        assert result is not None

    async def test_creates_with_null_title(self, ai_service):
        conv = _mock_conversation(id=1, title=None)

        with patch.object(ai_service, "create_conversation", autospec=True) as mock_method:
            mock_method.return_value = conv
            result = await ai_service.create_conversation(
                tenant_id=1, user_id=99, title=None
            )
        assert result is not None


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------

class TestGetConversation:
    async def test_returns_conversation(self, ai_service, mock_session):
        conv = _mock_conversation(id=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = conv
        mock_session.execute.return_value = mock_result

        result = await ai_service.get_conversation(conversation_id=1, tenant_id=1)
        assert result is not None
        assert result.id == 1

    async def test_raises_not_found_for_missing_conversation(self, ai_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(NotFoundException):
            await ai_service.get_conversation(conversation_id=9999, tenant_id=1)


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------

class TestListConversations:
    async def test_returns_conversations_and_count(self, ai_service, mock_session):
        conv1 = _mock_conversation(id=1)
        conv2 = _mock_conversation(id=2)

        count_result = MagicMock()
        count_result.scalar.return_value = 2

        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [conv1, conv2]

        mock_session.execute.side_effect = [count_result, list_result]

        items, total = await ai_service.list_conversations(tenant_id=1, user_id=99)
        assert isinstance(items, list)
        assert total == 2

    async def test_pagination_params(self, ai_service, mock_session):
        count_result = MagicMock()
        count_result.scalar.return_value = 10

        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, list_result]

        items, total = await ai_service.list_conversations(
            tenant_id=1, user_id=99, page=2, page_size=5
        )
        assert total == 10


# ---------------------------------------------------------------------------
# get_conversation_messages
# ---------------------------------------------------------------------------

class TestGetConversationMessages:
    async def test_returns_message_list(self, ai_service, mock_session):
        msgs = [
            _mock_message(id=1, role="user", content="Hello"),
            _mock_message(id=2, role="assistant", content="Hi there!"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = msgs
        mock_session.execute.return_value = mock_result

        result = await ai_service.get_conversation_messages(conversation_id=1, tenant_id=1)
        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"

    async def test_returns_empty_for_no_messages(self, ai_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await ai_service.get_conversation_messages(conversation_id=1, tenant_id=1)
        assert result == []


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    async def test_stores_user_and_assistant_messages(self, ai_service, mock_session):
        conv = _mock_conversation(id=1)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv

        msgs = [_mock_message(id=1, role="user", content="Hello")]
        msgs_result = MagicMock()
        msgs_result.scalars.return_value.all.return_value = msgs

        count_result = MagicMock()
        count_result.scalar.return_value = 3

        fetch_result = MagicMock()
        mock_cust = MagicMock()
        mock_cust.name = "Acme"
        fetch_result.scalars.return_value.all.return_value = [mock_cust]

        # 10 execute calls: get_conv(×2) + build_hist + enrich(×7) + get_conv(update)
        mock_session.execute.side_effect = [
            conv_result, conv_result, msgs_result,
            count_result, count_result, count_result, count_result, count_result,
            fetch_result, fetch_result, conv_result,
        ]

        added = []
        mock_session.add = MagicMock(side_effect=lambda obj: added.append(obj))

        result = await ai_service.send_message(
            conversation_id=1, message="Hello", tenant_id=1, user_id=99
        )
        assert result.reply == "Hello from AI!"
        assert len(added) >= 2  # user message + assistant reply

    async def test_calls_ai_gateway(self, ai_service, mock_session, mock_gateway):
        conv = _mock_conversation(id=1)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv

        msgs = [_mock_message(id=1, role="user", content="Hello")]
        msgs_result = MagicMock()
        msgs_result.scalars.return_value.all.return_value = msgs

        count_result = MagicMock()
        count_result.scalar.return_value = 3

        fetch_result = MagicMock()
        mock_cust = MagicMock()
        mock_cust.name = "Acme"
        fetch_result.scalars.return_value.all.return_value = [mock_cust]

        # 10 execute calls: get_conv (×2) + build_history (×1) + enrich_context (×7)
        mock_session.execute.side_effect = [
            conv_result,         # get_conversation
            msgs_result,         # _build_message_history
            count_result,        # _enrich_context: customer_count
            count_result,        # _enrich_context: open_ticket_count
            count_result,        # _enrich_context: opportunity_count
            count_result,        # _enrich_context: activity_count
            count_result,        # _enrich_context: task_count
            fetch_result,        # _enrich_context: recent_customers
            fetch_result,        # _enrich_context: open_tickets
            conv_result,         # get_conversation (for updated_at)
        ]

        await ai_service.send_message(
            conversation_id=1, message="Hello", tenant_id=1, user_id=99
        )
        mock_gateway.chat.assert_called_once()
        call_args = mock_gateway.chat.call_args
        messages = call_args[0][0]
        context = call_args[0][1]
        assert any(m["role"] == "user" and m["content"] == "Hello" for m in messages)
        assert "customer_count" in context

    async def test_raises_not_found_for_missing_conversation(self, ai_service, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(NotFoundException):
            await ai_service.send_message(
                conversation_id=9999, message="Hello", tenant_id=1, user_id=99
            )

    async def test_returns_chat_response(self, ai_service, mock_session, mock_gateway):
        conv = _mock_conversation(id=1)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv

        msgs = [_mock_message(id=1, role="user", content="Hello")]
        msgs_result = MagicMock()
        msgs_result.scalars.return_value.all.return_value = msgs

        count_result = MagicMock()
        count_result.scalar.return_value = 3

        fetch_result = MagicMock()
        mock_cust = MagicMock()
        mock_cust.name = "Acme"
        fetch_result.scalars.return_value.all.return_value = [mock_cust]

        mock_session.execute.side_effect = [
            conv_result, conv_result, msgs_result,
            count_result, count_result, count_result, count_result, count_result,
            fetch_result, fetch_result, conv_result,
        ]

        result = await ai_service.send_message(
            conversation_id=1, message="Hello", tenant_id=1, user_id=99
        )
        assert isinstance(result, AIResponse)
        assert result.reply == "Hello from AI!"
        assert result.suggestions == ["Show customers", "Show pipeline"]
        assert len(result.actions) == 1


# ---------------------------------------------------------------------------
# _enrich_context
# ---------------------------------------------------------------------------

class TestEnrichContext:
    async def test_enrich_context_returns_crm_counts(self, ai_service, mock_session):
        count_result = MagicMock()
        count_result.scalar.return_value = 5

        fetch_result = MagicMock()
        mock_customer = MagicMock()
        mock_customer.name = "Acme Corp"
        fetch_result.scalars.return_value.all.return_value = [mock_customer]

        # 5 count queries + 2 fetch queries = 7 calls
        mock_session.execute.side_effect = [
            count_result,  # customer_count
            count_result,  # open_ticket_count
            count_result,  # opportunity_count
            count_result,  # activity_count
            count_result,  # task_count
            fetch_result,  # recent_customers
            fetch_result,  # open_tickets
        ]

        context = await ai_service._enrich_context(tenant_id=1, user_id=99)
        assert "customer_count" in context
        assert "open_ticket_count" in context
        assert "opportunity_count" in context
        assert "activity_count" in context
        assert "task_count" in context
        assert isinstance(context["customer_count"], int)