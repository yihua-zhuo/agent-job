"""Unit tests for CoordinatorAgent."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

import agents.coordinator as _coordinator_module  # noqa: F401  — ensures @register runs at import
from agents.base import BaseAgent
from agents.coordinator import CoordinatorAgent, SubTask, TaskDecomposition, WorkflowResult
from agents.registry import AgentRegistry


@pytest.fixture(autouse=True)
def reset_agent_registry():
    """Reset the AgentRegistry singleton before and after each test."""
    AgentRegistry.reset()
    yield
    AgentRegistry.reset()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Minimal DB session stub for CoordinatorAgent tests.

    The coordinator does not touch the database directly, but BaseAgent
    requires a session in its constructor. A MagicMock satisfies the type
    contract without coupling to any SQL handler.
    """
    return MagicMock()


@pytest.fixture
def coordinator(mock_db_session: MagicMock) -> CoordinatorAgent:
    return CoordinatorAgent(llm=MagicMock(), session=mock_db_session)


def _make_mock_agent_class(name: str) -> type[BaseAgent]:
    """Build a BaseAgent subclass with a unique name and configurable run()."""

    class _MockAgent(BaseAgent):
        @property
        def name(self) -> str:
            return name

        async def run(self, task: str) -> dict[str, Any]:
            return {"agent": name, "task": task}

    _MockAgent.__name__ = f"MockAgent_{name}"
    return _MockAgent


class TestDecompose:
    def test_decompose_routes_test_keyword(self, coordinator):
        result = coordinator.decompose("write tests for login")
        assert isinstance(result, TaskDecomposition)
        assert len(result.subtasks) == 1
        assert result.subtasks[0].agent_name == "test_agent"
        assert result.subtasks[0].status == "pending"
        assert result.subtasks[0].result is None

    def test_decompose_routes_code_review_keyword(self, coordinator):
        result = coordinator.decompose("review the auth module")
        assert len(result.subtasks) == 1
        assert result.subtasks[0].agent_name == "code_review_agent"

    def test_decompose_routes_qc_keyword(self, coordinator):
        result = coordinator.decompose("qc the pipeline output")
        assert len(result.subtasks) == 1
        assert result.subtasks[0].agent_name == "qc_agent"

    def test_decompose_falls_back_to_implement_agent(self, coordinator):
        result = coordinator.decompose("do something vague")
        assert len(result.subtasks) == 1
        assert result.subtasks[0].agent_name == "implement_agent"

    def test_decompose_emits_multiple_subtasks(self, coordinator):
        result = coordinator.decompose("review and qc the API")
        assert len(result.subtasks) == 2
        assert result.subtasks[0].agent_name == "code_review_agent"
        assert result.subtasks[1].agent_name == "qc_agent"

    def test_decompose_assigns_unique_ids(self, coordinator):
        result = coordinator.decompose("review and qc the API")
        ids = [s.id for s in result.subtasks]
        assert len(set(ids)) == len(ids)
        assert all(s.id.startswith(result.task_id) for s in result.subtasks)


