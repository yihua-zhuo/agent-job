# identity.py · Define Organization and Department ORM models

| 元数据 | 值 |
|---|---|
| Issue | #426 |
| 分类 | [00-foundations](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [实现 Identity Service（用户与部门绑定）](../10-customers/0430-create-src-db-repositories-customer-py-with-customerrepository.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统当前只有 `TenantModel` 和 `UserModel`（在 `db.base.Base` 上定义），缺少组织架构层面的抽象。`OrganizationModel` 和 `DepartmentModel` 是多租户系统的核心层级节点：Organization 承载租户下的业务单元，Department 提供人员与岗位的归属结构。没有这两个模型，权限分配和人员归属都将缺少持久化承载体。#270 的后续子任务（Service 层、API 层）都依赖于此处定义的模型。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 ORM schema 定义。
- **开发者视角**：`from db.models.identity import OrganizationModel, DepartmentModel` 可用；后续 `OrganizationService` / `DepartmentService` 可基于这两个 ORM 模型构建 CRUD。

### 1.3 不做什么（剔除）

- [ ] 不创建 `OrganizationService` / `DepartmentService`（属于后续板块）
- [ ] 不创建对应的 API router（属于后续板块）
- [ ] 不迁移或移动现有的 `TenantModel` / `UserModel`（按 issue 要求，仅创建新模型）
- [ ] 不修改 `alembic/env.py` 的 Base 导入（Base 本身已就绪）

### 1.4 关键 KPI

- `src/db/models/identity.py` 文件存在且可被 Python import（`PYTHONPATH=src python -c "from db.models.identity import OrganizationModel, DepartmentModel"`）→ exit 0
- `src/db/models/__init__.py` re-exports `OrganizationModel` 和 `DepartmentModel` → `PYTHONPATH=src python -c "from db.models import OrganizationModel, DepartmentModel"` → exit 0
- `ruff check src/db/models/identity.py src/db/models/__init__.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_identity.py -v` → 全 passed（预期 2-4 个测试用例）

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

`src/db/models/identity.py` 不存在，这是本板块的起点。

TBD - 待验证：现有 TenantModel / UserModel 的定义位置（可能在 `src/db/models/tenant.py` 或 `src/db/models/user.py`），以及它们使用的列类型和 mixin 模式，作为本板块的建模参考。

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/__init__.py`](../../src/db/models/__init__.py) — 新增 `OrganizationModel`、`DepartmentModel` 的 re-export
- 要建：
  - `src/db/models/identity.py` — 定义 `OrganizationModel` 和 `DepartmentModel` 两个 ORM 类
  - `tests/unit/test_identity.py` — 单元测试，覆盖两模型的字段和可导入性

### 2.3 缺什么

- [ ] `src/db/models/identity.py` 文件不存在，无法 import OrganizationModel / DepartmentModel
- [ ] `src/db/models/__init__.py` 未 re-export 新模型，下游无法通过 `from db.models import ...` 获取
- [ ] 无针对 OrganizationModel / DepartmentModel 的单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/identity.py` | 定义 `OrganizationModel`（组织）和 `DepartmentModel`（部门）两个 ORM 模型，含 tenant_id 索引、软删除和时间戳 |
| `tests/unit/test_identity.py` | 单元测试：验证两模型字段定义正确、可被 import、to_dict() 正常 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/__init__.py`](../../src/db/models/__init__.py) | 新增 `OrganizationModel`、`DepartmentModel` 的 re-export |

### 3.3 新增能力

- **ORM model**：`OrganizationModel` — `__tablename__ = "organizations"`，含 `id`, `tenant_id`, `name`, `description`, `created_at`, `updated_at`, `deleted_at`，`tenant_id` 上有 `index=True`
- **ORM model**：`DepartmentModel` — `__tablename__ = "departments"`，含 `id`, `tenant_id`, `organization_id`（FK）, `name`, `parent_id`（自引用，可空，支持树形）, `created_at`, `updated_at`, `deleted_at`，`tenant_id` 上有 `index=True`
- **Re-export**：`from db.models import OrganizationModel, DepartmentModel` 可用

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **ORM 基类选 `Base`（来自 `db.base`）不自己定义**：`db.base` 已在 Alembic 迁移链中注册，使用它保证迁移兼容性。
- **`deleted_at` 软删除列选 TIMESTAMPTZ 而非 DATE**：保持与其他模型（如 TenantModel/UserModel）一致，使用 `DateTime(timezone=True)` 并在 service 层处理过滤。
- **`parent_id` 自引用 FK 放在 `DepartmentModel` 上**：支持树形部门结构；外键指向自身 `departments.id`，`ondelete='SET NULL'` 防止级联删除导致整棵子树消失。
- **`organization_id` FK 指向 `organizations.id`**：部门从属于组织，租户隔离由 `tenant_id` 保证。

### 4.2 版本约束

无新引入的第三方依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 列名不使用 `metadata`（与 `Base.metadata` 冲突），本板块两模型均不使用该名

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不可用 `metadata`** → 规避：本板块所有列名均为 `name`, `description`, `created_at`, `updated_at`, `deleted_at`, `parent_id`, `organization_id`，无冲突。
2. **Alembic autogen 会把 `DateTime(timezone=True)` 写成 `DateTime`（无 timezone）、把 `JSONB` 写成 `JSON`** → 规避：本板块仅含 `DateTime(timezone=True)` 字段，alembic 迁移若涉及此处须手动校正为 `DateTime(timezone=True)` 或 `TIMESTAMPTZ`。

---

## 5. 实现步骤（按顺序）

### Step 1: Create src/db/models/identity.py with OrganizationModel and DepartmentModel

新建 `identity.py` 文件，定义两个 ORM 类。参考 `db.base.Base` 的注册模式，使用 `Mapped[...]` 类型注解和 `mapped_column` 函数。软删除列 `deleted_at` 可空。`tenant_id` 和 `organization_id` 均加 `index=True`。

操作：
- a) 在 `src/db/models/` 下新建 `identity.py`
- b) 写入两个模型类，字段见 §3.3

示例代码：

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DepartmentModel(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.identity import OrganizationModel, DepartmentModel; print('OK')"` → 输出 `OK` / `ruff check src/db/models/identity.py` → exit 0

---

### Step 2: Update src/db/models/__init__.py to re-export the new models

操作：
- 在 `src/db/models/__init__.py` 的 re-export 区块中添加 `OrganizationModel` 和 `DepartmentModel`

示例代码：

```python
from db.models.identity import DepartmentModel, OrganizationModel  # 新增
```

**完成判定**：`PYTHONPATH=src python -c "from db.models import OrganizationModel, DepartmentModel; print('OK')"` → 输出 `OK`

---

### Step 3: Create tests/unit/test_identity.py

新建单元测试文件，参考 `tests/unit/conftest.py` 中已有的 `MockRow` / `MockResult` 模式。测试目标：

操作：
- a) 在 `tests/unit/` 下新建 `test_identity.py`
- b) 测试两模型可被正确 import
- c) 测试 `to_dict()` 方法存在且不抛异常（继承自 Base，router 层需要）
- d) 测试 `tenant_id` 列存在于两模型

