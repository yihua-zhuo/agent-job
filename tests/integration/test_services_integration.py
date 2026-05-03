"""
Integration tests for Workflow, Marketing, Task, Activity & Notification services.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_services_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from models.marketing import TriggerType, CampaignType
from models.response import ResponseStatus
from services.activity_service import ActivityService
from services.customer_service import CustomerService
from services.marketing_service import MarketingService
from services.notification_service import NotificationService
from services.task_service import TaskService
from services.tenant_service import TenantService
from services.user_service import UserService
from services.workflow_service import WorkflowService


# ──────────────────────────────────────────────────────────────────────────────────────
#  Workflow integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestWorkflowIntegration:
    """Full workflow lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        """Create a user and return their id (needed for created_by)."""
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"wfuser_{suffix}",
            email=f"wf_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def test_create_and_get_workflow(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        svc = WorkflowService()
        result = await svc.create_workflow(
            name="Lead Follow-up",
            trigger_type="lead_created",
            created_by=uid,
            tenant_id=tenant_id,
            description="Auto-follow-up on new leads",
            conditions=[{"field": "status", "operator": "equals", "value": "new"}],
            actions=[{"type": "send_email", "params": {"template": "welcome"}}],
        )
        assert result.status == ResponseStatus.SUCCESS, f"Got: {result.status}, {result.message}"
        data = result.data
        assert data["name"] == "Lead Follow-up"
        assert data["status"] == "draft"

        fetched = await svc.get_workflow(data["id"])
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == "Lead Follow-up"

    async def test_workflow_activate_and_pause(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        svc = WorkflowService()
        created = await svc.create_workflow(
            name="Activation Test",
            trigger_type="deal_created",
            created_by=uid,
            tenant_id=tenant_id,
            conditions=[],
            actions=[],
        )
        wid = created.data["id"]

        activated = await svc.activate_workflow(wid)
        assert activated.status == ResponseStatus.SUCCESS
        assert activated.data["status"] == "active"

        paused = await svc.pause_workflow(wid)
        assert paused.status == ResponseStatus.SUCCESS
        assert paused.data["status"] == "paused"

    async def test_workflow_evaluate_conditions(self, db_schema, tenant_id, async_session):
        uid = await self._seed_user(tenant_id, async_session)
        svc = WorkflowService()
        created = await svc.create_workflow(
            name="Condition Test",
            trigger_type="deal_created",
            created_by=uid,
            tenant_id=tenant_id,
            conditions=[
                {"field": "amount", "operator": "gte", "value": 10000},
                {"field": "stage", "operator": "contains", "value": "qualified"},
            ],
            actions=[],
        )
        wid = created.data["id"]

        # Matching context
        match = await svc.evaluate_conditions(
            wid, {"amount": 50000, "stage": "qualified"}
        )
        assert match is True

        # Non-matching context
        no_match = await svc.evaluate_conditions(
            wid, {"amount": 500, "stage": "new"}
        )
        assert no_match is False

    async def test_workflow_execute_not_found(self, db_schema, tenant_id, async_session):
        """execute_workflow with a non-existent id returns NOT_FOUND."""
        svc = WorkflowService()
        executed = await svc.execute_workflow(
            workflow_id=999_999_999,
            context={"amount": 1000},
        )
        assert executed.status == ResponseStatus.NOT_FOUND


# ──────────────────────────────────────────────────────────────────────────────────────
#  Marketing integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestMarketingIntegration:
    """Full campaign lifecycle via the real DB."""

    async def test_create_and_get_campaign(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        user_reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = user_reg.data.id
        svc = MarketingService()
        result = await svc.create_campaign(
            name="Summer Sale 2026",
            campaign_type=CampaignType.EMAIL,
            content="Check out our summer collection.",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Summer deals inside!",
            trigger_type=TriggerType.CUSTOM,
        )
        assert result.status == ResponseStatus.SUCCESS, f"Got: {result.status}, {result.message}"
        data = result.data
        assert data.name == "Summer Sale 2026"
        assert data.status.value == "draft"

        fetched = await svc.get_campaign(data.id, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data.name == "Summer Sale 2026"

    async def test_launch_and_pause_campaign(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        user_reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = user_reg.data.id
        svc = MarketingService()
        created = await svc.create_campaign(
            name="Launch Test",
            campaign_type=CampaignType.EMAIL,
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Test",
            trigger_type=TriggerType.CUSTOM,
        )
        cid = created.data.id

        launched = await svc.launch_campaign(cid, tenant_id=tenant_id)
        assert launched.status == ResponseStatus.SUCCESS
        assert launched.data.status.value == "active"

        paused = await svc.pause_campaign(cid, tenant_id=tenant_id)
        assert paused.status == ResponseStatus.SUCCESS
        assert paused.data.status.value == "paused"

    async def test_campaign_stats(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        user_reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = user_reg.data.id
        svc = MarketingService()
        created = await svc.create_campaign(
            name="Stats Test",
            campaign_type=CampaignType.EMAIL,
            content="Body",
            created_by=uid,
            tenant_id=tenant_id,
            subject="Stats",
            trigger_type=TriggerType.CUSTOM,
        )
        cid = created.data.id

        stats = await svc.get_campaign_stats(cid)
        assert stats.status == ResponseStatus.SUCCESS
        assert stats.data.get("sent_count", stats.data.get("sent")) == 0
        assert "opened" in stats.data or "open_count" in stats.data
        assert "clicked" in stats.data or "click_count" in stats.data

    async def test_list_campaigns(self, db_schema, tenant_id, async_session):
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        user_reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        uid = user_reg.data.id
        svc = MarketingService()
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

        result = await svc.list_campaigns(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        names = [c.name for c in result.data.items]
        assert any(f"List Test A {suffix}" in n for n in names)
        assert any(f"List Test B {suffix}" in n for n in names)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Task integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestTaskIntegration:
    """Full task lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"taskuser_{suffix}",
            email=f"task_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id  # User is a dataclass, not a dict

    async def test_create_and_get_task(self, db_schema, tenant_id, async_session):
        from datetime import date
        svc = TaskService()
        uid = await self._seed_user(tenant_id, async_session)
        result = await svc.create_task(
            tenant_id=tenant_id,
            title="Review PR #42",
            description="Review the new feature PR",
            assigned_to=uid,
            priority="high",
            due_date=date(2026, 12, 31),
        )
        task = result["data"]
        assert task["title"] == "Review PR #42"
        assert task["status"] == "pending"
        assert task["priority"] == "high"

        fetched = await svc.get_task(task["id"])
        assert fetched["data"]["title"] == "Review PR #42"

    async def test_update_and_complete_task(self, db_schema, tenant_id, async_session):
        svc = TaskService()
        uid = await self._seed_user(tenant_id, async_session)
        created = await svc.create_task(
            tenant_id=tenant_id,
            title="Original Task",
            assigned_to=uid,
            priority="low",
        )
        tid = created["data"]["id"]

        updated = await svc.update_task(tid, title="Updated Task", priority="high")
        assert updated["data"]["title"] == "Updated Task"
        assert updated["data"]["priority"] == "high"

        completed = await svc.complete_task(tid)
        assert completed["data"]["status"] == "completed"

    async def test_delete_task(self, db_schema, tenant_id, async_session):
        svc = TaskService()
        uid = await self._seed_user(tenant_id, async_session)
        created = await svc.create_task(tenant_id=tenant_id, title="To Delete", assigned_to=uid)
        tid = created["data"]["id"]

        await svc.delete_task(tid)
        fetched = await svc.get_task(tid)
        assert fetched["data"] is None

    async def test_list_tasks(self, db_schema, tenant_id, async_session):
        svc = TaskService()
        uid = await self._seed_user(tenant_id, async_session)
        suffix = uuid.uuid4().hex[:8]
        await svc.create_task(tenant_id=tenant_id, title=f"List Task 1 {suffix}", assigned_to=uid)
        await svc.create_task(tenant_id=tenant_id, title=f"List Task 2 {suffix}", assigned_to=uid)

        result = await svc.list_tasks(tenant_id=tenant_id)
        titles = [t["title"] for t in result["data"]["items"]]
        assert any(f"List Task 1 {suffix}" in t for t in titles)
        assert any(f"List Task 2 {suffix}" in t for t in titles)


# ──────────────────────────────────────────────────────────────────────────────────────
#  Activity integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestActivityIntegration:
    """Full activity lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"actuser_{suffix}",
            email=f"act_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def _seed_customer(self, tenant_id: int, async_session) -> int:
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await cust_svc.create_customer(
            data={"name": f"Activity Cust {suffix}", "email": f"act_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        return result.data["id"]

    async def test_create_and_get_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        cid = await self._seed_customer(tenant_id, async_session)
        result = await svc.create_activity(
            customer_id=cid,
            activity_type="call",
            content="Follow-up call - Discussed pricing",
            created_by=uid,
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        assert result.data.type.value == "call"
        assert result.data.content == "Follow-up call - Discussed pricing"

        fetched = await svc.get_activity(result.data.id, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data.content == "Follow-up call - Discussed pricing"

    async def test_update_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        cid = await self._seed_customer(tenant_id, async_session)
        created = await svc.create_activity(
            customer_id=cid,
            activity_type="email",
            content="Original Subject",
            created_by=uid,
            tenant_id=tenant_id,
        )
        aid = created.data.id

        updated = await svc.update_activity(aid, tenant_id=tenant_id, content="Updated Subject")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data.content == "Updated Subject"

    async def test_list_activities(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        cid = await self._seed_customer(tenant_id, async_session)
        suffix = uuid.uuid4().hex[:8]
        await svc.create_activity(
            customer_id=cid, activity_type="call",
            content=f"Call {suffix}", created_by=uid, tenant_id=tenant_id
        )
        await svc.create_activity(
            customer_id=cid, activity_type="email",
            content=f"Email {suffix}", created_by=uid, tenant_id=tenant_id
        )

        result = await svc.list_activities(tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        contents = [a.content for a in result.data.items]
        assert any(f"Call {suffix}" in c for c in contents)
        assert any(f"Email {suffix}" in c for c in contents)

    async def test_get_customer_activities(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        cid = await self._seed_customer(tenant_id, async_session)
        await svc.create_activity(customer_id=cid, activity_type="call", content="Call 1", created_by=uid, tenant_id=tenant_id)
        await svc.create_activity(customer_id=cid, activity_type="call", content="Call 2", created_by=uid, tenant_id=tenant_id)

        result = await svc.get_customer_activities(customer_id=cid, tenant_id=tenant_id)
        assert result.status == ResponseStatus.SUCCESS
        assert len(result.data) >= 2

    async def test_delete_activity(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        cid = await self._seed_customer(tenant_id, async_session)
        created = await svc.create_activity(
            customer_id=cid, activity_type="note", content="To Delete", created_by=uid, tenant_id=tenant_id
        )
        aid = created.data.id

        deleted = await svc.delete_activity(aid, tenant_id=tenant_id)
        assert deleted.status == ResponseStatus.SUCCESS


# ──────────────────────────────────────────────────────────────────────────────────────
#  Notification integration tests
# ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestNotificationIntegration:
    """Notification and reminder lifecycle via the real DB."""

    async def _seed_user(self, tenant_id: int, async_session) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"notif_{suffix}",
            email=f"notif_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.data.id

    async def test_send_and_get_notification(self, db_schema, tenant_id, async_session):
        svc = NotificationService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        result = await svc.send_notification(
            user_id=uid,
            notification_type="info",
            title="Pipeline Updated",
            content="Your deal moved to closed_won!",
            tenant_id=tenant_id,
        )
        assert result.status == ResponseStatus.SUCCESS
        nid = result.data["id"]

        fetched = await svc.get_user_notifications(user_id=uid, tenant_id=tenant_id)
        assert fetched.status == ResponseStatus.SUCCESS
        ids = [n["id"] for n in fetched.data.items]
        assert nid in ids

    async def test_mark_notification_as_read(self, db_schema, tenant_id, async_session):
        svc = NotificationService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        sent = await svc.send_notification(
            user_id=uid, notification_type="info", title="Test", content="Body", tenant_id=tenant_id
        )
        nid = sent.data["id"]

        marked = await svc.mark_as_read(nid, tenant_id=tenant_id)
        assert marked.status == ResponseStatus.SUCCESS

        unread = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert unread == 0

    async def test_unread_count(self, db_schema, tenant_id, async_session):
        svc = NotificationService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        await svc.send_notification(user_id=uid, notification_type="info", title="N1", content="m", tenant_id=tenant_id)
        await svc.send_notification(user_id=uid, notification_type="info", title="N2", content="m", tenant_id=tenant_id)

        count = await svc.get_unread_count(user_id=uid, tenant_id=tenant_id)
        assert count >= 2

    async def test_create_and_cancel_reminder(self, db_schema, tenant_id, async_session):
        svc = NotificationService(async_session)
        uid = await self._seed_user(tenant_id, async_session)
        result = await svc.create_reminder(
            user_id=uid,
            tenant_id=tenant_id,
            title="Team standup",
            content="Daily standup meeting",
            remind_at="2026-12-31T10:00:00",
        )
        assert result.status == ResponseStatus.SUCCESS
        rid = result.data["id"]

        cancelled = await svc.cancel_reminder(rid, tenant_id=tenant_id)
        assert cancelled.status == ResponseStatus.SUCCESS


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
        assert result.status == ResponseStatus.SUCCESS
        data = result.data
        assert data["name"] == f"Acme Corp {suffix}"
        assert data["plan"] == "pro"

        fetched = await svc.get_tenant(data["id"])
        assert fetched.status == ResponseStatus.SUCCESS
        assert fetched.data["name"] == f"Acme Corp {suffix}"

    async def test_update_tenant(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(
            name=f"Original {suffix}", plan="free", admin_email=f"admin_{suffix}@example.com"
        )
        tid = created.data["id"]

        updated = await svc.update_tenant(tid, plan="enterprise", name=f"Updated {suffix}")
        assert updated.status == ResponseStatus.SUCCESS
        assert updated.data["plan"] == "enterprise"
        assert updated.data["name"] == f"Updated {suffix}"

    async def test_list_tenants(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await svc.create_tenant(name=f"List Tenant A {suffix}", plan="free", admin_email=f"a_{suffix}@x.com")
        await svc.create_tenant(name=f"List Tenant B {suffix}", plan="pro", admin_email=f"b_{suffix}@x.com")

        result = await svc.list_tenants()
        assert result.status == ResponseStatus.SUCCESS
        names = [t["name"] for t in result.data.items]
        assert any(f"List Tenant A {suffix}" in n for n in names)
        assert any(f"List Tenant B {suffix}" in n for n in names)

    async def test_get_tenant_stats(self, db_schema, async_session):
        svc = TenantService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await svc.create_tenant(name=f"Stats Tenant {suffix}", plan="pro", admin_email=f"s_{suffix}@x.com")
        tid = created.data["id"]

        stats = await svc.get_tenant_stats(tid)
        assert stats.status == ResponseStatus.SUCCESS
        assert "user_count" in stats.data
        assert "api_calls" in stats.data
