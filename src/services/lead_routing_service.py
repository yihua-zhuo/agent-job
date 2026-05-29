"""Lead routing service — rule evaluation, auto-assignment, load balancing, and recycling."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.routing_rule import RoutingRuleModel
from db.models.tenant import TenantModel
from db.models.user import UserModel
from models.routing import SUPPORTED_FIELDS, ConditionOperator, LeadAssignPreview, RuleCondition
from pkg.errors.app_exceptions import ValidationException

logger = logging.getLogger(__name__)

DEFAULT_MAX_LOAD_PER_REP = 20


def evaluate_conditions(conditions: list[RuleCondition], customer: dict[str, Any]) -> bool:
    """Evaluate a rule's conditions against a customer record.

    Returns True only if ALL conditions match (AND logic).
    """
    for cond in conditions:
        field_val = customer.get(cond.field)
        cond_val = cond.value

        if cond.operator == ConditionOperator.EQUALS:
            if field_val != cond_val:
                return False
        elif cond.operator == ConditionOperator.NOT_EQUALS:
            if field_val == cond_val:
                return False
        elif cond.operator == ConditionOperator.IN:
            if not isinstance(cond_val, list):
                return False
            if field_val not in cond_val:
                return False
        elif cond.operator == ConditionOperator.NOT_IN:
            if not isinstance(cond_val, list):
                return False
            if field_val in cond_val:
                return False
        elif cond.operator == ConditionOperator.GT:
            try:
                if (field_val is None) or (float(field_val) <= float(cond_val)):
                    return False
            except (TypeError, ValueError):
                return False
        elif cond.operator == ConditionOperator.LT:
            try:
                if (field_val is None) or (float(field_val) >= float(cond_val)):
                    return False
            except (TypeError, ValueError):
                return False
        elif cond.operator == ConditionOperator.GTE:
            try:
                if (field_val is None) or (float(field_val) < float(cond_val)):
                    return False
            except (TypeError, ValueError):
                return False
        elif cond.operator == ConditionOperator.LTE:
            try:
                if (field_val is None) or (float(field_val) > float(cond_val)):
                    return False
            except (TypeError, ValueError):
                return False
        elif cond.operator == ConditionOperator.BETWEEN:
            if not isinstance(cond_val, (list, tuple)) or len(cond_val) != 2:
                return False
            try:
                fv = float(field_val) if field_val is not None else None
                lo, hi = float(cond_val[0]), float(cond_val[1])
                if fv is None or not (lo <= fv <= hi):
                    return False
            except (TypeError, ValueError):
                return False

    return True


async def _get_load_balanced_assignee(
    session: AsyncSession,
    rule: RoutingRuleModel,
    tenant_id: int,
    max_load_per_rep: int = DEFAULT_MAX_LOAD_PER_REP,
) -> int | None:
    """Pick the eligible user with the lowest active lead count.

    For "user" type: just the user.
    For "team" type: all active users in the team (by role or assignee_id).
    For "round_robin": all active users, lowest load wins.
    """
    # Build base query for eligible users (active, same tenant)
    base_conditions = [
        UserModel.tenant_id == tenant_id,
        UserModel.status == "active",
    ]

    if rule.assignee_type == "user" and rule.assignee_id:
        base_conditions.append(UserModel.id == rule.assignee_id)
    elif rule.assignee_type == "team" and rule.assignee_id:
        # team: assignee_id is the team/role id — include all users with the matching role
        base_conditions.append(UserModel.role == rule.assignee_id)

    result = await session.execute(select(UserModel).where(and_(*base_conditions)))
    users = result.scalars().all()

    if not users:
        return None

    # Count active leads per user (owner_id != 0, status="lead")
    lead_counts: dict[int, int] = {u.id: 0 for u in users}
    lead_result = await session.execute(
        select(CustomerModel.owner_id, func.count(CustomerModel.id))
        .where(
            and_(
                CustomerModel.tenant_id == tenant_id,
                CustomerModel.status == "lead",
                CustomerModel.owner_id.in_(list(lead_counts.keys())),
            )
        )
        .group_by(CustomerModel.owner_id)
    )
    for owner_id, count in lead_result.fetchall():
        lead_counts[owner_id] = count

    # Filter to users below load threshold, pick the lowest among them
    under_threshold = [u for u in users if lead_counts.get(u.id, 0) < max_load_per_rep]
    candidates = under_threshold if under_threshold else users

    return min(candidates, key=lambda u: lead_counts.get(u.id, 0)).id if candidates else None


class LeadRoutingService:
    """Routing engine for automatic lead assignment and recycling."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_max_load_per_rep(self, tenant_id: int) -> int:
        """Read max_load_per_rep from tenant settings with fallback to 20."""
        result = await self.session.execute(select(TenantModel.settings).where(TenantModel.id == tenant_id))
        row = result.scalar_one_or_none()
        settings = row or {}
        return settings.get("lead_routing", {}).get("max_load_per_rep", DEFAULT_MAX_LOAD_PER_REP)

    async def get_matching_rule(self, tenant_id: int, customer: dict[str, Any]) -> RoutingRuleModel | None:
        """Find the highest-priority active rule whose conditions match."""
        result = await self.session.execute(
            select(RoutingRuleModel)
            .where(
                and_(
                    RoutingRuleModel.tenant_id == tenant_id,
                    RoutingRuleModel.is_active == True,  # noqa: E712
                )
            )
            .order_by(RoutingRuleModel.priority.desc())
        )
        for rule in result.scalars().all():
            conditions = [RuleCondition.model_validate(c) for c in (rule.conditions_json or [])]
            if evaluate_conditions(conditions, customer):
                return rule
        return None

    async def select_assignee(self, rule: RoutingRuleModel, tenant_id: int) -> int | None:
        """Select the best assignee for a rule using load balancing."""
        max_load = await self._get_max_load_per_rep(tenant_id)
        return await _get_load_balanced_assignee(self.session, rule, tenant_id, max_load)

    async def auto_assign_lead(self, customer_id: int, tenant_id: int) -> int | None:
        """Evaluate rules and assign the lead. Returns assigned owner_id or None."""
        # Fetch the customer
        result = await self.session.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.id == customer_id,
                    CustomerModel.tenant_id == tenant_id,
                )
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            return None

        customer_dict = {
            "region": getattr(customer, "region", None),
            "industry": getattr(customer, "industry", None),
            "employee_count": getattr(customer, "employee_count", None),
            "source": getattr(customer, "source", None),
            "created_date": customer.created_at,
            "status": customer.status,
            "owner_id": customer.owner_id,
            "company": customer.company,
        }

        rule = await self.get_matching_rule(tenant_id, customer_dict)
        now = datetime.now(UTC)

        if rule:
            assignee_id = await self.select_assignee(rule, tenant_id)
            if assignee_id is None:
                # No eligible assignee — fall through to round-robin
                assignee_id = await self._round_robin_assignee(tenant_id)
        else:
            assignee_id = await self._round_robin_assignee(tenant_id)

        if assignee_id is None:
            return None

        await self.session.execute(
            update(CustomerModel)
            .where(and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id))
            .values(owner_id=assignee_id, assigned_at=now)
        )
        await self.session.flush()
        return assignee_id

    async def _round_robin_assignee(self, tenant_id: int) -> int | None:
        """Pick the active user with the fewest active leads (fallback)."""
        result = await self.session.execute(
            select(UserModel).where(and_(UserModel.tenant_id == tenant_id, UserModel.status == "active"))
        )
        users = result.scalars().all()
        if not users:
            return None

        lead_counts: dict[int, int] = {u.id: 0 for u in users}
        lead_result = await self.session.execute(
            select(CustomerModel.owner_id, func.count(CustomerModel.id))
            .where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    CustomerModel.status == "lead",
                    CustomerModel.owner_id.in_(list(lead_counts.keys())),
                )
            )
            .group_by(CustomerModel.owner_id)
        )
        for owner_id, count in lead_result.fetchall():
            lead_counts[owner_id] = count

        return min(users, key=lambda u: lead_counts.get(u.id, 0)).id

    async def recycle_stale_leads(
        self,
        tenant_id: int,
        stale_hours: int = 24,
        max_recycle: int = 3,
    ) -> list[int]:
        """Recycle leads with no response within the stale window.

        Sets owner_id=0, increments recycle_count, logs to recycle_history.
        Returns list of recycled customer IDs.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)
        result = await self.session.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    CustomerModel.status == "lead",
                    CustomerModel.owner_id != 0,
                    CustomerModel.assigned_at.isnot(None),  # assigned_at IS NOT NULL
                    CustomerModel.assigned_at < cutoff,
                    CustomerModel.recycle_count < max_recycle,
                )
            )
        )
        stale_leads = result.scalars().all()
        recycled_ids: list[int] = []
        now = datetime.now(UTC)

        for lead in stale_leads:
            entry = {
                "recycled_at": now.isoformat(),
                "previous_owner_id": lead.owner_id,
                "reason": "stale_no_response",
            }
            history = list(lead.recycle_history or [])
            history.append(entry)

            await self.session.execute(
                update(CustomerModel)
                .where(and_(CustomerModel.id == lead.id, CustomerModel.tenant_id == tenant_id))
                .values(
                    owner_id=0,
                    assigned_at=None,
                    recycle_count=lead.recycle_count + 1,
                    recycle_history=history,
                )
            )
            recycled_ids.append(lead.id)

        await self.session.flush()
        return recycled_ids

    async def disqualify_overcycled_leads(
        self,
        tenant_id: int,
        max_recycle: int = 3,
    ) -> list[int]:
        """Change status to 'disqualified' for leads that exceeded max recycle count."""
        result = await self.session.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.tenant_id == tenant_id,
                    CustomerModel.status == "lead",
                    CustomerModel.recycle_count >= max_recycle,
                )
            )
        )
        leads = result.scalars().all()
        disqualified_ids: list[int] = []

        for lead in leads:
            await self.session.execute(
                update(CustomerModel)
                .where(and_(CustomerModel.id == lead.id, CustomerModel.tenant_id == tenant_id))
                .values(status="disqualified")
            )
            disqualified_ids.append(lead.id)

        await self.session.flush()
        return disqualified_ids

    @staticmethod
    def get_sla_status(assigned_at: datetime | None) -> str:
        """Return SLA status: green (<2h), yellow (<24h), red (>24h)."""
        if assigned_at is None:
            return "green"
        now = datetime.now(UTC)
        age = now - assigned_at
        if age < timedelta(hours=2):
            return "green"
        if age < timedelta(hours=24):
            return "yellow"
        return "red"

    async def preview_assign(
        self,
        conditions: list[RuleCondition],
        customer_data: dict[str, Any],
        tenant_id: int,
    ) -> LeadAssignPreview:
        """Preview which rule and assignee would handle a lead. No side effects."""
        for cond in conditions:
            if cond.field not in SUPPORTED_FIELDS:
                raise ValidationException(f"Unsupported field in test: {cond.field}")

        matched_rule: RoutingRuleModel | None = None

        # First: check if input conditions match (rule-test flow)
        if evaluate_conditions(conditions, customer_data):
            # Use highest-priority active rule as the preview basis
            for rule in (
                (
                    await self.session.execute(
                        select(RoutingRuleModel)
                        .where(
                            and_(
                                RoutingRuleModel.tenant_id == tenant_id,
                                RoutingRuleModel.is_active == True,  # noqa: E712
                            )
                        )
                        .order_by(RoutingRuleModel.priority.desc())
                    )
                )
                .scalars()
                .all()
            ):
                conds = [RuleCondition.model_validate(c) for c in (rule.conditions_json or [])]
                if evaluate_conditions(conds, customer_data):
                    matched_rule = rule
                    break

        if matched_rule:
            assignee_id = await self.select_assignee(matched_rule, tenant_id)
            assignee_type = matched_rule.assignee_type
        else:
            assignee_id = await self._round_robin_assignee(tenant_id)
            assignee_type = "round_robin"

        return LeadAssignPreview(
            matched_rule_id=matched_rule.id if matched_rule else None,
            matched_rule_name=matched_rule.name if matched_rule else None,
            assignee_id=assignee_id,
            assignee_type=assignee_type,
            sla_status="green",
        )


async def check_and_recycle_leads(async_sessionmaker, stale_hours: int = 24, max_recycle: int = 3) -> dict:
    """Standalone background-job function called by an external scheduler.

    Iterates all tenants, recycles stale leads, disqualifies over-cycled ones,
    and triggers notifications for each recycled lead.
    """
    from services.notification_service import NotificationService

    async with async_sessionmaker() as session:
        svc = LeadRoutingService(session)
        result = {"recycled": 0, "disqualified": 0, "errors": []}

        tenants_result = await session.execute(select(TenantModel.id))
        tenant_ids = [r[0] for r in tenants_result.fetchall()]

        for tid in tenant_ids:
            try:
                recycled = await svc.recycle_stale_leads(tid, stale_hours=stale_hours, max_recycle=max_recycle)
                result["recycled"] += len(recycled)

                # Fetch previous owners for notification
                if recycled:
                    for cust_id in recycled:
                        hist_result = await session.execute(
                            select(CustomerModel.recycle_history).where(
                                and_(CustomerModel.id == cust_id, CustomerModel.tenant_id == tid)
                            )
                        )
                        history = hist_result.scalar_one_or_none() or []
                        if history:
                            prev_owner = history[-1].get("previous_owner_id", 0)
                            try:
                                notif_svc = NotificationService(session)
                                await notif_svc.send_notification(
                                    user_id=prev_owner,
                                    notification_type="lead_recycled",
                                    title="Lead Recycled",
                                    content=f"Lead {cust_id} has been recycled",
                                    tenant_id=tid,
                                )
                            except Exception as e:
                                logger.warning("notification failed for tenant %s: %s", tid, e)

                disqualified = await svc.disqualify_overcycled_leads(tid, max_recycle=max_recycle)
                result["disqualified"] += len(disqualified)

            except Exception as exc:
                result["errors"].append({"tenant_id": tid, "error": str(exc)})

        await session.commit()
        return result
