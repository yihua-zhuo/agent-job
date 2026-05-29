# 基础设施板块 · 新增 TenantModel ORM 模型与 Alembic 迁移

| 元数据 | 值 |
|---|---|
| Issue | #471 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 所有含 tenant_id 过滤的 service / router 板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `src/db/models/` 下不存在 `TenantModel`。所有 service 层的 `tenant_id` 过滤均依赖调用方自行传入 int 值，缺乏统一的 ORM 模型来约束 tenant 表结构。这也导致后续 alembic autogenerate 无法为 tenant 相关变更生成迁移。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 ORM + 数据库 schema 改动。
- **开发者视角**：`src/db/models/tenant.py` 中有 `TenantModel` 可被 import；`alembic/versions/` 中有对应迁移文件，可通过 `alembic upgrade head` 创建 tenant 表；后续 service 可直接用 `TenantModel` 做关联查询。

### 1.3 不做什么（剔除）

- [ ] 服务层代码（`src/services/tenant_service.py` 等）— 不在本板块范围内
- [ ] API 路由（`src/api/routers/tenant.py` 等）— 不在本板块范围内
- [ ] 中间件（`src/middleware/` 下任何 tenant 相关中间件）
- [ ] 多租户业务逻辑实现

### 1.4 关键 KPI

- `PYTHONPATH=src python -c "from db.models import TenantModel; print(TenantModel.__tablename__)"` → 输出 `tenants`
- `alembic upgrade head` → exit 0，迁移成功应用
- `alembic downgrade -1 && alembic upgrade head` → 两次 exit 0（升级降级往返干净）
- `ruff check src/db/models/tenant.py src/db/models/__init__.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 目录结构中是否已有 `tenant.py` 或其他 tenant 相关 model

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — 新增 `TenantModel` 导出
  - `alembic/env.py` — 新增 `TenantModel` import（确保 alembic autogen 能看到）
- 要建：
  - `src/db/models/tenant.py` — TenantModel ORM 模型定义
  - `alembic/versions/<id>_add_tenant_table.py` — Alembic 迁移文件
  - `tests/unit/test_tenant_model.py` — TenantModel 单元测试

### 2.3 缺什么

- [ ] 缺少 `TenantModel` ORM 模型定义（id, name, slug, status, plan, usage_limits, created_at, updated_at）
- [ ] 缺少 `TenantModel` 在 `__init__.py` 中的导出
- [ ] 缺少 `alembic/env.py` 对 TenantModel 的 import（autogenerate 需此 import）
- [ ] 缺少 tenant 表的 Alembic 迁移文件
- [ ] 缺少 TenantModel 的单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/tenant.py` | TenantModel ORM 模型，含 id/name/slug/status/plan/usage_limits/created_at/updated_at |
| `alembic/versions/<id>_add_tenant_table.py` | 创建 tenant 表的 Alembic 迁移（含 downgrade） |
| `tests/unit/test_tenant_model.py` | TenantModel 单元测试（mock session） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/__init__.py` | 新增 `TenantModel` 导出行 |
| `alembic/env.py` | 新增 `from db.models.tenant import TenantModel` import 语句 |

### 3.3 新增能力

- **ORM model**：`TenantModel` in `src/db/models/tenant.py`
- **Migration**：Alembic 迁移文件创建 `tenants` 表，含 `id` 主键、`slug` 唯一索引（无额外 `tenant_id` 列 — tenant 表自身 `id` 即为 tenant 标识）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `sa.String` / `sa.Text` 不选 `sa.VARCHAR(255)` 硬编码**：列宽用 `server_default` 或在列定义中用 `String(length=None)` 让 alembic 保持 clean，避免迁移中出现 `VARCHAR(255)` 硬编码分歧。
- **不引入 tenant_seeded 默认数据**：迁移仅建表，不填充数据；seed 数据由后续 seed 专用迁移处理。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 所有时间戳列使用 `TIMESTAMP WITH TIME ZONE`，Alembic autogenerate 可能误写为 `DateTime`，需手动修正。

### 4.4 已知坑

1. **Alembic autogen 将 `TIMESTAMPTZ` 写成 `DateTime`，将 `JSONB` 写成 `JSON`** → 规避：生成迁移后手动将 `DateTime()` 改为 `DateTime(timezone=True)`，将 `JSON()` 改为 `JSONB().as_computed(...)` 或显式 `JSONB`。
2. **Alembic autogen 漏掉 `server_default` 导致非空列在新行上无默认值** → 规避：显式为 `status`、`plan` 等列补写 `server_default`，参考同类 migration 中 `server_default="active"` 等写法。
3. **未在 `alembic/env.py` 中 import 新 model 导致 autogen 看不到该表** → 规避：每新建一个 ORM model 后必须在 `alembic/env.py` 的 import 块中新增对应 import 语句，再跑 autogenerate。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/tenant.py`

新建 `src/db/models/tenant.py`，定义 `TenantModel`。

