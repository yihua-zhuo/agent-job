"""Unit tests for CoordinatorAgent orchestration logic.

Exercises ``run()`` against registered sub-agents, covering happy-path,
boundary (no matching keyword falls back to implement_agent), and error
(unknown agent -> failed).
"""

# The coordinator does not touch the DB during dispatch, so we use the
# production AIChatGateway stub (deterministic, no network) and an
# AsyncMock session. AsyncMock is used here only because the coordinator
# forwards ``self.session`` to sub-agents — it never calls any session
# method itself, so no DB-backed fixture is needed.
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, register
from agents.coordinator import CoordinatorAgent, WorkflowResult
from internal.ai_gateway import AIChatGateway

# This module mutates the process-wide AgentRegistry singleton via
# @register() and the autouse reset_agent_registry fixture. Mark the whole
# module so pytest-xdist schedules tests in the same worker.
pytestmark = pytest.mark.xdist_group(name="agent_registry")


@pytest.fixture
def coordinator() -> CoordinatorAgent:
    return CoordinatorAgent(llm=AIChatGateway(), session=AsyncMock(spec=AsyncSession))


@pytest.fixture
def tenant_coordinator() -> CoordinatorAgent:
    """Coordinator with an explicit tenant_id for the propagation test."""
    return CoordinatorAgent(llm=AIChatGateway(), session=AsyncMock(spec=AsyncSession), tenant_id=42)


class TestCoordinatorAgentRun:
    """Unit tests for CoordinatorAgent.run() workflow dispatch."""

    async def test_run_dispatches_task_and_returns_completed(self, coordinator):
        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                return {"ok": True, "task": task}

        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.task_id  # non-empty UUID prefix from decompose()
        assert len(result.completed) + len(result.failed) == 1  # all subtasks accounted for
        assert len(result.completed) == 1
        assert result.completed[0].agent_name == "test_agent"
        assert result.completed[0].status == "completed"
        assert result.completed[0].result == {"ok": True, "task": "test the login module"}
        assert result.failed == []

    async def test_run_with_no_matching_keyword_falls_back_to_implement(self, coordinator):
        @register("implement_agent")
        class _Impl(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                return {"built": True}

        result = await coordinator.run("do something completely unrecognised")

        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert result.task_id  # non-empty UUID prefix from decompose()
        assert len(result.completed) + len(result.failed) == 1
        assert len(result.completed) == 1
        assert result.completed[0].agent_name == "implement_agent"
        assert result.completed[0].status == "completed"
        assert result.failed == []

    async def test_run_with_unknown_subagent_returns_failed(self, coordinator):
        # The token "test" in the task description matches the
        # ``_KEYWORD_GROUPS`` rule ``(("test",), "test_agent")`` in
        # ``agents.coordinator``, so decompose() emits a test_agent
        # subtask. Because the reset_agent_registry fixture has cleared
        # the registry and this test never re-registers test_agent,
        # _dispatch() hits the LookupError branch and the subtask lands
        # in ``result.failed`` rather than raising.
        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.task_id  # non-empty UUID prefix from decompose()
        assert len(result.completed) + len(result.failed) == 1
        assert len(result.completed) == 0
        assert len(result.failed) == 1
        assert result.failed[0].agent_name == "test_agent"
        assert result.failed[0].status == "failed"
        assert isinstance(result.failed[0].result, dict)
        assert "error" in result.failed[0].result
        assert "test_agent" in result.failed[0].result["error"]

    async def test_run_forwards_tenant_id_to_subagent(self, tenant_coordinator):
        captured: dict[str, Any] = {}

        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                captured["tenant_id"] = self.tenant_id
                return {"ok": True}

        result = await tenant_coordinator.run("test the login module")

        assert result.success is True
        assert captured["tenant_id"] == 42  # tenant_id propagated from coordinator to sub-agent
        assert tenant_coordinator.tenant_id == 42  # coordinator's own tenant_id preserved through dispatch

    async def test_run_without_tenant_id_forwards_none_to_subagent(self, coordinator):
        """A coordinator constructed without tenant_id forwards None downstream."""
        captured: dict[str, Any] = {}

        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                captured["tenant_id"] = self.tenant_id
                return {"ok": True}

        result = await coordinator.run("test the login module")

        assert result.success is True
        assert captured["tenant_id"] is None
        assert coordinator.tenant_id is None
