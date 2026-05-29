# 457 · Implement MarketingService with campaign CRUD and event recording

| 元数据 | 值 |
|---|---|
| Issue | #457 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [456 · Add Marketing API Router and wire into main.py](0456-add-marketing-api-router-and-wire-into-main-py.md) |
| 启用后赋能 | [458 · Add TriggerService with check-triggers and execute-trigger methods](0458-implement-triggerservice-with-check-triggers-and-execute-tri.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #450 确立了「营销自动化」板块，其中 MarketingService 是业务逻辑的核心层。目前没有任何 marketing domain service，所有 campaign 数据无法被业务代码操控。缺少这一层，launch/pause/stats 等运营操作无法落地，trigger 引擎也无从消费事件。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层服务层实现。
- **开发者视角**：`MarketingService` 提供 10 个方法（7 个 campaign CRUD + 3 个事件），所有方法签名包含 `tenant_id`，返回 ORM 对象，错误抛 `AppException` 子类。

### 1.3 不做什么（剔除）

- [ ] 不实现 trigger 执行逻辑（归 TriggerService，#458）
- [ ] 不实现 campaign 审批流程或版本管理
- [ ] 不创建 API router（已有 #456 负责）

### 1.4 关键 KPI

- `PYTHONPATH=src ruff check src/services/marketing_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥ 10 passed（每个 service 方法至少 1 个用例）
- `PYTHONPATH=src mypy src/services/marketing_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`grep -rn "class Campaign" src/db/models/` 或 `grep -rn "class CampaignEvent" src/db/models/` — Campaign ORM 模型及 CampaignEvent ORM 模型应在 #456 创建后存在；如不存在，本 step 需先补充 model 定义。

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 如有新的 ORM model 注册需求
- 要建：
  - `src/services/marketing_service.py` — 10 个 service 方法（主要交付物）
  - `tests/unit/test_marketing_service.py` — 单元测试（≥10 个用例）
  - `src/db/models/campaign.py` — 如 #456 未创建 ORM model 则在此新建
  - `src/db/models/campaign_event.py` — 如 #456 未创建 ORM model 则在此新建
  - `alembic/versions/<id>_create_campaign_tables.py` — 如 ORM model 为新建则补充 migration

### 2.3 缺什么

- [ ] `src/services/marketing_service.py` 完全不存在，无法进行 campaign 运营操作
- [ ] 无 campaign 创建 / 更新 / 发布 / 暂停的 service 层逻辑
- [ ] 无 campaign 统计数据（发送数、打开数、点击数）聚合方法
- [ ] 无事件记录（record_event）和事件查询（get_user_events）能力，trigger 引擎无法获取事件流
- [ ] 无 trigger setup 方法，trigger 规则无法与 campaign 关联

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/marketing_service.py` | MarketingService：7 个 campaign 方法 + 3 个事件方法 |
| `tests/unit/test_marketing_service.py` | 10+ 个单元测试用例，mock DB，不触真实 Postgres |
| `src/db/models/campaign.py` | Campaign ORM model（如 #456 未创建） |
| `src/db/models/campaign_event.py` | CampaignEvent ORM model（如 #456 未创建） |
| `alembic/versions/<id>_create_campaign_tables.py` | 建表 migration（如 model 为新建） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | 注册新的 Campaign / CampaignEvent model（如果本板块创建了 model） |

### 3.3 新增能力

- **Service class**：`MarketingService(session: AsyncSession)` — 10 个方法
  - Campaign CRUD：`create_campaign`, `get_campaign`, `update_campaign`, `launch_campaign`, `pause_campaign`, `get_campaign_stats`, `list_campaigns`
  - 事件方法：`record_event`, `get_user_events`, `setup_trigger`
- **ORM models**：`Campaign`（含 name, status, launched_at, paused_at, stats 等字段）、`CampaignEvent`（含 event_type, user_id, payload 等字段），均含 `tenant_id` 索引
- **Migration**：创建 `campaigns` 表和 `campaign_events` 表

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 SQLAlchemy AsyncSession + selectinload/options，不选 plain select**：确保关联数据（trigger_rules 等）一次性加载，避免 N+1。
- **选 service 层聚合 stats，不选 SQL VIEW**：stats 逻辑可能随业务演进需参数化，service 方法更灵活。
- **选 record_event 写事件表，不选直接调用 trigger**：record_event 纯存储，由 trigger 引擎主动拉取，保持单向依赖。

### 4.2 版本约束

无新外部依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`；session 注入在 `__init__` 完成，方法签名均为 `self, ..., tenant_id: int`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ConflictException`）
- 命名冲突：ORM model 的列**禁止**使用 `metadata`（与 `Base.metadata` 冲突），用 `event_metadata` / `payload` / `meta` 代替
- Import 路径：必须 `from db.models...`，禁止 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogenerate 把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 规避：migration 生成后手动检查并修正 `sa.JSON()` → `sa.JSONB()`，`DateTime(timezone=True)` 保留 timezone flag。
2. **SQLAlchemy Base 子类列名 `metadata` 与 `Base.metadata` 冲突** → 规避：所有 event/payload 相关字段命名用 `event_metadata` 或 `payload`，不在 ORM model 中出现裸 `metadata` 列名。
3. **`async with get_db() as session:` 是错误用法** → 规避：router 层用 `session: AsyncSession = Depends(get_db)`，service 层只接受 constructor 注入的 session。

---

## 5. 实现步骤（按顺序）

### Step 1: 确认或创建 Campaign 和 CampaignEvent ORM 模型

确认 `src/db/models/` 下是否存在 `campaign.py` 和 `campaign_event.py`。如果不存在，根据 issue #456 的设计意图创建：

```python
# src/db/models/campaign.py
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    LAUNCHED = "launched"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus), default=CampaignStatus.DRAFT
    )
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # stats stored as JSONB payload, not as separate columns
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

