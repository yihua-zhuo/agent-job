"""Unit tests for src/services/agent_service.py — AgentService dispatch and status."""

from unittest.mock import MagicMock

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.agent_service import AgentService


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def llm_service():
    return MagicMock()


@pytest.fixture
def registry():
    return MagicMock()


@pytest.fixture
def agent_service(session, llm_service, registry):
    return AgentService(session, llm_service, registry)


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    async def test_dispatch_success(self, agent_service, registry):
        """dispatch() returns the agent's run() result and looks up the agent by type."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = MagicMock(return_value={"result": "ok"})

        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        registry.get = MagicMock(return_value=mock_agent_cls)

        result = await agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert result == {"result": "ok"}
        registry.get.assert_called_once_with("greeting")
        mock_agent_instance.run.assert_called_once_with("hi")

    async def test_dispatch_unknown_type_raises_not_found(self, agent_service, registry):
        """dispatch() raises NotFoundException when the registry raises LookupError."""
        registry.get = MagicMock(side_effect=LookupError("greeting"))

        with pytest.raises(NotFoundException) as exc_info:
            await agent_service.dispatch("greeting", "hi", tenant_id=1)

        assert "greeting" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_get_status_returns_dict(self, agent_service, llm_service, registry):
        """get_status() returns llm, agents, and timestamp fields when LLM is healthy."""
        llm_service.__bool__ = MagicMock(return_value=True)
        registry.list_agents = MagicMock(return_value=["greeting", "support"])

        status = await agent_service.get_status()

        assert status["llm"] == "ok"
        assert status["agents"] == ["greeting", "support"]
        assert "timestamp" in status
        assert isinstance(status["timestamp"], str)
