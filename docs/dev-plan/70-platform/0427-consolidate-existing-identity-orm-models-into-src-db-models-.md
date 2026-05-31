#  Consolidate identity ORM models into src/db/models/identity.py

| 元数据 | 值 |
|---|---|
| Issue | #427 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：依赖前置 issue #426（add organization/department models migration batch 1） |
| 启用后赋能 | TBD - 待验证：后续 issue 完成 import 改写（#428 或类似） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #270 is a multi-batch migration to consolidate identity models into a single `identity.py` file. Issue #426 (batch 1, subtask 1) already added `OrganizationModel` and `DepartmentModel`. Batch 1, subtask 2 (this issue) copies `TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, and `UserRoleModel` from their scattered locations into `src/db/models/identity.py`. Keeping originals untouched during the batch avoids breaking in-progress work; a later issue will wire up the new imports and delete the originals.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层模型文件重组。
- **开发者视角**：`src/db/models/identity.py` becomes the canonical home for all identity models. The `__init__.py` re-exports them alongside `Organization`/`Department` from #426, giving downstream code a single import path (`from db.models.identity import TenantModel, UserModel, ...`).

### 1.3 不做什么（剔除）

- [ ] Do NOT update any imports in `src/services/`, `src/api/routers/`, `src/middleware/`, or test files — that is the scope of #428.
- [ ] Do NOT delete the original `tenant.py`, `user.py`, `rbac.py` files in this batch.
- [ ] Do NOT create Alembic migrations for this file-copy operation.

### 1.4 关键 KPI

- [指标 1：`src/db/models/identity.py` 包含全部 6 个模型（TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel），每个含正确列定义与关系]
- [指标 2：`src/db/models/__init__.py` re-exports 所有 6 个模型（加 #426 的 Organization/Department 共 8 个）]
- [指标 3：`PYTHONPATH=src python -c "from db.models.identity import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel; print('OK')"` → 输出 `OK` 且无 AttributeError / NameError]
- [指标 4：`ruff check src/db/models/identity.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/tenant.py` L? — 应含 TenantModel
TBD - 待验证：`src/db/models/user.py` L? — 应含 UserModel
TBD - 待验证：`src/db/models/rbac.py` L? — 应含 RoleModel, PermissionModel, RolePermissionModel, UserRoleModel
TBD - 待验证：`src/db/models/__init__.py` L? — 当前 re-exports 哪些模型

```python
# 典型模型结构示意（需验证实际文件）
# src/db/models/tenant.py
class TenantModel(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # ...
```

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — 新增 6 个模型的 re-export
- 要建：
  - `src/db/models/identity.py` — 接收 TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel 的目标文件
- 不动（保持原样，等 #428 处理）：
  - `src/db/models/tenant.py`
  - `src/db/models/user.py`
  - `src/db/models/rbac.py`

### 2.3 缺什么

- [ ] `src/db/models/identity.py` 文件尚未创建，无法集中导入 identity 相关模型]
- [ ] `src/db/models/__init__.py` 尚未 re-export 新模型，后续 #428 的 import 改写会断裂]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/identity.py` | 存放 TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel（含关系定义） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/__init__.py`](../../../src/db/models/__init__.py) | 新增 6 个模型的 re-export（TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel）；已包含 #426 的 OrganizationModel/DepartmentModel |

### 3.3 新增能力

- **ORM models**：`TenantModel`, `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel` 集中于 `src/db/models/identity.py`
- **Re-export**：所有 6 个模型可通过 `from db.models.identity import ...` 或 `from db.models import ...` 访问

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **直接复制而非移动**：本批次（BATCH 1）保持原始文件不变，仅做文件内容复制 — 避免与其他 in-progress 分支冲突；后续 #428 完成 import 改写后再由单独 issue 删除原始文件。
- **保留相对 import**：模型内对 `Base` 的 import 保持 `from db.base import Base`，无需修改。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个模型若含 `tenant_id` 列须保持 `index=True`（与其他租户模型一致）
- 模型关系（relationships）须与原文件一致，特别是 `RolePermissionModel` 的 `primary_key=True` 组合列、`UserRoleModel` 的组合主键
- `identity.py` 须 import `Base` from `db.base`（相对路径），不得使用 `from src.db.base import Base`
- `__init__.py` re-export 须与 #426 的 Organization/Department 并存，不能覆盖

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不可用 `metadata`** → 原 `tenant.py`/`user.py`/`rbac.py` 中如存在 `metadata` 列须改名为 `event_metadata` / `payload` 等（本批次检查，如无则跳过）
2. **relationship backref 名称冲突** → 若 TenantModel/UserModel 等在原始文件中有 `back_populates` 跨文件引用，复制时需确认目标文件内关系闭合；暂未跨文件引用则无需处理
3. **Alembic env.py 尚未 import identity.py** → 注意：本批次只建文件不建 migration，无需修改 `alembic/env.py`；后续 Alembic migration 由专项 issue 处理

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 src/db/models/identity.py 并复制 TenantModel

确认源文件 `src/db/models/tenant.py` 中 TenantModel 的完整定义（含 `__tablename__`、所有 `Mapped` 列、`__table_args__` 等），整体复制到新建的 `src/db/models/identity.py` 顶部。保持原样，不做代码改动。

操作：
- a) 读取 `src/db/models/tenant.py`，定位 TenantModel 完整 class 块
- b) 创建 `src/db/models/identity.py`，写入 `from db.base import Base` 和完整的 TenantModel

