"""Integration tests for ``docs.agents.coordinator.coordinator_agent.CoordinatorAgent``.

Covers ``run_workflow`` against the file-based agent script runner:

* happy-path — a real ``test_agent.py`` script exists in the workspace and
  exits 0, so dispatch returns ``status == "completed"``.
* boundary — an empty task list produces an empty results dict and does
  not raise.
* error — referencing a non-existent agent script returns
  ``status == "not_found"`` rather than crashing.

The coordinator's ``run_workflow`` does not interact with the database, so
``db_schema`` and ``async_session`` are consumed only to satisfy the
integration-test fixture contract; ``tenant_id`` is forwarded for
completeness even though dispatch is file-based. The session and tenant_id
are not asserted on.
"""

from __future__ import annotations

# docs/ has no __init__.py files, so we import the module file directly
# by adding the docs/agents/coordinator directory to sys.path. We do NOT
# add ``docs/`` because doing so would conflict with ``src.agents`` (the
# async BaseAgent package) for the bare name ``agents``.
import sys
from pathlib import Path

_coordinator_dir = Path(__file__).resolve().parents[2] / "docs" / "agents" / "coordinator"
if str(_coordinator_dir) not in sys.path:
    sys.path.insert(0, str(_coordinator_dir))

import pytest  # noqa: E402
from coordinator_agent import CoordinatorAgent  # noqa: E402


class TestCoordinatorAgent:
    """Integration tests for CoordinatorAgent.run_workflow."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Workspace with a real ``test_agent.py`` that exits 0 on --task."""
        agent_dir = tmp_path / "agents" / "test"
        agent_dir.mkdir(parents=True)
        (agent_dir / "test_agent.py").write_text(
            "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
        )
        return tmp_path

    async def test_run_workflow_dispatches_task_and_returns_completed(
        self, workspace, db_schema, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        tasks = [{"task_id": "t1", "assignee": "test", "type": "feature"}]
        results = agent.run_workflow(tasks)
        assert "dispatched" in results
        assert len(results["dispatched"]) == 1
        assert results["dispatched"][0]["status"] == "completed"

    async def test_run_workflow_with_empty_task_list_returns_empty_dispatched(
        self, workspace, db_schema, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        results = agent.run_workflow([])
        assert results["dispatched"] == []
        assert results["completed"] == []
        assert results["failed"] == []

    async def test_run_workflow_with_nonexistent_agent_script_returns_not_found(
        self, workspace, db_schema, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        # ``code_review`` is a known agent name in dispatch_to_agent's lookup
        # table, but its script file is NOT present in this workspace —
        # therefore dispatch hits the "not_found" branch.
        tasks = [{"task_id": "t2", "assignee": "code_review", "type": "feature"}]
        results = agent.run_workflow(tasks)
        assert results["dispatched"][0]["status"] == "not_found"
