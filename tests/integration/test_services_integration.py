"""
Integration tests for Workflow, Marketing, Task, Activity & Notification services.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_services_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from db.repositories.customer import CustomerRepository
from models.marketing import CampaignType, TriggerType
from pkg.errors.app_exceptions import NotFoundException
from services.activity_service import ActivityService
from services.customer_service import CustomerService
from services.marketing_service import MarketingService
from services.notification_service import NotificationService
from services.task_service import TaskService
from services.tenant_service import TenantService
from services.workflow_service import WorkflowService
from tests.integration.domain_fixtures._shared import seed_user


# ──────────────────────────────────────────────────────────────────────────────────────
#  Workflow integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestWorkflowIntegration:
    """Full workflow lifecycle via the real DB."""

    async def test_create_and_get_workflow(self, db_schema, _seed_tenant, async_session):
        tid = _seed_tenant
        uid = await seed_user(async_session, tid, username_prefix="wfuser", email_prefix="wf")
        svc = WorkflowService(async_session)
        result = await svc.create_workflow(
            tenant_id=tid,
            name="Lead Follow-up",
            trigger_type="lead_created",
            created_by=uid,
            description="Auto-follow-up on new leads",
            conditions=[{"field": "status", "operator": "==", "value": "new"}],
            actions=[{"type": "email.send", "template": "welcome"}],
        )
        assert result.name == "Lead Follow-up"
        assert result.status == "draft"
        assert result.description == "Auto-follow-up on new leads"
        assert result.conditions == [{"field": "status", "operator": "==", "value": "new"}]
        assert result.actions == [{"type": "email.send", "template": "welcome"}]

        fetched = await svc.get_workflow(result.id, tenant_id=tid)
        assert fetched.name == "Lead Follow-up"
        assert fetched.description == "Auto-follow-up on new leads"
        assert fetched.conditions == [{"field": "status", "operator": "==", "value": "new"}]
        assert fetched.actions == [{"type": "email.send", "template": "welcome"}]

    async def test_workflow_activate_and_pause(self, db_schema, _seed_tenant, async_session):
        tid = _seed_tenant
        uid = await seed_user(async_session, tid, username_prefix="wfuser", email_prefix="wf")
        svc = WorkflowService(async_session)
        created = await svc.create_workflow(
            tenant_id=tid,
            name="Activation Test",
            trigger_type="deal_created",
            created_by=uid,
            conditions=[],
            actions=[],
        )

        activated = await svc.activate_workflow(created.id, tenant_id=tid)
        assert activated.status == "active"

        # Re-fetch from DB to confirm status persisted
        refetched = await svc.get_workflow(created.id, tenant_id=tid)
        assert refetched.status == "active"

        paused = await svc.pause_workflow(created.id, tenant_id=tid)
        assert paused.status == "paused"

        # Re-fetch to confirm pause persisted
        refetched_paused = await svc.get_workflow(created.id, tenant_id=tid)
        assert refetched_paused.status == "paused"

    async def test_workflow_evaluate_conditions(self, db_schema, _seed_tenant, async_session):
        tid = _seed_tenant
        uid = await seed_user(async_session, tid, username_prefix="wfuser", email_prefix="wf")
        svc = WorkflowService(async_session)
        created = await svc.create_workflow(
            tenant_id=tid,
            name="Condition Test",
            trigger_type="deal_created",
            created_by=uid,
            conditions=[
                {"field": "amount", "operator": ">=", "value": 10000},
                {"field": "stage", "operator": "contains", "value": "qualified"},
            ],
            actions=[],
        )

        match = await svc.evaluate_conditions(
            workflow_id=created.id,
            context={"amount": 50000, "stage": "qualified"},
            tenant_id=tid,
        )
        assert match is True

        no_match = await svc.evaluate_conditions(
            workflow_id=created.id,
            context={"amount": 500, "stage": "new"},
            tenant_id=tid,
        )
        assert no_match is False

        # Partial match: amount matches but stage doesn't — should fail (all must match)
        partial_match = await svc.evaluate_conditions(
            workflow_id=created.id,
            context={"amount": 50000, "stage": "new"},
            tenant_id=tid,
        )
        assert partial_match is False

        # Empty conditions list — should match everything
        empty_cond_wf = await svc.create_workflow(
            tenant_id=tid,
            name="Empty Conditions",
            trigger_type="manual",
            created_by=uid,
            conditions=[],
            actions=[],
        )
        empty_match = await svc.evaluate_conditions(
            workflow_id=empty_cond_wf.id,
            context={"anything": "goes"},
            tenant_id=tid,
        )
        assert empty_match is True

    async def test_workflow_execute_not_found(self, db_schema, _seed_tenant, async_session):
        """execute_workflow with a non-existent id raises NotFoundException."""
        tid = _seed_tenant
        svc = WorkflowService(async_session)
        # Use a real tenant_id with a non-existent workflow_id (Rule 49).
        with pytest.raises(NotFoundException):
            await svc.execute_workflow(
                workflow_id=999_999_999,
                context={"amount": 1000},
                tenant_id=tid,
            )

    async def test_workflow_cross_tenant_isolation(self, db_schema, _seed_tenant, _seed_tenant_2, async_session):
        """WorkflowService.get_workflow must raise NotFoundException when called
        with a different tenant_id than the one that owns the workflow (Rule 126)."""
        tenant_id = _seed_tenant
        tenant_id_2 = _seed_tenant_2
        svc = WorkflowService(async_session)
        uid1 = await seed_user(async_session, tenant_id, username_prefix="wfuser1", email_prefix="wf1")
        uid2 = await seed_user(async_session, tenant_id_2, username_prefix="wfuser2", email_prefix="wf2")

        # Create a workflow under tenant 1
        wf1 = await svc.create_workflow(
            tenant_id=tenant_id,
            name="T1 Workflow",
            trigger_type="manual",
            created_by=uid1,
            conditions=[],
            actions=[],
        )

        # Create a workflow under tenant 2
        wf2 = await svc.create_workflow(
            tenant_id=tenant_id_2,
            name="T2 Workflow",
            trigger_type="manual",
            created_by=uid2,
            conditions=[],
            actions=[],
        )

        # Each tenant can read its own workflow
        fetched1 = await svc.get_workflow(wf1.id, tenant_id=tenant_id)
        assert fetched1.id == wf1.id
        fetched2 = await svc.get_workflow(wf2.id, tenant_id=tenant_id_2)
        assert fetched2.id == wf2.id

        # Cross-tenant reads must raise NotFoundException
        with pytest.raises(NotFoundException):
            await svc.get_workflow(wf1.id, tenant_id=tenant_id_2)
        with pytest.raises(NotFoundException):
            await svc.get_workflow(wf2.id, tenant_id=tenant_id)

        # Cross-tenant state transitions must also raise NotFoundException
        with pytest.raises(NotFoundException):
            await svc.activate_workflow(wf1.id, tenant_id=tenant_id_2)
        with pytest.raises(NotFoundException):
            await svc.pause_workflow(wf2.id, tenant_id=tenant_id)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Marketing integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestMarketingIntegration:
    """Full campaign lifecycle via the real DB."""

    async def test_create_and_get_campaign(self, db_schema, tenant_id, async_session):
        uid = await seed_user(async_session, tenant_id, username_prefix="mktuser", email_prefix="mkt")
        svc = MarketingService(async_session)
        result = await svc.create_campaign(
            name="Summer Sale 2026",
            campaign_type=CampaignType.EMAIL,
            content="Check out our summer collection.",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Summer deals inside!",
            trigger_type=TriggerType.CUSTOM,
        )
        assert result.name == "Summer Sale 2026"
        assert result.status == "draft"

        fetched = await svc.get_campaign(result.id, tenant_id=tenant_id)
        assert fetched.name == "Summer Sale 2026"

    async def test_launch_and_pause_campaign(self, db_schema, tenant_id, async_session):
        uid = await seed_user(async_session, tenant_id, username_prefix="mktuser", email_prefix="mkt")
        svc = MarketingService(async_session)
        created = await svc.create_campaign(
            name="Launch Test",
            campaign_type=CampaignType.EMAIL,
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Test",
            trigger_type=TriggerType.CUSTOM,
        )
        cid = created.id

        launched = await svc.launch_campaign(cid, tenant_id=tenant_id)
        assert launched.status == "active"

        paused = await svc.pause_campaign(cid, tenant_id=tenant_id)
        assert paused.status == "paused"

    async def test_campaign_stats(self, db_schema, tenant_id, async_session):
        uid = await seed_user(async_session, tenant_id, username_prefix="mktuser", email_prefix="mkt")
        svc = MarketingService(async_session)
        created = await svc.create_campaign(
            name="Stats Test",
            campaign_type=CampaignType.EMAIL,
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Stats",
            trigger_type=TriggerType.CUSTOM,
        )
        cid = created.id

        stats = await svc.get_campaign_stats(cid, tenant_id=tenant_id)
        assert stats["sent_count"] == 0
        assert "open_count" in stats
        assert "click_count" in stats

    async def test_list_campaigns(self, db_schema, tenant_id, async_session):
        uid = await seed_user(async_session, tenant_id, username_prefix="mktuser", email_prefix="mkt")
        svc = MarketingService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await svc.create_campaign(
            name=f"List Test A {suffix}",
            campaign_type="email",
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="A",
            trigger_type=TriggerType.CUSTOM,
        )
        await svc.create_campaign(
            name=f"List Test B {suffix}",
            campaign_type="email",
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="B",
            trigger_type=TriggerType.CUSTOM,
        )

        items, total = await svc.list_campaigns(tenant_id=tenant_id)
        names = [c.name for c in items]
        assert any(f"List Test A {suffix}" in n for n in names)
        assert any(f"List Test B {suffix}" in n for n in names)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Task integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTaskIntegration:
    """Full task lifecycle via the real DB."""

    async def test_create_and_get_task(self, db_schema, tenant_id, async_session):
        svc = TaskService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="taskuser", email_prefix="task")
        result = await svc.create_task(
            title="Review PR #42",
            description="Review the new feature PR",
            assigned_to=uid,
            priority="high",
            due_date=date(2026, 12, 31),
            tenant_id=tenant_id,  # keyword for clarity and to prevent silent transposition
        )
        task = result
        assert task.title == "Review PR #42"
        assert task.status == "pending"
        assert task.priority == "high"

        fetched = await svc.get_task(tenant_id, task.id)
        assert fetched.title == "Review PR #42"

    async def test_update_and_complete_task(self, db_schema, tenant_id, async_session):
        svc = TaskService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="taskuser", email_prefix="task")
        created = await svc.create_task(
            title="Original Task",
            description="",
            assigned_to=uid,
            priority="low",
            tenant_id=tenant_id,
        )
        tid = created.id

        updated = await svc.update_task(tenant_id, tid, title="Updated Task", priority="high")
        assert updated.title == "Updated Task"
        assert updated.priority == "high"

        completed = await svc.complete_task(tenant_id, tid)
        assert completed.status == "completed"

    async def test_delete_task(self, db_schema, tenant_id, async_session):
        svc = TaskService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="taskuser", email_prefix="task")
        created = await svc.create_task(
            title="To Delete",
            description="",
            assigned_to=uid,
            tenant_id=tenant_id,
        )
        tid = created.id

        await svc.delete_task(tenant_id, tid)
        with pytest.raises(NotFoundException):
            await svc.get_task(tenant_id, tid)

    async def test_list_tasks(self, db_schema, tenant_id, async_session):
        svc = TaskService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="taskuser", email_prefix="task")
        suffix = uuid.uuid4().hex[:8]
        await svc.create_task(
            title=f"List Task 1 {suffix}",
            description="",
            assigned_to=uid,
            tenant_id=tenant_id,
        )
        await svc.create_task(
            title=f"List Task 2 {suffix}",
            description="",
            assigned_to=uid,
            tenant_id=tenant_id,
        )

        items, total = await svc.list_tasks(tenant_id)
        titles = [t.title for t in items]
        assert total >= 2
        assert any(f"List Task 1 {suffix}" in t for t in titles)
        assert any(f"List Task 2 {suffix}" in t for t in titles)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Activity integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestActivityIntegration:
    """Full activity lifecycle via the real DB."""

    async def _seed_customer(self, tenant_id: int, async_session) -> int:
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await cust_svc.create_customer(
            data={"name": f"Activity Cust {suffix}", "email": f"act_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        return result.id

    async def test_create_and_get_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="actuser", email_prefix="act")
        cid = await self._seed_customer(tenant_id, async_session)
        result = await svc.create_activity(
            customer_id=cid,
            activity_type="call",
            content="Follow-up call - Discussed pricing",
            created_by=uid,
            tenant_id=tenant_id,
        )
        assert result is not None
        assert result.type.value == "call"
        assert result.content == "Follow-up call - Discussed pricing"

        fetched = await svc.get_activity(result.id, tenant_id=tenant_id)
        assert fetched is not None
        assert fetched.content == "Follow-up call - Discussed pricing"

    async def test_update_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="actuser", email_prefix="act")
        cid = await self._seed_customer(tenant_id, async_session)
        created = await svc.create_activity(
            customer_id=cid,
            activity_type="email",
            content="Original Subject",
            created_by=uid,
            tenant_id=tenant_id,
        )
        aid = created.id

        updated = await svc.update_activity(aid, tenant_id=tenant_id, content="Updated Subject")
        assert updated is not None
        assert updated.content == "Updated Subject"

    async def test_list_activities(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="actuser", email_prefix="act")
        cid = await self._seed_customer(tenant_id, async_session)
        suffix = uuid.uuid4().hex[:8]
        await svc.create_activity(
            customer_id=cid, activity_type="call", content=f"Call {suffix}", created_by=uid, tenant_id=tenant_id
        )
        await svc.create_activity(
            customer_id=cid, activity_type="email", content=f"Email {suffix}", created_by=uid, tenant_id=tenant_id
        )

        items, total = await svc.list_activities(tenant_id=tenant_id)
        contents = [a.content for a in items]
        assert any(f"Call {suffix}" in c for c in contents)
        assert any(f"Email {suffix}" in c for c in contents)

    async def test_get_customer_activities(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="actuser", email_prefix="act")
        cid = await self._seed_customer(tenant_id, async_session)
        await svc.create_activity(
            customer_id=cid,
            activity_type="call",
            content="Call 1",
            created_by=uid,
            tenant_id=tenant_id,
        )
        await svc.create_activity(
            customer_id=cid,
            activity_type="call",
            content="Call 2",
            created_by=uid,
            tenant_id=tenant_id,
        )

        result = await svc.get_customer_activities(customer_id=cid, tenant_id=tenant_id)
        assert len(result) >= 2

    async def test_delete_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="actuser", email_prefix="act")
        cid = await self._seed_customer(tenant_id, async_session)
        created = await svc.create_activity(
            customer_id=cid, activity_type="note", content="To Delete", created_by=uid, tenant_id=tenant_id
        )
        aid = created.id

        deleted = await svc.delete_activity(aid, tenant_id=tenant_id)
        assert deleted is not None


# ──────────────────────────────────────────────────────────────────────────────────────
#  Notification integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestNotificationIntegration:
    """Notification and reminder lifecycle via the real DB."""

    async def test_send_and_get_notification(self, db_schema, tenant_id, async_session, _seed_tenant):
        svc = NotificationService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="notif", email_prefix="notif")
        result = await svc.send_notification(
            user_id=uid,
            notification_type="in_app",
            title="Pipeline Updated",
            content="Your deal moved to closed_won!",
            tenant_id=tenant_id,
        )
        nid = result.id

        items, total = await svc.get_user_notifications(user_id=uid, tenant_id=tenant_id)
        ids = [n.id for n in items]
        assert nid in ids
        assert total == 1

    async def test_mark_notification_as_read(self, db_schema, tenant_id, async_session, _seed_tenant):
        svc = NotificationService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="notif", email_prefix="notif")

        # Verify truncation guarantees a clean baseline before making assertions
        # that depend on zero pre-existing unread notifications.
        baseline = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert baseline == 0

        sent = await svc.send_notification(
            user_id=uid, notification_type="in_app", title="Test", content="Body", tenant_id=tenant_id
        )

        # After send, unread count should be 1 (pending notification).
        after_send = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert after_send == 1

        marked = await svc.mark_as_read(sent.id, tenant_id=tenant_id)
        assert marked.read_at is not None

        unread = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert unread == 0

    async def test_unread_count(self, db_schema, tenant_id, async_session, _seed_tenant):
        svc = NotificationService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="notif", email_prefix="notif")
        await svc.send_notification(
            user_id=uid, notification_type="in_app", title="N1", content="m", tenant_id=tenant_id
        )
        await svc.send_notification(
            user_id=uid, notification_type="in_app", title="N2", content="m", tenant_id=tenant_id
        )

        count = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert count == 2

    async def test_create_and_cancel_reminder(self, db_schema, tenant_id, async_session, _seed_tenant):
        svc = NotificationService(async_session)
        uid = await seed_user(async_session, tenant_id, username_prefix="notif", email_prefix="notif")
        result = await svc.create_reminder(
            user_id=uid,
            tenant_id=tenant_id,
            title="Team standup",
            content="Daily standup meeting",
            remind_at=datetime(2099, 12, 31, 10, 0, 0, tzinfo=UTC),
        )

        cancelled = await svc.cancel_reminder(result.id, tenant_id=tenant_id)
        assert cancelled.id == result.id

        # Verify the reminder was actually deleted from the DB.
        from sqlalchemy import select

        from db.models.reminder import ReminderModel

        result_check = await async_session.execute(select(ReminderModel).where(ReminderModel.id == result.id))
        assert result_check.scalar_one_or_none() is None

    async def test_notification_cross_tenant_isolation(self, db_schema, _seed_tenant, _seed_tenant_2, async_session):
        svc = NotificationService(async_session)
        tenant_id = _seed_tenant
        tenant_id_2 = _seed_tenant_2

        # Create user and notification under tenant 1
        uid1 = await seed_user(async_session, tenant_id, username_prefix="notif1", email_prefix="notif1")
        notif1 = await svc.send_notification(
            user_id=uid1, notification_type="in_app", title="T1", content="m", tenant_id=tenant_id
        )

        # Create user under tenant 2 and send a notification to them
        uid2 = await seed_user(async_session, tenant_id_2, username_prefix="notif2", email_prefix="notif2")
        notif2 = await svc.send_notification(
            user_id=uid2, notification_type="in_app", title="T2", content="m", tenant_id=tenant_id_2
        )

        # Tenant 2 sees only their own T2 notification, not tenant 1's T1.
        items2, total2 = await svc.get_user_notifications(user_id=uid2, tenant_id=tenant_id_2)
        assert total2 == 1
        assert len(items2) == 1
        assert items2[0].id == notif2.id

        # Tenant 1 sees only their own T1 notification, not tenant 2's T2.
        items1, total1 = await svc.get_user_notifications(user_id=uid1, tenant_id=tenant_id)
        assert total1 == 1
        assert len(items1) == 1
        assert items1[0].id == notif1.id

        with pytest.raises(NotFoundException):
            # Use tenant 1's context to fetch tenant 2's notification ID.
            await svc.mark_as_read(notif2.id, tenant_id=tenant_id)
        with pytest.raises(NotFoundException):
            # Use tenant 2's context to fetch tenant 1's notification ID.
            await svc.mark_as_read(notif1.id, tenant_id=tenant_id_2)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Tenant integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTenantIntegration:
    """Tenant lifecycle via the real DB."""

    async def test_create_and_get_tenant(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await svc.create_tenant(
            name=f"Acme Corp {suffix}",
            plan="pro",
            admin_email=f"admin_{suffix}@example.com",
        )
        assert result is not None
        assert result.name == f"Acme Corp {suffix}"
        assert result.plan == "pro"

        fetched = await svc.get_tenant(result.id, requesting_tenant_id=result.id)
        assert fetched is not None
        assert fetched.name == f"Acme Corp {suffix}"

    async def test_update_tenant(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Original {suffix}", plan="free", admin_email=f"admin_{suffix}@example.com"
        )
        tid = created.id

        updated = await svc.update_tenant(tid, requesting_tenant_id=tid, plan="enterprise", name=f"Updated {suffix}")
        assert updated is not None
        assert updated.plan == "enterprise"
        assert updated.name == f"Updated {suffix}"

    async def test_list_tenants(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created_a = await svc.create_tenant(
            name=f"List Tenant A {suffix}", plan="free", admin_email=f"a_{suffix}@x.com"
        )
        await svc.create_tenant(name=f"List Tenant B {suffix}", plan="pro", admin_email=f"b_{suffix}@x.com")

        # A tenant can only see itself via list_tenants (Rule126 enforcement).
        items, total = await svc.list_tenants(requesting_tenant_id=created_a.id)
        names = [t.name for t in items]
        assert any(f"List Tenant A {suffix}" in n for n in names)
        # Verify tenant B's record is absent (Rule 126).
        assert all(f"List Tenant B {suffix}" not in n for n in names)
        assert total == 1

    async def test_get_tenant_stats(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(name=f"Stats Tenant {suffix}", plan="pro", admin_email=f"s_{suffix}@x.com")
        tid = created.id

        stats = await svc.get_tenant_stats(tid, requesting_tenant_id=tid)
        assert stats is not None
        assert stats.user_count is not None
        assert stats.tenant.id == tid
        assert stats.tenant.name is not None
