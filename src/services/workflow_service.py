"""Workflow service — DB-backed via SQLAlchemy async ORM."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.workflow import WorkflowExecutionModel, WorkflowModel
from pkg.errors.app_exceptions import NotFoundException


def _enum_val(v):
    """Coerce enum-or-string to string."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


class WorkflowService:
    """工作流自动化引擎 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow(
        self,
        name: str,
        trigger_type,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> WorkflowModel:
        """创建工作流"""
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name=name,
            description=kwargs.get("description"),
            trigger_type=_enum_val(trigger_type) or "manual",
            trigger_config=kwargs.get("trigger_config", {}),
            actions=kwargs.get("actions", []),
            conditions=kwargs.get("conditions", []),
            status="draft",
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(workflow)
        await self.session.flush()
        await self.session.refresh(workflow)
        await self.session.commit()
        return workflow

    async def get_workflow(self, workflow_id: int, tenant_id: int = 0) -> WorkflowModel:
        """获取工作流详情"""
        result = await self.session.execute(
            select(WorkflowModel).where(and_(WorkflowModel.id == workflow_id, WorkflowModel.tenant_id == tenant_id))
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise NotFoundException("Workflow")
        return workflow

    async def update_workflow(self, workflow_id: int, tenant_id: int = 0, **kwargs) -> WorkflowModel:
        """更新工作流"""
        workflow = await self.get_workflow(workflow_id, tenant_id)
        allowed = {"name", "description", "trigger_type", "trigger_config", "actions", "conditions", "status"}
        for key, value in kwargs.items():
            if key in allowed:
                if key in ("trigger_type", "status"):
                    value = _enum_val(value)
                setattr(workflow, key, value)
        workflow.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def activate_workflow(self, workflow_id: int, tenant_id: int = 0) -> WorkflowModel:
        """激活工作流"""
        return await self.update_workflow(workflow_id, tenant_id, status="active")

    async def pause_workflow(self, workflow_id: int, tenant_id: int = 0) -> WorkflowModel:
        """暂停工作流"""
        return await self.update_workflow(workflow_id, tenant_id, status="paused")

    async def delete_workflow(self, workflow_id: int, tenant_id: int = 0) -> int:
        """删除工作流"""
        result = await self.session.execute(
            delete(WorkflowModel).where(and_(WorkflowModel.id == workflow_id, WorkflowModel.tenant_id == tenant_id))
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("Workflow")
        await self.session.commit()
        return workflow_id

    async def list_workflows(
        self,
        tenant_id: int = 0,
        page: int = 1,
        page_size: int = 20,
        status=None,
    ) -> tuple[list[WorkflowModel], int]:
        """工作流列表"""
        conditions = [WorkflowModel.tenant_id == tenant_id]
        if status is not None:
            conditions.append(WorkflowModel.status == _enum_val(status))

        count_result = await self.session.execute(select(func.count(WorkflowModel.id)).where(and_(*conditions)))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(WorkflowModel).where(and_(*conditions)).order_by(WorkflowModel.id).offset(offset).limit(page_size)
        )
        return result.scalars().all(), total

    async def execute_workflow(
        self,
        workflow_id: int,
        context: dict,
        tenant_id: int = 0,
    ) -> WorkflowExecutionModel:
        """手动执行工作流"""
        workflow = await self.get_workflow(workflow_id, tenant_id)

        execution = WorkflowExecutionModel(
            workflow_id=workflow_id,
            trigger_type=workflow.trigger_type,
            triggered_by=context.get("user_id", 0),
            started_at=datetime.now(UTC),
            status="running",
        )
        self.session.add(execution)
        await self.session.flush()

        if workflow.conditions and not self._evaluate_conditions(workflow, context):
            execution.status = "failed"
            execution.result = {"error": "Conditions not met"}
            execution.completed_at = datetime.now(UTC)
        else:
            try:
                result = self._execute_actions(workflow)
                execution.status = "success"
                execution.result = result
            except Exception as e:
                execution.status = "failed"
                execution.result = {"error": str(e)}
            execution.completed_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(execution)
        return execution

    async def evaluate_conditions(self, workflow_id: int, context: dict, tenant_id: int = 0) -> bool:
        """评估条件是否满足"""
        workflow = await self.get_workflow(workflow_id, tenant_id)
        return self._evaluate_conditions(workflow, context)

    @staticmethod
    def _evaluate_conditions(workflow: WorkflowModel, context: dict) -> bool:
        for condition in workflow.conditions or []:
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
                if value not in str(context_value):
                    return False
        return True

    async def execute_actions(self, workflow_id: int, context: dict, tenant_id: int = 0) -> dict:
        """执行动作列表"""
        workflow = await self.get_workflow(workflow_id, tenant_id)
        return self._execute_actions(workflow)

    @staticmethod
    def _execute_actions(workflow: WorkflowModel) -> dict:
        results = []
        for action in workflow.actions or []:
            action_type = action.get("type")
            if action_type == "email.send":
                results.append({"type": "email.send", "status": "sent", "template": action.get("template")})
            elif action_type == "notification.send":
                results.append({"type": "notification.send", "status": "sent", "to": action.get("to")})
            elif action_type == "tag.add":
                results.append({"type": "tag.add", "status": "added", "tag": action.get("tag")})
            elif action_type == "task.create":
                results.append({"type": "task.create", "status": "created", "title": action.get("title")})
            elif action_type == "activity.log":
                results.append({"type": "activity.log", "status": "logged", "content": action.get("content")})
            else:
                results.append({"type": action_type, "status": "unknown"})
        return {"actions_executed": results}

    async def get_execution_history(
        self,
        workflow_id: int,
        tenant_id: int = 0,
    ) -> list[WorkflowExecutionModel]:
        """获取执行历史"""
        # Verify ownership
        await self.get_workflow(workflow_id, tenant_id)
        result = await self.session.execute(
            select(WorkflowExecutionModel)
            .where(WorkflowExecutionModel.workflow_id == workflow_id)
            .order_by(WorkflowExecutionModel.started_at.desc())
        )
        return result.scalars().all()
