from typing import Optional, List, Dict
from datetime import datetime
from src.models.workflow import Workflow, WorkflowExecution, WorkflowStatus, TriggerType


class WorkflowService:
    """工作流自动化引擎"""

    def __init__(self):
        self._workflows: Dict[int, Workflow] = {}
        self._executions: Dict[int, List[WorkflowExecution]] = {}
        self._next_id = 1

    def create_workflow(self, name, trigger_type, created_by, **kwargs) -> Workflow:
        """创建工作流"""
        workflow = Workflow(
            id=self._next_id,
            name=name,
            description=kwargs.get("description"),
            trigger_type=trigger_type,
            trigger_config=kwargs.get("trigger_config", {}),
            actions=kwargs.get("actions", []),
            conditions=kwargs.get("conditions", []),
            status=WorkflowStatus.DRAFT,
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._workflows[self._next_id] = workflow
        self._executions[self._next_id] = []
        self._next_id += 1
        return workflow

    def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """获取工作流详情"""
        return self._workflows.get(workflow_id)

    def update_workflow(self, workflow_id: int, **kwargs) -> Optional[Workflow]:
        """更新工作流"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        if "name" in kwargs:
            workflow.name = kwargs["name"]
        if "description" in kwargs:
            workflow.description = kwargs["description"]
        if "trigger_type" in kwargs:
            workflow.trigger_type = kwargs["trigger_type"]
        if "trigger_config" in kwargs:
            workflow.trigger_config = kwargs["trigger_config"]
        if "actions" in kwargs:
            workflow.actions = kwargs["actions"]
        if "conditions" in kwargs:
            workflow.conditions = kwargs["conditions"]
        workflow.updated_at = datetime.now()
        return workflow

    def activate_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """激活工作流"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        workflow.status = WorkflowStatus.ACTIVE
        workflow.updated_at = datetime.now()
        return workflow

    def pause_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """暂停工作流"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        workflow.status = WorkflowStatus.PAUSED
        workflow.updated_at = datetime.now()
        return workflow

    def delete_workflow(self, workflow_id: int) -> bool:
        """删除工作流"""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            if workflow_id in self._executions:
                del self._executions[workflow_id]
            return True
        return False

    def list_workflows(self, page: int = 1, page_size: int = 20, status: WorkflowStatus = None) -> Dict:
        """工作流列表"""
        workflows = list(self._workflows.values())
        if status:
            workflows = [w for w in workflows if w.status == status]
        total = len(workflows)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": workflows[start:end],
        }

    def execute_workflow(self, workflow_id: int, context: Dict) -> WorkflowExecution:
        """手动执行工作流"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        execution = WorkflowExecution(
            id=len(self._executions.get(workflow_id, [])) + 1,
            workflow_id=workflow_id,
            trigger_type=workflow.trigger_type.value,
            triggered_by=context.get("user_id", 0),
            started_at=datetime.now(),
            completed_at=None,
            status="running",
            result=None,
        )

        if workflow.conditions and not self.evaluate_conditions(workflow_id, context):
            execution.status = "failed"
            execution.result = {"error": "Conditions not met"}
            execution.completed_at = datetime.now()
        else:
            try:
                result = self.execute_actions(workflow_id, context)
                execution.status = "success"
                execution.result = result
            except Exception as e:
                execution.status = "failed"
                execution.result = {"error": str(e)}

        self._executions.setdefault(workflow_id, []).append(execution)
        return execution

    def evaluate_conditions(self, workflow_id: int, context: Dict) -> bool:
        """评估条件是否满足"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        for condition in workflow.conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            context_value = context.get(field)

            if operator == "==":
                if context_value != value:
                    return False
            elif operator == "!=":
                if context_value == value:
                    return False
            elif operator == ">":
                if not (context_value and context_value > value):
                    return False
            elif operator == "<":
                if not (context_value and context_value < value):
                    return False
            elif operator == ">=":
                if not (context_value and context_value >= value):
                    return False
            elif operator == "<=":
                if not (context_value and context_value <= value):
                    return False
            elif operator == "contains":
                if context_value is None or value not in str(context_value):  # type: ignore[operator]
                    return False

        return True

    def execute_actions(self, workflow_id: int, context: Dict) -> Dict:
        """执行动作列表"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        results = []
        for action in workflow.actions:
            action_type = action.get("type")
            if action_type == "email.send":
                results.append({
                    "type": "email.send",
                    "status": "sent",
                    "template": action.get("template"),
                })
            elif action_type == "notification.send":
                results.append({
                    "type": "notification.send",
                    "status": "sent",
                    "to": action.get("to"),
                })
            elif action_type == "tag.add":
                results.append({
                    "type": "tag.add",
                    "status": "added",
                    "tag": action.get("tag"),
                })
            elif action_type == "task.create":
                results.append({
                    "type": "task.create",
                    "status": "created",
                    "title": action.get("title"),
                })
            elif action_type == "activity.log":
                results.append({
                    "type": "activity.log",
                    "status": "logged",
                    "content": action.get("content"),
                })
            else:
                results.append({
                    "type": action_type,
                    "status": "unknown",
                })

        return {"actions_executed": results}

    def get_execution_history(self, workflow_id: int) -> List[WorkflowExecution]:
        """获取执行历史"""
        return self._executions.get(workflow_id, [])
