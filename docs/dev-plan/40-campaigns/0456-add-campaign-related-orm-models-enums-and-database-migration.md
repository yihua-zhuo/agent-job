# Campaigns · 添加 Campaign 相关 ORM 模型、枚举与数据库迁移

| 元数据 | 值 |
|---|---|
| Issue | #456 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | 无 |
| 启用后赋能 | MarketingService（#459）、TriggerService（#458）、WorkflowService（#463） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统目前缺少营销自动化（Marketing Automation）所需的底层数据模型。#450 规划了完整的营销活动体系，但核心 ORM 模型（Campaign、CampaignEvent、Trigger）和业务枚举尚未实现，导致下游服务层和 API 层无法构建。本板块是整个 Campaign 功能线的地基。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 本板块为纯底层 schema 迁移，为后续 API 和前端提供数据模型基础。
- **开发者视角**：可 `from db.models.campaign import Campaign, CampaignType, CampaignStatus` 导入模型和枚举；可执行 `alembic upgrade head` 创建三张新表；单元测试验证模型字段和枚举值符合预期。

### 1.3 不做什么（剔除）

- [ ] 不实现 CampaignService、TriggerService、WorkflowService 等业务逻辑层（分别归属 #459、#458、#463）
- [ ] 不实现 Campaign 相关的 API Router（归属 #459）
- [ ] 不实现与 Customer、Pipeline 等已有模型之外的关联关系（先聚焦独立模型，后续板块补充外键）

### 1.4 关键 KPI

