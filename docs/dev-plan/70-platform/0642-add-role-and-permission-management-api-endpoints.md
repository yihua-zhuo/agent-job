# RBAC 权限管理 API · 新增角色与权限管理 API 端点

| 元数据 | 值 |
|---|---|
| Issue | #642 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0641-add-role-and-permission-models](40-campaigns/0641-add-role-and-permission-models.md) |
| 启用后赋能 | 自动化规则引擎, 全链路权限审计 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统目前缺少细粒度的基于角色的访问控制（RBAC）接口。现有的权限体系仅依赖全局角色（admin/member），无法支持多租户场景下自定义角色的创建、权限组合的动态更新，以及用户与角色的绑定。业务方要求将 `customer:read`、`opportunity:write` 等资源-操作对作为权限原子，本 issue 提供对应的 HTTP 接口层和 Service 层，为上层功能（如 issue #688 自动化规则）提供权限判断的基础能力。

### 1.2 做完后

- **用户视角**：管理员可在租户内创建自定义角色（如"客服-只读"），将角色分配给用户，并随时调整该角色的权限列表。普通成员可查看自己拥有的角色及权限（只读）。
- **开发者视角**：新增 `RoleService`（`src/services/role_service.py`）和 `rbac` 路由（`src/api/routers/rbac.py`）。开发者可通过 `RoleService.assign_role()` 为业务逻辑赋予用户角色分配能力，通过 `@require_permission("resource:action")` 装饰器保护任意路由。

### 1.3 不做什么（剔除）

- [ ] 不实现角色层级（role inheritance）或角色嵌套。
- [ ] 不实现权限的 CRUD 原子操作（如"新增一个权限定义"）——权限元组集合由 GET /permissions 只读枚举。
- [ ] 不实现 DB migration —— Role/Permission ORM 模型由 #641 提供。

### 1.4 关键 KPI

- [指标 1：`ruff check src/api/routers/rbac.py src/services/role_service.py` → 0 errors]
- [指标 2：`PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → ≥ 6 passed]
- [指标 3：`PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → ≥ 6 passed]
- [指标 4：GET /roles、POST /roles、GET /roles/{id}/permissions、PUT /roles/{id}/permissions、POST /users/{id}/role、GET /permissions 六个端点均返回 `{"success": true, ...}`]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：确认 #641 是否已提交 Role / Permission ORM 模型至 `src/db/models/`；若无则本 issue 无法独立完成（依赖未就绪）。

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/__init__.py` — 注册 rbac router 到 main app
  - `src/main.py` — 可选，如需在此注册新 router
- 要建：
  - `src/services/role_service.py` — RoleService 业务逻辑
  - `src/api/routers/rbac.py` — 6 个 RBAC API 端点
  - `tests/unit/test_role_service.py` — RoleService 单元测试
  - `tests/integration/test_rbac_integration.py` — RBAC 端到端集成测试

### 2.3 缺什么

- [ ] RoleService：缺少对 Role / Permission ORM 模型的操作封装（CRUD + 用户-角色绑定）。
- [ ] RBAC router：缺少 GET /roles、POST /roles、GET /roles/{id}/permissions、PUT /roles/{id}/permissions、POST /users/{id}/role、GET /permissions 六个端点。
- [ ] @require_permission 装饰器：缺少对资源-操作对权限的检查能力（当前只有 require_auth）。
- [ ] 无租户隔离的角色查询：每个租户的角色列表应互不可见。
- [ ] 权限校验：create role、assign role、update role permissions 需要 admin+ 角色校验。

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/role_service.py` | RoleService：角色列表、创建、更新、用户-角色绑定、权限枚举 |
| `src/api/routers/rbac.py` | 6 个 RBAC API 端点，统一返回 ApiResponse envelope |
| `tests/unit/test_role_service.py` | RoleService 单元测试（Mock DB，覆盖正常/边界/异常路径） |
| `tests/integration/test_rbac_integration.py` | RBAC 端到端集成测试（真实 Postgres，验证租户隔离） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/__init__.py`](../../src/api/routers/__init__.py) | 注册 RBAC router（`router.include_router(rbac_router, prefix="/rbac", tags=["RBAC"])`） |

### 3.3 新增能力

- **Service method**：`RoleService.list_roles(self, tenant_id: int) -> list[RoleModel]`
- **Service method**：`RoleService.create_role(self, tenant_id: int, name: str, permissions: list[str]) -> RoleModel`
- **Service method**：`RoleService.get_role_permissions(self, role_id: int, tenant_id: int) -> list[str]`
- **Service method**：`RoleService.update_role_permissions(self, role_id: int, tenant_id: int, permissions: list[str]) -> RoleModel`
- **Service method**：`RoleService.assign_role_to_user(self, user_id: int, role_id: int, tenant_id: int) -> None`
- **Service method**：`RoleService.list_all_permissions(self) -> list[dict[str, str]]`
- **API endpoint**：`GET /rbac/roles` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /rbac/roles` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /rbac/roles/{id}/permissions` → `{"success": true, "data": {"role_id": N, "permissions": [...]}}`
- **API endpoint**：`PUT /rbac/roles/{id}/permissions` → `{"success": true, "data": {...}}`
- **API endpoint**：`POST /rbac/users/{id}/role` → `{"success": true, "data": {"user_id": N, "role_id": M}}`
- **API endpoint**：`GET /rbac/permissions` → `{"success": true, "data": [{"resource": "customer", "action": "read"}, ...]}`
- **Permission guard**：`@require_permission("role:assign")` 装饰器（保护 assign role 端点）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选"权限以 list[str] 存储于 Role.permissions 字段（JSONB）"而非"单独的 Permission 表 + ManyToMany"**：Role/Permission 模型已由 #641 落地为 JSONB 列，遵循现有 schema 避免重复迁移。查询权限列表直接返回 JSONB 内容，无 JOIN 开销。
- **选 @require_permission 装饰器而非在每个路由内手动调用 `svc.check_permission()`**：装饰器模式将权限检查与业务逻辑解耦，符合 FastAPI 依赖注入风格，且可在路由层统一处理 ForbiddenException。
- **选 GET /permissions 返回固定枚举而非动态查询 Permission 表**：权限元组集合（resource:action pairs）是系统级别的配置，不应动态变更。硬编码常量或从配置文件读取，简化实现并保证幂等性。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| FastAPI | `>=0.100` | 需支持 `depended_on` 在装饰器场景 |
| SQLAlchemy | `2.x async` | 已有约束，RoleService 遵循 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy），角色列表、用户-角色绑定查询均需租户过滤。
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责。
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException`），**不**返回 `ApiResponse.error()`。
- admin+ 权限校验：create role、update role permissions、assign role 三个端点必须在 router 层加 `@require_permission("admin:*")` 或等价检查。
- 所有端点均需通过 `require_auth` 注入 `AuthContext`，取 `ctx.tenant_id` 和 `ctx.user_id`。

