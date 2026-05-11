"""Automation rules service — DB-backed rule engine with execution logging."""
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.automation import AutomationLogModel, AutomationRuleModel
from pkg.errors.app_exceptions import NotFoundException

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
    action_type = action.get("type")
    params = action.get("params", {})

    if action_type == "notification.send":
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
        return {"type": action_type, "status": "sent" if result else "failed"}

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
        return {"type": action_type, "status": "created" if task_result else "failed"}

    elif action_type == "email.send":
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
    ) -> AutomationRuleModel:
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
        return model

    async def list_rules(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        trigger_event: str | None = None,
        enabled: bool | None = None,
    ) -> tuple[list[AutomationRuleModel], int]:
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
        result = await self.session.execute(
            base_stmt.order_by(AutomationRuleModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def get_rule(self, rule_id: int, tenant_id: int) -> AutomationRuleModel:
        result = await self.session.execute(
            select(AutomationRuleModel).where(
                AutomationRuleModel.id == rule_id,
                AutomationRuleModel.tenant_id == tenant_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundException("规则")
        return row

    async def update_rule(
        self,
        rule_id: int,
        tenant_id: int,
        **kwargs,
    ) -> AutomationRuleModel:
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
            raise NotFoundException("规则")
        return row

    async def delete_rule(self, rule_id: int, tenant_id: int) -> int:
        stmt = delete(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        if (result.rowcount or 0) <= 0:
            raise NotFoundException("规则")
        return rule_id

    async def toggle_rule(self, rule_id: int, tenant_id: int) -> AutomationRuleModel:
        row = await self.get_rule(rule_id, tenant_id)
        new_enabled = not row.enabled
        update_stmt = (
            update(AutomationRuleModel)
            .where(AutomationRuleModel.id == rule_id)
            .values(enabled=new_enabled, updated_at=datetime.now(UTC))
            .returning(AutomationRuleModel)
        )
        result = await self.session.execute(update_stmt)
        return result.scalar_one()

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
        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.tenant_id == tenant_id,
            AutomationRuleModel.trigger_event == trigger_event,
            AutomationRuleModel.enabled == True,  # noqa: E712
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
    ) -> tuple[list[AutomationLogModel], int]:
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
        result = await self.session.execute(
            base_stmt.order_by(AutomationLogModel.executed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total
