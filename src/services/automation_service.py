"""Automation rules service — DB-backed rule engine with execution logging."""
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.automation import AutomationLogModel, AutomationRuleModel
from models.response import ApiResponse, PaginatedData

# Supported trigger events
TRIGGER_EVENTS = [
    "ticket.created", "ticket.updated", "ticket.assigned",
    "opportunity.stage_changed", "opportunity.created",
    "customer.created", "customer.updated",
    "user.login", "lead.created",
]

# Supported action types
ACTION_TYPES = [
    "notification.send", "ticket.assign", "ticket.update_priority",
    "opportunity.add_note", "task.create", "email.send",
    "webhook.call", "tag.add",
]


def _eval_condition(condition: dict, context: dict) -> bool:
    """Evaluate a single condition against trigger context."""
    field = condition.get("field")
    operator = condition.get("operator")
    expected = condition.get("value")
    actual = context.get(field)

    if actual is None:
        return False

    op_map = {
        "eq": lambda a, e: a == e,
        "ne": lambda a, e: a != e,
        "gt": lambda a, e: float(a) > float(e),
        "gte": lambda a, e: float(a) >= float(e),
        "lt": lambda a, e: float(a) < float(e),
        "lte": lambda a, e: float(a) <= float(e),
        "contains": lambda a, e: str(e) in str(a),
        "startswith": lambda a, e: str(a).startswith(str(e)),
        "endswith": lambda a, e: str(a).endswith(str(e)),
    }

    fn = op_map.get(operator)
    if fn is None:
        return False
    try:
        return fn(actual, expected)
    except (ValueError, TypeError):
        return False


def _match_conditions(conditions: list, context: dict) -> bool:
    """Evaluate all conditions (AND logic). Returns True if no conditions."""
    if not conditions:
        return True
    return all(_eval_condition(c, context) for c in conditions)


async def _execute_action(
    action: dict,
    context: dict,
    session: AsyncSession,
    tenant_id: int,
    executed_by: int,
) -> dict:
    """Execute a single action and return result."""
    action_type = action.get("type")
    params = action.get("params", {})

    if action_type == "notification.send":
        # Delegate to NotificationService if available
        from services.notification_service import NotificationService
        svc = NotificationService(session)
        result = await svc.send_notification(
            user_id=params.get("user_id", context.get("user_id", 0)),
            notification_type="automation",
            title=params.get("title", "Automation triggered"),
            content=params.get("message", f"Automation rule triggered: {context.get('rule_name')}"),
            tenant_id=tenant_id,
            related_type=context.get("entity_type"),
            related_id=context.get("entity_id"),
        )
        return {"type": action_type, "status": "sent" if result.status.value == "success" else "failed"}

    elif action_type == "task.create":
        from services.task_service import TaskService
        svc = TaskService(session)
        task_result = await svc.create_task(
            tenant_id=tenant_id,
            title=params.get("title", "Automated task"),
            description=params.get("description", ""),
            assigned_to=params.get("assignee_id"),
            created_by=executed_by,
        )
        return {"type": action_type, "status": "created" if task_result.status.value == "success" else "failed"}

    elif action_type == "email.send":
        # Placeholder: record that email would be sent
        return {"type": action_type, "status": "queued", "template": params.get("template")}

    elif action_type == "webhook.call":
        return {"type": action_type, "status": "queued", "url": params.get("url")}

    elif action_type == "tag.add":
        return {"type": action_type, "status": "added", "tag": params.get("tag")}

    elif action_type == "ticket.assign":
        return {"type": action_type, "status": "assigned", "assignee_id": params.get("assignee_id")}

    elif action_type == "ticket.update_priority":
        return {"type": action_type, "status": "updated", "priority": params.get("priority")}

    elif action_type == "opportunity.add_note":
        return {"type": action_type, "status": "added", "note": params.get("note")}

    else:
        return {"type": action_type, "status": "unknown_action"}


