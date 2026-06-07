# 销售 · Add OpportunityModel ORM and alembic migration

| 元数据 | 值 |
|---|---|
| Issue | #567 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：后续板块依赖 OpportunityModel（见 #552 子任务链） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

#552（CRM 数据模型补全）将销售机会（Opportunity）列入核心领域模型。当前 `src/db/models/` 中没有 `OpportunityModel`，导致后续销售流程、pipeline 看板、统计等板块无法引用机会实体，所有关联业务逻辑均无法落地。此为阻塞性缺口。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 ORM + migration
- **开发者视角**：可在任意 service / router 中 `from db.models.opportunity import OpportunityModel` 引用机会实体，支持按 tenant_id 过滤的 CRUD 操作

### 1.3 不做什么（剔除）

- [ ] 销售机会的 Service 类（由后续板块承接）
- [ ] 销售机会的 API Router（由后续板块承接）
- [ ] 销售机会的 Unit Tests（本 issue 明确排除）
- [ ] 前端展示层改动

### 1.4 关键 KPI

- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `ruff check src/db/models/opportunity.py` → 0 errors
- `alembic revision --autogenerate -m "drift_check"` → 生成文件 `up_revision()` / `down_revision()` 均为 `pass`（无 drift）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 目录结构 — 现有 model 文件列表及命名约定（是否存在 `ticket.py` / `campaign.py` 等类似子模块供参照）

新建模块，无历史实现可直接引用。参照 CLAUDE.md §Alembic Migrations 中关于 `alembic/env.py` 导入模型的说明，以及 `pkg/errors/app_exceptions.py` 中的异常类定义规范。

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 新增 `from db.models.opportunity import OpportunityModel` 导入语句
- 要建：
  - `src/db/models/opportunity.py` — `OpportunityModel` ORM 定义
  - `alembic/versions/<id>_add_opportunity.py` — Alembic autogenerate 生成的 migration 文件

### 2.3 缺什么

- [ ] `src/db/models/opportunity.py` 文件不存在，无法在业务层引用销售机会实体
- [ ] Alembic env 未注册 `OpportunityModel`，`alembic revision --autogenerate` 无法感知新表
- [ ] 数据库无 `opportunity` 表，multi-tenant CRUD 缺少底层 schema 支撑
- [ ] 无 Opportunity stage 枚举定义，销售流程阶段无标准化约束

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/opportunity.py` | OpportunityModel ORM 类，含 stage 枚举、必填字段、tenant_id 索引 |
| `alembic/versions/<id>_add_opportunity.py` | Alembic migration，创建 `opportunity` 表（含外键和索引） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | 新增一行 `from db.models.opportunity import OpportunityModel` |

### 3.3 新增能力

- **ORM model**：`OpportunityModel` in `src/db/models/opportunity.py`，字段：id、tenant_id、name、stage（枚举）、company、value（Decimal）、expected_close_date、owner_id、created_at、updated_at
- **Migration**：`alembic upgrade head` 创建 `opportunity` 表，含 `tenant_id` 索引和外键约束

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `Enum` 作为 stage 类型，不选字符串**：避免拼写错误、保证数据一致性，SQLAlchemy `mapped_column` + `Enum` 天然映射 PG enum 类型
- **选 `Decimal(p, 2)` 作为 value，不选 float**：货币值不可用浮点运算（精度问题），Decimal 在金融场景为标准实践

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| SQLAlchemy | 2.x（已有约束） | 使用 `Mapped[]` / `mapped_column` 语法 |
| asyncpg | 驱动（已有约束） | async session 必要条件 |

### 4.3 兼容性约束

- 多租户：表必须含 `tenant_id INTEGER NOT NULL` 列，并建立 `INDEX`（见 CLAUDE.md §Multi-Tenancy）
- 列名不可用 `metadata`（与 `Base.metadata` 冲突）→ 用 `attrs` / `payload` 等替代
- Service 层返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- 所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- `OpportunityModel.__init__` 不接受 `session` 参数 — 新建 model 无业务逻辑，纯数据持有

### 4.4 已知坑

1. **Alembic autogen 会把 `JSONB` 误写为 `JSON`，把 `TIMESTAMPTZ` 误写为 `DateTime`** → migration 生成后人工检查：将 `sa.JSON()` 改回 `sa.JSONB()`；将无 `timezone=True` 的 `DateTime` 改回 `DateTime(timezone=True)`
2. **Alembic autogen 不生成外键索引** → 若 `owner_id` 建立外键，需人工添加 `Index('ix_opportunity_owner_id', 'owner_id')`
3. **`alembic/env.py` 若未 import 新 model，autogenerate 看不到表** → 生成 migration 前必须先完成 import 语句的添加步骤

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/opportunity.py`

在 `src/db/models/` 下新建 `opportunity.py`。

定义 `OpportunityStage` 枚举（五阶段），定义 `OpportunityModel`，字段：

