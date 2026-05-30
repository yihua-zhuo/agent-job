Now I have everything I need. Let me write the implementation plan.

# Implementation Plan — Issue #657

## Goal

Create two new SQLAlchemy ORM models — `WorkflowDefinitionModel` and `WorkflowInstanceModel` — in `src/db/models/`, mirroring the conventions of existing models (e.g., `customer.py`, `workflow.py`). Both models must include a `to_dict()` method, use `JSONB` for JSON columns, and have `tenant_id` indexed. Both must be imported in `alembic/env.py` so autogenerate picks them up. Tests cover model instantiation and `to_dict()` output.

---

## Affected Files

- `src/db/models/workflow_definition.py` — **new** — `WorkflowDefinitionModel` ORM model
- `src/db/models/workflow_instance.py` — **new** — `WorkflowInstanceModel` ORM model with FK to `workflow_definitions`
- `alembic/env.py` — add imports for the two new model modules
- `tests/unit/conftest.py` — add `make_workflow_definition_handler(state)` and `make_workflow_instance_handler(state)` factory functions and `get_handlers()` for both
- `tests/unit/test_workflow_definition_model.py` — **new** — unit tests for `WorkflowDefinitionModel`
- `tests/unit/test_workflow_instance_model.py` — **new** — unit tests for `WorkflowInstanceModel`
- `tests/integration/test_workflow_definition_integration.py` — **new** — integration tests for `WorkflowDefinitionModel` against a real PostgreSQL DB
- `tests/integration/test_workflow_instance_integration.py` — **new** — integration tests for `WorkflowInstanceModel` against a real PostgreSQL DB

---

## Implementation Steps

1. **Create `src/db/models/workflow_definition.py`** following the `workflow.py` pattern:
   - `__tablename__ = "workflow_definitions"`
   - Columns: `id` (Integer, PK, autoincrement), `tenant_id` (Integer, nullable=False, index=True), `name` (String(255), nullable=False), `description` (String(2000), nullable=True), `version` (String(50), default="1.0", nullable=False), `definition_data` (JSONB, default=dict, nullable=False), `created_at` (DateTime timezone=True, server_default=func.now()), `updated_at` (DateTime timezone=True, server_default=func.now(), onupdate=func.now())
   - Add `to_dict()` that returns all fields; datetime fields formatted as ISO strings via `.isoformat()`, JSON fields default to `{}` when None
   - Import `Base` from `db.base`, `JSONB` from `sqlalchemy.dialects.postgresql`, `DateTime`/`Integer`/`String`/`func` from `sqlalchemy`

2. **Create `src/db/models/workflow_instance.py`** following the `pipeline_stage.py` FK pattern:
   - `__tablename__ = "workflow_instances"`
   - Columns: `id` (Integer, PK, autoincrement), `tenant_id` (Integer, nullable=False, index=True), `definition_id` (Integer, ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True), `status` (String(50), default="pending", nullable=False), `context` (JSONB, default=dict, nullable=False), `started_at` (DateTime timezone=True, server_default=func.now()), `completed_at` (DateTime timezone=True, nullable=True)
   - Add `to_dict()` with ISO-formatted datetimes, `{}` defaults for JSON fields
   - Use `TYPE_CHECKING` guard for the forward reference to `WorkflowDefinitionModel` (or import at top of file — since `WorkflowDefinitionModel` is in a separate file, use `from db.models.workflow_definition import WorkflowDefinitionModel` under `TYPE_CHECKING`)
   - Add a `workflow_definition: Mapped["WorkflowDefinitionModel"]` relationship with `back_populates` (add `back_populates="instances"` to `WorkflowDefinitionModel` in step 3)

3. **Update `src/db/models/workflow_definition.py`** — add a `instances: Mapped[list["WorkflowInstanceModel"]]` relationship on `WorkflowDefinitionModel` with `back_populates="workflow_definition"`, `cascade="all, delete-orphan"`, `lazy="raise"`. Place the import under `TYPE_CHECKING` (same pattern as `pipeline_stage.py`).

4. **Update `alembic/env.py`** — add two lines below the existing `import db.models  # noqa: F401` block (or alongside it): `import db.models.workflow_definition` and `import db.models.workflow_instance`. These explicit imports guarantee the models are registered with `Base.metadata` even if the auto-discovery ever misses them. Keep the existing `import db.models` line intact.

