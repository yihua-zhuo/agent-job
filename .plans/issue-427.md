Now I have all the information needed to write the implementation plan. Let me produce it.

# Implementation Plan — Issue #427

## Goal
Consolidate the six existing identity ORM models (`TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel`) from their scattered source files (`src/db/models/tenant.py`, `user.py`, `rbac.py`) into a single new `src/db/models/identity.py`, then update `src/db/models/__init__.py` to re-export them. This is batch 1, subtask 2 of the multi-batch #270 migration. The originals are left untouched so #428 can later rewire imports and a follow-up issue can delete the old files.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0427-consolidate-existing-identity-orm-models-into-src-db-models-.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0427-consolidate-existing-identity-orm-models-into-src-db-models-.md`

## Affected Files
- `src/db/models/identity.py` — new file, will contain all 6 copied model classes with their `to_dict()` methods and import `Base` via `from db.base import Base`
- `src/db/models/__init__.py` — append 6 re-export lines for the newly-copied models; preserve the existing `Identity*` re-exports from #426 and the auto-discovery block

## Implementation Steps

1. **Read the three source files end-to-end and capture each class verbatim.** Read `src/db/models/tenant.py` (L1-L41, `TenantModel` with `to_dict()`), `src/db/models/user.py` (L1-L43, `UserModel` with `to_dict()`), and `src/db/models/rbac.py` (L1-L124, four classes: `RoleModel` L11-L44, `PermissionModel` L47-L72, `RolePermissionModel` L75-L96, `UserRoleModel` L99-L123). Note the `__table_args__` on `RoleModel` (composite index `ix_roles_tenant_name`), `RolePermissionModel` (unique constraint `uq_role_permission`), and `UserRoleModel` (unique index `ix_user_roles_user_tenant_role`). Note the `relationship` back-references between `RoleModel`, `PermissionModel`, `RolePermissionModel`, and `UserRoleModel`.

2. **Create `src/db/models/identity.py` with a consolidated import block and all six models.** At the top of the new file, write the union of imports actually used across the three sources: `from datetime import datetime`; `from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text`; `from sqlalchemy.dialects.postgresql import JSON`; `from sqlalchemy.orm import Mapped, mapped_column, relationship`; `from db.base import Base`. Then paste each class body exactly as it appears in the original file, in the order `TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel`. Keep all `__tablename__` values (`tenants`, `users`, `roles`, `permissions`, `role_permissions`, `user_roles`), all `to_dict()` methods, and all `relationship(...)` definitions unchanged.

3. **Update `src/db/models/__init__.py` to re-export the six new names.** The file already imports `Identity*` models from `internal.db.models` (L14-L23) and runs a `pkgutil.iter_modules` auto-discovery loop (L26-L32) that will now also pick up the new `identity.py`. To make the six old-style names (`TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel`) reachable via `from db.models import ...` regardless of whether the auto-discovery loop runs first, append an explicit import block after the existing `internal.db.models` import:
   ```python
   from db.models.identity import (
       TenantModel,
       UserModel,
       RoleModel,
       PermissionModel,
       RolePermissionModel,
       UserRoleModel,
   )
   ```
   Do not remove or alter the existing `Identity*` import block (L14-L23) or the auto-discovery loop (L26-L32) — the `__all__` computation at L35-L39 will still gather all eight identity-related names.

4. **Verify no import of the new `db.models.identity` module shadows the existing `internal.db.models.identity` module.** These are two distinct modules at distinct paths, so no collision occurs. Confirm by running the imports below in §"Test Plan".

5. **Run `ruff check src/db/models/identity.py src/db/models/__init__.py` and resolve any `F401` (unused import) or `E402` (module-level import order) errors** that may appear. The consolidated import block in the new file should use every imported symbol; if ruff reports an unused import (e.g. `text` if it is not used outside `TenantModel`'s `server_default=text(...)` call), it can be suppressed with `# noqa: F401` on the affected line.

## Test Plan

- **Unit tests in `tests/unit/`:** No new or modified unit tests are required. The dev-plan §6 acceptance is verified by import-time checks, not by test fixtures. The 7+ existing files that import from `db.models.tenant`, `db.models.user`, and `db.models.rbac` (e.g. `tests/unit/test_auth_service.py`, `tests/unit/test_rbac_service.py`, `tests/unit/test_tenant_service.py` if present) must continue to pass unchanged because the original files are not touched. Run `PYTHONPATH=src pytest tests/unit/ -v` to confirm.

- **Integration tests in `tests/integration/`:** No new or modified integration tests. The 4+ existing imports in `tests/integration/test_tenant_integration.py` (L16, L107, L128) and `tests/integration/conftest.py` (L259, L275, L383, L435) target the original `db.models.tenant.TenantModel` and must continue to work because the original file is left intact. Run `PYTHONPATH=src pytest tests/integration/ -v` to confirm.

- **Dev-plan verification:** The board's §6 specifies four machine-checkable commands, all run from the repository root with `PYTHONPATH=src`:
  1. `python -c "from db.models.identity import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel; print('All 6 OK')"` → expected `All 6 OK`
  2. `python -c "from db.models import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel, OrganizationModel, DepartmentModel; print('All 8 re-exports OK')"` → expected `All 8 re-exports OK` (note: `OrganizationModel` and `DepartmentModel` come from the #426 subtask 1 output; if they are not yet present, the expected count is 6 and the test should be adapted accordingly — verify by reading `src/internal/db/models/__init__.py` and confirming the re-export names)
  3. `ruff check src/db/models/identity.py src/db/models/__init__.py` → expected `0 errors` (exit 0)
  4. `python -c "import inspect; from db.models.identity import TenantModel; src = inspect.getsource(TenantModel); assert 'id' in src and 'name' in src; print('TenantModel cols OK')"` → expected `TenantModel cols OK`
  5. `python -c "import inspect; from db.models.identity import RolePermissionModel, UserRoleModel; src = inspect.getsource(RolePermissionModel); assert 'primary_key' in src; print('Assoc models PK OK')"` → expected `Assoc models PK OK`

## Acceptance Criteria
- `src/db/models/identity.py` exists, contains exactly six `Base` subclasses named `TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel`, with `__tablename__` values `tenants`, `users`, `roles`, `permissions`, `role_permissions`, `user_roles` respectively, and all original column definitions / `__table_args__` / `relationship()` strings / `to_dict()` methods preserved.
- `src/db/models/__init__.py` exposes all six names via `from db.models import ...` (either via explicit re-export or via the existing auto-discovery loop, or both), while the pre-existing `Identity*` re-exports and auto-discovery block remain intact.
- The three original files `src/db/models/tenant.py`, `src/db/models/user.py`, `src/db/models/rbac.py` are byte-identical to their pre-change contents (diff is empty).
- `PYTHONPATH=src python -c "from db.models.identity import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel; print('All 6 OK')"` prints `All 6 OK` with exit code 0.
- `ruff check src/db/models/identity.py src/db/models/__init__.py` exits 0 with no error output.
- `PYTHONPATH=src pytest tests/unit/ tests/integration/ -v` passes with no new failures introduced by the change.
