"""Unit tests for CoordinatorAgent workflow orchestration.

Exercises the end-to-end ``run()`` and ``_dispatch()`` methods of the real
``src.agents.coordinator.CoordinatorAgent`` against registered sub-agents,
covering happy-path (task dispatch completes), boundary (no matching keyword
falls back to implement_agent), and error (unknown agent -> failed) scenarios.
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
    AgentRegistry.reset()
    yield
    AgentRegistry.reset()


@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def coordinator(mock_db_session: MagicMock) -> CoordinatorAgent:
    return CoordinatorAgent(llm=MagicMock(), session=mock_db_session)


class TestCoordinatorAgentRunWorkflow:
    """End-to-end tests for CoordinatorAgent.run() workflow dispatch."""

    async def test_run_dispatches_task_and_returns_completed(self, coordinator):
        @register("test_agent")
        class _T(BaseAgent):
            async def run(self, task: str) -> dict[str, Any]:
                return {"ok": True, "task": task}

        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is True
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
        assert len(result.completed) == 1
        assert result.completed[0].agent_name == "implement_agent"
        assert result.completed[0].status == "completed"

    async def test_run_with_unknown_subagent_returns_failed(self, coordinator):
        result = await coordinator.run("test the login module")

        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert len(result.completed) == 0
        assert len(result.failed) == 1
        assert result.failed[0].agent_name == "test_agent"
        assert result.failed[0].status == "failed"
        assert "test_agent" in result.failed[0].result["error"]
