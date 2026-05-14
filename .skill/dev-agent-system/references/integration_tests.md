# Integration Tests

Integration tests run against a real PostgreSQL database.  
They use fixtures from `tests/integration/conftest.py` and are marked `@pytest.mark.integration`.

## File Naming

`tests/integration/test_<domain>_integration.py`

## Fixture Reference

| Fixture | Scope | Purpose |
|---|---|---|
| `db_schema` | function | Creates all tables before test, drops after |
| `tenant_id` | function | Current tenant ID (int) |
| `async_session` | function | Real `AsyncSession` shared across services in one test |

Always include `db_schema` as the first fixture so tables exist before anything else runs.

## Template

```python
import pytest
from services.my_service import MyService
from pkg.errors.app_exceptions import NotFoundException


@pytest.mark.integration
class TestMyServiceIntegration:

    async def test_create_and_get(self, db_schema, tenant_id, async_session):
        svc = MyService(async_session)
        created = await svc.create_entity({"name": "Acme"}, tenant_id=tenant_id)
        assert created.id is not None

        fetched = await svc.get_entity(created.id, tenant_id=tenant_id)
        assert fetched.name == "Acme"

    async def test_not_found(self, db_schema, tenant_id, async_session):
        svc = MyService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_entity(99999, tenant_id=tenant_id)

    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        svc = MyService(async_session)
        entity = await svc.create_entity({"name": "Tenant A"}, tenant_id=tenant_id)

        with pytest.raises(NotFoundException):
            await svc.get_entity(entity.id, tenant_id=tenant_id + 1)

    async def test_list_paginated(self, db_schema, tenant_id, async_session):
        svc = MyService(async_session)
        for i in range(5):
            await svc.create_entity({"name": f"Entity {i}"}, tenant_id=tenant_id)

        items, total = await svc.list_entities(tenant_id=tenant_id, page=1, page_size=3)
        assert total == 5
        assert len(items) == 3
```

## Cross-Service Seeding

When your entity depends on another (e.g., a ticket needs a customer):

```python
from tests.integration.conftest import _seed_customer, _seed_user

async def test_ticket_requires_customer(self, db_schema, tenant_id, async_session):
    customer = await _seed_customer(async_session, tenant_id)
    svc = TicketService(async_session)
    ticket = await svc.create_ticket(
        {"subject": "Help", "customer_id": customer.id}, tenant_id=tenant_id
    )
    assert ticket.customer_id == customer.id
```

## Run

```bash
export PYTHONPATH=src
DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" \
  pytest tests/integration/ -v

# Single file
DATABASE_URL="..." pytest tests/integration/test_my_service_integration.py -v
```

## Gotchas

- `db_schema` uses `TRUNCATE CASCADE` between tests — don't rely on data persisting across test functions.
- Don't run against the same DB you use for Alembic autogenerate — it causes phantom diffs.
- Services raise exceptions on error — always use `pytest.raises()` to test failure paths.
- Use `async_session` (singular) — all services in one test share the same session so FK constraints resolve.
