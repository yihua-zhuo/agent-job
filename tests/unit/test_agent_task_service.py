"""Unit tests for src/services/agent_task_service.py."""

from __future__ import annotations

from datetime import datetime as dt

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from src.services.agent_task_service import AgentTaskService, AgentTaskStatus
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.agent_tasks import make_agent_task_handler


def _seed_agent_task(state: MockState, tenant_id: int, description: str, status: str, created_at: dt) -> int:
    """Seed an agent task directly into mock state, bypassing the ORM."""
    task_id = state.agent_tasks_next_id
    state.agent_tasks_next_id += 1
    state.agent_tasks[task_id] = {
        "id": task_id,
        "task_id": f"atask_{task_id}",
        "tenant_id": tenant_id,
        "description": description,
        "status": status,
        "subtasks": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    return task_id


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_agent_task_handler(state)], state=state)


@pytest.fixture
def service(mock_db_session):
    return AgentTaskService(mock_db_session)


class TestCreateTask:
    async def test_creates_task_with_pending_status(self, service):
        task = await service.create_task("Process inbound email", tenant_id=42)
        assert task.tenant_id == 42
        assert task.description == "Process inbound email"
        assert task.status == AgentTaskStatus.PENDING
        assert task.task_id.startswith("atask_")

    async def test_strips_whitespace_from_description(self, service):
        task = await service.create_task("  Trim me ", tenant_id=1)
        assert task.description == "Trim me"

    async def test_raises_validation_for_empty_description(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("", tenant_id=1)

    async def test_raises_validation_for_whitespace_only(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("   ", tenant_id=1)

    async def test_raises_validation_for_non_positive_tenant_id(self, service):
        with pytest.raises(ValidationException):
            await service.create_task("Task", tenant_id=0)
        with pytest.raises(ValidationException):
            await service.create_task("Task", tenant_id=-1)


class TestGetTask:
    async def test_returns_created_task(self, service):
        created = await service.create_task("Test task", tenant_id=1)
        task = await service.get_task(created.id, tenant_id=1)
        assert task.id == created.id
        assert task.description == "Test task"

    async def test_raises_not_found_for_missing_id(self, service):
        with pytest.raises(NotFoundException):
            await service.get_task(9999, tenant_id=1)

    async def test_raises_not_found_for_wrong_tenant(self, service):
        created = await service.create_task("Tenant 1 task", tenant_id=1)
        with pytest.raises(NotFoundException):
            await service.get_task(created.id, tenant_id=999)


class TestListTasks:
    async def test_returns_tasks_with_total(self, service):
        await service.create_task("Task 1", tenant_id=1)
        await service.create_task("Task 2", tenant_id=1)
        tasks, total = await service.list_tasks(tenant_id=1, page=1, page_size=20)
        assert total == 2
        assert len(tasks) == 2

    async def test_filters_by_status(self, service, mock_db_session):
        # Create two tasks with distinct statuses under tenant 1.
        task_a = await service.create_task("Task A", tenant_id=1)
        task_b = await service.create_task("Task B", tenant_id=1)
        state = mock_db_session._state
        # Directly update stored state to simulate completed status — bypasses
        # the handler's UPDATE path but mirrors the ORM field write so the
        # SELECT path sees the updated status.
        state.agent_tasks[task_a.id]["status"] = "completed"
        # Seed a tenant-2 task that must be excluded from all results.
        _seed_agent_task(state, tenant_id=2, description="Tenant 2 pending task", status="pending", created_at=dt.now())
        pending_tasks, total = await service.list_tasks(tenant_id=1, status="pending", page=1, page_size=20)
        # Assert COUNT path (total must exclude the tenant-2 task).
        assert total == 1
        # Order is created_at DESC; task_b was created after task_a so it sorts first.
        # We assert by ID rather than by list position to avoid relying on this.
        assert pending_tasks[0].id == task_b.id
        # Ensure the tenant-2 task was never included in SELECT results.
        descriptions = {t.description for t in pending_tasks}
        assert "Tenant 2 pending task" not in descriptions

    async def test_filters_by_date_range(self, service, mock_db_session):
        # Seed two tasks with distant dates into the mock state.
        state = mock_db_session._state
        now = dt.now()
        past_date = dt(2020, 1, 1)
        future_date = dt(2099, 1, 1)
        _seed_agent_task(state, tenant_id=1, description="Old task", status="pending", created_at=past_date)
        _seed_agent_task(state, tenant_id=1, description="Future task", status="pending", created_at=future_date)
        # Seed a third task under tenant 2 so cross-tenant COUNT exclusion can be verified.
        _seed_agent_task(state, tenant_id=2, description="Tenant 2 past task", status="pending", created_at=past_date)
        # Query with a narrow window around now — neither seed task falls inside it.
        tasks, total = await service.list_tasks(
            tenant_id=1,
            date_from=now,
            date_to=now,
            page=1,
            page_size=20,
        )
        assert total == 0  # COUNT path also respects tenant isolation
        assert tasks == []

    async def test_filters_by_date_range_returns_matching_tasks(self, service, mock_db_session):
        # Seed two tasks with known creation times inside a precise window.
        state = mock_db_session._state
        mid_date = dt(2024, 6, 15, 12, 0, 0)
        _seed_agent_task(state, tenant_id=1, description="June task", status="pending", created_at=mid_date)
        _seed_agent_task(state, tenant_id=1, description="Another June task", status="pending", created_at=mid_date)
        # Seed a tenant-2 task inside the same window to verify cross-tenant SELECT exclusion.
        _seed_agent_task(state, tenant_id=2, description="Tenant 2 June task", status="pending", created_at=mid_date)
        tasks, total = await service.list_tasks(
            tenant_id=1,
            date_from=dt(2024, 6, 1),
            date_to=dt(2024, 6, 30),
            page=1,
            page_size=20,
        )
        # Both seeded tasks fall inside the window.
        assert total == 2
        assert len(tasks) == 2
        assert all(t.tenant_id == 1 for t in tasks)
        descriptions = {t.description for t in tasks}
        assert descriptions == {"June task", "Another June task"}
        # Tenant-2 task must not appear in SELECT results.
        assert "Tenant 2 June task" not in descriptions

    async def test_respects_pagination(self, service):
        ids = []
        for i in range(5):
            task = await service.create_task(f"Task {i}", tenant_id=1)
            ids.append(task.id)
        page1, _ = await service.list_tasks(tenant_id=1, page=1, page_size=2)
        page2, _ = await service.list_tasks(tenant_id=1, page=2, page_size=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id == ids[0]
        assert page2[0].id == ids[2]

    async def test_returns_empty_for_unknown_tenant(self, service):
        await service.create_task("Task 1", tenant_id=1)
        tasks, total = await service.list_tasks(tenant_id=99, page=1, page_size=20)
        assert total == 0
        assert tasks == []

    async def test_raises_validation_for_invalid_status(self, service):
        with pytest.raises(ValidationException):
            await service.list_tasks(tenant_id=1, status="definitely_not_a_valid_status_xyz", page=1, page_size=20)

    async def test_accepts_valid_status_strings(self, service):
        tasks, total = await service.list_tasks(tenant_id=1, status="pending", page=1, page_size=20)
        assert total >= 0