在 `alembic/env.py` 注册新 model（如有新建）。

**完成判定**：`PYTHONPATH=src python -c "from db.models.campaign import Campaign; print('OK')"` exit 0

---

### Step 2: 创建 `src/services/marketing_service.py` 主文件

按 CRM service 规范编写，核心骨架：

```python
# src/services/marketing_service.py
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.campaign import Campaign, CampaignStatus
from db.models.campaign_event import CampaignEvent
from pkg.errors.app_exceptions import NotFoundException, ValidationException, ConflictException


class MarketingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- campaign CRUD ---

    async def create_campaign(self, tenant_id: int, name: str, ...) -> Campaign:
        ...

    async def get_campaign(self, campaign_id: int, tenant_id: int) -> Campaign:
        ...

    async def update_campaign(self, campaign_id: int, tenant_id: int, ...) -> Campaign:
        ...

    async def launch_campaign(self, campaign_id: int, tenant_id: int) -> Campaign:
        ...

    async def pause_campaign(self, campaign_id: int, tenant_id: int) -> Campaign:
        ...

    async def get_campaign_stats(self, campaign_id: int, tenant_id: int) -> dict:
        # SELECT event_type, COUNT(*) FROM campaign_events WHERE campaign_id = :id GROUP BY event_type
        ...

    async def list_campaigns(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Campaign], int]:
        ...

    # --- event methods ---

    async def record_event(self, tenant_id: int, campaign_id: int, event_type: str, user_id: int, payload: dict | None = None) -> CampaignEvent:
        ...

    async def get_user_events(self, user_id: int, tenant_id: int, event_type: str | None = None) -> list[CampaignEvent]:
        ...

    async def setup_trigger(self, tenant_id: int, campaign_id: int, trigger_rule: dict) -> Campaign:
        ...
```

每个方法：
- 有 `tenant_id` 参数并在 SQL 中 `WHERE tenant_id = :tenant_id`
- 找不到资源抛 `NotFoundException`
- 状态冲突抛 `ConflictException`（如重复 launch）
- 返回 ORM 对象，不调用 `.to_dict()`
- 使用 `await self.session.execute(select(...).where(...))` 风格

**完成判定**：`PYTHONPATH=src ruff check src/services/marketing_service.py` exit 0

---

### Step 3: 补充 CampaignEvent ORM model（如 #456 未创建）