- [ `PYTHONPATH=src python -c "from db.models.campaign import Campaign, CampaignType, CampaignStatus; from db.models.campaign_event import CampaignEvent, EventType; from db.models.trigger import Trigger, TriggerType; print('OK')"` → 输出 `OK`，exit 0 ]
- [ `PYTHONPATH=src pytest tests/unit/ -v` → 全 passed ]
- [ `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0 ]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

TBD - 待验证：`src/db/models/` 目录下现有 ORM 模型的文件组织方式（参考现有模型如 `customer.py` / `pipeline.py` 的 Base 继承方式、字段声明顺序、`tenant_id` 处理习惯）

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — 导出新增的 Campaign、CampaignEvent、Trigger 模型及枚举
  - `alembic/env.py` — 导入新增模型，使 autogen 可识别
- 要建：
  - `src/db/models/campaign.py` — Campaign ORM 模型 + CampaignType/CampaignStatus 枚举
  - `src/db/models/campaign_event.py` — CampaignEvent ORM 模型 + EventType 枚举
  - `src/db/models/trigger.py` — Trigger ORM 模型 + TriggerType 枚举
  - `alembic/versions/<id>_add_campaign_tables.py` — 三个新表的 migration
  - `tests/unit/test_campaign_model.py` — 模型字段和枚举值的单元测试
  - `tests/unit/test_campaign_event_model.py` — 同上
  - `tests/unit/test_trigger_model.py` — 同上

### 2.3 缺什么

- [ ] 缺少 `Campaign` ORM 模型（包含 name、type、status、scheduled_at、ended_at 等字段）
- [ ] 缺少 `CampaignType`（EMAIL, SMS, PUSH, AUTO）和 `CampaignStatus`（DRAFT, ACTIVE, PAUSED, COMPLETED, CANCELLED）枚举
- [ ] 缺少 `CampaignEvent` ORM 模型（记录 sent/opened/clicked/bounced 等事件）
- [ ] 缺少 `EventType`（sent, opened, clicked, bounced）枚举
- [ ] 缺少 `Trigger` ORM 模型（USER_REGISTER, USER_INACTIVE, PURCHASE_MADE, CUSTOM）
- [ ] 缺少 `TriggerType` 枚举
- [ ] 缺少数据库迁移脚本（alembic revision --autogenerate 后需手工修正 JSONB / TIMESTAMPTZ）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/campaign.py` | Campaign ORM 模型 + CampaignType/CampaignStatus 枚举 |
| `src/db/models/campaign_event.py` | CampaignEvent ORM 模型 + EventType 枚举 |
| `src/db/models/trigger.py` | Trigger ORM 模型 + TriggerType 枚举 |
| `alembic/versions/<id>_add_campaign_tables.py` | 创建 campaign / campaign_event / trigger 三张表的 migration |
| `tests/unit/test_campaign_model.py` | Campaign 模型和枚举的单元测试 |
| `tests/unit/test_campaign_event_model.py` | CampaignEvent 模型和枚举的单元测试 |
| `tests/unit/test_trigger_model.py` | Trigger 模型和枚举的单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/__init__.py`](../../src/db/models/__init__.py) | 新增 Campaign、CampaignEvent、Trigger 模型及全部枚举的导出 |
| `alembic/env.py` | import 新增的三个模型类，使 autogen 可识别 |

### 3.3 新增能力

- **ORM model**：`Campaign` in `src/db/models/campaign.py`（含 `tenant_id` 索引）
- **ORM model**：`CampaignEvent` in `src/db/models/campaign_event.py`（含 `tenant_id` 索引）
- **ORM model**：`Trigger` in `src/db/models/trigger.py`（含 `tenant_id` 索引）
- **Enum**：`CampaignType`（EMAIL, SMS, PUSH, AUTO）
- **Enum**：`CampaignStatus`（DRAFT, ACTIVE, PAUSED, COMPLETED, CANCELLED）
- **Enum**：`EventType`（sent, opened, clicked, bounced）
- **Enum**：`TriggerType`（USER_REGISTER, USER_INACTIVE, PURCHASE_MAILED, CUSTOM）
- **Migration**：`alembic upgrade head` 创建三张表及索引

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **枚举使用 SQLAlchemy `Enum` 而非 Pydantic `StrEnum`**：ORM 模型层直接使用 SQLAlchemy Enum，配合 `create_constraint=False` 让枚举值在 DB 层无约束（方便后续值扩增），应用层做验证。
- **JSON 字段选 `JSONB` 而非 `JSON`**：campaign.event_metadata、trigger.conditions 等结构化字段用 JSONB 支持 GIN 索引和高效查询，Alembic autogen 易误生成 `sa.JSON()`，需手工改回。
- **外键暂不加**：`CampaignEvent.campaign_id` 和 `CampaignEvent.recipient_id` 先不加 FK 约束（需确认 target 表已存在且已有迁移），避免循环依赖；后续 #459/#463 板块补齐。

### 4.2 版本约束

无新引入的第三方依赖。

### 4.3 兼容性约束

- 多租户：三张表均含 `tenant_id` 列，所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- ORM 模型继承 `Base`（来自 `db.base`），不使用 `metadata` 作列名（与 `Base.metadata` 冲突），改用 `event_metadata`、`trigger_metadata` 等
- Service 层尚未实现，模型层遵循：属性用 `Mapped[type]` + `mapped_column`，主键用 `primary_key=True`
- 枚举成员值统一用大写下划线（Python 风格）：`CampaignType.EMAIL` / `CampaignStatus.DRAFT`
- Migration 使用 `async_op = True` 的 batch_alter_table（ Alembic PG async 规范）

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON** → 规避：migration 中将 `sa.JSON()` 手动改为 `sa.JSONB().with_variant(postgresql.JSONB(), "postgresql")`
2. **Alembic autogen 把 TIMESTAMPTZ 写成 DateTime（丢失 timezone=True）** → 规避：检查 migration 中的 `DateTime` 字段，若用于时间戳则加 `timezone=True`
3. **`metadata` 列名与 Base.metadata 冲突** → 规避：新模型中避免使用 `metadata` 作列名；用 `event_metadata`（CampaignEvent）、`trigger_conditions`（Trigger）等替代
4. **autogen 不生成 `index=True` 的 tenant_id 索引** → 规避：手工确认 migration 中三张表的 `tenant_id` 列均有 `index=True`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 campaign.py 模型文件及单元测试

参照 `db.base.Base` 和已有模型写法，新建 `campaign.py`，包含：
- `CampaignType` 枚举：EMAIL, SMS, PUSH, AUTO
- `CampaignStatus` 枚举：DRAFT, ACTIVE, PAUSED, COMPLETED, CANCELLED
- `Campaign` ORM 模型：id, tenant_id, name, type, status, description, scheduled_at, ended_at, created_at, updated_at，其中 `tenant_id` 加 `index=True`

操作：
- a) 创建 `src/db/models/campaign.py`
- b) 创建 `tests/unit/test_campaign_model.py`，验证 `Campaign.__table__.columns.keys()` 含所需字段、枚举成员数量正确

示例代码（≤15 行）：

```python
import enum

from sqlalchemy import String, DateTime, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CampaignType(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    AUTO = "AUTO"


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Campaign(Base):
    __tablename__ = "campaign"
    __table_args__ = (
        Index("ix_campaign_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[CampaignType] = mapped_column(SAEnum(CampaignType, name="campaign_type", create_constraint=False))
    status: Mapped[CampaignStatus] = mapped_column(SAEnum(CampaignStatus, name="campaign_status", create_constraint=False))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.campaign import Campaign, CampaignType, CampaignStatus; print('OK')"` → 输出 `OK`

---

### Step 2: 创建 campaign_event.py 模型文件及单元测试

新建 `campaign_event.py`，包含：
- `EventType` 枚举：sent, opened, clicked, bounced
- `CampaignEvent` ORM 模型：id, tenant_id, campaign_id, recipient_id（Integer，暂不设 FK）, event_type, event_metadata（JSONB 列，不用 `metadata` 名避免冲突）, occurred_at, created_at

操作：
- a) 创建 `src/db/models/campaign_event.py`
- b) 创建 `tests/unit/test_campaign_event_model.py`

**完成判定**：`PYTHONPATH=src python -c "from db.models.campaign_event import CampaignEvent, EventType; print('OK')"` → 输出 `OK`

---

### Step 3: 创建 trigger.py 模型文件及单元测试

新建 `trigger.py`，包含：
- `TriggerType` 枚举：USER_REGISTER, USER_INACTIVE, PURCHASE_MADE, CUSTOM
- `Trigger` ORM 模型：id, tenant_id, name, type, conditions（JSONB，存储触发规则）, is_active, created_at, updated_at

操作：
- a) 创建 `src/db/models/trigger.py`
- b) 创建 `tests/unit/test_trigger_model.py`

