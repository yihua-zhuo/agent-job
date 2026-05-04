"""
Integration tests for Customer, Pipeline & Opportunity services.

Run against a real PostgreSQL database (Supabase via DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_sales_customer_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest

from pkg.errors.app_exceptions import NotFoundException
from services.customer_service import CustomerService
from services.pipeline_service import PipelineService
from services.sales_service import SalesService
from services.user_service import UserService

# ──────────────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────────────


async def _seed_user(async_session, tenant_id: int = 1) -> int:
    """Create a user and return their id."""
    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=f"scuser_{suffix}",
        email=f"sc_{suffix}@example.com",
        password="Test@Pass1234",
        tenant_id=tenant_id,
    )
    return reg.id


async def _seed_customer(async_session, tenant_id: int = 1, **overrides):
    """Create a customer and return the CustomerModel."""
    cust_svc = CustomerService(async_session)
    suffix = uuid.uuid4().hex[:8]
    data = {"name": f"SC Cust {suffix}", "email": f"sc_{suffix}@example.com", **overrides}
    result = await cust_svc.create_customer(data=data, tenant_id=tenant_id)
    return result


# ──────────────────────────────────────────────────────────────────────────────────────
#  CustomerService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestCustomerServiceIntegration:
    """Full customer lifecycle via the real DB using the shared async_session fixture."""

    async def test_create_and_get_customer(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await cust_svc.create_customer(
            data={"name": f"Create Get {suffix}", "email": f"cg_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        assert result is not None
        cid = result.id

        fetched = await cust_svc.get_customer(cid, tenant_id=tenant_id)
        assert fetched.name == f"Create Get {suffix}"
        assert fetched.email == f"cg_{suffix}@example.com"

    async def test_create_customer_with_all_fields(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        result = await cust_svc.create_customer(
            data={
                "name": f"All Fields {suffix}",
                "email": f"af_{suffix}@example.com",
                "phone": "+1-555-0001",
                "company": "Acme Corp",
                "status": "customer",
            },
            tenant_id=tenant_id,
        )
        assert result is not None
        assert result.company == "Acme Corp"
        assert result.status == "customer"

    async def test_update_customer(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await cust_svc.create_customer(
            data={"name": f"Update {suffix}", "email": f"up_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        cid = created.id

        updated = await cust_svc.update_customer(cid, {"name": f"Updated {suffix}"}, tenant_id=tenant_id)
        assert updated.name == f"Updated {suffix}"

    async def test_update_customer_not_found(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        with pytest.raises(NotFoundException):
            await cust_svc.update_customer(99999, {"name": "Ghost"}, tenant_id=tenant_id)

    async def test_delete_customer(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await cust_svc.create_customer(
            data={"name": f"Delete {suffix}", "email": f"del_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        cid = created.id

        deleted = await cust_svc.delete_customer(cid, tenant_id=tenant_id)
        assert deleted is not None

        with pytest.raises(NotFoundException):
            await cust_svc.get_customer(cid, tenant_id=tenant_id)

    async def test_list_customers(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        for i in range(3):
            await cust_svc.create_customer(
                data={"name": f"List {suffix} {i}", "email": f"list_{suffix}_{i}@example.com"},
                tenant_id=tenant_id,
            )

        items, total = await cust_svc.list_customers(page=1, page_size=20, tenant_id=tenant_id)
        assert len(items) >= 3

    async def test_list_customers_pagination(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        for i in range(5):
            await cust_svc.create_customer(
                data={"name": f"Page {suffix} {i}", "email": f"page_{suffix}_{i}@example.com"},
                tenant_id=tenant_id,
            )

        items1, total1 = await cust_svc.list_customers(page=1, page_size=2, tenant_id=tenant_id)
        assert len(items1) == 2
        assert total1 >= 5

        items2, _total2 = await cust_svc.list_customers(page=2, page_size=2, tenant_id=tenant_id)
        assert len(items2) == 2

    async def test_search_customers(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await cust_svc.create_customer(
            data={"name": f"Search Target {suffix}", "email": f"st_{suffix}@example.com"},
            tenant_id=tenant_id,
        )

        result = await cust_svc.search_customers(suffix, tenant_id=tenant_id)
        assert isinstance(result, list)
        assert any(suffix.lower() in item.name.lower() for item in result)

    async def test_add_and_remove_tag(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await cust_svc.create_customer(
            data={"name": f"Tag {suffix}", "email": f"tag_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        cid = created.id

        tagged = await cust_svc.add_tag(cid, "vip", tenant_id=tenant_id)
        assert tagged is not None

        removed = await cust_svc.remove_tag(cid, "vip", tenant_id=tenant_id)
        assert removed is not None

    async def test_change_status(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        created = await cust_svc.create_customer(
            data={"name": f"Status {suffix}", "email": f"st_{suffix}@example.com", "status": "lead"},
            tenant_id=tenant_id,
        )
        cid = created.id

        changed = await cust_svc.change_status(cid, "customer", tenant_id=tenant_id)
        assert changed.status == "customer"

    async def test_assign_owner(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        suffix = uuid.uuid4().hex[:8]
        created = await cust_svc.create_customer(
            data={"name": f"Owner {suffix}", "email": f"ow_{suffix}@example.com"},
            tenant_id=tenant_id,
        )
        cid = created.id

        assigned = await cust_svc.assign_owner(cid, uid, tenant_id=tenant_id)
        assert assigned.owner_id == uid

    async def test_bulk_import(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        customers = [
            {"name": f"Bulk {suffix} {i}", "email": f"bulk_{suffix}_{i}@example.com", "owner_id": 1}
            for i in range(3)
        ]
        result = await cust_svc.bulk_import(customers, tenant_id=tenant_id)
        assert result == 3

    async def test_count_by_status(self, db_schema, tenant_id, async_session):
        cust_svc = CustomerService(async_session)
        suffix = uuid.uuid4().hex[:8]
        await cust_svc.create_customer(
            data={"name": f"Count {suffix}", "email": f"cnt_{suffix}@example.com", "status": "lead"},
            tenant_id=tenant_id,
        )
        result = await cust_svc.count_by_status(tenant_id=tenant_id)
        assert isinstance(result, dict)


# ──────────────────────────────────────────────────────────────────────────────────────
#  PipelineService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestPipelineServiceIntegration:
    """Full pipeline lifecycle via the real DB using the shared async_session fixture."""

    async def test_create_and_get_pipeline(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        result = await pipe_svc.create_pipeline(
            tenant_id=tenant_id,
            data={"name": "Sales Pipeline"},
        )
        assert result is not None
        pid = result.id

        fetched = await pipe_svc.get_pipeline(tenant_id, pid)
        assert fetched.name == "Sales Pipeline"

    async def test_update_pipeline(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        created = await pipe_svc.create_pipeline(
            tenant_id=tenant_id,
            data={"name": "Old Name"},
        )
        pid = created.id

        updated = await pipe_svc.update_pipeline(tenant_id, pid, {"name": "New Name"})
        assert updated.name == "New Name"

    async def test_delete_pipeline(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        created = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "To Delete"})
        pid = created.id

        deleted = await pipe_svc.delete_pipeline(tenant_id, pid)
        assert deleted == pid

        with pytest.raises(NotFoundException):
            await pipe_svc.get_pipeline(tenant_id, pid)

    async def test_list_pipelines(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        for name in ["Pipe A", "Pipe B"]:
            await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": name})

        items, total = await pipe_svc.list_pipelines(tenant_id)
        assert len(items) >= 2

    async def test_add_stage(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        created = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Stage Test"})
        pid = created.id

        stage = await pipe_svc.add_stage(tenant_id, pid, {"name": "Qualification", "order": 1})
        assert stage.name == "Qualification"

    async def test_update_stage(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        created = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Stage Update"})
        pid = created.id
        stage = await pipe_svc.add_stage(tenant_id, pid, {"name": "Initial", "order": 1})
        sid = stage.id

        updated = await pipe_svc.update_stage(tenant_id, pid, sid, {"name": "Updated Stage Name"})
        assert updated.name == "Updated Stage Name"

    async def test_reorder_stages(self, db_schema, tenant_id, async_session):
        pipe_svc = PipelineService(async_session)
        created = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Reorder Pipeline"})
        pid = created.id
        s1 = await pipe_svc.add_stage(tenant_id, pid, {"name": "Stage 1", "order": 1})
        s2 = await pipe_svc.add_stage(tenant_id, pid, {"name": "Stage 2", "order": 2})

        # reorder_stages returns None; just verify it does not raise
        await pipe_svc.reorder_stages(tenant_id, pid, [s1.id, s2.id])


# ──────────────────────────────────────────────────────────────────────────────────────
#  SalesService integration tests
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.integration
class TestSalesServiceIntegration:
    """Full opportunity lifecycle + pipeline stats via the real DB."""

    async def test_create_and_get_opportunity(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        cust = await _seed_customer(async_session, tenant_id)
        cid = cust.id
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Opp Pipe"})
        pid = pipe.id
        uid = await _seed_user(async_session, tenant_id)
        result = await sales_svc.create_opportunity(
            tenant_id=tenant_id,
            data={
                "name": "Big Deal", "customer_id": cid, "pipeline_id": pid,
                "amount": "50000", "stage": "qualified", "owner_id": uid,
            },
        )
        assert result is not None
        oid = result["id"]

        fetched = await sales_svc.get_opportunity(tenant_id, oid)
        assert fetched["name"] == "Big Deal"

    async def test_update_opportunity(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        cust = await _seed_customer(async_session, tenant_id)
        cid = cust.id
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Upd Pipe"})
        pid = pipe.id
        uid = await _seed_user(async_session, tenant_id)
        created = await sales_svc.create_opportunity(
            tenant_id=tenant_id,
            data={
                "name": "Old Title", "customer_id": cid, "pipeline_id": pid,
                "amount": "1000", "stage": "lead", "owner_id": uid,
            },
        )
        oid = created["id"]

        updated = await sales_svc.update_opportunity(tenant_id, oid, {"name": "New Title"})
        assert updated["name"] == "New Title"

    async def test_change_stage(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        cust = await _seed_customer(async_session, tenant_id)
        cid = cust.id
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Chg Pipe"})
        pid = pipe.id
        uid = await _seed_user(async_session, tenant_id)
        created = await sales_svc.create_opportunity(
            tenant_id=tenant_id,
            data={
                "name": "Stage Change", "customer_id": cid, "pipeline_id": pid,
                "amount": "500", "stage": "lead", "owner_id": uid,
            },
        )
        oid = created["id"]

        changed = await sales_svc.change_stage(tenant_id, oid, "qualified")
        assert changed["stage"] == "qualified"

    async def test_list_opportunities(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "List Opp Pipe"})
        pid = pipe.id
        uid = await _seed_user(async_session, tenant_id)
        for i in range(3):
            cust = await _seed_customer(async_session, tenant_id)
            cid = cust.id
            await sales_svc.create_opportunity(
                tenant_id=tenant_id,
                data={
                    "name": f"List Opp {i}", "customer_id": cid,
                    "pipeline_id": pid, "amount": "100",
                    "stage": "lead", "owner_id": uid,
                },
            )

        result = await sales_svc.list_opportunities(tenant_id)
        assert result is not None
        assert "items" in result

    async def test_get_forecast(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        uid = await _seed_user(async_session, tenant_id)
        result = await sales_svc.get_forecast(tenant_id, owner_id=uid)
        assert result is not None
        assert isinstance(result, dict)

    async def test_get_pipeline_stats(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Stats Pipe"})
        pid = pipe.id

        stats = await sales_svc.get_pipeline_stats(tenant_id, pid)
        assert stats is not None
        assert isinstance(stats, dict)

    async def test_get_pipeline_funnel(self, db_schema, tenant_id, async_session):
        sales_svc = SalesService(async_session)
        pipe_svc = PipelineService(async_session)
        pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": "Funnel Pipe"})
        pid = pipe.id

        funnel = await sales_svc.get_pipeline_funnel(tenant_id, pid)
        assert funnel is not None
        assert isinstance(funnel, dict)
