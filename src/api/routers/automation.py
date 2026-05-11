"""Automation rules router — /api/v1/automation/rules endpoints.

Services raise AppException on errors (caught by global handler in main.py).
Router serializes ORM objects via .to_dict().
"""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.automation_service import AutomationService

automation_router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


def _paginated(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class ConditionItem(BaseModel):
    field: str = Field(..., min_length=1, max_length=100)
    operator: str = Field(..., min_length=1, max_length=20)
    value: str = Field(...)


class ActionItem(BaseModel):
    type: str = Field(..., min_length=1, max_length=50)
    params: dict = Field(default_factory=dict)


class AutomationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    trigger_event: str = Field(..., min_length=1, max_length=100)
    conditions: list[ConditionItem] = Field(default_factory=list)
    actions: list[ActionItem] = Field(..., min_length=1)
    enabled: bool = Field(default=True)


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    trigger_event: str | None = Field(None, max_length=100)
    conditions: list[ConditionItem] | None = Field(None)
    actions: list[ActionItem] | None = Field(None)
    enabled: bool | None = Field(None)


class TriggerEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    context: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@automation_router.post("/rules", status_code=201)
async def create_automation_rule(
    rule: AutomationRuleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    service = AutomationService(session)
    result = await service.create_rule(
        tenant_id=ctx.tenant_id,
        name=rule.name,
        description=rule.description,
        trigger_event=rule.trigger_event,
        conditions=[c.model_dump() for c in rule.conditions],
        actions=[a.model_dump() for a in rule.actions],
        enabled=rule.enabled,
        created_by=ctx.user_id,
    )
    return {"success": True, "data": result.to_dict(), "message": "自动化规则创建成功"}


@automation_router.get("/rules")
async def list_automation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trigger_event: str | None = Query(None),
    enabled: bool | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List automation rules for the tenant."""
    service = AutomationService(session)
    items, total = await service.list_rules(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        trigger_event=trigger_event,
        enabled=enabled,
    )
    return _paginated(items, total, page, page_size)


@automation_router.get("/rules/{rule_id}")
async def get_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific automation rule."""
    service = AutomationService(session)
    rule = await service.get_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict()}


@automation_router.put("/rules/{rule_id}")
async def update_automation_rule(
    rule_id: int,
    rule: AutomationRuleUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update an automation rule."""
    service = AutomationService(session)
    update_data = rule.model_dump(exclude_unset=True)
    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [dict(c) if hasattr(c, "model_dump") else c for c in update_data["conditions"]]
    if "actions" in update_data and update_data["actions"] is not None:
        update_data["actions"] = [dict(a) if hasattr(a, "model_dump") else a for a in update_data["actions"]]
    result = await service.update_rule(
        rule_id=rule_id,
        tenant_id=ctx.tenant_id,
        **update_data,
    )
    return {"success": True, "data": result.to_dict(), "message": "自动化规则更新成功"}


@automation_router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete an automation rule."""
    service = AutomationService(session)
    deleted_id = await service.delete_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"id": deleted_id}, "message": "自动化规则删除成功"}


@automation_router.post("/rules/{rule_id}/toggle")
async def toggle_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Enable or disable an automation rule."""
    service = AutomationService(session)
    rule = await service.toggle_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict(), "message": "自动化规则状态已切换"}


@automation_router.post("/trigger")
async def trigger_event(
    body: TriggerEventRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Trigger an automation event and execute matching rules."""
    service = AutomationService(session)
    results = await service.trigger_event(
        tenant_id=ctx.tenant_id,
        event_type=body.event_type,
        context=body.context,
    )
    return {"success": True, "data": results}


@automation_router.get("/logs")
async def list_automation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_id: int | None = Query(None),
    status: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List automation execution logs."""
    service = AutomationService(session)
    items, total = await service.list_logs(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        rule_id=rule_id,
        status=status,
    )
    return _paginated(items, total, page, page_size)
