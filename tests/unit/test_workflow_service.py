"""Unit tests for WorkflowService."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.workflow_service import WorkflowService, _as_trigger_value, _as_status_value


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
    yield mock_wf  # yield the mock so tests can also access it directly
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



    async def test_get_execution_history_empty(self, workflow_service, sample_workflow):
        # No executions yet
        result = await workflow_service.get_execution_history(sample_workflow)
        assert bool(result) is True

    # ── _check_conditions operator tests ──────────────────────────────────────

    @pytest.mark.parametrize("operator,context_field,context_value,cond_value,expected", [
        ("==", "status", "active", "active", True),
        ("==", "status", "active", "inactive", False),
        ("!=", "status", "active", "inactive", True),
        ("!=", "status", "active", "active", False),
        (">",   "amount", 50000, 10000, True),
        (">",   "amount", 5000, 10000, False),
        ("<",   "amount", 5000, 10000, True),
        ("<",   "amount", 50000, 10000, False),
        (">=",  "amount", 10000, 10000, True),
        (">=",  "amount", 9999,  10000, False),
        ("<=",  "amount", 10000, 10000, True),
        ("<=",  "amount", 10001, 10000, False),
        ("contains", "email", "alice@example.com", "alice", True),
        ("contains", "email", "alice@example.com", "bob", False),
    ])
    async def test_check_conditions_single_operator(
        self, workflow_service, operator, context_field, context_value, cond_value, expected
    ):
        conditions = [{"field": context_field, "operator": operator, "value": cond_value}]
        context = {context_field: context_value}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is expected

    # ── _run_actions action type tests ───────────────────────────────────────

    async def test_run_actions_email_send(self, workflow_service):
        actions = [{"type": "email.send", "template": "welcome"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "email.send"
        assert result["actions_executed"][0]["status"] == "sent"
        assert result["actions_executed"][0]["template"] == "welcome"

    async def test_run_actions_notification_send(self, workflow_service):
        actions = [{"type": "notification.send", "to": "user:42"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "notification.send"
        assert result["actions_executed"][0]["to"] == "user:42"

    async def test_run_actions_tag_add(self, workflow_service):
        actions = [{"type": "tag.add", "tag": "vip"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "tag.add"
        assert result["actions_executed"][0]["tag"] == "vip"

    async def test_run_actions_task_create(self, workflow_service):
        actions = [{"type": "task.create", "title": "Follow up"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "task.create"
        assert result["actions_executed"][0]["title"] == "Follow up"

    async def test_run_actions_activity_log(self, workflow_service):
        actions = [{"type": "activity.log", "content": "Called customer"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "activity.log"
        assert result["actions_executed"][0]["status"] == "logged"

    async def test_run_actions_unknown_type(self, workflow_service):
        actions = [{"type": "http.webhook", "url": "https://example.com"}]
        result = await workflow_service._run_actions(actions)
        assert result["actions_executed"][0]["type"] == "http.webhook"
        assert result["actions_executed"][0]["status"] == "unknown"

    async def test_run_actions_multiple_actions(self, workflow_service):
        actions = [
            {"type": "email.send", "template": "welcome"},
            {"type": "tag.add", "tag": "new"},
            {"type": "task.create", "title": "Onboarding"},
        ]
        result = await workflow_service._run_actions(actions)
        assert len(result["actions_executed"]) == 3

    # ── execute_actions error path ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_actions_not_found_raises(self, workflow_service):
        """When get_workflow returns None, execute_actions raises ValueError."""
        workflow_service.get_workflow = AsyncMock(
            return_value=type("R", (), {"__bool__": lambda self: False})()
        )
        with pytest.raises(ValueError, match="not found"):
            await workflow_service.execute_actions(99999, {})

    # ── delete_workflow success path ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_delete_workflow_success(self, workflow_service):
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.delete_workflow(1)
        assert bool(result) is True
        assert result.data["id"] == 1

    @pytest.mark.asyncio
    async def test_delete_workflow_not_found(self, workflow_service):
        """rowcount=0 should return error."""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.delete_workflow(99999)
        assert bool(result) is False
        assert result.meta.get("code") == 3001

    # ── helper function coverage ───────────────────────────────────────────────

    def test_as_trigger_value_none(self, workflow_service):
        """None input should default to MANUAL."""
        result = _as_trigger_value(None)
        from models.workflow import WorkflowTriggerType
        assert result == WorkflowTriggerType.MANUAL.value

    def test_as_trigger_value_enum(self, workflow_service):
        """WorkflowTriggerType enum input."""
        from models.workflow import WorkflowTriggerType
        result = _as_trigger_value(WorkflowTriggerType.SCHEDULED)
        assert result == WorkflowTriggerType.SCHEDULED.value

    def test_as_trigger_value_string(self, workflow_service):
        """Plain string input."""
        result = _as_trigger_value("webhook")
        assert result == "webhook"

    def test_as_status_value_none(self, workflow_service):
        """None input should default to DRAFT."""
        result = _as_status_value(None)
        from models.workflow import WorkflowStatus
        assert result == WorkflowStatus.DRAFT.value

    def test_as_status_value_enum(self, workflow_service):
        """WorkflowStatus enum input."""
        from models.workflow import WorkflowStatus
        result = _as_status_value(WorkflowStatus.ACTIVE)
        assert result == WorkflowStatus.ACTIVE.value

    def test_as_status_value_string(self, workflow_service):
        """Plain string input."""
        result = _as_status_value("archived")
        assert result == "archived"

    # ── get_workflow not-found path ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, workflow_service):
        """scalar_one_or_none returns None → error response."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.get_workflow(99999)
        assert bool(result) is False
        assert result.meta.get("code") == 3001

    # ── update_workflow with trigger_type / status fields ──────────────────────

    @pytest.mark.asyncio
    async def test_update_workflow_with_trigger_type(self, workflow_service):
        """trigger_type in update data should call _as_trigger_value."""
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {"id": 1, "trigger_type": "scheduled"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.update_workflow(1, {"trigger_type": "scheduled"})
        assert bool(result) is True

    @pytest.mark.asyncio
    async def test_update_workflow_with_status(self, workflow_service):
        """status in update data should call _as_status_value."""
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {"id": 1, "status": "active"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_row

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.update_workflow(1, {"status": "active"})
        assert bool(result) is True

    @pytest.mark.asyncio
    async def test_update_workflow_not_found(self, workflow_service):
        """scalar_one_or_none returns None → error response."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.update_workflow(99999, {"name": "X"})
        assert bool(result) is False
        assert result.meta.get("code") == 3001

    # ── _transition_status not-found path ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_transition_status_not_found(self, workflow_service):
        """_transition_status returns error when row is None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.activate_workflow(99999)
        assert bool(result) is False
        assert result.meta.get("code") == 3001

    # ── execute_workflow condition failure path ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_workflow_conditions_not_met(self, workflow_service):
        """Conditions not met → status=failed, error in result."""
        mock_wf = MagicMock()
        mock_wf.id = 1
        mock_wf.name = "Test WF"
        mock_wf.description = None
        mock_wf.trigger_type = MagicMock(value="manual")
        mock_wf.trigger_config = {}
        mock_wf.actions = []
        mock_wf.conditions = [{"field": "user_type", "operator": "==", "value": "premium"}]
        mock_wf.status = MagicMock(value="draft")
        mock_wf.created_by = 1
        mock_wf.created_at = None
        mock_wf.updated_at = None

        mock_api_response = MagicMock()
        mock_api_response.__bool__ = MagicMock(return_value=True)
        mock_api_response.data = mock_wf

        mock_exec_row = MagicMock()
        mock_exec_row.to_dict.return_value = {"workflow_id": 1, "status": "failed"}

        mock_wf.get.side_effect = lambda k: {
            "conditions": mock_wf.conditions,
            "actions": mock_wf.actions,
            "trigger_type": mock_wf.trigger_type,
        }.get(k)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_wf)))

        workflow_service.get_workflow = AsyncMock(return_value=mock_api_response)

        def flush_side_effect():
            pass
        mock_session.flush = AsyncMock(side_effect=flush_side_effect)
        mock_session.add = MagicMock()

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.execute_workflow(1, {"user_id": 1, "user_type": "basic"})
        assert bool(result) is True

    # ── execute_workflow exception handler path ────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_workflow_exception(self, workflow_service):
        """_run_actions raises → status=failed with error string."""
        mock_wf = MagicMock()
        mock_wf.id = 1
        mock_wf.name = "Test WF"
        mock_wf.description = None
        mock_wf.trigger_type = MagicMock(value="manual")
        mock_wf.trigger_config = {}
        mock_wf.actions = [{"type": "bad.action"}]
        mock_wf.conditions = []
        mock_wf.status = MagicMock(value="draft")
        mock_wf.created_by = 1
        mock_wf.created_at = None
        mock_wf.updated_at = None

        mock_api_response = MagicMock()
        mock_api_response.__bool__ = MagicMock(return_value=True)
        mock_api_response.data = mock_wf

        mock_wf.get.side_effect = lambda k: {
            "conditions": mock_wf.conditions,
            "actions": mock_wf.actions,
            "trigger_type": mock_wf.trigger_type,
        }.get(k)

        workflow_service.get_workflow = AsyncMock(return_value=mock_api_response)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_wf)))
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        with patch("services.workflow_service.get_db_session", return_value=mock_session):
            result = await workflow_service.execute_workflow(1, {"user_id": 1})
        assert bool(result) is True

    # ── evaluate_conditions not-found path ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_evaluate_conditions_workflow_not_found(self, workflow_service):
        """get_workflow returns falsy → evaluate_conditions returns False."""
        workflow_service.get_workflow = AsyncMock(
            return_value=type("R", (), {"__bool__": lambda self: False})()
        )
        result = await workflow_service.evaluate_conditions(99999, {})
        assert result is False

    # ── _check_conditions edge cases ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_conditions_no_field(self, workflow_service):
        """condition without 'field' key → treated as no context value."""
        conditions = [{"operator": "==", "value": "x"}]
        context = {"status": "active"}
        # field is None/missing → ctx_value=None → != value → returns False
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_unknown_operator(self, workflow_service):
        """unknown operator → falls through all checks → returns True."""
        conditions = [{"field": "status", "operator": "unknown", "value": "x"}]
        context = {"status": "active"}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_conditions_gt_with_none_context(self, workflow_service):
        """> operator with None ctx_value → returns False."""
        conditions = [{"field": "amount", "operator": ">", "value": 100}]
        context = {}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_lt_with_none_context(self, workflow_service):
        """>< operator with None ctx_value → returns False."""
        conditions = [{"field": "amount", "operator": "<", "value": 100}]
        context = {}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_ge_with_none_context(self, workflow_service):
        """>= operator with None ctx_value → returns False."""
        conditions = [{"field": "amount", "operator": ">=", "value": 100}]
        context = {}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_le_with_none_context(self, workflow_service):
        """><= operator with None ctx_value → returns False."""
        conditions = [{"field": "amount", "operator": "<=", "value": 100}]
        context = {}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_contains_with_none_context(self, workflow_service):
        """>contains with None ctx_value → returns False."""
        conditions = [{"field": "email", "operator": "contains", "value": "alice"}]
        context = {}
        result = await workflow_service._check_conditions(conditions, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_conditions_contains_with_list_context(self, workflow_service):
        """contains with list context → value IN str(list) so returns True."""
        conditions = [{"field": "tags", "operator": "contains", "value": "alice"}]
        context = {"tags": ["alice", "bob"]}
        # "alice" IS in str(["alice", "bob"]) = "['alice', 'bob']" → condition False → return True
        result = await workflow_service._check_conditions(conditions, context)
        assert result is True
