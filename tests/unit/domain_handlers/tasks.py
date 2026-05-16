"""Task SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def task_handler(sql_text, params):
    """Handle task-related SQL (stateless)."""

    if "insert into tasks" in sql_text:
        return MockResult(
            [
                MockRow(
                    {
                        "id": 1,
                        "tenant_id": params.get("tenant_id", 0),
                        "title": params.get("title", "Task"),
                        "description": params.get("description", ""),
                        "assigned_to": params.get("assigned_to", 0),
                        "due_date": params.get("due_date"),
                        "status": params.get("status", "pending"),
                        "priority": params.get("priority", "normal"),
                        "created_by": params.get("created_by", 0),
                        "completed_at": None,
                        "created_at": params.get("created_at"),
                        "updated_at": params.get("updated_at"),
                    }
                )
            ]
        )

    if "from tasks where id" in sql_text:
        task_id = params.get("id")
        tenant_id = params.get("tenant_id")
        fixtures = {
            1: {
                "id": 1,
                "tenant_id": 1,
                "title": "Task A",
                "description": "Desc A",
                "assigned_to": 1,
                "due_date": None,
                "status": "pending",
                "priority": "normal",
                "created_by": 1,
                "completed_at": None,
                "created_at": None,
                "updated_at": None,
            },
            2: {
                "id": 2,
                "tenant_id": 1,
                "title": "Task B",
                "description": "Desc B",
                "assigned_to": 0,
                "due_date": None,
                "status": "in_progress",
                "priority": "high",
                "created_by": 1,
                "completed_at": None,
                "created_at": None,
                "updated_at": None,
            },
        }
        if task_id in fixtures and fixtures[task_id].get("tenant_id") == tenant_id:
            return MockResult([MockRow(fixtures[task_id].copy())])
        return MockResult([])

    if "from tasks" in sql_text:
        tenant_id = params.get("tenant_id")
        rows = [
            {
                "id": 1,
                "tenant_id": 1,
                "title": "Task A",
                "description": "Desc A",
                "assigned_to": 1,
                "due_date": None,
                "status": "pending",
                "priority": "normal",
                "created_by": 1,
                "completed_at": None,
                "created_at": None,
                "updated_at": None,
            }
        ]
        return MockResult([MockRow(r) for r in rows if r.get("tenant_id") == tenant_id])

    return None


def get_handlers(state: MockState):
    return [task_handler]


__all__ = ["get_handlers", "task_handler"]