```python
# src/db/models/campaign_event.py
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class CampaignEvent(Base):
    __tablename__ = "campaign_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

注意：列名用 `payload` 而非 `metadata`，用 `occurred_at` 记录时间而非 `created_at` 避免歧义。

**完成判定**：`PYTHONPATH=src python -c "from db.models.campaign_event import CampaignEvent; print('OK')"` exit 0

---

### Step 4: 生成 Alembic migration（如 model 为新建）

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
cd /Users/yihuazhuo/Desktop/git/github/agent-job && alembic upgrade head
alembic revision --autogenerate -m "create campaign and campaign_event tables"
# 手动修正：sa.JSON → sa.JSONB，DateTime 加 timezone=True
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

生成文件后检查 `alembic/versions/<id>_create_campaign_and_campaign_event_tables.py`：
- `campaigns` 表有 `tenant_id` 索引
- `campaign_events` 表有 `tenant_id`、`campaign_id`、`user_id`、`event_type` 索引
- JSON 列用 `JSONB` 而非 `JSON`

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次 exit 0

---

### Step 5: 创建单元测试 `tests/unit/test_marketing_service.py`

参考 `tests/unit/conftest.py` 的 MockState + make_mock_session 模式：

```python
# tests/unit/test_marketing_service.py
import pytest
from tests.unit.conftest import MockState, make_mock_session, MockRow
from services.marketing_service import MarketingService

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([...handlers...])

@pytest.fixture
def svc(mock_db_session):
    return MarketingService(mock_db_session)

class TestCreateCampaign:
    async def test_creates_campaign(self, svc, mock_db_session):
        # arrange: 准备 mock state
        # act
        result = await svc.create_campaign(tenant_id=1, name="Q2 Promo")
        # assert
        assert result.name == "Q2 Promo"

    async def test_raises_on_duplicate_name(self, svc):
        with pytest.raises(ValidationException):
            await svc.create_campaign(tenant_id=1, name="Q2 Promo")  # 重复

# 同理为 get_campaign / update_campaign / launch_campaign / pause_campaign /
# get_campaign_stats / list_campaigns / record_event / get_user_events / setup_trigger
# 各写 1-2 个用例
```

覆盖 10 个 service 方法，每个至少 1 个 happy-path 测试 + 1 个异常路径（`NotFoundException` 或 `ValidationException`）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥ 10 passed

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/marketing_service.py` → 0 errors
- [ ] `PYTHONPATH=src ruff check src/db/models/campaign.py src/db/models/campaign_event.py` → 0 errors（如文件存在）
- [ ] `PYTHONPATH=src mypy src/services/marketing_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥ 10 passed
- [ ] `PYTHONPATH=src python -c "from services.marketing_service import MarketingService; print(dir(MarketingService))"` 列出全部 10 个方法名
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #456 的 ORM model 未完成，marketing_service 无法 import Base model | 中 | 高 | 本板块先定义 stub model，后续 #456 合并后删除重复定义并更新 import |
| Alembic migration 与已有 migration 冲突（列重名） | 低 | 中 | 手动合并 conflict，删除重复列定义；migrate 前检查 `alembic history` |
| `record_event` 并发写入 campaign_events 表压力 | 低 | 低 | 依赖 PostgreSQL 行锁或 `asyncpg` 默认事务隔离；暂不引入消息队列 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/marketing_service.py tests/unit/test_marketing_service.py
git add src/db/models/campaign.py src/db/models/campaign_event.py
git add alembic/versions/
git add alembic/env.py
git commit -m "feat(marketing): add MarketingService with 10 methods and unit tests"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(marketing): implement MarketingService with campaign CRUD and event recording" --body "Closes #457

## Summary
- Add MarketingService (7 campaign + 3 event methods)
- Add Campaign and CampaignEvent ORM models
- Add unit tests (≥10 passed)

## Test plan
- [x] ruff check src/services/marketing_service.py → 0 errors
- [x] mypy src/services/marketing_service.py → 0 errors
- [x] pytest tests/unit/test_marketing_service.py -v → ≥ 10 passed"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — CRM service 规范范本
- 同类参考实现：[`src/services/sales_service.py`](../../src/services/sales_service.py) — 多 entity service 模式参考
- 父 issue / 关联：#450（营销自动化总 issue）、#456（Marketing API Router）
- 依赖 issue：#456
