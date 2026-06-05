"""Integration tests for CoordinatorAgent.run() using the real async_session
fixture, the db_schema and tenant_id fixtures from conftest, and the
production ``AIChatGateway`` stub (no mocks).

These tests exercise the dispatch path end-to-end against a real PostgreSQL
session so the wiring (commit/rollback, async driver) cannot silently drift
from the contract that sub-agents will see in production.
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.base import BaseAgent, register
from agents.coordinator import CoordinatorAgent, WorkflowResult
from internal.ai_gateway import AIChatGateway

# Import the domain-owned reset_agent_registry fixture so tests that register
# custom sub-agents can request it explicitly to isolate AgentRegistry state.
from tests.integration.domain_fixtures import coordinator as _coordinator_fixtures  # noqa: F401


@pytest.fixture(autouse=True)
def _reset_agent_registry():
    """Autouse wrapper that delegates to the domain-owned fixture logic,
    ensuring every test in this file gets a clean AgentRegistry.
    """
    _coordinator_fixtures.reset_agent_registry_singleton()
    yield
    _coordinator_fixtures.reset_agent_registry_singleton()


@pytest.fixture
def coordinator(async_session, tenant_id) -> CoordinatorAgent:
    """Coordinator wired to the real async_session fixture with a real
    AIChatGateway and the integration-test tenant_id. The sub-agents
    registered in these tests never invoke the LLM, so the gateway's
    deterministic stub is sufficient and no mocks are needed.
    """
    return CoordinatorAgent(llm=AIChatGateway(), session=async_session, tenant_id=tenant_id)


class TestCoordinatorAgentIntegration:
    """Integration tests for CoordinatorAgent.run() against a real async session."""

    async def test_run_dispatches_registered_subagent_and_returns_completed(
        self, coordinator, db_schema, tenant_id, async_session
    ):
        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                return {"ok": True, "task": task}

        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.task_id
        assert len(result.completed) == 1
        assert len(result.failed) == 0
        assert result.completed[0].agent_name == "test_agent"
        assert result.completed[0].status == "completed"
        assert result.completed[0].result == {"ok": True, "task": "test the login module"}

    async def test_run_with_unfamiliar_task_falls_back_to_implement_agent(
        self, coordinator, db_schema, tenant_id, async_session
    ):
        @register("implement_agent")
        class _Impl(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                return {"built": True, "task": task}

        result = await coordinator.run("do something completely unrecognised")

        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.task_id
        assert len(result.completed) == 1
        assert len(result.failed) == 0
        assert result.completed[0].agent_name == "implement_agent"
        assert result.completed[0].status == "completed"
        assert result.completed[0].result == {"built": True, "task": "do something completely unrecognised"}

    async def test_run_forwards_tenant_id_to_subagent_and_preserves_coordinator_state(
        self, db_schema, tenant_id, async_session
    ):
        captured: dict[str, Any] = {}

        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                captured["tenant_id"] = self.tenant_id
                return {"ok": True}

        coordinator = CoordinatorAgent(llm=AIChatGateway(), session=async_session, tenant_id=tenant_id)
        result = await coordinator.run("test the login module")

        assert result.success is True
        assert captured["tenant_id"] == tenant_id
        assert coordinator.tenant_id == tenant_id

    async def test_run_with_unknown_subagent_returns_failed(
        self, coordinator, db_schema, tenant_id, async_session
    ):
        """When no agent is registered for the dispatched name, the
        coordinator records the failure in ``result.failed`` instead of
        raising — this is the documented LookupError path in _dispatch().

        Depends on the autouse ``_reset_agent_registry`` fixture to ensure
        ``test_agent`` is not registered from a prior test in this file.
        """
        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.task_id
        assert len(result.completed) == 0
        assert len(result.failed) == 1
        assert result.failed[0].agent_name == "test_agent"
        assert result.failed[0].status == "failed"
        assert isinstance(result.failed[0].result, dict)
        assert "error" in result.failed[0].result
        assert "test_agent" in result.failed[0].result["error"]
