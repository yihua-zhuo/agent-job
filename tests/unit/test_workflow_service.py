"""Unit tests for WorkflowService."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from services.workflow_service import WorkflowService


@pytest.fixture
def workflow_service():
    return WorkflowService()


@pytest_asyncio.fixture
async def sample_workflow(workflow_service):
    """Mock workflow — no real DB."""
    mock_wf = MagicMock()
    mock_wf.id = 1
    mock_wf.name = "Test Workflow"
    mock_wf.description = "A test workflow"
    mock_wf.trigger_type = MagicMock(value="manual")
    mock_wf.trigger_config = {}
    mock_wf.actions = [{"type": "email.send", "template": "welcome"}]
    mock_wf.conditions = [{"field": "user_type", "operator": "==", "value": "premium"}]
    mock_wf.status = MagicMock(value="draft")
    mock_wf.created_by = 1
    mock_wf.created_at = None
    mock_wf.updated_at = None
    # Patch get_workflow to return this mock
    original_get = workflow_service.get_workflow
    workflow_service.get_workflow = AsyncMock(return_value=mock_wf)
    yield 1
    workflow_service.get_workflow = original_get


@pytest.mark.asyncio
class TestWorkflowService:
    async def test_create_workflow(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="New Workflow",
            trigger_type="scheduled",
            created_by=1,
            description="Scheduled workflow",
            trigger_config={"cron": "0 9 * * *"},
        )
        assert bool(result) is True
        assert result.data["name"] == "New Workflow"

    async def test_get_workflow(self, workflow_service, sample_workflow):
        result = await workflow_service.get_workflow(sample_workflow)
        assert bool(result) is True
        assert result.data["id"] == sample_workflow

    async def test_update_workflow(self, workflow_service, sample_workflow):
        result = await workflow_service.update_workflow(
            sample_workflow,
            {"name": "Updated Workflow", "description": "Updated desc",
             "actions": [{"type": "notification.send"}]},
        )
        assert bool(result) is True
        assert result.data["name"] == "Updated Workflow"

    async def test_activate_workflow(self, workflow_service, sample_workflow):
        result = await workflow_service.activate_workflow(sample_workflow)
        assert bool(result) is True

    async def test_pause_workflow(self, workflow_service, sample_workflow):
        await workflow_service.activate_workflow(sample_workflow)
        result = await workflow_service.pause_workflow(sample_workflow)
        assert bool(result) is True

    async def test_delete_workflow(self, workflow_service, sample_workflow):
        result = await workflow_service.delete_workflow(sample_workflow)
        assert bool(result) is True
        gone = await workflow_service.get_workflow(sample_workflow)
        assert bool(gone) is False

    async def test_list_workflows(self, workflow_service):
        result = await workflow_service.list_workflows()
        assert bool(result) is True

    async def test_execute_workflow(self, workflow_service, sample_workflow):
        result = await workflow_service.execute_workflow(
            sample_workflow,
            context={"user_id": 1, "user_type": "premium"},
        )
        assert bool(result) is True
        assert result.data["workflow_id"] == sample_workflow

    async def test_evaluate_conditions(self, workflow_service, sample_workflow):
        result = await workflow_service.evaluate_conditions(
            sample_workflow, {"user_type": "premium"}
        )
        assert result is True
        result2 = await workflow_service.evaluate_conditions(
            sample_workflow, {"user_type": "basic"}
        )
        assert result2 is False

    async def test_execute_actions(self, workflow_service, sample_workflow):
        result = await workflow_service.execute_actions(sample_workflow, {"user_id": 1})
        assert "actions_executed" in result
        assert len(result["actions_executed"]) > 0

    async def test_get_execution_history(self, workflow_service, sample_workflow):
        await workflow_service.execute_workflow(sample_workflow, context={"user_id": 1})
        result = await workflow_service.get_execution_history(sample_workflow)
        assert bool(result) is True
        assert len(result.data["items"]) >= 1

    async def test_create_workflow_minimal_fields(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="Minimal Workflow",
            trigger_type="manual",
            created_by=1,
        )
        assert bool(result) is True
        assert result.data["actions"] == []

    async def test_get_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.get_workflow(99999)
        assert bool(result) is False

    async def test_update_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.update_workflow(99999, {"name": "X"})
        assert bool(result) is False

    async def test_activate_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.activate_workflow(99999)
        assert bool(result) is False

    async def test_pause_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.pause_workflow(99999)
        assert bool(result) is False

    async def test_delete_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.delete_workflow(99999)
        assert bool(result) is False

    async def test_execute_nonexistent_workflow(self, workflow_service):
        result = await workflow_service.execute_workflow(99999, {})
        assert bool(result) is False

    async def test_list_workflows_with_status_filter(self, workflow_service):
        result = await workflow_service.list_workflows(status="draft")
        assert bool(result) is True

    async def test_list_workflows_pagination(self, workflow_service):
        result = await workflow_service.list_workflows(page=1, page_size=5)
        assert bool(result) is True
        assert result.data.page == 1
        assert result.data.page_size == 5

    async def test_evaluate_conditions_no_conditions(self, workflow_service, sample_workflow):
        await workflow_service.update_workflow(sample_workflow, {"conditions": []})
        result = await workflow_service.evaluate_conditions(sample_workflow, {})
        assert result is True

    async def test_evaluate_conditions_multiple(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="Multi-condition",
            trigger_type="manual",
            created_by=1,
            conditions=[
                {"field": "amount", "operator": ">=", "value": 100},
                {"field": "status", "operator": "==", "value": "active"},
            ],
        )
        wf_id = result.data["id"]
        ok = await workflow_service.evaluate_conditions(wf_id, {"amount": 150, "status": "active"})
        assert ok is True

    async def test_evaluate_conditions_greater_than_operator(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="GT Test",
            trigger_type="manual",
            created_by=1,
            conditions=[{"field": "amount", "operator": ">", "value": 100}],
        )
        wf_id = result.data["id"]
        assert await workflow_service.evaluate_conditions(wf_id, {"amount": 150}) is True
        assert await workflow_service.evaluate_conditions(wf_id, {"amount": 50}) is False

    async def test_evaluate_conditions_less_than_operator(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="LT Test",
            trigger_type="manual",
            created_by=1,
            conditions=[{"field": "score", "operator": "<", "value": 50}],
        )
        wf_id = result.data["id"]
        assert await workflow_service.evaluate_conditions(wf_id, {"score": 30}) is True
        assert await workflow_service.evaluate_conditions(wf_id, {"score": 60}) is False

    async def test_evaluate_conditions_not_equal_operator(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="NE Test",
            trigger_type="manual",
            created_by=1,
            conditions=[{"field": "status", "operator": "!=", "value": "blocked"}],
        )
        wf_id = result.data["id"]
        assert await workflow_service.evaluate_conditions(wf_id, {"status": "active"}) is True
        assert await workflow_service.evaluate_conditions(wf_id, {"status": "blocked"}) is False

    async def test_evaluate_conditions_contains_operator(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="Contains Test",
            trigger_type="manual",
            created_by=1,
            conditions=[{"field": "tags", "operator": "contains", "value": "vip"}],
        )
        wf_id = result.data["id"]
        assert await workflow_service.evaluate_conditions(wf_id, {"tags": "vip,premium"}) is True
        assert await workflow_service.evaluate_conditions(wf_id, {"tags": "basic"}) is False

    async def test_execute_workflow_conditions_not_met(self, workflow_service, sample_workflow):
        result = await workflow_service.execute_workflow(
            sample_workflow,
            context={"user_id": 1, "user_type": "basic"},
        )
        assert bool(result) is True

    async def test_execute_workflow_conditions_met(self, workflow_service, sample_workflow):
        result = await workflow_service.execute_workflow(
            sample_workflow,
            context={"user_id": 1, "user_type": "premium"},
        )
        assert bool(result) is True

    async def test_execute_actions_various_types(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="Multi-action",
            trigger_type="manual",
            created_by=1,
            actions=[
                {"type": "email.send", "template": "welcome"},
                {"type": "notification.send", "to": "admin"},
                {"type": "tag.add", "tag": "new_user"},
                {"type": "task.create", "title": "Follow up"},
                {"type": "activity.log", "content": "User onboarded"},
            ],
        )
        wf_id = result.data["id"]
        exec_result = await workflow_service.execute_actions(wf_id, {})
        assert len(exec_result["actions_executed"]) == 5

    async def test_execute_actions_unknown_type(self, workflow_service):
        result = await workflow_service.create_workflow(
            name="Unknown Action",
            trigger_type="manual",
            created_by=1,
            actions=[{"type": "unknown.action"}],
        )
        wf_id = result.data["id"]
        exec_result = await workflow_service.execute_actions(wf_id, {})
        assert exec_result["actions_executed"][0]["status"] == "unknown"

    async def test_get_execution_history_empty(self, workflow_service, sample_workflow):
        # No executions yet
        result = await workflow_service.get_execution_history(sample_workflow)
        assert bool(result) is True
