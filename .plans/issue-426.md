Now I have everything I need to write the plan.

# Implementation Plan — Issue #426

## Goal
Create `src/db/models/identity.py` with `OrganizationModel` and `DepartmentModel` ORM models, following the same patterns as `UserModel`/`CustomerModel` (mapped columns, `tenant_id` index, timestamps). The `__init__.py` auto-discovery mechanism means no changes are needed there. Unit tests are added to verify the models.

## Affected Files
- `src/db/models/identity.py` — **create new file** with `OrganizationModel` and `DepartmentModel` ORM classes
- `tests/unit/test_identity_model.py` — **create new file** with unit tests for both models

## Implementation Steps
1. Create `src/db/models/identity.py` with two SQLAlchemy ORM models:
   - `OrganizationModel`: `id` (pk), `tenant_id` (indexed), `name` (String 255), `status` (String 50, default "active"), `description` (Text, nullable), `created_at`/`updated_at` (DateTime with `server_default=func.now()` and `onupdate`), `to_dict()` method.
   - `DepartmentModel`: `id` (pk), `tenant_id` (indexed), `organization_id` (FK to organizations.id, indexed), `name` (String 255), `status` (String 50, default "active"), `created_at`/`updated_at`, `to_dict()` method.
   - Use `from db.base import Base`, `from sqlalchemy import ...`, `from sqlalchemy.orm import Mapped, mapped_column`, `from datetime import datetime`, follow exact column patterns from `UserModel`/`CustomerModel`.
2. The `pkgutil.iter_modules()` loop in `src/db/models/__init__.py` auto-discovers all `Base` subclasses in submodules, so no changes to `__init__.py` are needed — `OrganizationModel` and `DepartmentModel` will be re-exported automatically.
3. Create `tests/unit/test_identity_model.py` with test classes for `OrganizationModel` and `DepartmentModel` covering: default creation, field values, `to_dict()` output, `from_dict()` parsing (if applicable), and nullability checks.

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_identity_model.py` — two `Test*Model` classes each covering instantiation with defaults, explicit field values, `to_dict()` serialization, and `from_dict()` parsing.
- Integration tests in `tests/integration/`: none required for this task — no service/router exists yet for these models.

## Acceptance Criteria
- `src/db/models/identity.py` exists with both `OrganizationModel` and `DepartmentModel` defined, each subclassing `Base`.
- `src/db/models/__init__.py` re-exports `OrganizationModel` and `DepartmentModel` via its auto-discovery loop (no manual exports needed).
- `pytest tests/unit/ -v` passes with no errors, including any new `test_identity_model.py` tests.
- Both models have `tenant_id` with `index=True`, `created_at`/`updated_at` with `server_default=func.now()`, and a `to_dict()` method.
