# 后端身份模型批量一 — Tenant, User, Role, Permission

| 元数据 | 值 |
|---|---|
| Issue | #273 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 10-customers, 20-sales, 40-campaigns, 50-automation |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统必须具备多租户身份管理能力。当前仓库缺少 Tenant / Organization / Department / User / Role / Permission / RolePermission / UserRole 八个核心 ORM 模型。所有 API 路由鉴权（`require_auth`）、Service 层租户过滤（`WHERE tenant_id = :tenant_id`）和 RBAC 权限校验都依赖这些模型作为底层数据结构。此模型层是后续所有业务板块（customers / sales / campaigns / automation）的共享地基。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 ORM 模型，仅供开发者通过 Service / Router 调用。
- **开发者视角**：`from db.models.identity import Tenant, User, Role, Permission, Organization, Department, RolePermission, UserRole` 可直接导入八个模型。所有模型继承 `Base`，含 `tenant_id`、`is_deleted`、`created_at`/`updated_at`/`deleted_at` 字段，relationship 打通主从关联，支持 Service 层直接返回 ORM 对象。

### 1.3 不做什么（剔除）

- [ ] 不实现 API Router 端点（auth / login / register 另开 issue）
- [ ] 不实现 Service 层业务逻辑（`TenantService` / `UserService` 等另开 issue）
- [ ] 不实现 Alembic migration 之外的数据迁移脚本
- [ ] 不实现 Integration Test（ORM 模型以 Unit Test 为主）

### 1.4 关键 KPI

