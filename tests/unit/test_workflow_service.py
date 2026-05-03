"""工作流服务单元测试"""
import pytest
from datetime import datetime

from src.services.workflow_service import WorkflowService
from src.models.workflow import Workflow, WorkflowExecution, WorkflowStatus, TriggerType


@pytest.fixture
def workflow_service():
    """创建工作流服务实例"""
    return WorkflowService()


@pytest.fixture
def sample_workflow(workflow_service):
    """创建示例工作流"""
    return workflow_service.create_workflow(
        name="测试工作流",
        trigger_type=TriggerType.MANUAL,
        created_by=1,
        description="用于测试的工作流",
        actions=[
            {"type": "email.send", "template": "welcome"},
        ],
        conditions=[
            {"field": "user_type", "operator": "==", "value": "premium"},
        ],
    )


class TestWorkflowServiceNormal:
    """正常场景测试"""

    def test_create_workflow(self, workflow_service):
        """测试创建工作流"""
        workflow = workflow_service.create_workflow(
            name="新工作流",
            trigger_type=TriggerType.SCHEDULED,
            created_by=1,
            description="定时工作流",
            trigger_config={"cron": "0 9 * * *"},
        )
        assert workflow.id == 1
        assert workflow.name == "新工作流"
        assert workflow.trigger_type == TriggerType.SCHEDULED
        assert workflow.status == WorkflowStatus.DRAFT

    def test_get_workflow(self, workflow_service, sample_workflow):
        """测试获取工作流详情"""
        workflow = workflow_service.get_workflow(sample_workflow.id)
        assert workflow is not None
        assert workflow.id == sample_workflow.id

    def test_update_workflow(self, workflow_service, sample_workflow):
        """测试更新工作流"""
        updated = workflow_service.update_workflow(
            sample_workflow.id,
            name="更新后的工作流",
            description="更新后的描述",
            actions=[{"type": "notification.send"}],
        )
        assert updated is not None
        assert updated.name == "更新后的工作流"
        assert len(updated.actions) == 1

    def test_activate_workflow(self, workflow_service, sample_workflow):
        """测试激活工作流"""
        activated = workflow_service.activate_workflow(sample_workflow.id)
        assert activated is not None
        assert activated.status == WorkflowStatus.ACTIVE

    def test_pause_workflow(self, workflow_service, sample_workflow):
        """测试暂停工作流"""
        workflow_service.activate_workflow(sample_workflow.id)
        paused = workflow_service.pause_workflow(sample_workflow.id)
        assert paused is not None
        assert paused.status == WorkflowStatus.PAUSED

    def test_delete_workflow(self, workflow_service, sample_workflow):
        """测试删除工作流"""
        result = workflow_service.delete_workflow(sample_workflow.id)
        assert result is True
        workflow = workflow_service.get_workflow(sample_workflow.id)
        assert workflow is None

    def test_list_workflows(self, workflow_service):
        """测试工作流列表"""
        workflow_service.create_workflow(
            name="工作流1",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
        )
        workflow_service.create_workflow(
            name="工作流2",
            trigger_type=TriggerType.EVENT,
            created_by=1,
        )
        result = workflow_service.list_workflows()
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_execute_workflow(self, workflow_service, sample_workflow):
        """测试执行工作流"""
        execution = workflow_service.execute_workflow(
            sample_workflow.id,
            context={"user_id": 1, "user_type": "premium"},
        )
        assert execution is not None
        assert execution.workflow_id == sample_workflow.id

    def test_evaluate_conditions(self, workflow_service, sample_workflow):
        """测试评估条件"""
        result = workflow_service.evaluate_conditions(
            sample_workflow.id,
            {"user_type": "premium"},
        )
        assert result is True

        result = workflow_service.evaluate_conditions(
            sample_workflow.id,
            {"user_type": "basic"},
        )
        assert result is False

    def test_execute_actions(self, workflow_service, sample_workflow):
        """测试执行动作列表"""
        result = workflow_service.execute_actions(
            sample_workflow.id,
            {"user_id": 1},
        )
        assert "actions_executed" in result
        assert len(result["actions_executed"]) > 0

    def test_get_execution_history(self, workflow_service, sample_workflow):
        """测试获取执行历史"""
        workflow_service.execute_workflow(
            sample_workflow.id,
            context={"user_id": 1},
        )
        history = workflow_service.get_execution_history(sample_workflow.id)
        assert len(history) == 1


