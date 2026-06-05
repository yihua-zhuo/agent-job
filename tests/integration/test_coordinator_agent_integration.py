"""Integration tests for CoordinatorAgent.run_workflow.

Exercises CoordinatorAgent against a real PostgreSQL session, covering
happy-path (task dispatch completes), boundary (empty task list), and
error (agent script missing -> not_found) scenarios.

The CoordinatorAgent is not a service class (no AsyncSession in its
constructor), so the `async_session` and `tenant_id` fixtures are accepted
for lifecycle validation (db_schema isolation runs before each test) but
are not directly used by the SUT.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path so `from docs.agents...` resolves.
_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pytest  # noqa: E402

from docs.agents.coordinator.coordinator_agent import CoordinatorAgent  # noqa: E402


class TestCoordinatorAgent:
    """Integration tests for CoordinatorAgent.run_workflow."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Workspace containing a fake test agent script that exits 0."""
        agent_dir = tmp_path / "agents" / "test"
        agent_dir.mkdir(parents=True)
        (agent_dir / "test_agent.py").write_text(
            "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
        )
        return tmp_path

    @pytest.fixture
    def empty_workspace(self, tmp_path):
        """Workspace with no agent scripts — known agent names resolve to
        paths that do not exist, exercising the not_found branch."""
        return tmp_path

    def test_run_workflow_dispatches_task_and_returns_completed(
        self, workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        tasks = [{"task_id": "t1", "assignee": "test", "type": "feature"}]
        results = agent.run_workflow(tasks)

        assert "dispatched" in results
        assert len(results["dispatched"]) == 1
        assert results["dispatched"][0]["status"] == "completed"

    def test_run_workflow_with_empty_task_list_returns_empty_dispatched(
        self, workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        results = agent.run_workflow([])

        assert results["dispatched"] == []
        assert results["completed"] == []
        assert results["failed"] == []

    def test_run_workflow_with_nonexistent_agent_returns_not_found(
        self, empty_workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=empty_workspace)
        tasks = [{"task_id": "t2", "assignee": "test", "type": "feature"}]
        results = agent.run_workflow(tasks)

        assert results["dispatched"][0]["status"] == "not_found"
