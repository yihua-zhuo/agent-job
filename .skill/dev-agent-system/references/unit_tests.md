# Unit Tests

Unit tests mock the DB — **no real PostgreSQL**, no `DATABASE_URL` needed.  
Each test file owns its mock fixtures; no global autouse patching.

## Fixture Setup (per file)

```python
import pytest
from tests.unit.conftest import (
    make_mock_session,
    make_customer_handler,
    make_count_handler,
    MockState,
)
from services.my_service import MyService


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_customer_handler(state),
        make_count_handler(state),
    ])


@pytest.fixture
def my_service(mock_db_session):
    return MyService(mock_db_session)
```

Only include handlers your tests actually exercise.

## Available Handlers (from `tests/unit/conftest.py`)

| Handler | Factory | Has state |
|---|---|---|
| `make_customer_handler(state)` | yes | yes |
| `make_user_handler(state)` | yes | yes |
| `tenant_handler` | no (import directly) | no |
| `pipeline_handler` | no | no |
| `opportunity_handler` | no | no |
| `ticket_sql_handler` | no | no |
| `campaign_handler` | no | no |
| `make_count_handler(state)` | yes | yes |

Domain-specific handlers are discovered from `tests/unit/domain_handlers/*.py`.
Current domain handler modules also re-export their helpers through
`tests.unit.conftest` for compatibility.

If your service queries a table not covered above, add a new file:

```python
# tests/unit/domain_handlers/my_domain.py
from tests.unit.conftest import MockResult, MockRow, MockState


def make_my_domain_handler(state: MockState):
    def handler(sql_text, params):
        if "from my_table" in sql_text:
            return MockResult([MockRow({"id": 1, "tenant_id": params.get("tenant_id")})])
        return None

    return handler


def get_handlers(state: MockState):
    return [make_my_domain_handler(state)]


__all__ = ["get_handlers", "make_my_domain_handler"]
```

Do not add routine domain handlers to `tests/unit/conftest.py`; keep them in
their own domain module.

## Writing Tests

```python
import pytest
from pkg.errors.app_exceptions import NotFoundException


class TestMyService:

    async def test_get_entity_success(self, my_service):
        # Arrange — seed state if needed via handler or MockState
        # Act
        entity = await my_service.get_entity(entity_id=1, tenant_id=1)
        # Assert
        assert entity.id == 1
        assert entity.tenant_id == 1

    async def test_get_entity_not_found(self, my_service):
        with pytest.raises(NotFoundException):
            await my_service.get_entity(entity_id=9999, tenant_id=1)

    async def test_list_entities_returns_tuple(self, my_service):
        items, total = await my_service.list_entities(tenant_id=1, page=1, page_size=10)
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_create_entity(self, my_service):
        entity = await my_service.create_entity(
            {"name": "Test"}, tenant_id=1
        )
        assert entity.name == "Test"
        assert entity.tenant_id == 1
```

## Run

```bash
export PYTHONPATH=src
pytest tests/unit/ -v
# or just this file:
pytest tests/unit/test_my_service.py -v
```

## Rules

- Each file defines its own `mock_db_session` fixture — no shared autouse patching.
- Real SQL is **never** executed in unit tests.
- Use `pytest.raises(SomeException)` to assert error paths.
- Don't import `MockState` / handlers in the test body — only in fixtures.
- New domain SQL handlers belong in `tests/unit/domain_handlers/<domain>.py`.
