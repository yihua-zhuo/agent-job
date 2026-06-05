"""Unit tests for CoordinatorAgent.run_workflow.

Exercises the dispatch/aggregation logic of the standalone
``docs.agents.coordinator.coordinator_agent.CoordinatorAgent`` across
happy-path (task dispatch completes), boundary (empty task list), and
error (agent script missing -> not_found) scenarios.

The CoordinatorAgent has no database interaction — these are pure unit
tests that use a ``tmp_path`` workspace with fake agent scripts to
validate dispatch behavior.
"""

from __future__ import annotations

from pathlib import Path

from docs.agents.coordinator.coordinator_agent import CoordinatorAgent


def _make_fake_agent(workspace: Path, agent_name: str, expected_task: dict) -> Path:
    """Create a fake agent script that validates the task payload and prints a sentinel."""
    agent_dir = workspace / "agents" / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    script = agent_dir / f"{agent_name}_agent.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "assert '--task' in sys.argv, 'missing --task arg'\n"
        f"task = json.loads(sys.argv[sys.argv.index('--task') + 1])\n"
        f"assert task == {expected_task!r}, f'task mismatch: {{task}}'\n"
        "print('FAKE_AGENT_OK')\n"
    )
    return script


class TestCoordinatorAgentRunWorkflow:
    """Unit tests for CoordinatorAgent.run_workflow."""

    def test_run_workflow_dispatches_task_and_returns_completed(self, tmp_path):
        expected_task = {"task_id": "t1", "assignee": "test", "type": "feature"}
        _make_fake_agent(tmp_path, "test", expected_task)

        agent = CoordinatorAgent(workspace=tmp_path)
        results = agent.run_workflow([expected_task])

        assert "dispatched" in results
        assert len(results["dispatched"]) == 1
        entry = results["dispatched"][0]
        assert entry["status"] == "completed"
        assert "FAKE_AGENT_OK" in entry.get("output", "")

    def test_run_workflow_with_empty_task_list_returns_empty_dispatched(self, tmp_path):
        _make_fake_agent(tmp_path, "test", {})

        agent = CoordinatorAgent(workspace=tmp_path)
        results = agent.run_workflow([])

        assert results["dispatched"] == []
        assert results["completed"] == []
        assert results["failed"] == []

    def test_run_workflow_with_missing_agent_script_returns_not_found(self, tmp_path):
        # "coordinator" is a known agent name in dispatch_to_agent's script map,
        # but the workspace has no agents/coordinator/ directory — the script
        # path will not exist, exercising the not_found branch.
        agent = CoordinatorAgent(workspace=tmp_path)
        tasks = [{"task_id": "t2", "assignee": "coordinator", "type": "feature"}]
        results = agent.run_workflow(tasks)

        assert len(results["dispatched"]) == 1
        assert results["dispatched"][0]["status"] == "not_found"