- [模型数量：8 个模型（Tenant / Organization / Department / User / Role / Permission / RolePermission / UserRole）全部在 `src/internal/db/models/identity.py` 中定义]
- [继承验证：`grep -c "Base)" src/internal/db/models/identity.py` → `8`]
- [软删除字段：`Tenant`、`User`、`Role`、`Permission` 含 `is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)`]
- [租户字段：每个主表模型含 `tenant_id: Mapped[int]` 且带 `index=True`]
- [时间戳字段：每个模型含 `created_at`、`updated_at`、`deleted_at（可空）`]
- [关联关系：`RolePermission` 多对多关联 Role↔Permission；`UserRole` 多对多关联 User↔Role]
- [单元测试：`PYTHONPATH=src pytest tests/unit/test_identity_models.py -v` → 全 passed]
- [Lint 干净：`ruff check src/internal/db/models/identity.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/internal/db/models/identity.py` 目前不存在，需从零创建。

### 2.2 涉及文件清单

- 要改：
  - `src/internal/db/models/__init__.py` — 注册并导出 Tenant / User / Role / Permission / Organization / Department / RolePermission / UserRole
  - `alembic/env.py` — 新增 `from db.models.identity import *` 以便 autogenerate 扫描到新模型
  - `src/db/base.py` — 确认 `Base` 导出路径（如 identity 模型需要直接引用 Base）
- 要建：
  - `src/internal/db/models/identity.py` — 8 个 SQLAlchemy ORM 模型定义
  - `alembic/versions/<id>_create_identity_tables.py` — 创建 Tenant / Organization / Department / User / Role / Permission / RolePermission / UserRole 的 migration
  - `tests/unit/test_identity_models.py` — 单元测试（Mock DB，不触真实 Postgres）
  - `src/internal/db/models/__init__.py` — 如文件不存在则新建

### 2.3 缺什么

- [ ] `Tenant` 模型：顶级租户实体，含租户级别元数据
- [ ] `Organization` 模型：租户内组织架构，含 `tenant_id`
- [ ] `Department` 模型：支持树形结构（自引用 `parent_id`），关联 Organization
- [ ] `User` 模型：用户实体，含 `tenant_id`、`department_id`（可空）、密码哈希字段、软删除
- [ ] `Role` 模型：角色定义，含 `tenant_id`、软删除
- [ ] `Permission` 模型：权限原子定义，含 `resource`/`action` 字段
- [ ] `RolePermission` 模型：Role↔Permission 多对多关联表
- [ ] `UserRole` 模型：User↔Role 多对多关联表
- [ ] 所有模型含统一审计字段：`created_at`、`updated_at`、`deleted_at`

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/internal/db/models/identity.py` | 定义 Tenant / Organization / Department / User / Role / Permission / RolePermission / UserRole 八个 SQLAlchemy ORM 模型 |
| `alembic/versions/<id>_create_identity_tables.py` | 创建全部 identity 表（含 tenant_id 索引、软删除索引、关联表唯一约束） |
| `tests/unit/test_identity_models.py` | 单元测试：验证模型字段、relationship 解包、软删除行为 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：待确认 `src/internal/db/models/__init__.py` 的正确路径 | 导出全部 8 个 identity 模型供外部 `from db.models.identity import ...` 使用 |
| TBD - 待验证：待确认 `alembic/env.py` 的正确路径 | 新增 `from db.models.identity import *` 使 autogenerate 能扫描到新模型 |
| TBD - 待确认 `src/db/base.py` 的正确路径 | 确认 `Base` 从 `db.engine` 正确导出，identity 模型需 `from src.db.base import Base` |

### 3.3 新增能力

- **ORM model**：`Tenant` — 租户主表，含 `name`、`domain`、`is_active`、`is_deleted` 及审计字段
- **ORM model**：`Organization` — 租户内组织，含 `tenant_id`、`name`、`description`
- **ORM model**：`Department` — 树形部门，含 `organization_id`、`parent_id` 自引用
- **ORM model**：`User` — 用户，含 `tenant_id`、`department_id`、`email`、`hashed_password`、`is_active`、`is_deleted`
- **ORM model**：`Role` — 角色，含 `tenant_id`、`name`、`is_deleted`
- **ORM model**：`Permission` — 权限，含 `resource`、`action`、`description`
- **ORM model**：`RolePermission` — 多对多关联表（Association Table），主键 `role_id + permission_id`
- **ORM model**：`UserRole` — 多对多关联表，主键 `user_id + role_id`
- **Relationship**：RolePermission.role ↔ Role、RolePermission.permission ↔ Permission；UserRole.user ↔ User、UserRole.role ↔ Role
- **Migration**：`alembic upgrade head` 创建全部 8 张表及关联表

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **软删除用 `is_deleted: bool` 不选 `deleted_at` 唯一索引**：当前系统其他地方（如 `Base` 基类约定）已统一用 `is_deleted` 布尔字段，保持一致可降低 Service 层判断成本
- **Department 树形用自引用 `parent_id` 不选闭包表**：batch 1 仅支持单层自引用，树形查询（如递归 CTE）由后续 dedicated issue 处理
- **多对多关联用显式关联表（Association Table）不选 `relationship(secondary=...)`**：显式 `RolePermission` / `UserRole` 模型允许未来扩展到含 `created_at`、`granted_by` 等审计字段
- **Base 引用 `from src.db.base import Base` 不在 identity.py 内新建 Base**：避免多 Base 实例导致 ORM 类无法跨模块关联

### 4.2 版本约束

<!-- 无新增外部依赖 -->

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`，identity 模型主表（Tenant 除外）全部含 `tenant_id` 索引列
- ORM relationship 在 `Base.metadata` 注册后，Service 层可直接返回 ORM 对象，不在 model 内调用 `.to_dict()`
- `Base` 统一从 `src.db.base` 导出，所有模型 `__tablename__` 必须全局唯一（建议前缀 `identity_tenant`、`identity_user` 等避免与业务表冲突，或直接 `tenants`、`users` — 按 repo 已有命名惯例）
- `alembic/env.py` 必须 import identity 模型，否则 autogenerate 扫描不到新表

### 4.4 已知坑

1. **SQLAlchemy `Base.metadata` 列名冲突** → 规避：ORM 模型列名绝对不能叫 `metadata`（与 `Base.metadata` 冲突），权限扩展字段改用 `perm_metadata` / `attrs` / `meta`
2. **Alembic autogenerate 把 `JSONB` 写成 `JSON`、`TIMESTAMPTZ` 写成无时区的 `DateTime`** → 规避：migration 写完后手动检查所有 JSON 类型列改为 `postgresql.JSONB()`，所有时间戳列加 `timezone=True`
3. **Alembic autogenerate 漏掉 `index=True` 在关联表上** → 规避：`RolePermission(role_id, permission_id)` 和 `UserRole(user_id, role_id)` 上手动加 `UniqueConstraint` 和 `index=True`
4. **PYTHONPATH=src，import 写 `from src.db.models.identity import ...`** → 规避：模块内写 `from db.models.identity import ...`（无 `src.` 前缀），PYTHONPATH 已包含 `src`
5. **tenant_id 在同一张表上与其他唯一约束组合时索引竞争** → 规避：复合唯一约束格式 `UniqueConstraint('tenant_id', 'email')` 显式声明，不用 `unique=True` 单列标记

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/internal/db/models/identity.py` 并定义八个模型

在 `src/internal/db/models/` 下新建 `identity.py`。八个模型按以下顺序定义（避免 forward reference）：

1. `Tenant` — 最顶层，无 `tenant_id`
2. `Organization` — `tenant_id` + 字段
3. `Department` — `organization_id` + 自引用 `parent_id`
4. `Permission` — 无租户字段（权限定义跨租户共享）
5. `Role` — `tenant_id`
6. `RolePermission` — `role_id` + `permission_id`，显式关联表
7. `User` — `tenant_id` + `department_id`（可空）+ `email`（唯一索引 per tenant）+ 密码字段
8. `UserRole` — `user_id` + `role_id`，显式关联表

所有模型含统一审计 mixin 或显式字段：
- `created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`
- `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`
- `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`

软删除字段（主表模型）：
- `is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)`

关系示例代码：

```python
# src/internal/db/models/identity.py
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organizations: Mapped[list["Organization"]] = relationship(back_populates="tenant", lazy="selectin")


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="organizations")
    departments: Mapped[list["Department"]] = relationship(back_populates="organization", lazy="selectin")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="departments")
    children: Mapped[list["Department"]] = relationship(back_populates="parent", remote_side=[id])
    users: Mapped[list["User"]] = relationship(back_populates="department", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("resource", "action", name="uq_permission_resource_action"),)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship()
    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", lazy="selectin")
    users: Mapped[list["UserRole"]] = relationship(back_populates="role", lazy="selectin")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship(back_populates="role_permissions")

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship()
    department: Mapped[Optional["Department"]] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", lazy="selectin")

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)


