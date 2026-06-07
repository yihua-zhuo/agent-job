"""Churn prediction domain SQL mock handlers.

The tenant-aware customer handler in this module is the recommended fixture
for ChurnPredictionService tests because the shared ``make_customer_handler``
ignores the ``tenant_id`` bind parameter — using it would silently pass
cross-tenant queries and mask isolation bugs.
"""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 10


def _bind_value(params: dict, base_name: str):
    """Return the bind value for *base_name*, accepting SQLAlchemy's suffix variants.

    SQLAlchemy compiles ``CustomerModel.id == customer_id`` to a bind key
    named ``id`` when no other ``id`` exists in the same statement, but
    becomes ``id_1`` (or higher) when a conflict is detected. Tests assert
    on the service's intent (filter by both ``id`` and ``tenant_id``), not
    on the internal suffix SQLAlchemy chose.
    """
    if base_name in params:
        return params[base_name]
    for key, value in params.items():
        if key == base_name or key.startswith(f"{base_name}_"):
            return value
    return None


def make_tenant_aware_customer_handler(state: MockState):
    """Customer handler that filters by tenant_id in the SQL predicate.

    Unlike the shared ``make_customer_handler`` (which matches ``from customers
    where id`` and ignores tenant_id), this handler inspects the tenant_id
    bind param and only returns the customer when it matches the seeded
    record. Wrong-tenant queries therefore return an empty result set,
    allowing the service to raise NotFoundException at its tenant predicate.
    """

    def handler(sql_text, params):
        normalized = " ".join(sql_text.split())
        if "from customers" not in normalized:
            return None
        if "where" not in normalized:
            return None
        # Only intercept single-row lookups (id + tenant_id) — that's the
        # isolation contract this handler exists to enforce. List/count
        # queries (no id bind) fall through to the regular customer handler.
        customer_id = _bind_value(params, "id")
        tenant_id = _bind_value(params, "tenant_id")
        if customer_id is None or tenant_id is None:
            return None
        if customer_id not in state.customers:
            return MockResult([])
        rec = state.customers[customer_id]
        if tenant_id is None or rec.get("tenant_id") == tenant_id:
            return MockResult([MockRow(rec.copy())])
        return MockResult([])

    return handler


def get_handlers(state: MockState):
    return [make_tenant_aware_customer_handler(state)]


__all__ = ["get_handlers", "make_tenant_aware_customer_handler"]