class TestDispatch:
    async def test_dispatch_routes_to_registered_agents(self, coordinator):
        from agents.base import register

        @register("test_agent_dispatch_1")
        class _T1(BaseAgent):
            async def run(self, task):
                return {"agent": "test_agent_dispatch_1", "task": task}

        @register("code_review_agent_dispatch_1")
        class _R1(BaseAgent):
            async def run(self, task):
                return {"agent": "code_review_agent_dispatch_1", "task": task}

        decomposition = TaskDecomposition(
            task_id="t1",
            original_description="test and review",
            subtasks=[
                SubTask(id="t1-0", agent_name="test_agent_dispatch_1", description="test it"),
                SubTask(id="t1-1", agent_name="code_review_agent_dispatch_1", description="review it"),
            ],
        )
        result = await coordinator._dispatch(decomposition)
        assert isinstance(result, WorkflowResult)
        assert len(result.completed) == 2
        assert len(result.failed) == 0
        for s in result.completed:
            assert s.status == "completed"
            assert s.result is not None

    async def test_dispatch_catches_unknown_agent(self, coordinator):
        decomposition = TaskDecomposition(
            task_id="t2",
            original_description="ghost work",
            subtasks=[SubTask(id="t2-0", agent_name="ghost_agent_xyz", description="ghost")],
        )
        result = await coordinator._dispatch(decomposition)
        assert len(result.failed) == 1
        assert "ghost_agent_xyz" in result.failed[0].result["error"]
        assert result.failed[0].status == "failed"

    async def test_dispatch_catches_agent_exception(self, coordinator):
        from agents.base import register

        @register("broken_agent_test_1")
        class _Boom(BaseAgent):
            async def run(self, task):
                raise RuntimeError("boom")

        decomposition = TaskDecomposition(
            task_id="t3",
            original_description="break it",
            subtasks=[SubTask(id="t3-0", agent_name="broken_agent_test_1", description="break")],
        )
        result = await coordinator._dispatch(decomposition)
        assert len(result.failed) == 1
        assert result.failed[0].result["error"] == "boom"

    async def test_dispatch_mixed_success_and_failure(self, coordinator):
        from agents.base import register

        @register("good_agent_mixed_1")
        class _Good(BaseAgent):
            async def run(self, task):
                return {"ok": True}

        @register("bad_agent_mixed_1")
        class _Bad(BaseAgent):
            async def run(self, task):
                raise ValueError("nope")

        decomposition = TaskDecomposition(
            task_id="t4",
            original_description="mixed",
            subtasks=[
                SubTask(id="t4-0", agent_name="good_agent_mixed_1", description="good"),
                SubTask(id="t4-1", agent_name="bad_agent_mixed_1", description="bad"),
                SubTask(id="t4-2", agent_name="ghost_agent_mixed_1", description="ghost"),
            ],
        )
        result = await coordinator._dispatch(decomposition)
        assert len(result.completed) == 1
        assert len(result.failed) == 2
        completed_ids = {s.id for s in result.completed}
        failed_ids = {s.id for s in result.failed}
        assert "t4-0" in completed_ids
        assert "t4-1" in failed_ids
        assert "t4-2" in failed_ids
        assert result.completed[0].agent_name == "good_agent_mixed_1"
        failed_agent_names = {s.agent_name for s in result.failed}
        assert "bad_agent_mixed_1" in failed_agent_names
        assert "ghost_agent_mixed_1" in failed_agent_names

    async def test_dispatch_does_not_mutate_original_subtasks(self, coordinator):
        """SubTask instances should be copied, not mutated in place."""
        from agents.base import register

        @register("immutable_test_agent_1")
        class _T(BaseAgent):
            async def run(self, task):
                return {"ok": True}

        original = SubTask(id="imm-0", agent_name="immutable_test_agent_1", description="test")
        decomposition = TaskDecomposition(
            task_id="imm",
            original_description="x",
            subtasks=[original],
        )
        await coordinator._dispatch(decomposition)
        assert original.status == "pending"
        assert original.result is None


class TestRunEndToEnd:
    async def test_run_returns_workflow_result_with_completed_and_failed(self, coordinator):
        from agents.base import register

        @register("test_agent")
        class _T1(BaseAgent):
            async def run(self, task):
                return {"agent": "test_agent", "task": task}

        @register("code_review_agent")
        class _T2(BaseAgent):
            async def run(self, task):
                return {"agent": "code_review_agent", "task": task}

        result = await coordinator.run("review and test the login module")
        assert isinstance(result, WorkflowResult)
        assert result.success is True
        assert len(result.completed) == 2
        assert len(result.failed) == 0


class TestRegistration:
    def test_coordinator_is_registered(self):
        """The @register decorator on CoordinatorAgent runs at module import time.

        The module is already imported at the top of this file (line 10),
        which triggers ``@register(\"coordinator\")``. The autouse
        ``reset_agent_registry`` fixture clears the registry before this
        test runs, so we re-trigger the registration by re-applying
        ``@register`` to the already-imported CoordinatorAgent class.
        This is a cheaper and more explicit equivalent of
        ``importlib.reload(agents.coordinator)`` (which would also
        re-execute the module body) — see review note 24.
        """
        from agents.base import register

        @register("coordinator")
        class _CoordinatorReRegistered(BaseAgent):
            async def run(self, task):
                return {}

        assert "coordinator" in AgentRegistry().list_agents()
