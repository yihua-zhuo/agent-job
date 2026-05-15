# Implementation Plan — Issue #273

## Goal
Define SQLAlchemy ORM models for eight identity tables (Tenant, Organization, Department, User, Role, Permission, RolePermission, UserRole) in `src/internal/db/models/identity.py`, subclassing `Base` from `src/internal/db/engine.py`. All models include full tenant scoping, soft delete, timestamps, and audit fields, matching existing ORM patterns in `src/db/models/`. A unit test suite verifies model instantiation and `to_dict()` output for all eight models.

## Affected Files
- `src/internal/db/models/identity.py` — **create** with all eight ORM model classes
- `src/internal/db/models/__init__.py` — **create** re-exporting the eight model classes
- `tests/unit/test_identity_models.py` — **create** unit tests for all eight models

## Implementation Steps
1. **Create directory** `src/internal/db/models/` (does not yet exist).
2. **Create `src/internal/db/models/identity.py`** with the following model classes, each subclassing `Base` from `internal.db.engine`:

   - **`TenantModel`** (`__tablename__ = "tenants"`) — `id`, `name`, `plan`, `status`, `settings` (JSON), `created_at`, `updated_at`, `is_deleted` (soft delete bool), `deleted_at`. No tenant_id. `to_dict()` included.

   - **`OrganizationModel`** (`__tablename__ = "organizations"`) — `id`, `tenant_id`, `name`, `slug`, `description`, `is_active`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`. Unique constraint on `(tenant_id, slug)`. `to_dict()` included.

   - **`DepartmentModel`** (`__tablename__ = "departments"`) — `id`, `tenant_id`, `organization_id` (FK), `name`, `description`, `parent_id` (self-referential FK for hierarchy), `created_at`, `updated_at`, `is_deleted`, `deleted_at`. `to_dict()` included.

   - **`UserModel`** (`__tablename__ = "users"`) — `id`, `tenant_id`, `username`, `email`, `password_hash`, `full_name`, `bio`, `status`, `is_deleted`, `deleted_at`, `deleted_by`, `created_at`, `updated_at`. Unique constraint on `(tenant_id, username)` and `(tenant_id, email)`. `to_dict()` included.

   - **`RoleModel`** (`__tablename__ = "roles"`) — `id`, `tenant_id`, `name`, `display_name`, `description`, `is_system`, `priority`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`. Unique constraint on `(tenant_id, name)`. Relationships to `RolePermissionModel` and `UserRoleModel`. `to_dict()` included.

   - **`PermissionModel`** (`__tablename__ = "permissions"`) — `id`, `name`, `display_name`, `category`, `description`, `created_at`, `updated_at`, `is_deleted`, `deleted_at`. Unique constraint on `name`. Relationship to `RolePermissionModel`. `to_dict()` included.

   - **`RolePermissionModel`** (`__tablename__ = "role_permissions"`) — `id`, `role_id` (FK, CASCADE), `permission_id` (FK, CASCADE). Unique constraint on `(role_id, permission_id)`. `to_dict()` included.

   - **`UserRoleModel`** (`__tablename__ = "user_roles"`) — `id`, `user_id`, `role_id` (FK, CASCADE), `tenant_id`, `granted_by`, `granted_at`, `is_deleted`, `deleted_at`. Unique constraint on `(user_id, tenant_id, role_id)`. Relationship to `RoleModel`. `to_dict()` included.

3. **Add `created_by`/`updated_by` audit fields** to `TenantModel` and `OrganizationModel` as `Integer` columns (default 0, nullable=False). Add `granted_by`/`granted_at` audit trail to `UserRoleModel`.

4. **Create `src/internal/db/models/__init__.py`** that re-exports all eight classes and sets `__all__`.

## Test Plan
- Unit tests in `tests/unit/test_identity_models.py`: Test all eight models by instantiating each class directly (no DB required). Cover field defaults (soft delete False, timestamps set), relationship resolution on back-populates pairs, and `to_dict()` output for each model. Also test that `TenantModel`, `OrganizationModel`, and `DepartmentModel` do NOT have `tenant_id` as nullable key (org/dept have it; tenant is the root).

## Acceptance Criteria
- `src/internal/db/models/identity.py` defines all 8 classes, each inheriting from the `Base` exported by `internal.db.engine`.
- `src/db/models/__init__.py` is not modified (the target path is `internal/db/models/__init__.py`).
- All models have `to_dict()` returning a dict with all fields serialised (datetimes as ISO strings, bools as bools).
- `TenantModel` has no `tenant_id` column; `OrganizationModel`, `DepartmentModel`, `UserModel`, `RoleModel`, `UserRoleModel` all carry `tenant_id` and filter by it.
- All models with soft delete have `is_deleted: Mapped[bool] = mapped_column(default=False)` and `deleted_at: Mapped[datetime | None]`.
- `pytest tests/unit/test_identity_models.py -v` passes.
- `ruff check src/internal/db/models/identity.py` passes with no errors.
