"""
工作流自动化引擎
使用 PostgreSQL + SQLAlchemy async 进行持久化存储
"""
from datetime import datetime
from typing import List, Dict, Optional

from sqlalchemy import select, update, delete, func, and_, or_, insert as pg_insert

from db.connection import get_db_session
from models.workflow import Workflow, WorkflowExecution, WorkflowStatus, TriggerType


class WorkflowService:
    """工作流自动化引擎"""

    def __init__(self):
        pass

    async def create_workflow(
        self,
        name: str,
        trigger_type: TriggerType,
        created_by: int,
        **kwargs,
    ) -> Workflow:
        """创建工作流"""
        async with get_db_session() as session:
            stmt = pg_insert(Workflow).values(
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
            ).returning(
                Workflow.id,
                Workflow.name,
                Workflow.description,
                Workflow.trigger_type,
                Workflow.trigger_config,
                Workflow.actions,
                Workflow.conditions,
                Workflow.status,
                Workflow.created_by,
                Workflow.created_at,
                Workflow.updated_at,
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            return Workflow(*row)

    async def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """获取工作流详情"""
        async with get_db_session() as session:
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await session.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return Workflow(*row) if not isinstance(row, Workflow) else row

    async def update_workflow(self, workflow_id: int, **kwargs) -> Optional[Workflow]:
        """更新工作流"""
        update_values: Dict = {"updated_at": datetime.now()}
        if "name" in kwargs:
            update_values["name"] = kwargs["name"]
        if "description" in kwargs:
            update_values["description"] = kwargs["description"]
        if "trigger_type" in kwargs:
            update_values["trigger_type"] = kwargs["trigger_type"]
        if "trigger_config" in kwargs:
            update_values["trigger_config"] = kwargs["trigger_config"]
        if "actions" in kwargs:
            update_values["actions"] = kwargs["actions"]
        if "conditions" in kwargs:
            update_values["conditions"] = kwargs["conditions"]

        async with get_db_session() as session:
            stmt = (
                update(Workflow)
                .where(Workflow.id == workflow_id)
                .values(**update_values)
                .returning(
                    Workflow.id,
                    Workflow.name,
                    Workflow.description,
                    Workflow.trigger_type,
                    Workflow.trigger_config,
                    Workflow.actions,
                    Workflow.conditions,
                    Workflow.status,
                    Workflow.created_by,
                    Workflow.created_at,
                    Workflow.updated_at,
                )
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return Workflow(*row)

    async def activate_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """激活工作流"""
        async with get_db_session() as session:
            stmt = (
                update(Workflow)
                .where(Workflow.id == workflow_id)
                .values(status=WorkflowStatus.ACTIVE, updated_at=datetime.now())
                .returning(
                    Workflow.id,
                    Workflow.name,
                    Workflow.description,
                    Workflow.trigger_type,
                    Workflow.trigger_config,
                    Workflow.actions,
                    Workflow.conditions,
                    Workflow.status,
                    Workflow.created_by,
                    Workflow.created_at,
                    Workflow.updated_at,
                )
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return Workflow(*row)

    async def pause_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """暂停工作流"""
        async with get_db_session() as session:
            stmt = (
                update(Workflow)
                .where(Workflow.id == workflow_id)
                .values(status=WorkflowStatus.PAUSED, updated_at=datetime.now())
                .returning(
                    Workflow.id,
                    Workflow.name,
                    Workflow.description,
                    Workflow.trigger_type,
                    Workflow.trigger_config,
                    Workflow.actions,
                    Workflow.conditions,
                    Workflow.status,
                    Workflow.created_by,
                    Workflow.created_at,
                    Workflow.updated_at,
                )
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return Workflow(*row)

    async def delete_workflow(self, workflow_id: int) -> bool:
        """删除工作流"""
        async with get_db_session() as session:
            stmt = delete(Workflow).where(Workflow.id == workflow_id)
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def list_workflows(
        self,
        page: int = 1,
        page_size: int = 20,
        status: WorkflowStatus = None,
    ) -> Dict:
        """工作流列表"""
        async with get_db_session() as session:
            base_stmt = select(Workflow)
            count_stmt = select(func.count(Workflow.id))

            if status is not None:
                base_stmt = base_stmt.where(Workflow.status == status)
                count_stmt = count_stmt.where(Workflow.status == status)

            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            offset = (page - 1) * page_size
            paginated_stmt = (
                base_stmt.order_by(Workflow.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(paginated_stmt)
            rows = result.fetchall()
            items = [Workflow(*row) if not isinstance(row, Workflow) else row for row in rows]

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    async def execute_workflow(self, workflow_id: int, context: Dict) -> WorkflowExecution:
        """手动执行工作流"""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        execution = WorkflowExecution(
            id=None,
            workflow_id=workflow_id,
            trigger_type=workflow.trigger_type.value,
            triggered_by=context.get("user_id", 0),
            started_at=datetime.now(),
            completed_at=None,
            status="running",
            result=None,
        )

        if workflow.conditions and not await self.evaluate_conditions(workflow_id, context):
            execution.status = "failed"
            execution.result = {"error": "Conditions not met"}
            execution.completed_at = datetime.now()
        else:
            try:
                result = await self.execute_actions(workflow_id, context)
                execution.status = "success"
                execution.result = result
            except Exception as e:
                execution.status = "failed"
                execution.result = {"error": str(e)}
            execution.completed_at = datetime.now()

        # Persist execution record
        async with get_db_session() as session:
            stmt = pg_insert(WorkflowExecution).values(
                workflow_id=execution.workflow_id,
                trigger_type=execution.trigger_type,
                triggered_by=execution.triggered_by,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                status=execution.status,
                result=execution.result,
            ).returning(WorkflowExecution.id)
            result = await session.execute(stmt)
            execution_id_row = result.fetchone()
            if execution_id_row is not None:
                execution.id = execution_id_row[0]
        return execution

    async def evaluate_conditions(self, workflow_id: int, context: Dict) -> bool:
        """评估条件是否满足"""
        workflow = await self.get_workflow(workflow_id)
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

    async def execute_actions(self, workflow_id: int, context: Dict) -> Dict:
        """执行动作列表"""
        workflow = await self.get_workflow(workflow_id)
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

    async def get_execution_history(self, workflow_id: int) -> List[WorkflowExecution]:
        """获取执行历史"""
        async with get_db_session() as session:
            stmt = (
                select(WorkflowExecution)
                .where(WorkflowExecution.workflow_id == workflow_id)
                .order_by(WorkflowExecution.started_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.fetchall()
            return [WorkflowExecution(*row) if not isinstance(row, WorkflowExecution) else row for row in rows]