操作：
- a) 创建 `src/db/models/tenant.py` 文件
- b) 参考 `src/db/models/` 下已有 model 的 Base 继承写法（如 `customer.py`）
- c) 定义列：id（自增主键）、name（非空 String）、slug（非空唯一索引）、status（非空默认 'active'）、plan（非空默认 'free'）、usage_limits（JSONB，默认空对象 `{}`）、created_at（DateTime with timezone）、updated_at（DateTime with timezone）
- d) `__tablename__ = "tenants"`，表名复数

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")
    plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="free")
    usage_limits: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.tenant import TenantModel; print(TenantModel.__tablename__)"` → `tenant`（无报错）

---

### Step 2: 导出 `TenantModel` 到 `src/db/models/__init__.py`

操作：
- a) 读取 `src/db/models/__init__.py`
- b) 添加 `from db.models.tenant import TenantModel`
- c) 在 `__all__` 中添加 `"TenantModel"`（如已有 `__all__`）

**完成判定**：`PYTHONPATH=src python -c "from db.models import TenantModel; print('ok')"` → `ok`

---

### Step 3: 在 `alembic/env.py` 中新增 `TenantModel` import

操作：
- a) 读取 `alembic/env.py`
- b) 在现有 model import 块中添加 `from db.models.tenant import TenantModel`（注意：不导入 `Base`，已在别处导入）
- c) 确保所有 model import 后 `models.Base.metadata` 包含 TenantModel

**完成判定**：`grep "from db.models.tenant import TenantModel" alembic/env.py` → 找到一行

---

### Step 4: 生成 Alembic 迁移文件

操作：
- a) 确保 `alembic_dev` 数据库干净且在 `head`：`alembic upgrade head`
- b) `alembic revision --autogenerate -m "add tenant table"`
- c) 读取生成的 `alembic/versions/<id>_add_tenant_table.py`
- d) 手动修正已知坑：
   - `DateTime()` → `DateTime(timezone=True)`
   - `JSON` → `JSONB`
   - `server_default` 补全（如 status、plan、usage_limits 的默认值）
- e) 检查 `downgrade()` 是否调用 `op.drop_table("tenants")`

**完成判定**：`ruff check alembic/versions/<id>_add_tenant_table.py` → 0 errors；文件含 `op.create_table("tenants"` 和 `op.drop_table("tenants")`

---

### Step 5: 验证迁移双向可用

操作：
- a) `alembic upgrade head`（如尚未应用）
- b) `alembic downgrade -1` → exit 0
- c) `alembic upgrade head` → exit 0
- d) `alembic current` 确认在 head

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 6: 编写 `tests/unit/test_tenant_model.py`

操作：
- a) 新建 `tests/unit/test_tenant_model.py`
- b) 参考 `tests/unit/conftest.py` 中的 `make_mock_session` 模式
- c) 定义 `tenant_handler`（INSERT / SELECT 按 id 查询）
- d) 测试用例：
   - `test_tenant_model_columns`：验证 TenantModel 各列属性
   - `test_tenant_to_dict`：验证 `.to_dict()` 序列化输出含所有字段

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tenant_model.py -v` → 全部 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/tenant.py src/db/models/__init__.py alembic/env.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models import TenantModel; assert TenantModel.__tablename__ == 'tenants'"` → 无报错
- [ ] `PYTHONPATH=src pytest tests/unit/test_tenant_model.py -v` → 全部 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `grep "from db.models.tenant import TenantModel" alembic/env.py` → 找到 import 行

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| alembic autogenerate 将 JSONB 误写为 JSON，运行时报 "operator does not exist: json = json" | 低 | 中 | 手动修改生成的迁移文件，将 `JSON()` 替换为 `JSONB()` 后重新 upgrade |
| 生成迁移时未在 `alembic/env.py` 中 import TenantModel，导致 autogen 忽略表 | 中 | 高 | 在 `alembic/env.py` 添加 import 后重新运行 `alembic revision --autogenerate` |
| downgrade 缺失 `op.drop_table("tenants")` 导致回退不干净 | 低 | 中 | 手动在迁移文件的 `downgrade()` 中补写 `op.drop_table("tenants")` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/tenant.py src/db/models/__init__.py alembic/env.py alembic/versions/<id>_add_tenant_table.py tests/unit/test_tenant_model.py
git commit -m "feat(models): add TenantModel ORM and initial migration

Closes #471

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(models): add TenantModel ORM and Alembic migration (#471)" --body "Closes #471

## Summary
- Add `TenantModel` in `src/db/models/tenant.py` (id, name, slug, status, plan, usage_limits, created_at, updated_at)
- Export in `src/db/models/__init__.py`
- Import in `alembic/env.py` for autogenerate visibility
- Alembic migration for `tenant` table with proper downgrade

## Test plan
- [ ] \`ruff check src/db/models/tenant.py\` → 0 errors
- [ ] \`PYTHONPATH=src pytest tests/unit/test_tenant_model.py -v\` → all passed
- [ ] \`alembic upgrade head && alembic downgrade -1 && alembic upgrade head\` → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# 本板块文档状态变更为「✅ 已完成」
# docs/dev-plan/README.md §1.1 AUTO-INDEX 由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#447（多租户基础设施总览）
- 同类参考实现（已有 model 文件结构）：TBD - 待验证：`src/db/models/customer.py` 或 `src/db/models/` 下任一已有 model 的 Base 继承模式
- Alembic 官方文档：https://alembic.sqlalchemy.org/en/latest/autogenerate.html

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