```python
import decimal
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class OpportunityStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class OpportunityModel(Base):
    __tablename__ = "opportunity"
    __table_args__ = (
        Index("ix_opportunity_tenant_id", "tenant_id"),
        Index("ix_opportunity_owner_id", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[OpportunityStage] = mapped_column(
        SAEnum(OpportunityStage, name="opportunity_stage", create_type=False),
        nullable=False,
        default=OpportunityStage.LEAD,
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

**完成判定**：`ruff check src/db/models/opportunity.py` → 0 errors

---

### Step 2: 在 `alembic/env.py` 注册 `OpportunityModel`

找到 `alembic/env.py` 中的 import 区段，新增一行：

```python
from db.models.opportunity import OpportunityModel
```

确认 import 区段与 `from db.models import *` 或其他 model imports 放在一起。

**完成判定**：`grep -n "opportunity" alembic/env.py` 返回 import 行

---

### Step 3: 准备 alembic_dev 数据库

启动干净的 alembic_dev 数据库（参考 CLAUDE.md §Alembic Migrations）：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 将 alembic_dev 带到当前 head
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

**完成判定**：`alembic current` 输出当前 revision 非空

---

### Step 4: autogenerate migration

```bash
alembic revision --autogenerate -m "add opportunity table"
```

生成的 migration 文件路径：`alembic/versions/<id>_add_opportunity_table.py`

**完成判定**：`alembic/versions/<id>_add_opportunity_table.py` 文件存在且 `up_revision()` / `down_revision()` 非 `pass`

---

### Step 5: 手动审查并修复 migration

打开生成的 migration 文件，检查并修正以下内容：

1. **JSONB**：`column(server_default=text('{}'))` 类型若为 `JSON` 需改为 `JSONB`（本模型无 JSON 字段可跳过此条）
2. **DateTime + timezone=True**：所有 `DateTime()` 必须为 `DateTime(timezone=True)`
3. **owner_id 外键索引**：确认存在 `Index('ix_opportunity_owner_id', 'owner_id')` 或等效定义
4. **`onupdate` lambda 不支持 autoflush**：将 `onupdate=lambda: datetime.now(timezone.utc)` 替换为 `onupdate=text("NOW()")` 或直接在 SQL 中处理

示例修复：

```python
# uprev 中手动添加索引（若 autogen 未生成）
opportunity_owner_id_idx = op.create_index(
    "ix_opportunity_owner_id",
    "opportunity",
    ["owner_id"],
    unique=False,
)
```

**完成判定**：`ruff check alembic/versions/<id>_add_opportunity_table.py` → 0 errors

---

### Step 6: 验证 upgrade / downgrade / 二次 drift check

```bash
# 1. upgrade to head
alembic upgrade head
# 预期：running upgrade 产生 opportunity 表

# 2. downgrade one step
alembic downgrade -1
# 预期：running downgrade 成功

# 3. re-upgrade to confirm clean round-trip
alembic upgrade head

# 4. drift check — second autogenerate must be empty
alembic revision --autogenerate -m "drift_check"
# 预期：新文件 up/down 均为 pass；若有实际 diff 则返回 Step 5 修正
```

**完成判定**：`echo $?` 为 0，三条 alembic 命令均无报错输出

---

## 6. 验收

- [ ] `ruff check src/db/models/opportunity.py` → 0 errors
- [ ] `grep "opportunity" alembic/env.py` → 找到 import 语句
- [ ] `alembic upgrade head` → exit 0，创建 `opportunity` 表
- [ ] `alembic downgrade -1` → exit 0，drop `opportunity` 表
- [ ] `alembic upgrade head`（第二次）→ exit 0（round-trip clean）
- [ ] `alembic revision --autogenerate -m "drift_check"` → 新文件 `up_revision() == "pending"` 或 `pass`，无实际 diff

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| alembic autogen 未生成正确列类型（如 DateTime 缺 timezone） | 中 | 中 | Step 5 人工修正后重新验证；不阻塞后续板块（migration 本身可独立修复） |
| owner_id 外键约束导致 downgrade 卡死（PG FK 顺序） | 低 | 中 | downgrade 前先手动 `ALTER TABLE opportunity DROP CONSTRAINT IF EXISTS` 再删表；不依赖本迁移的 downstream 可继续开发 |
| `Base.metadata` 未注册 model（import 未生效） | 低 | 高 | 确认 `alembic/env.py` 中 import 语句在所有 `from db.models` 块之后；重新 `alembic upgrade head` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/opportunity.py alembic/env.py alembic/versions/<id>_add_opportunity_table.py
git commit -m "feat(db): add OpportunityModel ORM and alembic migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(db): add OpportunityModel ORM and alembic migration" --body "Closes #567\n\nSubtask of #552"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/ticket.py` 或 `src/db/models/campaign.py` — 现有 model 的表结构/枚举写法
- 第三方文档：[SQLAlchemy 2.x mapped_column](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html)
- 父 issue / 关联：#552

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