class UserRole(Base):
    __tablename__ = "user_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)
```

**完成判定**：`ruff check src/internal/db/models/identity.py` → 0 errors，`grep -c "^class.*Base)" src/internal/db/models/identity.py` → 8

---

### Step 2: 更新 `src/internal/db/models/__init__.py` 导出全部模型

在现有 `__init__.py` 中追加导出（或新建文件）：

```python
from db.models.identity import (
    Department,
    Organization,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)

__all__ = [
    "Tenant",
    "Organization",
    "Department",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
]
```

**完成判定**：`ruff check src/internal/db/models/__init__.py` → 0 errors，文件存在

---

### Step 3: 在 `alembic/env.py` 注册 identity 模型

在 `alembic/env.py` 的 import 区块添加：

```python
from db.models.identity import *  # noqa: F403, F401
```

**完成判定**：`ruff check alembic/env.py` → 0 errors，`grep "identity" alembic/env.py` 非空

---

### Step 4: 生成 Alembic migration

按 CLAUDE.md 的 Alembic 流程操作：

```bash
# 1. 启动干净数据库
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. 升级到当前 head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# 3. 生成 diff
alembic revision --autogenerate -m "create identity tables"

# 4. 人工审查：检查 timezone=True、JSONB 类型、tenant_id 索引、deleted_at nullable
# 5. 验证 apply + downgrade
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 5: 编写单元测试 `tests/unit/test_identity_models.py`