**完成判定**：`PYTHONPATH=src python -c "from db.models.trigger import Trigger, TriggerType; print('OK')"` → 输出 `OK`

---

### Step 4: 更新 __init__.py 和 alembic/env.py

操作：
- a) 在 `src/db/models/__init__.py` 中添加导出：Campaign, CampaignType, CampaignStatus, CampaignEvent, EventType, Trigger, TriggerType
- b) 在 `alembic/env.py` 中添加新增三个模型的 import，使 autogen 可识别

**完成判定**：`PYTHONPATH=src python -c "from db.models import Campaign, CampaignEvent, Trigger; from db.models.campaign import CampaignType; from db.models.campaign_event import EventType; from db.models.trigger import TriggerType; print('all imported')"` → 输出 `all imported`

---

### Step 5: 生成 Alembic migration 并手工修正

操作：
- a) 确保 `alembic/env.py` 已 import 新模型
- b) `alembic revision --autogenerate -m "add campaign campaign_event trigger tables"`
- c) 检查生成的 migration：将所有 `sa.JSON()` 改为 `sa.JSONB()`；检查 DateTime 列是否需加 `timezone=True`；确认 tenant_id 列含 `index=True`
- d) 执行 `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`，三次 exit 0

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 6: 运行全量单元测试和 lint

操作：
- a) `ruff check src/db/models/campaign.py src/db/models/campaign_event.py src/db/models/trigger.py` → 0 errors
- b) `PYTHONPATH=src pytest tests/unit/test_campaign_model.py tests/unit/test_campaign_event_model.py tests/unit/test_trigger_model.py -v` → 全 passed

**完成判定**：上述两条命令均 exit 0

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models.campaign import Campaign, CampaignType, CampaignStatus; from db.models.campaign_event import CampaignEvent, EventType; from db.models.trigger import Trigger, TriggerType; print('OK')"` → 输出 `OK`
- [ ] `PYTHONPATH=src pytest tests/unit/test_campaign_model.py tests/unit/test_campaign_event_model.py tests/unit/test_trigger_model.py -v` → 全 passed
- [ ] `ruff check src/db/models/campaign.py src/db/models/campaign_event.py src/db/models/trigger.py src/db/models/__init__.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `alembic history --verbose | grep "add campaign"` → 输出包含新 revision 描述

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Migration 中 JSONB 字段误写为 JSON，autogen 后未手工修正 | 中 | 高 | 回退：`alembic downgrade -1` 删除三张表，修正后重新 upgrade |
| 三张表加 `tenant_id` 索引漏写，查询性能不达标 | 中 | 中 | 新增 `alembic revision -m "add tenant_id index to campaign tables"` 补索引，不阻塞下游 |
| autogen 生成 FK 约束指向尚不存在的表（如 recipient_id），导致 upgrade 失败 | 低 | 中 | 移除 migration 中相关 FK 约束列（改回纯 Integer），后续板块补 FK |
| 多租户查询缺少 tenant_id 过滤（模型层正确但服务层遗漏） | 低 | 高 | 由后续板块 #459/#463 的单元测试覆盖，确保所有 service 方法含 tenant_id 过滤 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/campaign.py src/db/models/campaign_event.py src/db/models/trigger.py src/db/models/__init__.py alembic/env.py alembic/versions/<id>_add_campaign_tables.py tests/unit/test_campaign_model.py tests/unit/test_campaign_event_model.py tests/unit/test_trigger_model.py
git commit -m "feat(campaigns): add Campaign/CampaignEvent/Trigger ORM models, enums, and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#456): add campaign ORM models, enums, and migration" --body "Closes #456"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/db/models/customer.py` — 现有 ORM 模型的字段声明风格、`tenant_id` 处理方式
- 同类参考实现：`src/db/models/pipeline.py` — 枚举 + ORM 模型同文件的写法参考
- 父 issue / 关联：#450（营销活动总览）、#459（MarketingService，依赖本板块）、#458（TriggerService，依赖本板块）、#463（WorkflowService，依赖本板块）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
