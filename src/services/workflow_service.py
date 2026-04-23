"""Workflow automation service backed by PostgreSQL via SQLAlchemy async."""
from datetime import datetime
from typing import Dict, List, Optional, Union

from sqlalchemy import delete, func, select, update

from db.connection import get_db_session
from db.models.workflow import WorkflowExecutionModel, WorkflowModel
from models.response import ApiResponse, PaginatedData
from models.workflow import TriggerType, WorkflowStatus


def _as_trigger_value(value: Union[str, TriggerType, None]) -> str:
    if value is None:
        return TriggerType.MANUAL.value
    if isinstance(value, TriggerType):
        return value.value
    return str(value)


def _as_status_value(value: Union[str, WorkflowStatus, None]) -> str:
    if value is None:
        return WorkflowStatus.DRAFT.value
    if isinstance(value, WorkflowStatus):
        return value.value
    return str(value)


class WorkflowService:
    """Workflow automation engine."""

    async def create_workflow(
        self,
        name: str,
        trigger_type: Union[str, TriggerType],
        created_by: int,
        **kwargs,
    ) -> ApiResponse:
        """Create a new workflow."""
        now = datetime.utcnow()
        async with get_db_session() as session:
            row = WorkflowModel(
                tenant_id=kwargs.get("tenant_id", 0),
                name=name,
                description=kwargs.get("description"),
                trigger_type=_as_trigger_value(trigger_type),
                trigger_config=kwargs.get("trigger_config") or {},
                actions=kwargs.get("actions") or [],
                conditions=kwargs.get("conditions") or [],
                status=_as_status_value(kwargs.get("status", WorkflowStatus.DRAFT)),
                created_by=created_by,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return ApiResponse.success(data=row.to_dict(), message="工作流创建成功")

    async def get_workflow(self, workflow_id: int) -> ApiResponse:
        """Fetch a workflow by id."""
        async with get_db_session() as session:
            result = await session.execute(
                select(WorkflowModel).where(WorkflowModel.id == workflow_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return ApiResponse.error(message="工作流不存在", code=3001)
            return ApiResponse.success(data=row.to_dict(), message="")

    async def update_workflow(self, workflow_id: int, data: Dict) -> ApiResponse:
        """Update fields on a workflow."""
        update_values: Dict = {"updated_at": datetime.utcnow()}
        for key in ("name", "description", "trigger_config", "actions", "conditions"):
            if key in data:
                update_values[key] = data[key]
        if "trigger_type" in data:
            update_values["trigger_type"] = _as_trigger_value(data["trigger_type"])
        if "status" in data:
            update_values["status"] = _as_status_value(data["status"])

        async with get_db_session() as session:
            stmt = (
                update(WorkflowModel)
                .where(WorkflowModel.id == workflow_id)
                .values(**update_values)
                .returning(WorkflowModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return ApiResponse.error(message="工作流不存在", code=3001)
            return ApiResponse.success(data=row.to_dict(), message="工作流更新成功")

    async def _transition_status(
        self, workflow_id: int, new_status: WorkflowStatus
    ) -> ApiResponse:
        async with get_db_session() as session:
            stmt = (
                update(WorkflowModel)
                .where(WorkflowModel.id == workflow_id)
                .values(status=new_status.value, updated_at=datetime.utcnow())
                .returning(WorkflowModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return ApiResponse.error(message="工作流不存在", code=3001)
            return ApiResponse.success(data=row.to_dict(), message="状态更新成功")

    async def activate_workflow(self, workflow_id: int) -> ApiResponse:
        return await self._transition_status(workflow_id, WorkflowStatus.ACTIVE)

    async def pause_workflow(self, workflow_id: int) -> ApiResponse:
        return await self._transition_status(workflow_id, WorkflowStatus.PAUSED)

    async def delete_workflow(self, workflow_id: int) -> ApiResponse:
        async with get_db_session() as session:
            result = await session.execute(
                delete(WorkflowModel).where(WorkflowModel.id == workflow_id)
            )
            if (result.rowcount or 0) <= 0:
                return ApiResponse.error(message="工作流不存在", code=3001)
            return ApiResponse.success(
                data={"id": workflow_id}, message="工作流删除成功"
            )

    async def list_workflows(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Union[str, WorkflowStatus, None] = None,
    ) -> ApiResponse:
        """Paginated workflow listing."""
        async with get_db_session() as session:
            base_stmt = select(WorkflowModel)
            count_stmt = select(func.count(WorkflowModel.id))
            if status is not None:
                status_value = _as_status_value(status)
                base_stmt = base_stmt.where(WorkflowModel.status == status_value)
                count_stmt = count_stmt.where(WorkflowModel.status == status_value)

            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            offset = (page - 1) * page_size
            paginated_stmt = (
                base_stmt.order_by(WorkflowModel.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(paginated_stmt)
            items = [row.to_dict() for row in result.scalars().all()]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="",
        )

    async def execute_workflow(self, workflow_id: int, context: Dict) -> ApiResponse:
        """Execute a workflow and record the execution."""
        wf_resp = await self.get_workflow(workflow_id)
        if not bool(wf_resp):
            return wf_resp
        workflow = wf_resp.data

        status: str = "running"
        exec_result: Optional[Dict] = None
        completed_at: Optional[datetime] = None

        conditions = workflow.get("conditions") or []
        if conditions and not await self._check_conditions(conditions, context):
            status = "failed"
            exec_result = {"error": "Conditions not met"}
            completed_at = datetime.utcnow()
        else:
            try:
                exec_result = await self._run_actions(
                    workflow.get("actions") or []
                )
                status = "success"
            except Exception as exc:  # noqa: BLE001 - surface runtime failure to caller
                status = "failed"
                exec_result = {"error": str(exc)}
            completed_at = datetime.utcnow()

        started_at = datetime.utcnow()
        async with get_db_session() as session:
            exec_row = WorkflowExecutionModel(
                workflow_id=workflow_id,
                trigger_type=_as_trigger_value(workflow.get("trigger_type")),
                triggered_by=int(context.get("user_id", 0) or 0),
                started_at=started_at,
                completed_at=completed_at,
                status=status,
                result=exec_result,
            )
            session.add(exec_row)
            await session.flush()
            return ApiResponse.success(
                data=exec_row.to_dict(), message="工作流已执行"
            )

    async def evaluate_conditions(self, workflow_id: int, context: Dict) -> bool:
        wf_resp = await self.get_workflow(workflow_id)
        if not bool(wf_resp):
            return False
        conditions = wf_resp.data.get("conditions") or []
        return await self._check_conditions(conditions, context)

    async def execute_actions(self, workflow_id: int, context: Dict) -> Dict:
        wf_resp = await self.get_workflow(workflow_id)
        if not bool(wf_resp):
            raise ValueError(f"Workflow {workflow_id} not found")
        return await self._run_actions(wf_resp.data.get("actions") or [])

    async def get_execution_history(self, workflow_id: int) -> ApiResponse:
        async with get_db_session() as session:
            result = await session.execute(
                select(WorkflowExecutionModel)
                .where(WorkflowExecutionModel.workflow_id == workflow_id)
                .order_by(WorkflowExecutionModel.started_at.desc())
            )
            items = [row.to_dict() for row in result.scalars().all()]
        return ApiResponse.success(
            data={"items": items, "total": len(items)}, message=""
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def _check_conditions(conditions: List[Dict], context: Dict) -> bool:
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            ctx_value = context.get(field) if field else None

            if operator == "==":
                if ctx_value != value:
                    return False
            elif operator == "!=":
                if ctx_value == value:
                    return False
            elif operator == ">":
                if ctx_value is None or not (ctx_value > value):
                    return False
            elif operator == "<":
                if ctx_value is None or not (ctx_value < value):
                    return False
            elif operator == ">=":
                if ctx_value is None or not (ctx_value >= value):
                    return False
            elif operator == "<=":
                if ctx_value is None or not (ctx_value <= value):
                    return False
            elif operator == "contains":
                if ctx_value is None or not isinstance(value, str) or value not in str(ctx_value):
                    return False
        return True

    @staticmethod
    async def _run_actions(actions: List[Dict]) -> Dict:
        results: List[Dict] = []
        for action in actions:
            action_type = action.get("type")
            if action_type == "email.send":
                results.append(
                    {
                        "type": "email.send",
                        "status": "sent",
                        "template": action.get("template"),
                    }
                )
            elif action_type == "notification.send":
                results.append(
                    {
                        "type": "notification.send",
                        "status": "sent",
                        "to": action.get("to"),
                    }
                )
            elif action_type == "tag.add":
                results.append(
                    {"type": "tag.add", "status": "added", "tag": action.get("tag")}
                )
            elif action_type == "task.create":
                results.append(
                    {
                        "type": "task.create",
                        "status": "created",
                        "title": action.get("title"),
                    }
                )
            elif action_type == "activity.log":
                results.append(
                    {
                        "type": "activity.log",
                        "status": "logged",
                        "content": action.get("content"),
                    }
                )
            else:
                results.append({"type": action_type, "status": "unknown"})
        return {"actions_executed": results}
