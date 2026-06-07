# admin（不含 * ）精确匹配
assert has_permission("admin", "customer", "read") is True
# viewer 无法访问 delete
assert has_permission("viewer", "customer", "delete") is False
# owner 的 * 全通配
assert has_permission("owner", "anyresource", "anyaction") is True
# tickets:* 前缀通配模拟（如 ROLE_PERMISSIONS 支持 glob）
# 边界：角色不存在assert has_permission("nonexistent", "customer", "read") is False
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_permission_service.py -v` → ≥ 9 passed

---

### Step 5: 创建单元测试 `tests/unit/test_require_permission.py`

测试 `@require_permission` 装饰器行为。

操作：
- Mock `require_auth` dependency 返回带特定 roles 的 `AuthContext`
- 测试三个场景：
1. **权限足够** →装饰器返回 ctx，不抛异常
  2. **权限不足** →装饰器内部 `has_permission` 返回 False，抛 `ForbiddenException`
  3. **无 roles / tenant_id=None** → 抛 `ForbiddenException`

示例代码：

```python
import pytest
from unittest.mock import patch, MagicMock

from dependencies.rbac import require_permission
from internal.middleware.fastapi_auth import AuthContext
from pkg.errors.app_exceptions import ForbiddenException

class TestRequirePermission:
    def test_admin_customer_read_allowed(self):
        ctx = AuthContext(user_id=1, tenant_id=1, roles=["admin"])
        with patch("dependencies.rbac.require_auth", return_value=ctx):
            decorated = require_permission("customer", "read")
            result = decorated()
            assert result == ctx

    def test_viewer_customer_delete_denied(self):
        ctx = AuthContext(user_id=1, tenant_id=1, roles=["viewer"])
        with patch("dependencies.rbac.require_auth", return_value=ctx):
            decorated = require_permission("customer", "delete")
            with pytest.raises(ForbiddenException):
                decorated()
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_require_permission.py -v` → ≥ 6 passed

---

### Step 6: 全局 ruff check操作：
- 运行 `ruff check src/services/permission_service.py src/dependencies/rbac.py`
- 如有 lint错误立即修复

**完成判定**：`ruff check src/services/permission_service.py src/dependencies/rbac.py` →0 errors

---

## 6. 验收

- [ ] `ruff check src/services/permission_service.py src/dependencies/rbac.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_permission_service.py -v` → ≥ 9 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_require_permission.py -v` → ≥ 6 passed
- [ ] `PYTHONPATH=src python -c "from services.permission_service import has_permission; print(has_permission('owner', 'foo', 'bar'))"` → `True`
- [ ] `PYTHONPATH=src python -c "from services.permission_service import has_permission; print(has_permission('viewer', 'customer', 'delete'))"` → `False`
- [ ] `PYTHONPATH=src python -c "from dependencies.rbac import require_permission; print('OK')"` → `OK`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `has_permission` glob 逻辑实现错误（如正则边界条件导致误匹配） | 低 | 中 | 先全覆盖单元测试；glob逻辑错误只影响 `has_permission`，不影响已存在的 `RBACService` |
| `tenant_id is None` 时装饰器行为导致现有端点 403 — 部分旧 token 用户被误拦 | 低 | 中 | 装饰器抛 `ForbiddenException` 前打印 debug 日志（已加），定位到后可在 `require_auth` 层拒绝旧 token，不影响本板块 PR |
| `RBACService.get_user_roles` 无法在装饰器无 session环境下使用（`check_permission` 需要 session） | 低 | 低 | `check_permission` 是可选辅助函数，不影响装饰器；装饰器用 `AuthContext.roles` 已足够 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/permission_service.py \
      src/dependencies/rbac.py \
      src/dependencies/__init__.py \
      tests/unit/test_permission_service.py \
      tests/unit/test_require_permission.py
git commit -m "feat(rbac): add PermissionService and @require_permission decorator (closes #641)"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(rbac): add PermissionService and @require_permission decorator" --body "Closes #641

- src/services/permission_service.py: ROLE_PERMISSIONS constant + has_permission() (glob support) + check_permission()
- src/dependencies/rbac.py: @require_permission(resource, action) FastAPI Depends decorator
- Unit tests covering glob matching, boundary cases, and decorator behavior🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/rbac_service.py`](../../../src/services/rbac_service.py) —现有 DB-backed RBAC，`DEFAULT_ROLE_PERMISSIONS` 和 `has_permission` 的原始出处
- 同类参考实现：[`src/dependencies/auth.py`](../../../src/dependencies/auth.py) —现有 FastAPI `require_role` 装饰器实现（参考其 Depends工厂模式）
- 同类参考实现：[`src/internal/middleware/fastapi_auth.py`](../../../src/internal/middleware/fastapi_auth.py) — `AuthContext` 定义
- 父 issue / 关联：#38（父 issue权限管控体系）、#640（依赖项，ORM + migrations先行）、#643（启用后赋能，装饰器接入所有 router）、#642（装饰器定义 — 与本板块并列，实际由本板块实现）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