示例代码（测试结构）：

```python
import pytest
from db.models.identity import OrganizationModel, DepartmentModel


class TestOrganizationModel:
    def test_import(self):
        assert OrganizationModel is not None

    def test_tablename(self):
        assert OrganizationModel.__tablename__ == "organizations"

    def test_has_tenant_id_column(self):
        assert hasattr(OrganizationModel, "tenant_id")

    def test_to_dict_does_not_raise(self):
        org = OrganizationModel(id=1, tenant_id=1, name="Acme Corp", description=None)
        d = org.to_dict()
        assert "id" in d
        assert d["name"] == "Acme Corp"


class TestDepartmentModel:
    def test_import(self):
        assert DepartmentModel is not None

    def test_tablename(self):
        assert DepartmentModel.__tablename__ == "departments"

    def test_has_tenant_id_column(self):
        assert hasattr(DepartmentModel, "tenant_id")

    def test_has_organization_id_column(self):
        assert hasattr(DepartmentModel, "organization_id")

    def test_to_dict_does_not_raise(self):
        dept = DepartmentModel(id=1, tenant_id=1, organization_id=1, name="Engineering")
        d = dept.to_dict()
        assert "id" in d
        assert d["name"] == "Engineering"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_identity.py -v` → `6 passed` / `ruff check tests/unit/test_identity.py` → exit 0

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models.identity import OrganizationModel, DepartmentModel; print('OK')"` → `OK`
- [ ] `PYTHONPATH=src python -c "from db.models import OrganizationModel, DepartmentModel; print('OK')"` → `OK`
- [ ] `ruff check src/db/models/identity.py src/db/models/__init__.py` → 0 errors
- [ ] `ruff check tests/unit/test_identity.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_identity.py -v` → `6 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → 全部 passed（包括新增文件不破坏已有测试）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 模型字段与其他已有模型（如 TenantModel）不一致，导致 Alembic autogen 产生意外 diff | 低 | 中 | 确认所有时间戳字段均使用 `DateTime(timezone=True)`，不依赖 autogen 的自动推断 |
| 新模型 import 触发 `db.base.Base` 的循环导入 | 低 | 高 | 将 `from db.base import Base` 放在文件顶部，不在函数内延迟导入；如出现循环，明确在 `db/base.py` 中使用 TYPE_CHECKING guard |
| 单元测试覆盖不足导致后续集成阶段才发现字段缺失 | 低 | 中 | 在 `test_identity.py` 中补充对所有必需列的 `hasattr` 检查（已在 Step 3 覆盖） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/identity.py src/db/models/__init__.py tests/unit/test_identity.py
git commit -m "feat(identity): add OrganizationModel and DepartmentModel ORM classes"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(identity): define Organization and Department ORM models (#426)" --body "Closes #426"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：现有 TenantModel / UserModel 的定义文件（用于确认字段命名和 mixin 使用方式）
- 父 issue / 关联：#270

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