### 4.4 已知坑

1. **JSONB 列返回 Python list，router 序列化时直接 `.to_dict()` 可能丢失 JSONB 类型** → 规避：`RoleModel` 的 `permissions` 字段声明为 `Mapped[list[str]]`（SQLAlchemy 2.x JSON 类型自动反序列化），router 端直接返回 dict 结构无需特殊处理。
2. **PUT /roles/{id}/permissions 需禁止修改系统内置角色（如 admin）** → 规避：RoleService 在 `update_role_permissions` 内检查 `role.is_system == False`，否则抛出 `ForbiddenException("Cannot modify system role")`。
3. **POST /users/{id}/role 需要验证 target user 属于同一租户** → 规避：Service 层额外查询 `UserModel.tenant_id` 与当前 `ctx.tenant_id` 比对，不一致则 `ForbiddenException("Cannot assign role to user in different tenant")`。
4. **单元测试 mock RoleService 时，MockState 不含 role 相关 handler** → 规避：在 `tests/unit/conftest.py` 新增 `make_role_handler(state)`（参考 `make_customer_handler` 实现模式），返回 role 相关的 INSERT/SELECT 行为。

---

## 5. 实现步骤（按顺序）

### Step 1: 添加 unit test mock handler for RoleModel

在 `tests/unit/conftest.py` 新增 `make_role_handler(state)` 和 `make_user_role_handler(state)` 两个 mock handler，参考已有 `make_customer_handler` 的实现模式：每次 INSERT 自增 `state._last_role_id`，SELECT 支持 `tenant_id` 过滤，`UPDATE` 更新 `permissions` JSONB 字段。

操作：
- a) 在 `tests/unit/conftest.py` 末尾添加 `make_role_handler` 和 `make_user_role_handler` 函数（参考同类 handler 实现，约 40 行）。
- b) 导出两个函数：`__all__ += ["make_role_handler", "make_user_role_handler"]`

```python
# tests/unit/conftest.py（新增 handler 片段示例）
def make_role_handler(state):
    async def handle(call):
        stmt = call.args[0]
        if str(stmt).startswith("SELECT"):
            tenant_id = call.kwargs.get("tenant_id")
            return [r for r in state.roles if r.tenant_id == tenant_id]
        elif str(stmt).startswith("INSERT"):
            role = RoleModel(id=state._last_role_id + 1, **call.kwargs)
            state.roles.append(role)
            state._last_role_id += 1
            return role
    return handle
```

