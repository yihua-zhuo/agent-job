"""Customer SQL handlers for unit tests."""

from __future__ import annotations

import json as _json

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def make_customer_handler(state: MockState):
    """Handle all customer-related SQL (INSERT, UPDATE, DELETE, SELECT, COUNT)."""

    def handler(sql_text, params):
        if "insert into customers" in sql_text:
            cid = state.customers_next_id
            state.customers_next_id += 1
            tags_raw = params.get("tags", [])
            tags_val = _json.dumps(tags_raw) if not isinstance(tags_raw, str) else tags_raw
            record = {
                "id": cid,
                "tenant_id": params.get("tenant_id", 0),
                "name": params.get("name", "Test"),
                "email": params.get("email"),
                "phone": params.get("phone"),
                "company": params.get("company"),
                "status": params.get("status", "lead"),
                "owner_id": params.get("owner_id", 0),
                "tags": tags_val,
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            state.customers[cid] = record
            return MockResult([MockRow(record.copy())])

        if sql_text.startswith("update") and "customers" in sql_text:
            customer_id = params.get("id")
            if customer_id in state.customers:
                rec = state.customers[customer_id]
                for k, v in params.items():
                    if k not in ("id", "tenant_id"):
                        rec[k] = v
                return MockResult([MockRow(rec.copy())])
            if customer_id and customer_id >= 1:
                return MockResult(
                    [
                        MockRow(
                            {
                                "id": customer_id,
                                "tenant_id": params.get("tenant_id", 1),
                                "name": params.get("name", "Customer A"),
                                "email": params.get("email", "a@test.com"),
                                "phone": params.get("phone", "123"),
                                "company": params.get("company", "Acme"),
                                "status": params.get("status", "lead"),
                                "owner_id": params.get("owner_id", 1),
                                "tags": _json.dumps(params.get("tags", [])),
                                "created_at": None,
                                "updated_at": None,
                            }
                        )
                    ]
                )
            return MockResult([])

        if sql_text.startswith("delete") and "customers" in sql_text:
            return MockResult([MockRow({"id": params.get("id", 1)})])

        if "select" in sql_text and "count(" in sql_text and "from customers" in sql_text:
            tenant_id = params.get("tenant_id")
            count_val = 3 if tenant_id == 1 else 7
            return MockResult([[count_val]])

        if "select" in sql_text and "from customers" in sql_text and "tags" in sql_text:
            # Only match when filtering BY tags, not when 'tags' appears in SELECT
            after_where = ""
            if "where" in sql_text:
                after_where = sql_text.split("where", 1)[1].split("order")[0].split("limit")[0]
            if "tags" not in after_where:
                return None  # not a tag-filter query; let other handlers deal with it
            customer_id = params.get("id")
            if customer_id in state.customers:
                c = state.customers[customer_id]
                return MockResult([MockRow({"id": customer_id, "tags": c.get("tags", "[]")})])
            return MockResult([])

        # Single-customer lookup by id (recognized by 'where customers.id' in SQL text)
        if "from customers" in sql_text and "where" in sql_text and "customers.id" in sql_text:
            customer_id = params.get("id") or params.get("id_1")
            tenant_id_param = params.get("tenant_id") or params.get("tenant_id_1")
            if customer_id is not None:
                # Only return state-seeded customers — no fallback fixtures
                if customer_id in state.customers:
                    rec = state.customers[customer_id]
                    if rec.get("tenant_id") == tenant_id_param:
                        return MockResult([MockRow(rec.copy())])
                return MockResult([])

        if "select" in sql_text and "from customers" in sql_text and "id" not in params and "id_1" not in params:
            tenant_filter = params.get("tenant_id", 0)
            rows = []
            for rec in state.customers.values():
                if rec.get("tenant_id") == tenant_filter:
                    rows.append(MockRow(rec.copy()))
            rows.extend(
                [
                    MockRow(
                        {
                            "id": 1,
                            "tenant_id": tenant_filter,
                            "name": "Customer A",
                            "email": "a@test.com",
                            "phone": "123",
                            "company": "Acme",
                            "status": "lead",
                            "owner_id": 1,
                            "tags": "[]",
                            "created_at": None,
                            "updated_at": None,
                        }
                    ),
                    MockRow(
                        {
                            "id": 2,
                            "tenant_id": tenant_filter,
                            "name": "Customer B",
                            "email": "b@test.com",
                            "phone": "456",
                            "company": "Beta",
                            "status": "customer",
                            "owner_id": 1,
                            "tags": "[]",
                            "created_at": None,
                            "updated_at": None,
                        }
                    ),
                ]
            )
            if tenant_filter == 2:
                rows = []
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_customer_handler(state)]


__all__ = ["get_handlers", "make_customer_handler"]
