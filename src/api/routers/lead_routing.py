"""Lead routing rules REST API — CRUD, priority ordering, and rule test preview."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.routing import (
    RoutingRuleCreate,
    RoutingRulePriorityUpdate,
    RoutingRuleUpdate,
    RuleTestRequest,
)
from pkg.errors.app_exceptions import ForbiddenException, NotFoundException
from services.lead_routing_service import LeadRoutingService

lead_routing_router = APIRouter(prefix="/api/v1/settings/routing", tags=["lead_routing"])


async def _require_admin_or_manager(ctx: AuthContext) -> None:
    """Raise ForbiddenException if user is neither admin nor manager."""
    if "admin" not in ctx.roles and "manager" not in ctx.roles:
        raise ForbiddenException("需要 admin 或 manager 角色才能管理路由规则")


@lead_routing_router.get("")
async def list_routing_rules(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List all routing rules for the current tenant."""
    from sqlalchemy import select

    from db.models.routing_rule import RoutingRuleModel

    result = await session.execute(
        select(RoutingRuleModel)
        .where(RoutingRuleModel.tenant_id == ctx.tenant_id)
        .order_by(RoutingRuleModel.priority.desc(), RoutingRuleModel.id.asc())
    )
    rules = result.scalars().all()
    return {
        "success": True,
        "data": {
            "items": [r.to_dict() for r in rules],
            "total": len(rules),
        },
        "message": "OK",
    }


@lead_routing_router.post("")
async def create_routing_rule(
    body: RoutingRuleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new routing rule."""
    await _require_admin_or_manager(ctx)
    from db.models.routing_rule import RoutingRuleModel

    now = datetime.now(UTC)
    rule = RoutingRuleModel(
        tenant_id=ctx.tenant_id,
        name=body.name,
        conditions_json=[c.model_dump() for c in body.conditions_json],
        assignee_type=body.assignee_type,
        assignee_id=body.assignee_id,
        priority=body.priority,
        is_active=body.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return {"success": True, "data": rule.to_dict(), "message": "路由规则创建成功"}


@lead_routing_router.post("/test")
async def test_routing_rule(
    body: RuleTestRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Test routing conditions without persisting any changes."""
    svc = LeadRoutingService(session)
    preview = await svc.preview_assign(body.conditions, body.customer_data, tenant_id=ctx.tenant_id)
    return {"success": True, "data": preview.model_dump(), "message": "OK"}


@lead_routing_router.get("/{rule_id}")
async def get_routing_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a single routing rule by ID."""
    from sqlalchemy import select

    from db.models.routing_rule import RoutingRuleModel

    result = await session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.tenant_id == ctx.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundException("路由规则")
    return {"success": True, "data": rule.to_dict(), "message": "OK"}


@lead_routing_router.put("/{rule_id}")
async def update_routing_rule(
    rule_id: int,
    body: RoutingRuleUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update an existing routing rule."""
    await _require_admin_or_manager(ctx, session)
    from sqlalchemy import select, update

    from db.models.routing_rule import RoutingRuleModel

    result = await session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.tenant_id == ctx.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundException("路由规则")

    update_vals: dict = {}
    if body.name is not None:
        update_vals["name"] = body.name
    if body.conditions_json is not None:
        update_vals["conditions_json"] = [c.model_dump() for c in body.conditions_json]
    if body.assignee_type is not None:
        update_vals["assignee_type"] = body.assignee_type
    if body.assignee_id is not None:
        update_vals["assignee_id"] = body.assignee_id
    if body.priority is not None:
        update_vals["priority"] = body.priority
    if body.is_active is not None:
        update_vals["is_active"] = body.is_active

    if update_vals:
        update_vals["updated_at"] = datetime.now(UTC)
        await session.execute(
            update(RoutingRuleModel)
            .where(
                RoutingRuleModel.id == rule_id,
                RoutingRuleModel.tenant_id == ctx.tenant_id,
            )
            .values(**update_vals)
        )
        await session.flush()
        # refresh() intentionally omitted after raw UPDATE — stale object returned to caller

    return {"success": True, "data": rule.to_dict(), "message": "路由规则更新成功"}


@lead_routing_router.delete("/{rule_id}")
async def delete_routing_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a routing rule."""
    await _require_admin_or_manager(ctx, session)
    from sqlalchemy import delete

    from db.models.routing_rule import RoutingRuleModel

    result = await session.execute(
        delete(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.tenant_id == ctx.tenant_id,
        )
    )
    if result.rowcount == 0:
        raise NotFoundException("路由规则")
    return {"success": True, "data": {"id": rule_id}, "message": "路由规则删除成功"}


@lead_routing_router.put("/priority")
async def reorder_routing_rules(
    body: RoutingRulePriorityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Bulk reorder routing rules by priority.

    Body: {rule_ids: [3, 1, 2]} assigns priority len - index (highest first).
    """
    await _require_admin_or_manager(ctx, session)
    from sqlalchemy import update

    from db.models.routing_rule import RoutingRuleModel

    rule_ids = body.rule_ids
    if len(rule_ids) != len(set(rule_ids)):
        from pkg.errors.app_exceptions import ValidationException

        raise ValidationException("rule_ids must not contain duplicates")
    # Assign priority: highest priority = highest position in the list
    now = datetime.now(UTC)
    # Batch into a single UPDATE per rule to avoid N statements
    for idx, rid in enumerate(rule_ids):
        await session.execute(
            update(RoutingRuleModel)
            .where(
                RoutingRuleModel.id == rid,
                RoutingRuleModel.tenant_id == ctx.tenant_id,
            )
            .values(priority=len(rule_ids) - idx, updated_at=now)
        )
    await session.flush()
    return {"success": True, "message": "优先级更新成功"}


@lead_routing_router.put("/{rule_id}/toggle")
async def toggle_routing_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Toggle is_active status of a routing rule."""
    await _require_admin_or_manager(ctx, session)
    from sqlalchemy import select, update

    from db.models.routing_rule import RoutingRuleModel

    result = await session.execute(
        select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.tenant_id == ctx.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundException("路由规则")

    await session.execute(
        update(RoutingRuleModel)
        .where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.tenant_id == ctx.tenant_id,
        )
        .values(is_active=not rule.is_active, updated_at=datetime.now(UTC))
    )
    new_is_active = not rule.is_active
    return {
        "success": True,
        "data": {"id": rule_id, "is_active": new_is_active},
        "message": f"路由规则已{'启用' if new_is_active else '禁用'}",
    }