5. **Add domain handlers in `tests/unit/conftest.py`** — add `make_workflow_definition_handler(state: MockState)` and `make_workflow_instance_handler(state: MockState)` factory functions, each returning a handler callable with signature `(sql_text: str, params: dict) -> MockResult | None`. Both handlers manage in-memory dicts on `state` (e.g., `state.workflow_definitions`, `state.workflow_instances`) with auto-increment IDs. SQL patterns to handle: INSERT (returns `MockResult([MockRow(record)])`), SELECT by id, SELECT list (filter by tenant_id), COUNT, UPDATE, DELETE. Add a `workflow_definition_handler` and `workflow_instance_handler` export. The `make_mock_session` builder is used in test files by composing handlers — no global wiring is needed.

6. **Create `tests/unit/test_workflow_definition_model.py`** — test `WorkflowDefinitionModel` in isolation:
   - `test_to_dict_returns_all_fields` — instantiate the model and call `to_dict()`, assert all expected keys are present
   - `test_to_dict_datetime_iso_format` — verify datetime fields are ISO strings
   - `test_to_dict_json_fields_default_empty` — verify `definition_data` defaults to `{}` when None
   - `test_attribute_assignment` — verify all fields can be set and read back
   - Use a plain `WorkflowDefinitionModel(...)` constructor without a DB session (no session needed for model unit tests)

7. **Create `tests/unit/test_workflow_instance_model.py`** — same pattern for `WorkflowInstanceModel`:
   - `test_to_dict_returns_all_fields`
   - `test_to_dict_datetime_iso_format`
   - `test_to_dict_json_fields_default_empty`
   - `test_attribute_assignment`
   - `test_default_status_is_pending`

8. **Create `tests/integration/test_workflow_definition_integration.py`** — use fixtures `db_schema`, `tenant_id`, `async_session`:
   - `test_insert_workflow_definition` — create a record via `async_session.add()`, flush, verify `id` is assigned
   - `test_query_workflow_definition_by_tenant` — insert multiple definitions for two tenants, query by tenant_id, assert correct count
   - `test_update_workflow_definition` — insert, modify field, flush, verify updated_at changes
   - `test_delete_workflow_definition` — insert and delete, assert it is gone
   - Use `pytest.mark.integration` on the class

9. **Create `tests/integration/test_workflow_instance_integration.py`** — same structure:
   - `test_insert_workflow_instance` — insert a definition first (use `_seed_customer` helper or direct insert), then an instance, verify FK linkage
   - `test_query_instances_by_tenant` — multi-tenant isolation check
   - `test_update_instance_status` — change status from "pending" to "running", verify
   - `test_complete_instance` — set `completed_at`, verify it is not None after update
   - `test_cascade_delete_on_definition_delete` — insert definition + instance, delete definition, assert instance is gone

---

## Test Plan

- **Unit tests in `tests/unit/`**: `test_workflow_definition_model.py` and `test_workflow_instance_model.py` cover model construction and `to_dict()` output — no DB, no async, fast (<5s total).
- **Integration tests in `tests/integration/`**: `test_workflow_definition_integration.py` and `test_workflow_instance_integration.py` cover persistence, tenant isolation, FK cascade, and status transitions against a real PostgreSQL DB.

---

## Acceptance Criteria

- `WorkflowDefinitionModel` has all seven fields (id, tenant_id, name, description, version, definition_data, created_at, updated_at) and a working `to_dict()`.
- `WorkflowInstanceModel` has all seven fields (id, tenant_id, definition_id, status, context, started_at, completed_at), a working `to_dict()`, and a `ForeignKey` to `workflow_definitions.id` with `ondelete="CASCADE"`.
- Both models appear in `Base.metadata.tables` when `import db.models` is evaluated (verifiable via `alembic current` after a migration).
- `alembic revision --autogenerate` produces a migration file that includes CREATE TABLE for both tables when run against a clean `alembic_dev` DB.
- All new unit tests pass: `pytest tests/unit/test_workflow_definition_model.py tests/unit/test_workflow_instance_model.py -v`.
- All new integration tests pass: `pytest tests/integration/test_workflow_definition_integration.py tests/integration/test_workflow_instance_integration.py -v`.
- `ruff check src/db/models/workflow_definition.py src/db/models/workflow_instance.py` produces no errors.
