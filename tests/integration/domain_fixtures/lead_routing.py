"""Lead routing integration test helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def seed_routing_rule(
    session: AsyncSession,
    tenant_id: int,
    name: str = "APAC Rule",
    conditions: list[dict] | None = None,
    assignee_type: str = "user",
    assignee_id: int | None = 5,
    priority: int = 100,
    is_active: bool = True,
):
    """Seed a routing rule for lead routing tests."""
    from datetime import UTC, datetime

    from db.models.routing_rule import RoutingRuleModel

    rule = RoutingRuleModel(
        tenant_id=tenant_id,
        name=name,
        conditions_json=(
            conditions
            if conditions is not None
            else [{"field": "region", "operator": "in", "value": ["APAC"]}]
        ),
        assignee_type=assignee_type,
        assignee_id=assignee_id,
        priority=priority,
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(rule)
    await session.flush()
    return rule


__all__ = ["seed_routing_rule"]
