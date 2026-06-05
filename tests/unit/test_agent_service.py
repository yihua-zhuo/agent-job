"""Unit tests for src/services/agent_service.py — AgentService dispatch and status."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from internal.ai_gateway import AIChatGateway
from pkg.errors.app_exceptions import NotFoundException
from services.agent_service import AgentService, AgentStatus


@pytest.fixture
def session():
    """AsyncSession-shaped mock — uses spec= so attribute access is type-checked."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def llm():
    return MagicMock(spec=AIChatGateway)


@pytest.fixture
def registry():
    return MagicMock()


@pytest.fixture
def agent_service(session, llm, registry):
    return AgentService(session, llm, registry)


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    async def test_dispatch_success(self, agent_service, registry, session, llm):
        """dispatch() returns the agent's run() result and looks up the agent by type."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value={"result": "ok"})

        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        registry.get = MagicMock(return_value=mock_agent_cls)

        result = await agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert result == {"result": "ok"}
        registry.get.assert_called_once_with("greeting")
        mock_agent_cls.assert_called_once_with(llm, session, tenant_id=1)
        mock_agent_instance.run.assert_awaited_once_with("hi")

    async def test_dispatch_unknown_type_raises_not_found(self, agent_service, registry):
        """dispatch() raises NotFoundException when the registry raises LookupError."""
        registry.get = MagicMock(side_effect=LookupError("greeting"))

        with pytest.raises(NotFoundException) as exc_info:
            await agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert "greeting" in str(exc_info.value.detail)

    async def test_dispatch_propagates_agent_runtime_error(self, agent_service, registry):
        """dispatch() propagates exceptions raised by the agent's run() unchanged."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("agent exploded"))

        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        registry.get = MagicMock(return_value=mock_agent_cls)

        with pytest.raises(RuntimeError, match="agent exploded"):
            await agent_service.dispatch("greeting", "hi", tenant_id=1)


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_get_status_returns_agent_status(self, agent_service, registry):
        """get_status() returns an AgentStatus dataclass with the expected fields."""
        registry.list_agents = MagicMock(return_value=["greeting", "support"])

        status = await agent_service.get_status(tenant_id=42)

        assert isinstance(status, AgentStatus)
        assert status.llm_status == "ok"
        assert status.agents == ["greeting", "support"]
        assert status.tenant_id == 42
        assert isinstance(status.checked_at, datetime)

    async def test_agent_status_to_dict_shape(self, agent_service, registry):
        """AgentStatus.to_dict() produces the legacy llm/agents/tenant_id/timestamp shape."""
        registry.list_agents = MagicMock(return_value=["greeting", "support"])

        status = await agent_service.get_status(tenant_id=42)

        payload = status.to_dict()
        assert payload["llm"] == "ok"
        assert payload["agents"] == ["greeting", "support"]
        assert payload["tenant_id"] == 42
        assert "timestamp" in payload
        assert isinstance(payload["timestamp"], str)

    @pytest.mark.parametrize(
        "tenant_id,agents",
        [
            (0, []),
            (1, ["base"]),
            (99_999_999, ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]),
        ],
    )
    async def test_get_status_timestamp_is_valid_utc_iso8601(self, agent_service, registry, tenant_id, agents):
        """get_status() emits an ISO-8601 UTC timestamp for any tenant/agent list."""
        registry.list_agents = MagicMock(return_value=agents)

        status = await agent_service.get_status(tenant_id=tenant_id)

        assert status.tenant_id == tenant_id
        assert status.agents == agents
        assert status.checked_at.tzinfo is not None
        assert status.checked_at.utcoffset().total_seconds() == 0
        parsed = datetime.fromisoformat(status.to_dict()["timestamp"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0
