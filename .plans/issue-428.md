Good — I now have a complete understanding. Files that import `from db.models import TenantModel` (i.e. from the package) rely on the auto-discovery in `__init__.py` which finds the stub re-exports. Once we remove the old files, the identity module's direct import in `__init__.py` will keep `TenantModel` accessible. Here's the final plan:

# Implementation Plan — Issue #428

## Goal
Migrate every `from db.models.tenant`, `from db.models.user`, and `from db.models.rbac` import across `src/` and `tests/` to import from the consolidated `db.models.identity` module, then delete the three stale re-export stub files (`tenant.py`, `user.py`, `rbac.py`) so that only one canonical path exists for identity models.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/00-foundations/0428-update-all-imports-referencing-old-identity-model-paths.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/00-foundations/0428-update-all-imports-referencing-old-identity-model-paths.md`

## Affected Files

### Source files with old imports (10 files)
- `src/api/routers/customers.py` (line 471) — replaces `from db.models.user import UserModel`
- `src/services/tenant_service.py` (lines 11–12) — replaces `TenantModel` (tenant) and `UserModel` (user); merge into single `from db.models.identity import` line
- `src/services/role_service.py` (lines 18–19) — replaces `PermissionModel, RoleModel, RolePermissionModel, UserRoleModel` (rbac) and `UserModel` (user); merge into single import
- `src/services/lead_routing_service.py` (lines 12–13) — replaces `TenantModel` (tenant) and `UserModel` (user); merge into single import
- `src/services/auth_service.py` (line 11) — replaces `UserModel`
- `src/services/user_service.py` (line 11) — replaces `UserModel`
- `src/services/rbac_service.py` (lines 8–9) — replaces RBAC models and `UserModel`; merge into single import
- `src/services/automation_service.py` (line 12) — replaces `UserModel`
- `src/services/notification_service.py` (line 14) — replaces `UserModel`
- `src/services/auth/webauthn_service.py` (line 22) — **edge case**: imports `UserCredentialModel` from `db.models.user_credential` (not in scope; verify if model exists in `identity.py` before changing; if not present, this import is out of scope and must be flagged, not changed)

### Files to delete (3 stub re-exports)
- `src/db/models/tenant.py` — re-exports `TenantModel` from `identity`
- `src/db/models/user.py` — re-exports `UserModel` from `identity`
- `src/db/models/rbac.py` — re-exports `PermissionModel, RoleModel, RolePermissionModel, UserRoleModel` from `identity`

### Test files with old imports (12 files)
- `tests/unit/test_tenant_model.py` (line 7) — module-level import
- `tests/unit/domain_handlers/rbac.py` (lines 43, 59) — function-level imports
- `tests/integration/test_tenant_integration.py` (lines 16, 107, 128) — function-level imports
- `tests/integration/test_automation_rules_ui_integration.py` (line 16) — module-level import
- `tests/integration/test_rules_integration.py` (line 18) — module-level import
- `tests/integration/test_ai_integration.py` (line 16) — module-level import
- `tests/integration/test_campaign_integration.py` (line 11) — module-level import
- `tests/integration/test_copilot_integration.py` (lines 26, 51, 79) — function-level imports
- `tests/integration/test_rbac_integration.py` (lines 20–21 module-level; lines 249, 284, 517, 531–532, 655 function-level) — mix of module-level and function-level
- `tests/integration/test_churn_prediction_integration.py` (lines 24, 40) — function-level imports
- `tests/integration/conftest.py` (lines 259, 275, 383, 435) — function-level imports
- `tests/integration/domain_fixtures/copilot.py` (line 9) — module-level import

### File to verify but not modify
- `src/db/models/__init__.py` — already imports identity models directly and uses auto-discovery; deleting the three stub files is safe because the `identity` module is already explicitly imported at the top of `__init__.py`. No re-export cleanup needed.

## Implementation Steps

1. **Scan and confirm scope.** Run `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/ tests/ --include="*.py"` and record the 22-file hit count as a baseline. This becomes the checklist to work through.

2. **Update `src/services/` imports (8 files).** In each service file, replace old `from db.models.{tenant,user,rbac} import ...` lines with a single `from db.models.identity import ...` line containing all symbols needed by that file. For files that import from two or three old modules (e.g. `tenant_service.py`, `role_service.py`, `lead_routing_service.py`, `rbac_service.py`), merge into one consolidated import.

3. **Update `src/api/routers/customers.py` (1 file).** Change the local-scope import on line 471 from `from db.models.user import UserModel` to `from db.models.identity import UserModel`. Keep it as a local-scope import to avoid a circular import — confirm by reading lines 1–20 to ensure no module-level identity import already exists.

4. **Update `src/services/auth/webauthn_service.py` (verify edge case).** Read the file to check what `UserCredentialModel` is and whether it exists in `db.models.identity`. If it does, change the import path. If `UserCredentialModel` is not in `db.models.identity` (i.e. it's a separate model that #427 did not consolidate), leave it alone and note it as a pre-existing issue outside the scope of #428.

5. **Update `tests/unit/` imports (2 files).** Replace imports in `test_tenant_model.py` (module-level) and `domain_handlers/rbac.py` (two function-level). Confirm `db.models.identity` is importable from the test root by checking `tests/unit/conftest.py` for how it sets `PYTHONPATH` / `sys.path`.

6. **Update `tests/integration/` imports (9 files).** Replace module-level imports first, then function-level/local-scope imports. In `test_rbac_integration.py` consolidate the module-level RBAC + user imports on lines 20–21 into a single `from db.models.identity import ...` line. In `conftest.py` the four function-level `TenantModel` imports can each stay local or be promoted to a single module-level import — choose module-level to reduce duplication.

7. **Delete the three stub re-export files.** Remove `src/db/models/tenant.py`, `src/db/models/user.py`, and `src/db/models/rbac.py`. These are thin wrappers that re-export from `db.models.identity`; their removal does not break any import because `src/db/models/__init__.py` already explicitly imports the identity models (lines 12–20) and auto-discovers any subclass of `Base` on disk.

8. **Run the acceptance verification commands from dev-plan §6.**

## Test Plan

- **Unit tests in `tests/unit/`**: No new test files. Existing tests in `test_tenant_model.py` and `test_rbac.py` are the primary regression targets. After the import swap, `PYTHONPATH=src pytest tests/unit/ -v` must pass unchanged.

- **Integration tests in `tests/integration/`**: No new test files. Existing tests across 8 files (tenant, rbac, copilot, churn, campaign, AI, rules, automation) must pass after the import swap. `PYTHONPATH=src pytest tests/integration/ -v` must pass unchanged.

- **Dev-plan verification** (from §6 of the target board):
  - `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/` → 0 results
  - `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" tests/` → 0 results
  - `PYTHONPATH=src pytest tests/unit/ -v` → all passed, exit 0
  - `PYTHONPATH=src pytest tests/integration/ -v` → all passed, exit 0
  - `ruff check src/` → 0 errors
  - `ruff check tests/` → 0 errors

## Acceptance Criteria
- `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/ tests/ --include="*.py"` returns 0 lines
- `src/db/models/tenant.py`, `src/db/models/user.py`, and `src/db/models/rbac.py` no longer exist
- `PYTHONPATH=src pytest tests/unit/ -v` exits 0 with all tests passing
- `ruff check src/` exits 0 with no errors
- `src/db/models/identity` is the sole import path for `TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, and `UserRoleModel` across the entire codebase

## Risks / Open Questions
- **`webauthn_service.py` `UserCredentialModel` import**: This file imports `from db.models.user_credential import UserCredentialModel`. The grep target for this issue was only `tenant`, `user`, and `rbac` — `user_credential` is a separate module not consolidated by #427. If `UserCredentialModel` is not present in `db.models.identity`, this import should be left untouched. If it *is* present, it should be migrated. **Requires verification by reading `identity.py` for the class before editing.**