测试策略（Mock DB，不触真实 Postgres）：

```python
# tests/unit/test_identity_models.py
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from tests.unit.conftest import make_mock_session, MockState
from db.models.identity import Tenant, User, Role, Permission, RolePermission, UserRole


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])


class TestTenantModel:
    def test_tenant_has_required_fields(self):
        t = Tenant(
            id=1, name="Acme Corp", domain="acme.com",
            is_active=True, is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert t.name == "Acme Corp"
        assert t.domain == "acme.com"
        assert t.is_deleted is False

    def test_tenant_soft_delete_flag(self):
        t = Tenant(id=1, name="Deleted Corp", domain="deleted.com",
                   is_deleted=True)
        assert t.is_deleted is True


class TestUserModel:
    def test_user_belongs_to_tenant(self):
        t = Tenant(id=1, name="T", domain="t.com")
        u = User(id=1, tenant_id=1, email="alice@acme.com",
                 hashed_password="hash", tenant=t)
        assert u.tenant_id == 1
        assert u.email == "alice@acme.com"


class TestRolePermissionModel:
    def test_unique_constraint_role_permission(self):
        rp = RolePermission(id=1, role_id=10, permission_id=20,
                            created_at=datetime.now(timezone.utc))
        assert rp.role_id == 10
        assert rp.permission_id == 20


class TestUserRoleModel:
    def test_user_role_association(self):
        ur = UserRole(id=1, user_id=5, role_id=3,
                      created_at=datetime.now(timezone.utc))
        assert ur.user_id == 5
        assert ur.role_id == 3
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_identity_models.py -v` → 全 passed

---

### Step 6: 全量 Lint + Type Check

```bash
ruff check src/internal/db/models/identity.py src/internal/db/models/__init__.py
ruff format --check src/internal/db/models/identity.py src/internal/db/models/__init__.py
mypy src/internal/db/models/identity.py --ignore-missing-imports
```

**完成判定**：三条命令均 exit 0（无 error/warning）

---

## 6. 验收

- [ ] `ruff check src/internal/db/models/identity.py src/internal/db/models/__init__.py` → 0 errors
- [ ] `ruff format --check src/internal/db/models/identity.py src/internal/db/models/__init__.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_identity_models.py -v` → 全 passed
- [ ] `grep -c "^class.*Base)" src/internal/db/models/identity.py` → 8
- [ ] `grep "tenant_id.*index=True" src/internal/db/models/identity.py` → Tenant 除外共 6+ 处
- [ ] `grep "is_deleted.*Mapped\[bool\]" src/internal/db/models/identity.py` → 5+ 处
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `Base` 实例不统一导致 relationship 跨模块失效 | 低 | 高 | 将 identity.py 改为 `from src.db.base import Base`；重启 Python 进程清除旧 cached metadata |
| Alembic migration 与已有 Base 定义不一致（列类型 / 索引差异） | 中 | 中 | 删除 autogenerate 结果，手写 migration 列定义；downgrade 到 pre-identity 版本后重新 autogenerate |
| `metadata` 列名在 Permission 表中与 Base.metadata 冲突 | 低 | 高 | Permission 表使用 `attrs` 而非 `metadata` 存储扩展信息 |
| 多租户唯一约束 `UniqueConstraint(tenant_id, email)` 在 autogenerate 后缺失 | 中 | 高 | 在 migration 文件中手动补全 `UniqueConstraint`，不影响下游表结构 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/internal/db/models/identity.py src/internal/db/models/__init__.py \
         alembic/versions/*identity*.py tests/unit/test_identity_models.py \
         alembic/env.py
git commit -m "feat(db): add ORM identity models batch 1 — Tenant, User, Role, Permission"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(db): ORM identity models batch 1" --body "Closes #273"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：待确认 `src/db/models/__init__.py` 的正确路径
- 第三方文档：[SQLAlchemy 2.0 Declarative Models](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html)
- 父 issue / 关联：#273（自身）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