示例代码（结构示意，实际内容以读取结果为准）：

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # ...其他列...
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.identity import TenantModel; print(TenantModel.__tablename__)"` → `tenants`

---

### Step 2: 复制 UserModel 到 identity.py

读取 `src/db/models/user.py`，将 UserModel 完整 class（含 relationship 到 TenantModel，如适用）追加到 `identity.py`。确保 `from db.models.identity import TenantModel` 在 UserModel 引用处可用（通过 Python 模块加载顺序）。

操作：
- a) 读取 `src/db/models/user.py`，定位 UserModel 完整 class 块
- b) 追加到 `identity.py`

**完成判定**：`PYTHONPATH=src python -c "from db.models.identity import UserModel; print(UserModel.__tablename__)"` → `users`

---

### Step 3: 复制 RBAC 模型到 identity.py

读取 `src/db/models/rbac.py`，将 RoleModel、PermissionModel、RolePermissionModel、UserRoleModel 依次追加到 `identity.py`。注意 RolePermissionModel 和 UserRoleModel 通常是关联表（组合主键，无独立主键列）。

操作：
- a) 读取 `src/db/models/rbac.py`，定位 RoleModel、PermissionModel、RolePermissionModel、UserRoleModel 完整 class 块
- b) 追加到 `identity.py`

示例代码（关联表示意）：

```python
class RolePermissionModel(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"), primary_key=True)


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), primary_key=True)
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.identity import RoleModel, PermissionModel, RolePermissionModel, UserRoleModel; print('RBAC OK')"` → `RBAC OK`

---

### Step 4: 更新 src/db/models/__init__.py 的 re-exports

读取当前 `src/db/models/__init__.py`，确认已有 OrganizationModel、DepartmentModel 的 re-export（来自 #426），然后追加以下 6 行：

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

操作：
- a) 读取 `src/db/models/__init__.py`
- b) 在文件末尾追加上述 6 行 import

**完成判定**：`PYTHONPATH=src python -c "from db.models import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel, OrganizationModel, DepartmentModel; print('All 8 re-exports OK')"` → `All 8 re-exports OK`

---

### Step 5: 运行 ruff 检查

```bash
ruff check src/db/models/identity.py src/db/models/__init__.py
```

操作：
- a) 执行 ruff check
- b) 如有 F401 unused import / E402 module level import 错误，调整 import 顺序

**完成判定**：命令 exit 0，stdout 无 error 输出

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models.identity import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel; print('All 6 OK')"` → `All 6 OK`
- [ ] `PYTHONPATH=src python -c "from db.models import TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel, UserRoleModel, OrganizationModel, DepartmentModel; print('All 8 re-exports OK')"` → `All 8 re-exports OK`
- [ ] `ruff check src/db/models/identity.py src/db/models/__init__.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "import inspect; from db.models.identity import TenantModel; src = inspect.getsource(TenantModel); assert 'id' in src and 'name' in src; print('TenantModel cols OK')"` → `TenantModel cols OK`
- [ ] `PYTHONPATH=src python -c "import inspect; from db.models.identity import RolePermissionModel, UserRoleModel; src = inspect.getsource(RolePermissionModel); assert 'primary_key' in src; print('Assoc models PK OK')"` → `Assoc models PK OK`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 原始文件（tenant.py/user.py/rbac.py）中的 relationship backref 指向原始模块名，复制到 identity.py 后引用断裂 | 低 | 中 | 在 identity.py 底部添加 `from db.models import tenant, user, rbac` 兼容导入；或在下个批次 #428 中一并修正 |
| `__init__.py` 追加 import 时覆盖了 #426 已有的 Organization/Department re-export | 低 | 高 | 验收标准第 2 条会捕获此问题；发现后保留两者的 import 行而非替换 |
| ruff F401（未使用的 Base import）在 identity.py 产生 lint 警告 | 低 | 低 | 使用 `ruff check --ignore F401` 或在 `__init__.py` 添加 `# noqa: F401` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/identity.py src/db/models/__init__.py
git commit -m "feat(identity): batch-1 consolidate Tenant/User/RBAC models into identity.py (#427)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(identity): consolidate Tenant/User/RBAC models into identity.py (#427)" --body "Closes #427

Copies TenantModel, UserModel, RoleModel, PermissionModel, RolePermissionModel,
UserRoleModel from tenant.py / user.py / rbac.py into src/db/models/identity.py.
Updates __init__.py re-exports. Original files left untouched for batch-integrity.

Subtask of #270"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/organization.py` 或 `src/db/models/department.py`（#426 的 subtask 1 输出，可作文件结构参考）
- 父 issue / 关联：#270（父）, #426（依赖的前置 subtask）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

