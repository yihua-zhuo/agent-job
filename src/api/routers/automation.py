"""Automation rules router — /api/v1/automation/rules endpoints."""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from services.automation_service import AutomationService

automation_router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


def _http_status(status: ResponseStatus) -> int:
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.CREATED: 201,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


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


class AutomationRuleData(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: str | None
    trigger_event: str
    conditions: list[dict]
    actions: list[dict]
    enabled: bool
    created_by: int
    created_at: str | None
    updated_at: str | None


class AutomationRuleResponse(BaseModel):
    success: bool
    data: AutomationRuleData | None = None
    message: str | None = None


class AutomationRuleListData(BaseModel):
    items: list[AutomationRuleData]
    total: int
    page: int
    page_size: int


class AutomationRuleListResponse(BaseModel):
    success: bool
    data: AutomationRuleListData | None = None
    message: str | None = None


class AutomationLogData(BaseModel):
    id: int
    rule_id: int
    tenant_id: int
    trigger_event: str
    trigger_context: dict
    actions_executed: list[dict]
    status: str
    error_message: str | None
    executed_by: int
    executed_at: str | None


class AutomationLogListData(BaseModel):
    items: list[AutomationLogData]
    total: int
    page: int
    page_size: int


class AutomationLogListResponse(BaseModel):
    success: bool
    data: AutomationLogListData | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@automation_router.post("/rules", status_code=201)
async def create_automation_rule(
    rule: AutomationRuleCreate,
    ctx: AuthContext = Depends(require_auth),
):
    """Create a new automation rule."""
    async with get_db() as session:
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
        status_code = _http_status(result.status)
        return result.to_dict(status_code=status_code)


@automation_router.get("/rules")
async def list_automation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trigger_event: str | None = Query(None),
    enabled: bool | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
):
    """List automation rules for the tenant."""
    async with get_db() as session:
        service = AutomationService(session)
        result = await service.list_rules(
            tenant_id=ctx.tenant_id,
            page=page,
            page_size=page_size,
            trigger_event=trigger_event,
            enabled=enabled,
        )
        return result.to_dict()


@automation_router.get("/rules/{rule_id}")
async def get_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    """Get a specific automation rule."""
    async with get_db() as session:
        service = AutomationService(session)
        result = await service.get_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
        status_code = _http_status(result.status)
        return result.to_dict(status_code=status_code)


@automation_router.put("/rules/{rule_id}")
async def update_automation_rule(
    rule_id: int,
    rule: AutomationRuleUpdate,
    ctx: AuthContext = Depends(require_auth),
):
    """Update an automation rule."""
    async with get_db() as session:
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
        status_code = _http_status(result.status)
        return result.to_dict(status_code=status_code)


@automation_router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    """Delete an automation rule."""
    async with get_db() as session:
        service = AutomationService(session)
        result = await service.delete_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
        status_code = _http_status(result.status)
        return result.to_dict(status_code=status_code)


@automation_router.post("/rules/{rule_id}/toggle")
async def toggle_automation_rule(
    rule_id: int = Path(..., ge=1),
    ctx: AuthContext = Depends(require_auth),
):
    """Enable or disable an automation rule."""
    async with get_db() as session:
        service = AutomationService(session)
        result = await service.toggle_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
        status_code = _http_status(result.status)
        return result.to_dict(status_code=status_code)


@automation_router.get("/logs")
async def list_automation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_id: int | None = Query(None),
    status: str | None = Query(None),
    ctx: AuthContext = Depends(require_auth),
):
    """List automation execution logs."""
    async with get_db() as session:
        service = AutomationService(session)
        result = await service.list_logs(
            tenant_id=ctx.tenant_id,
            page=page,
            page_size=page_size,
            rule_id=rule_id,
            status=status,
        )
        return result.to_dict()
