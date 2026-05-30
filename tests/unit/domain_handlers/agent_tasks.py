"""Agent task SQL handlers for unit tests."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from tests.unit.conftest import MockResult, MockRow, MockState

_OFFSET_RE = re.compile(r"offset\s*:?\s*(\w+)", re.IGNORECASE)
_LIMIT_RE = re.compile(r"limit\s*:?\s*(\w+)", re.IGNORECASE)
_ORDER_RE = re.compile(r"order\s+by\s+(.+?)(?:\s+offset|\s+limit|$)", re.IGNORECASE)


def make_agent_task_handler(state: MockState) -> Callable[[str, dict], MockResult | None]:
    if not hasattr(state, "agent_tasks"):
        state.agent_tasks = {}
    if not hasattr(state, "agent_tasks_next_id"):
        state.agent_tasks_next_id = 1

    def handler(sql_text: str, params: dict) -> MockResult | None:
        # Normalize compiled SQLAlchemy params: when SQLAlchemy emits multiple
        # params with the same base name (e.g. created_at_1, created_at_2 for two
        # >= and <= comparisons), keep ALL of them so filters receive both bounds.
        # For params that appear once, strip the trailing _<digit> suffix.
        normalized = {}
        for k, v in params.items():
            base = re.sub(r"_\d+$", "", k)
            if base not in normalized:
                normalized[base] = v
            elif isinstance(normalized[base], list):
                normalized[base].append(v)
            else:
                normalized[base] = [normalized[base], v]

        # UPDATE (set status after creation)
        if "update agent_tasks" in sql_text:
            tid = normalized.get("id")
            tenant_id = normalized.get("tenant_id")
            if tid not in state.agent_tasks or state.agent_tasks[tid].get("tenant_id") != tenant_id:
                return MockResult([])
            rec = state.agent_tasks[tid]
            base_keys = set(rec.keys())
            for k, v in params.items():
                base = re.sub(r"_\d+$", "", k)
                if base in base_keys:
                    state.agent_tasks[tid][base] = v
            return MockResult([MockRow(state.agent_tasks[tid].copy())])

        # INSERT
        if "insert into agent_tasks" in sql_text:
            # tenant_id must be explicitly provided by the service.
            tenant_id = normalized.get("tenant_id")
            if not tenant_id:
                raise ValueError("agent_tasks INSERT requires tenant_id in params")
            # Skip if already inserted (flush called after a prior refresh set the id).
            existing_id = normalized.get("id")
            if existing_id is not None and existing_id in state.agent_tasks:
                return MockResult([MockRow(state.agent_tasks[existing_id].copy())])
            new_id = state.agent_tasks_next_id
            state.agent_tasks_next_id += 1
            record = {
                "id": new_id,
                "task_id": normalized.get("task_id") or params.get("task_id") or f"atask_{new_id}",
                "tenant_id": tenant_id,
                "description": normalized.get("description") or params.get("description"),
                "status": normalized.get("status") or "pending",
                "subtasks": normalized.get("subtasks") or params.get("subtasks") or [],
                "created_at": normalized.get("created_at") or params.get("created_at") or datetime.utcnow(),
                "updated_at": normalized.get("updated_at") or params.get("updated_at") or datetime.utcnow(),
            }
            state.agent_tasks[new_id] = record
            return MockResult([MockRow(record.copy())])

        # COUNT
        if "select" in sql_text and "count" in sql_text and "from agent_tasks " in sql_text:
            tenant_id = normalized.get("tenant_id")
            if tenant_id is None:
                raise ValueError("agent_tasks COUNT requires tenant_id in params")
            status_filter = normalized.get("status")
            date_bounds = normalized.get("created_at")
            if date_bounds is not None and isinstance(date_bounds, list) and len(date_bounds) == 2:
                lo, hi = date_bounds[0], date_bounds[-1]
                if lo > hi:
                    lo, hi = hi, lo  # normalize regardless of SQLAlchemy's emission order
                date_bounds = (lo, hi)
            count_val = sum(
                1 for r in state.agent_tasks.values()
                if r.get("tenant_id") == tenant_id
                and (status_filter is None or r.get("status") == status_filter)
                and (
                    date_bounds is None
                    or (
                        r.get("created_at") is not None
                        and not (r.get("created_at") < date_bounds[0] or r.get("created_at") > date_bounds[-1])
                    )
                )
            )
            return MockResult([[count_val]])

        # SELECT by id + tenant
        if "from agent_tasks where id" in sql_text and "tenant_id" in sql_text:
            tid = normalized.get("id")
            tenant_id = normalized.get("tenant_id")
            if tid is None or tenant_id is None:
                raise ValueError("agent_tasks SELECT by id requires both id and tenant_id in params")
            rec = state.agent_tasks.get(tid)
            if rec is not None and rec.get("tenant_id") == tenant_id:
                return MockResult([MockRow(rec.copy())])
            return MockResult([])

        # SELECT list (no id filter)
        if "select" in sql_text and "from agent_tasks " in sql_text and "where id" not in sql_text:
            tenant_id = normalized.get("tenant_id")
            if tenant_id is None:
                raise ValueError("agent_tasks SELECT list requires tenant_id in params")
            rows = []
            for rec in state.agent_tasks.values():
                if rec.get("tenant_id") != tenant_id:
                    continue
                # Apply status filter
                status_filter = normalized.get("status")
                if status_filter is not None and rec.get("status") != status_filter:
                    continue
                # Apply date_from / date_to filters.
                # The service emits `created_at >= :created_at_1` and
                # `created_at <= :created_at_2`; after normalization both land in
                # normalized["created_at"] as [date_from, date_to]. Normalize
                # ordering so <= can appear before >= in the SQL.
                date_bounds = normalized.get("created_at")
                if date_bounds is not None and isinstance(date_bounds, list) and len(date_bounds) == 2:
                    lo, hi = date_bounds[0], date_bounds[-1]
                    if lo > hi:
                        lo, hi = hi, lo
                    date_bounds = (lo, hi)
                if date_bounds is not None:
                    created = rec.get("created_at")
                    if created is None:
                        continue
                    if created < date_bounds[0] or created > date_bounds[-1]:
                        continue
                rows.append(MockRow(rec.copy()))
            # Apply ORDER BY created_at DESC, id ASC (id is a stable secondary key
            # when timestamps collide) before pagination.
            order_match = _ORDER_RE.search(sql_text)
            if order_match is not None:
                order_clause = order_match.group(1).lower()
                if "desc" in order_clause and "created_at" in order_clause:
                    rows.sort(key=lambda r: (r.get("created_at") or datetime.min, r.get("id")), reverse=True)
            offset_match = _OFFSET_RE.search(sql_text)
            limit_match = _LIMIT_RE.search(sql_text)
            if offset_match is not None:
                offset_key = offset_match.group(1)
                assert offset_key in params, f"offset bind param '{offset_key}' not found in params"
                offset_val = params[offset_key]
                if offset_val is not None:
                    rows = rows[int(offset_val):]
            if limit_match is not None:
                limit_key = limit_match.group(1)
                assert limit_key in params, f"limit bind param '{limit_key}' not found in params"
                limit_val = params[limit_key]
                if limit_val is not None:
                    rows = rows[: int(limit_val)]
            return MockResult(rows)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_agent_task_handler(state)]


__all__ = ["get_handlers", "make_agent_task_handler"]