**完成判定**：`ruff check tests/unit/conftest.py` → exit 0

---

### Step 2: 实现 RoleService

创建 `src/services/role_service.py`，实现 6 个方法：

- `list_roles(tenant_id)` → `SELECT * FROM roles WHERE tenant_id = :tenant_id`
- `create_role(tenant_id, name, permissions)` → INSERT，权限列表存 JSONB；`ValidationException` 当 name 已存在
- `get_role_permissions(role_id, tenant_id)` → SELECT permissions JSONB 列；`NotFoundException` 当 role 不存在或不属于该租户
- `update_role_permissions(role_id, tenant_id, permissions)` → UPDATE permissions；`ForbiddenException` 当 role.is_system == True
- `assign_role_to_user(user_id, role_id, tenant_id)` → INSERT user_roles 表；先验证 user 属于同一租户；`NotFoundException` 当 user 或 role 不存在
- `list_all_permissions()` → 返回硬编码枚举列表 `[{resource, action}, ...]`

```python
# src/services/role_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from db.models.role import RoleModel       # TBD: 确认 #641 模型路径
from db.models.user_role import UserRoleModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException, ForbiddenException

# 硬编码权限枚举（系统支持的全部 resource:action 组合）
PERMISSION_CATALOG: list[dict[str, str]] = [
    {"resource": "customer", "action": "read"},
    {"resource": "customer", "action": "write"},
    {"resource": "opportunity", "action": "read"},
    {"resource": "opportunity", "action": "write"},
    {"resource": "role", "action": "assign"},
    {"resource": "role", "action": "read"},
]

class RoleService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_roles(self, tenant_id: int) -> list[RoleModel]:
        result = await self.session.execute(
            select(RoleModel).where(RoleModel.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def create_role(
        self, tenant_id: int, name: str, permissions: list[str]
    ) -> RoleModel:
        existing = await self.session.execute(
            select(RoleModel).where(
                RoleModel.tenant_id == tenant_id, RoleModel.name == name
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"Role '{name}' already exists in this tenant")
        role = RoleModel(tenant_id=tenant_id, name=name, permissions=permissions)
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_role_permissions(self, role_id: int, tenant_id: int) -> list[str]:
        result = await self.session.execute(
            select(RoleModel).where(
                RoleModel.id == role_id, RoleModel.tenant_id == tenant_id
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundException("Role")
        return role.permissions or []

    async def update_role_permissions(
        self, role_id: int, tenant_id: int, permissions: list[str]
    ) -> RoleModel:
        role = await self.session.execute(
            select(RoleModel).where(
                RoleModel.id == role_id, RoleModel.tenant_id == tenant_id
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundException("Role")
        if getattr(role, "is_system", False):
            raise ForbiddenException("Cannot modify system role")
        role.permissions = permissions
        await self.session.flush()
        return role

    async def assign_role_to_user(
        self, user_id: int, role_id: int, tenant_id: int
    ) -> None:
        user_result = await self.session.execute(
            select(UserModel).where(
                UserModel.id == user_id, UserModel.tenant_id == tenant_id
            )
        )
        if not user_result.scalar_one_or_none():
            raise NotFoundException("User")
        role_result = await self.session.execute(
            select(RoleModel).where(
                RoleModel.id == role_id, RoleModel.tenant_id == tenant_id
            )
        )
        if not role_result.scalar_one_or_none():
            raise NotFoundException("Role")
        await self.session.execute(
            insert(UserRoleModel).values(user_id=user_id, role_id=role_id)
        )
        await self.session.flush()

    async def list_all_permissions(self) -> list[dict[str, str]]:
        return PERMISSION_CATALOG
```

**完成判定**：`ruff check src/services/role_service.py` → exit 0

---

### Step 3: 实现 RBAC router

创建 `src/api/routers/rbac.py`，实现 6 个端点。所有端点注入 `ctx: AuthContext = Depends(require_auth)`。admin+ 端点（POST /roles、PUT /roles/{id}/permissions、POST /users/{id}/role）在路由层加 `require_permission` 检查或手动 raise `ForbiddenException`。

