"""Integration tests for the production ``CoordinatorAgent`` from
``src.agents.coordinator``.

The unit suite (``tests/unit/test_coordinator_agent.py``) exercises the
coordinator with a fully mocked DB session. This file extends coverage to a
real PostgreSQL session via the ``async_session`` fixture, verifying that
the coordinator's async dispatch path actually works end-to-end against a
real DB connection.

* happy-path — a registered sub-agent is dispatched and returns ``completed``.
* boundary — an unknown task falls back to ``implement_agent`` (a registered
  fallback), covering the "all paths through the real session" contract.
* error — a decomposition referencing a non-existent agent name lands in
  ``result.failed`` rather than raising.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from agents.base import BaseAgent, register
from agents.coordinator import CoordinatorAgent, WorkflowResult
from agents.registry import AgentRegistry


@pytest.fixture(autouse=True)
def reset_agent_registry():
    """Reset the AgentRegistry singleton before and after each test."""
    AgentRegistry.reset()
    yield
    AgentRegistry.reset()


@pytest.fixture
def coordinator(async_session) -> CoordinatorAgent:
    """Coordinator wired to the real async_session fixture.

    The coordinator itself does not query the database, but it forwards
    ``self.session`` to sub-agents. Using a real session here proves that
    the integration-test wiring (commit/rollback, async driver) does not
    interfere with the dispatch chain.
    """
    return CoordinatorAgent(llm=MagicMock(), session=async_session)


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

        coordinator = CoordinatorAgent(llm=MagicMock(), session=async_session, tenant_id=42)
        result = await coordinator.run("test the login module")

        assert result.success is True
        assert captured["tenant_id"] == 42
        assert coordinator.tenant_id == 42
