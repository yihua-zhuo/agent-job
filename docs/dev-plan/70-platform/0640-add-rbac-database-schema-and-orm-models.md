# RBAC 数据库Schema与ORM模型 · 新建RBAC三层表及迁移

| 元数据 | 值 |
|---|---|
| Issue | #640 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：依赖本板块的下游功能（如角色管理API、权限检查中间件等） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前仓库已有 [`src/db/models/rbac.py`](../../src/db/models/rbac.py) 中定义的 ORM 模型类和 `RBACService`，但数据库中尚无对应的物理表。`roles`、`permissions`、`user_roles` 三层表不存在，导致基于数据库的角色-权限赋权和查询无法工作，所有权限判断均依赖代码中硬编码的 `DEFAULT_ROLES` / `DEFAULT_PERMISSIONS` 枚举，而非持久化数据。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 及 ORM 模型。
- **开发者视角**：`RoleModel`、`PermissionModel`、`RolePermissionModel`、`UserRoleModel` 四个 ORM 模型对应数据库表已创建；可通过 Alembic 迁移脚本管理表结构版本；后续 `RBACService` 可改造为真实数据库查询而非内存枚举。

### 1.3 不做什么（剔除）

- [ ] `RBACService` 改造为数据库查询（本板块仅建 schema 和 seed；Service 改造由后续板块完成）
- [ ] 角色管理 API Router（本板块仅建表 + seed）
- [ ] 前端权限 UI

### 1.4 关键 KPI

- `alembic upgrade head` exit 0，生成 `roles`/`permissions`/`role_permissions`/`user_roles` 四张表
- `alembic downgrade -1` exit 0，四张表被正确删除
- `alembic revision --autogenerate -m drift_check` 产生空迁移（pass 两处）
- `ruff check src/db/models/rbac.py` exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

入口文件：[`src/db/models/rbac.py`](../../src/db/models/rbac.py) L{1}-L{30}