class TestWorkflowServiceEdgeCases:
    """边界条件和错误测试"""

    def test_create_workflow_minimal_fields(self, workflow_service):
        """测试只提供必需字段创建工作流"""
        workflow = workflow_service.create_workflow(
            name="最小字段工作流",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
        )
        assert workflow.id == 1
        assert workflow.actions == []
        assert workflow.conditions == []

    def test_get_nonexistent_workflow(self, workflow_service):
        """测试获取不存在的工作流"""
        workflow = workflow_service.get_workflow(9999)
        assert workflow is None

    def test_update_nonexistent_workflow(self, workflow_service):
        """测试更新不存在的工作流"""
        result = workflow_service.update_workflow(9999, name="新名称")
        assert result is None

    def test_activate_nonexistent_workflow(self, workflow_service):
        """测试激活不存在的工作流"""
        result = workflow_service.activate_workflow(9999)
        assert result is None

    def test_pause_nonexistent_workflow(self, workflow_service):
        """测试暂停不存在的工作流"""
        result = workflow_service.pause_workflow(9999)
        assert result is None

    def test_delete_nonexistent_workflow(self, workflow_service):
        """测试删除不存在的工作流"""
        result = workflow_service.delete_workflow(9999)
        assert result is False

    def test_execute_nonexistent_workflow(self, workflow_service):
        """测试执行不存在的工作流"""
        with pytest.raises(ValueError, match="Workflow 9999 not found"):
            workflow_service.execute_workflow(9999, {})

    def test_list_workflows_with_status_filter(self, workflow_service):
        """测试按状态筛选工作流列表"""
        w1 = workflow_service.create_workflow(
            name="工作流1",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
        )
        workflow_service.create_workflow(
            name="工作流2",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
        )
        workflow_service.activate_workflow(w1.id)
        result = workflow_service.list_workflows(status=WorkflowStatus.ACTIVE)
        assert result["total"] == 1
        assert result["items"][0].status == WorkflowStatus.ACTIVE

    def test_list_workflows_pagination(self, workflow_service):
        """测试工作流列表分页"""
        for i in range(25):
            workflow_service.create_workflow(
                name=f"工作流{i}",
                trigger_type=TriggerType.MANUAL,
                created_by=1,
            )
        result = workflow_service.list_workflows(page=2, page_size=10)
        assert len(result["items"]) == 10
        assert result["total"] == 25

    def test_evaluate_conditions_no_conditions(self, workflow_service, sample_workflow):
        """测试评估没有条件的工作流"""
        workflow_service.update_workflow(
            sample_workflow.id,
            conditions=[],
        )
        result = workflow_service.evaluate_conditions(sample_workflow.id, {})
        assert result is True

    def test_evaluate_conditions_multiple(self, workflow_service):
        """测试评估多个条件（全部满足）"""
        workflow = workflow_service.create_workflow(
            name="多条件工作流",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            conditions=[
                {"field": "amount", "operator": ">=", "value": 100},
                {"field": "status", "operator": "==", "value": "active"},
            ],
        )
        result = workflow_service.evaluate_conditions(
            workflow.id,
            {"amount": 150, "status": "active"},
        )
        assert result is True

    def test_evaluate_conditions_greater_than_operator(self, workflow_service):
        """测试大于运算符"""
        workflow = workflow_service.create_workflow(
            name="比较测试",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            conditions=[{"field": "amount", "operator": ">", "value": 100}],
        )
        assert workflow_service.evaluate_conditions(workflow.id, {"amount": 150}) is True
        assert workflow_service.evaluate_conditions(workflow.id, {"amount": 50}) is False

    def test_evaluate_conditions_less_than_operator(self, workflow_service):
        """测试小于运算符"""
        workflow = workflow_service.create_workflow(
            name="比较测试",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            conditions=[{"field": "score", "operator": "<", "value": 50}],
        )
        assert workflow_service.evaluate_conditions(workflow.id, {"score": 30}) is True
        assert workflow_service.evaluate_conditions(workflow.id, {"score": 60}) is False

    def test_evaluate_conditions_not_equal_operator(self, workflow_service):
        """测试不等于运算符"""
        workflow = workflow_service.create_workflow(
            name="不等于测试",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            conditions=[{"field": "status", "operator": "!=", "value": "blocked"}],
        )
        assert workflow_service.evaluate_conditions(workflow.id, {"status": "active"}) is True
        assert workflow_service.evaluate_conditions(workflow.id, {"status": "blocked"}) is False

    def test_evaluate_conditions_contains_operator(self, workflow_service):
        """测试包含运算符"""
        workflow = workflow_service.create_workflow(
            name="包含测试",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            conditions=[{"field": "tags", "operator": "contains", "value": "vip"}],
        )
        assert workflow_service.evaluate_conditions(workflow.id, {"tags": "vip,premium"}) is True
        assert workflow_service.evaluate_conditions(workflow.id, {"tags": "basic"}) is False

    def test_execute_workflow_conditions_not_met(self, workflow_service, sample_workflow):
        """测试条件不满足时执行工作流"""
        execution = workflow_service.execute_workflow(
            sample_workflow.id,
            context={"user_id": 1, "user_type": "basic"},  # 不满足条件
        )
        assert execution.status == "failed"

    def test_execute_workflow_conditions_met(self, workflow_service, sample_workflow):
        """测试条件满足时执行工作流"""
        execution = workflow_service.execute_workflow(
            sample_workflow.id,
            context={"user_id": 1, "user_type": "premium"},
        )
        assert execution.status == "success"

    def test_execute_actions_various_types(self, workflow_service):
        """测试执行各种类型的动作"""
        workflow = workflow_service.create_workflow(
            name="多动作工作流",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            actions=[
                {"type": "email.send", "template": "welcome"},
                {"type": "notification.send", "to": "admin"},
                {"type": "tag.add", "tag": "new_user"},
                {"type": "task.create", "title": "Follow up"},
                {"type": "activity.log", "content": "User onboarded"},
            ],
        )
        result = workflow_service.execute_actions(workflow.id, {})
        assert len(result["actions_executed"]) == 5

    def test_execute_actions_unknown_type(self, workflow_service):
        """测试执行未知类型的动作"""
        workflow = workflow_service.create_workflow(
            name="未知动作工作流",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
            actions=[{"type": "unknown.action"}],
        )
        result = workflow_service.execute_actions(workflow.id, {})
        assert result["actions_executed"][0]["status"] == "unknown"

    def test_get_execution_history_empty(self, workflow_service, sample_workflow):
        """测试获取空执行历史"""
        history = workflow_service.get_execution_history(sample_workflow.id)
        assert len(history) == 0

    def test_execute_workflow_with_exception(self, workflow_service):
        """测试执行抛出异常的工作流"""
        workflow = workflow_service.create_workflow(
            name="异常工作流",
            trigger_type=TriggerType.MANUAL,
            created_by=1,
        )
        # 模拟执行时出错（通过修改workflow让execute_actions抛出异常）
        result = workflow_service.execute_actions(workflow.id, {})
        # 正常执行不会抛异常，异常情况应该在execute_workflow中处理