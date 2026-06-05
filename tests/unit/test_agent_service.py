"""Unit tests for src/services/agent_service.py — AgentService dispatch and status."""

from unittest.mock import MagicMock

import pytest

from internal.ai_gateway import AIChatGateway
from pkg.errors.app_exceptions import NotFoundException
from services.agent_service import AgentService


@pytest.fixture
def session():
    return MagicMock()


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
    def test_dispatch_success(self, agent_service, registry):
        """dispatch() returns the agent's run() result and looks up the agent by type."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = MagicMock(return_value={"result": "ok"})

        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        registry.get = MagicMock(return_value=mock_agent_cls)

        result = agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert result == {"result": "ok"}
        registry.get.assert_called_once_with("greeting")
        mock_agent_cls.assert_called_once_with(
            agent_service._llm, agent_service.session, tenant_id=1
        )
        mock_agent_instance.run.assert_called_once_with("hi")

    def test_dispatch_unknown_type_raises_not_found(self, agent_service, registry):
        """dispatch() raises NotFoundException when the registry raises LookupError."""
        registry.get = MagicMock(side_effect=LookupError("greeting"))

        with pytest.raises(NotFoundException) as exc_info:
            agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert "greeting" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_get_status_returns_dict(self, agent_service, registry):
        """get_status() returns llm, agents, tenant_id, and timestamp fields."""
        registry.list_agents = MagicMock(return_value=["greeting", "support"])

        status = await agent_service.get_status(tenant_id=42)

        assert status["llm"] == "ok"
        assert status["agents"] == ["greeting", "support"]
        assert status["tenant_id"] == 42
        assert "timestamp" in status
        assert isinstance(status["timestamp"], str)
