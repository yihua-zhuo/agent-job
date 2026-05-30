"""Unit tests for src/services/agent_task_service.py."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from src.services.agent_task_service import AgentTaskService
from tests.unit.conftest import MockState, make_mock_session
from tests.unit.domain_handlers.agent_tasks import make_agent_task_handler


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
        assert task.status == "pending"
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
        # Create two tasks with distinct statuses
        task_a = await service.create_task("Task A", tenant_id=1)
        task_b = await service.create_task("Task B", tenant_id=1)
        # Directly update stored state to simulate completed status.
        state = mock_db_session._state
        state.agent_tasks[task_a.id]["status"] = "completed"
        pending_tasks, total = await service.list_tasks(tenant_id=1, status="pending", page=1, page_size=20)
        assert total == 1
        assert pending_tasks[0].description == task_b.description

    async def test_filters_by_date_range(self, service, mock_db_session):
        # Directly seed two tasks with distant dates into the mock state.
        state = mock_db_session._state
        now = datetime.now(UTC)
        past_date = datetime(2020, 1, 1, tzinfo=UTC)
        future_date = datetime(2099, 1, 1, tzinfo=UTC)
        id1 = state.agent_tasks_next_id
        state.agent_tasks[id1] = {
            "id": id1, "task_id": f"atask_{id1}", "tenant_id": 1,
            "description": "Old task", "status": "pending",
            "subtasks": [], "created_at": past_date, "updated_at": past_date,
        }
        state.agent_tasks_next_id += 1
        id2 = state.agent_tasks_next_id
        state.agent_tasks[id2] = {
            "id": id2, "task_id": f"atask_{id2}", "tenant_id": 1,
            "description": "Future task", "status": "pending",
            "subtasks": [], "created_at": future_date, "updated_at": future_date,
        }
        state.agent_tasks_next_id += 1
        # Query with a narrow window around now — neither seed task falls inside it.
        tasks, total = await service.list_tasks(
            tenant_id=1,
            date_from=now,
            date_to=now,
            page=1,
            page_size=20,
        )
        assert total == 0

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
            await service.list_tasks(tenant_id=1, status="invalid_status", page=1, page_size=20)