```python
1:  """RBAC ORM models — roles, permissions, user role assignments."""
2:  from datetime import datetime
3:  from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
4:  from sqlalchemy.orm import Mapped, mapped_column, relationship
5:  from db.base import Base
6:
7:  class RoleModel(Base):
8:      __tablename__ = "roles"
9:      __table_args__ = (Index("ix_roles_tenant_name", "tenant_id", "name", unique=True),)
10:     id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
11:     tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=0)
12:     name: Mapped[str] = mapped_column(String(50), nullable=False)
13:     display_name: Mapped[str] = mapped_column(String(100), nullable=False)
14:     description: Mapped[str] = mapped_column(Text, nullable=True)
15:     is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
16:     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

当前 `RBACService` ([`src/services/rbac_service.py`](../../src/services/rbac_service.py) L{1}-L{16}) 使用内存中的 `DEFAULT_ROLES` 列表提供权限判断，尚无数据库持久化依赖。

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../alembic/env.py) — 无需改动，`import db.models` 通过 `pkgutil` 自动发现 `rbac.py` 中的模型
- 要建：
  - `alembic/versions/<new_id>_add_rbac_tables.py` — 创建 roles / permissions / role_permissions / user_roles 四张表并 seed 数据

### 2.3 缺什么

- [ ] 数据库中无 `roles`、`permissions`、`role_permissions`、`user_roles` 物理表，`Base.metadata` 与数据库不同步
- [ ] `RBACService` 无法查询数据库权限，权限数据在服务启动时由内存枚举决定
- [ ] 无 Alembic 迁移记录此 schema 变更

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_rbac_tables.py` | 创建四张 RBAC 表并 seed 预定义角色和权限 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/rbac.py`](../../src/db/models/rbac.py) | 无需修改 — ORM 模型已存在且与迁移 schema 一致 |
| [`alembic/env.py`](../../alembic/env.py) | 无需修改 — `import db.models` 已通过 pkgutil 自动发现所有模型 |

### 3.3 新增能力

- **ORM model**：`RoleModel` in `src/db/models/rbac.py`（已存在，对应 `roles` 表）
- **ORM model**：`PermissionModel` in `src/db/models/rbac.py`（已存在，对应 `permissions` 表）
- **ORM model**：`RolePermissionModel` in `src/db/models/rbac.py`（已存在，对应 `role_permissions` 表）
- **ORM model**：`UserRoleModel` in `src/db/models/rbac.py`（已存在，对应 `user_roles` 表）
- **Migration**：`alembic upgrade head` 创建 `roles` / `permissions` / `role_permissions` / `user_roles` 四张表，并 seed 5 个预定义角色（owner, admin, manager, member, viewer）和所有 permission 行

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `role_permissions` 多对多junction表而非在 `roles` 表直接存 JSONB 权限列表**：便于细粒度管理单个权限的授予/撤销，且与现有 ORM 模型 `RolePermissionModel` 结构一致
- **选 seed 数据直接写在 `upgrade()` 而非单独 SQL 文件**：符合本仓库 Alembic 迁移惯例（参见 `alembic/versions/9d8e7f6a5b3c_add_auth_tables.py` 的做法），避免额外文件

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：`user_roles` 每条记录必须含 `tenant_id`，所有索引包含 `tenant_id`
- `roles.tenant_id = 0` 保留给系统预定义角色；自定义角色由具体 tenant_id 区分
- `alembic/env.py` 中 `import db.models` 通过 `pkgutil.iter_modules` 自动发现 `rbac.py`，无需显式 import

### 4.4 已知坑

1. **Alembic autogen 把 `TIMESTAMPTZ` 写成 `DateTime`，把 `JSONB` 写成 `JSON`** → 规避：手写 migration 时明确使用 `sa.DateTime(timezone=True)` 和 `postgresql.JSONB`
2. **`Base.metadata` 与数据库实际 schema 不同步（无迁移记录）** → 规避：首次迁移基于最新 head (`c94d682d4b03`)，`down_revision` 指向它；执行 `alembic upgrade head` 前确认当前 head

---

## 5. 实现步骤（按顺序）

### Step 1: 确认当前 Alembic head

确认最新迁移文件及 revision ID，作为新迁移的 `down_revision`。

操作：
- 在 `alembic/versions/` 目录执行：`ls -t *.py | head -1` 获取时间戳最新的迁移文件

**完成判定**：`grep "^revision = " alembic/versions/c94d682d4b03_add_ai_conversations.py` 输出 `revision: str = 'c94d682d4b03'`

---

### Step 2: 编写 alembic migration 文件

在 `alembic/versions/` 下新建 `XXXXXXXXXXXX_add_rbac_tables.py`（XXXX 为 12 位十六进制 hash，参考仓库现有命名风格如 `9d8e7f6a5b3c`）。

`down_revision = 'c94d682d4b03'`，`upgrade()` 依次创建：

```python
# 1. roles
op.create_table("roles",
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
    sa.Column("tenant_id", sa.Integer(), nullable=False),
    sa.Column("name", sa.String(length=50), nullable=False),
    sa.Column("display_name", sa.String(length=100), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)
op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
op.create_index("ix_roles_tenant_name", "roles", ["tenant_id", "name"], unique=True)

# 2. permissions
op.create_table("permissions",
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
    sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    sa.Column("display_name", sa.String(length=255), nullable=False),
    sa.Column("category", sa.String(length=50), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)
op.create_index("ix_permissions_name", "permissions", ["name"], unique=True)

# 3. role_permissions (junction)
op.create_table("role_permissions",
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
    sa.Column("role_id", sa.Integer(), nullable=False),
    sa.Column("permission_id", sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
)
op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])
op.create_unique_constraint("uq_role_permission", "role_permissions", ["role_id", "permission_id"])

# 4. user_roles
op.create_table("user_roles",
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("role_id", sa.Integer(), nullable=False),
    sa.Column("tenant_id", sa.Integer(), nullable=False),
    sa.Column("granted_by", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
)
op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
op.create_index("ix_user_roles_tenant_id", "user_roles", ["tenant_id"])
op.create_index("ix_user_roles_user_tenant_role", "user_roles", ["user_id", "tenant_id", "role_id"], unique=True)

# 5. Seed roles (tenant_id=0 = system)
op.execute("""
    INSERT INTO roles (tenant_id, name, display_name, description, is_system, priority, created_at)
    VALUES
        (0, 'owner',  'Owner',  'Full access including billing and user management', true,  100, now()),
        (0, 'admin',  'Admin',  'Full access to all resources',                    true,   90, now()),
        (0, 'manager','Manager','Manage team members and view reports',              true,   70, now()),
        (0, 'member', 'Member', 'Standard read/write access to assigned resources',  true,   50, now()),
        (0, 'viewer', 'Viewer', 'Read-only access',                                 true,   30, now());
""")

# 6. Seed permissions (representing granular resource:action pairs)
op.execute("""
    INSERT INTO permissions (name, display_name, category, description, created_at) VALUES
        ('users:read',    'View Users',    'users',    'Read user profiles and list',     now()),
        ('users:write',   'Manage Users', 'users',    'Create and update users',         now()),
        ('users:delete',  'Delete Users', 'users',    'Remove users',                   now()),
        ('customers:read',    'View Customers',    'customers',    'Read customer records',    now()),
        ('customers:write',   'Manage Customers',   'customers',    'Create/update customers',  now()),
        ('customers:delete',  'Delete Customers',    'customers',    'Remove customer records',  now()),
        ('opportunities:read',  'View Opportunities',  'opportunities',  'Read opportunity records', now()),
        ('opportunities:write', 'Manage Opportunities', 'opportunities', 'Create/update opportunities',now()),
        ('opportunities:delete','Delete Opportunities', 'opportunities', 'Remove opportunities',        now()),
        ('tickets:read',  'View Tickets',  'tickets',  'Read support tickets',    now()),
        ('tickets:write', 'Manage Tickets', 'tickets', 'Reply and update tickets', now()),
        ('tickets:delete','Delete Tickets', 'tickets', 'Close/delete tickets',    now()),
        ('billing:read',  'View Billing',  'billing',  'Read billing information', now()),
        ('billing:write', 'Manage Billing', 'billing', 'Update billing and plans', now()),
        ('settings:read', 'View Settings', 'settings', 'Read system settings',    now()),
        ('settings:write','Manage Settings', 'settings','Update system settings',   now()),
        ('roles:read',    'View Roles',    'roles',    'List roles and permissions', now()),
        ('roles:write',   'Manage Roles',   'roles',    'Create/update roles',        now()),
        ('roles:delete',  'Delete Roles',   'roles',   'Remove custom roles',        now()),
        ('reports:read',  'View Reports',   'reports',  'Access analytics reports',  now()),
        ('reports:export','Export Reports', 'reports', 'Export report data',         now());
""")

# 7. Seed role_permissions: owner/admin get all, manager gets most, member gets customer/opportunity/ticket read+write, viewer gets read-only
op.execute("""
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'owner';
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'admin';
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE r.name = 'manager'
      AND p.name NOT IN ('users:delete','billing:write','settings:write','roles:write','roles:delete');
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE r.name = 'member'
      AND p.name LIKE '%:read' OR p.name IN ('customers:write','opportunities:write','tickets:write');
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE r.name = 'viewer'
      AND p.name LIKE '%:read' AND p.name NOT IN ('billing:read','settings:read');
""")
```

`downgrade()` 依次 drop 所有表（先删有外键依赖的表）：

```python
op.drop_table("user_roles")
op.drop_table("role_permissions")
op.drop_table("permissions")
op.drop_table("roles")
```

**完成判定**：`wc -l alembic/versions/*_add_rbac_tables.py` 文件存在且行数 > 60

---

### Step 3: 执行迁移验证

```bash
# 1. 启动测试数据库
docker compose -f configs/docker-compose.test.yml up -d test-db

# 2. 确保 alembic_dev 数据库干净且在 head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

预期输出：`Migrating 1 migration(s) ... done`

```bash
# 3. 验证 downgrade 可逆
alembic downgrade -1
alembic upgrade head
```

预期：三次均 exit 0。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次均 exit 0

---

### Step 4: Drift check

```bash
alembic revision --autogenerate -m drift_check
```

**完成判定**：`grep -c "pass" alembic/versions/*_drift_check.py` 输出 2（即 `upgrade() → pass`，`downgrade() → pass`，无真实变更）

---

### Step 5: Lint 检查

```bash
ruff check src/db/models/rbac.py
```

**完成判定**：exit 0（无输出）

---

## 6. 验收

- [ ] `ruff check src/db/models/rbac.py` → 0 errors
- [ ] `alembic upgrade head` → exit 0 且输出 `done`
- [ ] `alembic downgrade -1` → exit 0，四张表（roles, permissions, role_permissions, user_roles）已删除
- [ ] `alembic upgrade head` → exit 0（再次升级成功）
- [ ] `alembic revision --autogenerate -m drift_check` → 生成的 migration 中 upgrade/downgrade 两处均为 `pass`，无 drift

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| migration 文件 revision hash 与现有 head 冲突（多人并发写） | 低 | 高 | 重新生成 migration，调整 `down_revision` 指向实际当前 head |
| seed 数据 INSERT 失败（如 unique constraint 冲突） | 低 | 中 | `downgrade` 删表后清理数据，重新 `upgrade` |
| Junction表 `role_permissions` 在 downgrade 时因FK级联顺序不对报错 | 低 | 中 | `downgrade()` 中显式按 `role_permissions` → `user_roles` → `permissions` → `roles` 顺序 drop |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add alembic/versions/
git commit -m "feat(platform): add RBAC database schema and seed data for #640"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#640): add RBAC database schema and ORM models" --body "Closes #640"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 现有 ORM 模型：[`src/db/models/rbac.py`](../../src/db/models/rbac.py)
- 现有 RBACService：[`src/services/rbac_service.py`](../../src/services/rbac_service.py)
- 同类迁移参考：[`alembic/versions/9d8e7f6a5b3c_add_auth_tables.py`](../../alembic/versions/9d8e7f6a5b3c_add_auth_tables.py)
- 父 issue：#38

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
