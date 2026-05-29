"""User SQL handlers for unit tests."""

from __future__ import annotations

from datetime import datetime as dt

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 20


def make_user_handler(state: MockState):
    """Handle all user-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into users" in sql_text:
            uid = state.users_next_id
            state.users_next_id += 1
            record = {
                "id": uid,
                "tenant_id": params.get("tenant_id", 0),
                "username": params.get("username"),
                "email": params.get("email"),
                "password_hash": None,
                "role": params.get("role", "user"),
                "status": "pending",
                "full_name": params.get("full_name"),
                "bio": None,
                "created_at": params.get("created_at"),
                "updated_at": params.get("created_at"),
            }
            state.users[uid] = record
            return MockResult([MockRow(record.copy())])

        is_user_query = "from users" in sql_text or (sql_text.startswith("update") and "users" in sql_text)
        if not is_user_query:
            return None

        if sql_text.startswith("delete") and "users" in sql_text:
            user_id = params.get("id")
            was_in_mock = user_id in state.users
            if was_in_mock:
                state.users[user_id]["status"] = "deleted"
                del state.users[user_id]
            state.deleted_user_ids.add(user_id)
            if was_in_mock:
                return MockResult([MockRow({"id": user_id})])
            return MockResult([])

        if ("set " in sql_text or sql_text.startswith("update")) and "where id" in sql_text:
            user_id = params.get("id")
            if user_id in state.users:
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        state.users[user_id][k] = v
                return MockResult([MockRow(state.users[user_id].copy())])
            return MockResult([])

        if "select" in sql_text and "count" in sql_text and "from users" in sql_text:
            count_val = len(state.users)
            if count_val == 0:
                tenant_id = params.get("tenant_id")
                count_val = 7 if tenant_id == 1 else 3
            return MockResult([[count_val]])

        if "where username" in sql_text:
            username = params.get("username")
            for rec in state.users.values():
                if rec.get("username") == username:
                    return MockResult([MockRow(rec.copy())])
            fixtures = {
                "existing": {"id": 1, "tenant_id": 0, "username": "existing", "email": "existing@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": None, "bio": None},
                "alice": {"id": 1, "tenant_id": 1, "username": "alice", "email": "alice@test.com", "password_hash": None, "role": "user", "status": "active", "full_name": "Alice", "bio": "bio"},
                "john_doe": {"id": 2, "tenant_id": 0, "username": "john_doe", "email": "john@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": "John Doe", "bio": None},
                "jane_doe": {"id": 3, "tenant_id": 0, "username": "jane_doe", "email": "jane@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": "Jane Doe", "bio": None},
            }
            if username in fixtures:
                row = fixtures[username].copy()
                now = dt.utcnow()
                row["created_at"] = now
                row["updated_at"] = now
                return MockResult([MockRow(row)])
            return MockResult([])

        if "where email" in sql_text:
            email = params.get("email")
            for rec in state.users.values():
                if rec.get("email") == email:
                    return MockResult([MockRow(rec.copy())])
            if email == "existing@test.com":
                now = dt.utcnow()
                return MockResult([MockRow({"id": 1, "tenant_id": 0, "username": "existing", "email": "existing@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": None, "bio": None, "created_at": now, "updated_at": now})])
            return MockResult([])

        if "where id" in sql_text:
            user_id = params.get("id")
            if user_id in state.users:
                return MockResult([MockRow(state.users[user_id].copy())])
            if user_id in state.deleted_user_ids:
                return MockResult([])
            fixtures = {
                1: {"id": 1, "tenant_id": 0, "username": "existing", "email": "existing@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": None, "bio": None},
                5: {"id": 5, "tenant_id": 1, "username": "charlie", "email": "charlie@test.com", "password_hash": None, "role": "admin", "status": "active", "full_name": "Charlie", "bio": "dev"},
            }
            if user_id in fixtures:
                row = fixtures[user_id].copy()
                now = dt.utcnow()
                row["created_at"] = now
                row["updated_at"] = now
                return MockResult([MockRow(row)])
            return MockResult([])

        if state.users:
            return MockResult([MockRow(r.copy()) for r in state.users.values()])
        now = dt.utcnow()
        rows = [
            MockRow({"id": 1, "tenant_id": 0, "username": "existing", "email": "existing@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": None, "bio": None, "created_at": now, "updated_at": now}),
            MockRow({"id": 2, "tenant_id": 0, "username": "john_doe", "email": "john@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": "John Doe", "bio": None, "created_at": now, "updated_at": now}),
            MockRow({"id": 3, "tenant_id": 0, "username": "jane_doe", "email": "jane@test.com", "password_hash": None, "role": "user", "status": "pending", "full_name": "Jane Doe", "bio": None, "created_at": now, "updated_at": now}),
        ]
        return MockResult(rows)

    return handler


def get_handlers(state: MockState):
    return [make_user_handler(state)]


__all__ = ["get_handlers", "make_user_handler"]