class AutomationService:
    """DB-backed automation rule engine."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Rule CRUD
    # -------------------------------------------------------------------------

    async def create_rule(
        self,
        tenant_id: int,
        name: str,
        trigger_event: str,
        actions: list[dict],
        description: str | None = None,
        conditions: list[dict] | None = None,
        enabled: bool = True,
        created_by: int = 0,
    ) -> ApiResponse[AutomationRuleModel]:
        """Create a new automation rule."""
        now = datetime.now(UTC)
        model = AutomationRuleModel(
            tenant_id=tenant_id,
            name=name,
            description=description,
            trigger_event=trigger_event,
            conditions=conditions or [],
            actions=actions,
            enabled=enabled,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return ApiResponse.success(data=model.to_dict(), message="规则创建成功")

    async def list_rules(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        trigger_event: str | None = None,
        enabled: bool | None = None,
    ) -> ApiResponse[PaginatedData[dict]]:
        """List automation rules with pagination and filters."""
        base_stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.tenant_id == tenant_id
        )
        count_stmt = select(func.count(AutomationRuleModel.id)).where(
            AutomationRuleModel.tenant_id == tenant_id
        )

        if trigger_event is not None:
            base_stmt = base_stmt.where(AutomationRuleModel.trigger_event == trigger_event)
            count_stmt = count_stmt.where(AutomationRuleModel.trigger_event == trigger_event)
        if enabled is not None:
            base_stmt = base_stmt.where(AutomationRuleModel.enabled == enabled)
            count_stmt = count_stmt.where(AutomationRuleModel.enabled == enabled)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        paginated_stmt = (
            base_stmt.order_by(AutomationRuleModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(paginated_stmt)
        rows = result.scalars().all()

        items = [row.to_dict() for row in rows]
        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_rule(self, rule_id: int, tenant_id: int) -> ApiResponse[dict]:
        """Get a single automation rule."""
        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="规则不存在", code=404)
        return ApiResponse.success(data=row.to_dict())

    async def update_rule(
        self,
        rule_id: int,
        tenant_id: int,
        **kwargs,
    ) -> ApiResponse[dict]:
        """Update an automation rule."""
        kwargs["updated_at"] = datetime.now(UTC)
        stmt = (
            update(AutomationRuleModel)
            .where(
                AutomationRuleModel.id == rule_id,
                AutomationRuleModel.tenant_id == tenant_id,
            )
            .values(**kwargs)
            .returning(AutomationRuleModel)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="规则不存在", code=404)
        return ApiResponse.success(data=row.to_dict(), message="规则更新成功")

    async def delete_rule(self, rule_id: int, tenant_id: int) -> ApiResponse[dict]:
        """Delete an automation rule and its logs."""
        stmt = delete(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        if (result.rowcount or 0) <= 0:
            return ApiResponse.error(message="规则不存在", code=404)
        return ApiResponse.success(data={"id": rule_id}, message="规则删除成功")

    async def toggle_rule(self, rule_id: int, tenant_id: int) -> ApiResponse[dict]:
        """Toggle enabled status of a rule."""
        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="规则不存在", code=404)

        new_enabled = not row.enabled
        update_stmt = (
            update(AutomationRuleModel)
            .where(AutomationRuleModel.id == rule_id)
            .values(enabled=new_enabled, updated_at=datetime.now(UTC))
            .returning(AutomationRuleModel)
        )
        result2 = await self.session.execute(update_stmt)
        updated = result2.scalar_one()
        return ApiResponse.success(
            data=updated.to_dict(),
            message=f"规则{'启用' if new_enabled else '禁用'}成功",
        )

    # -------------------------------------------------------------------------
    # Rule execution (triggered by events)
    # -------------------------------------------------------------------------

    async def trigger_event(
        self,
        tenant_id: int,
        trigger_event: str,
        context: dict,
        executed_by: int = 0,
    ) -> list[dict]:
        """Find and execute all matching enabled rules for a trigger event.
        
        Returns list of execution results for each matched rule.
        """
        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.tenant_id == tenant_id,
            AutomationRuleModel.trigger_event == trigger_event,
            AutomationRuleModel.enabled == True,
        )
        result = await self.session.execute(stmt)
        rules = result.scalars().all()

        results = []
        for rule in rules:
            if not _match_conditions(rule.conditions, context):
                continue

            executed_actions = []
            errors = []
            for action in rule.actions:
                try:
                    action_result = await _execute_action(
                        action, {**context, "rule_name": rule.name},
                        self.session, tenant_id, executed_by,
                    )
                    executed_actions.append(action_result)
                except Exception as e:
                    executed_actions.append({
                        "type": action.get("type"),
                        "status": "error",
                        "error": str(e),
                    })
                    errors.append(str(e))

            log_status = "success" if not errors else "failed"
            log = AutomationLogModel(
                rule_id=rule.id,
                tenant_id=tenant_id,
                trigger_event=trigger_event,
                trigger_context=context,
                actions_executed=executed_actions,
                status=log_status,
                error_message="; ".join(errors) if errors else None,
                executed_by=executed_by,
                executed_at=datetime.now(UTC),
            )
            self.session.add(log)
            await self.session.flush()

            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "status": log_status,
                "actions_executed": executed_actions,
                "log_id": log.id,
            })

        return results

    # -------------------------------------------------------------------------
    # Execution logs
    # -------------------------------------------------------------------------

    async def list_logs(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        rule_id: int | None = None,
        status: str | None = None,
    ) -> ApiResponse[PaginatedData[dict]]:
        """List automation execution logs."""
        base_stmt = select(AutomationLogModel).where(
            AutomationLogModel.tenant_id == tenant_id
        )
        count_stmt = select(func.count(AutomationLogModel.id)).where(
            AutomationLogModel.tenant_id == tenant_id
        )

        if rule_id is not None:
            base_stmt = base_stmt.where(AutomationLogModel.rule_id == rule_id)
            count_stmt = count_stmt.where(AutomationLogModel.rule_id == rule_id)
        if status is not None:
            base_stmt = base_stmt.where(AutomationLogModel.status == status)
            count_stmt = count_stmt.where(AutomationLogModel.status == status)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        paginated_stmt = (
            base_stmt.order_by(AutomationLogModel.executed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(paginated_stmt)
        rows = result.scalars().all()

        items = [row.to_dict() for row in rows]
        return ApiResponse.paginated(data=items, total=total, page=page, page_size=page_size)
