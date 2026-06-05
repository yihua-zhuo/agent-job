"""Unit tests for CoordinatorAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import agents.base as agent_base
import agents.coordinator as _coordinator_module  # noqa: F401  — ensures @register runs at import
from agents.base import BaseAgent
from agents.coordinator import CoordinatorAgent, SubTask, TaskDecomposition, WorkflowResult
from agents.registry import AgentRegistry


def _reset_registry() -> None:
    import agents.registry as agent_registry

    agent_base._registry = None
    agent_registry._registry = None


@pytest.fixture(autouse=True)
def reset_agent_registry():
    _reset_registry()
    yield


@pytest.fixture
def coordinator():
    return CoordinatorAgent(llm=MagicMock(), session=MagicMock())


class _MockAgent(BaseAgent):
    def __init__(self, llm=None, session=None) -> None:
        super().__init__(llm=llm or MagicMock(), session=session or MagicMock())
        self._name = "mock"

    @property
    def name(self) -> str:
        return self._name

    def run(self, task: str) -> dict:
        return {"agent": self._name, "task": task}


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
    def test_dispatch_routes_to_registered_agents(self, coordinator):
        AgentRegistry()._agents["test_agent"] = _MockAgent
        AgentRegistry()._agents["code_review_agent"] = _MockAgent

        decomposition = TaskDecomposition(
            task_id="t1",
            original_description="test and review",
            subtasks=[
                SubTask(id="t1-0", agent_name="test_agent", description="test it"),
                SubTask(id="t1-1", agent_name="code_review_agent", description="review it"),
            ],
        )
        result = coordinator._dispatch(decomposition)
        assert isinstance(result, WorkflowResult)
        assert len(result.completed) == 2
        assert len(result.failed) == 0
        for s in result.completed:
            assert s.status == "completed"
            assert s.result is not None

    def test_dispatch_catches_unknown_agent(self, coordinator):
        decomposition = TaskDecomposition(
            task_id="t2",
            original_description="ghost work",
            subtasks=[SubTask(id="t2-0", agent_name="ghost_agent", description="ghost")],
        )
        result = coordinator._dispatch(decomposition)
        assert len(result.failed) == 1
        assert "ghost_agent" in result.failed[0].result["error"]
        assert result.failed[0].status == "failed"

    def test_dispatch_catches_agent_exception(self, coordinator):
        class _Boom(BaseAgent):
            def __init__(self, llm=None, session=None) -> None:
                super().__init__(llm=llm or MagicMock(), session=session or MagicMock())

            @property
            def name(self):
                return "broken_agent"

            def run(self, task):
                raise RuntimeError("boom")

        AgentRegistry()._agents["broken_agent"] = _Boom

        decomposition = TaskDecomposition(
            task_id="t3",
            original_description="break it",
            subtasks=[SubTask(id="t3-0", agent_name="broken_agent", description="break")],
        )
        result = coordinator._dispatch(decomposition)
        assert len(result.failed) == 1
        assert result.failed[0].result["error"] == "boom"

    def test_dispatch_mixed_success_and_failure(self, coordinator):
        class _Good(BaseAgent):
            def __init__(self, llm=None, session=None) -> None:
                super().__init__(llm=llm or MagicMock(), session=session or MagicMock())

            @property
            def name(self):
                return "good_agent"

            def run(self, task):
                return {"ok": True}

        class _Bad(BaseAgent):
            def __init__(self, llm=None, session=None) -> None:
                super().__init__(llm=llm or MagicMock(), session=session or MagicMock())

            @property
            def name(self):
                return "bad_agent"

            def run(self, task):
                raise ValueError("nope")

        AgentRegistry()._agents["good_agent"] = _Good
        AgentRegistry()._agents["bad_agent"] = _Bad

        decomposition = TaskDecomposition(
            task_id="t4",
            original_description="mixed",
            subtasks=[
                SubTask(id="t4-0", agent_name="good_agent", description="good"),
                SubTask(id="t4-1", agent_name="bad_agent", description="bad"),
                SubTask(id="t4-2", agent_name="ghost_agent", description="ghost"),
            ],
        )
        result = coordinator._dispatch(decomposition)
        assert len(result.completed) == 1
        assert len(result.failed) == 2


class TestRunEndToEnd:
    def test_run_returns_dict_with_completed_and_failed(self, coordinator):
        AgentRegistry()._agents["test_agent"] = _MockAgent
        AgentRegistry()._agents["code_review_agent"] = _MockAgent

        result = coordinator.run("review and test the login module")
        assert isinstance(result, dict)
        assert "completed" in result
        assert "failed" in result
        assert len(result["completed"]) == 2
        assert len(result["failed"]) == 0


class TestRegistration:
    def test_coordinator_is_registered(self):
        # Re-import the coordinator module so the @register decorator runs
        # against the freshly-reset singleton.
        import importlib

        import agents.coordinator

        importlib.reload(agents.coordinator)
        names = AgentRegistry().list_agents()
        assert "coordinator" in names