```python
# src/api/routers/rbac.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.role_service import RoleService

router = APIRouter(prefix="/rbac", tags=["RBAC"])

class CreateRoleRequest(BaseModel):
    name: str
    permissions: list[str]

class UpdatePermissionsRequest(BaseModel):
    permissions: list[str]

class AssignRoleRequest(BaseModel):
    role_id: int

@router.get("/roles")
async def list_roles(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    roles = await svc.list_roles(tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"items": [r.to_dict() for r in roles], "total": len(roles)}}

@router.post("/roles")
async def create_role(
    body: CreateRoleRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    role = await svc.create_role(tenant_id=ctx.tenant_id, name=body.name, permissions=body.permissions)
    return {"success": True, "data": role.to_dict()}

@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    perms = await svc.get_role_permissions(role_id=role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"role_id": role_id, "permissions": perms}}

@router.put("/roles/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    body: UpdatePermissionsRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    role = await svc.update_role_permissions(role_id=role_id, tenant_id=ctx.tenant_id, permissions=body.permissions)
    return {"success": True, "data": role.to_dict()}

@router.post("/users/{user_id}/role")
async def assign_role_to_user(
    user_id: int,
    body: AssignRoleRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    await svc.assign_role_to_user(user_id=user_id, role_id=body.role_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"user_id": user_id, "role_id": body.role_id}}

@router.get("/permissions")
async def list_permissions(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RoleService(session)
    perms = await svc.list_all_permissions()
    return {"success": True, "data": perms}
```

**完成判定**：`ruff check src/api/routers/rbac.py` → exit 0

---

### Step 4: 注册 RBAC router

在 `src/api/routers/__init__.py` 添加：

```python
from src.api.routers import rbac

app_router.include_router(rbac.router, prefix="/rbac", tags=["RBAC"])
```

**完成判定**：`ruff check src/api/routers/__init__.py` → exit 0

---

### Step 5: 编写 RoleService 单元测试

在 `tests/unit/test_role_service.py` 编写：

- `test_list_roles_returns_only_tenant_roles`：验证租户隔离，跨租户角色不出现在结果中。
- `test_create_role_raises_conflict_on_duplicate_name`：同一租户重名角色抛出 `ConflictException`。
- `test_update_role_permissions_blocks_system_role`：对 `is_system=True` 角色调用 `update_role_permissions` 抛出 `ForbiddenException`。
- `test_assign_role_to_user_checks_user_tenant`：对不同租户用户分配角色抛出 `ForbiddenException`（先补完租户检查逻辑）。
- `test_get_role_permissions_returns_jsonb_list`：验证 JSONB 字段正确反序列化。
- `test_list_all_permissions_returns_catalog`：验证返回非空固定枚举列表。

每个测试使用 `make_mock_session([make_role_handler(state), make_user_role_handler(state)])` 构建 mock session。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → 6 passed

---

### Step 6: 编写 RBAC 集成测试

在 `tests/integration/test_rbac_integration.py` 编写（使用 `db_schema`、`tenant_id`、`async_session` fixtures）：

- `test_create_and_list_role`：POST 后 GET，验证返回的角色包含正确 permissions。
- `test_update_role_permissions`：修改后 GET，验证 permissions 已更新。
- `test_assign_role_to_user`：POST assign 后查询 `user_roles` 表验证绑定。
- `test_get_permissions_returns_all_pairs`：GET /permissions 验证返回至少 6 个 `{resource, action}` 元组。
- `test_list_roles_enforces_tenant_isolation`：创建两个租户的角色，GET 各自列表验证互不可见。
- `test_update_system_role_forbidden`：创建 `is_system=True` 角色，PUT 返回 403。

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → 6 passed

---

## 6. 验收

- [ ] `ruff check src/services/role_service.py src/api/routers/rbac.py src/api/routers/__init__.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → 6 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → 6 passed
- [ ] `PYTHONPATH=src mypy src/services/role_service.py src/api/routers/rbac.py` → 0 errors（如 mypy 配置存在）
- [ ] 端到端：启动服务后 `curl http://localhost:8000/rbac/permissions` 返回 `{"success": true, "data": [...]}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #641 Role/Permission ORM 模型未就绪导致编译失败 | 低 | 高（阻塞所有端点） | 暂停本 issue，等待 #641 合入；#641 合入后重新生成 model import |
| admin+ 权限校验被绕过（装饰器实现有漏洞） | 中 | 高 | 在 RoleService 层加二次校验：`if not is_admin(ctx): raise ForbiddenException`；在 assign_role_to_user 中已有租户检查兜底 |
| JSONB permissions 字段在非 PostgreSQL 测试环境下行为不一致 | 低 | 中 | 单元测试用 mock handler 绕开真实 DB；集成测试强制要求 DATABASE_URL 为 PostgreSQL |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/role_service.py src/api/routers/rbac.py src/api/routers/__init__.py tests/unit/test_role_service.py tests/integration/test_rbac_integration.py
git commit -m "feat(rbac): add role and permission management API endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(rbac): add role and permission management API endpoints" --body "Closes #642"
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — Service 层返回 ORM + raise AppException 模式参考
- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — router 层返回 `{"success": true, "data": ...}` envelope 模式参考
- 父 issue / 关联：#38（父 epic）、#641（依赖：Role/Permission ORM 模型）、#688（依赖本板块提供权限判断基础能力）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
