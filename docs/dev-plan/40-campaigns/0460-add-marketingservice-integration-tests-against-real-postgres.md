# MarketingService Integration Tests · Add real-DB integration tests for MarketingService

| 元数据 | 值 |
|---|---|
| Issue | #460 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 板块名不可用（#459尚未落地），以 #450 为父 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`MarketingService`（`src/services/marketing_service.py`）底层使用 SQLAlchemy async ORM，每次 `session.flush()` 后对象即为 ORM托管实体。对这些实体的 lazy-loading、关联对象的 cascade delete、tenant_id 过滤、事务边界的真实验证只能来自 real Postgres — mock 无法覆盖这类行为。现有的 `test_marketing_integration.py` 已实现了 campaign CRUD、tenant isolation、launch/sent_at 填写的部分覆盖，但 **record_event / get_user_events**（活动事件流）和 **setup_trigger**两条还未覆盖，且 list pagination 只写了一半。

Issue #460 要求在已有测试基础上实现完整覆盖（create+retrieve、status 更新含 launch/pause、record+fetch events、list pagination 完整触发 setup），确保所有 integration tests 对 real DB 全绿。

### 1.2 做完后

- **用户视角**：「无用户可见变化 — 纯测试层」
- **开发者视角**：`tests/integration/test_marketing_integration.py` 完整覆盖 `MarketingService` 所有 public 方法，含事件流 tenant隔离验证，可作为 regression guard。

### 1.3 不做什么（剔除）

- [ ] 不改造 `MarketingService`、`CampaignModel` 或 `CampaignEventModel` 的业务逻辑
- [ ] 不添加 router 层测试（留待 router专项）
- [ ] 不覆盖 `get_campaign_stats`（它依赖 `sent_count`/`open_count`/`click_count`，在 event record 测试中间接覆盖即可）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_marketing_integration.py -v` → 7 passed（含新增的 test_record_event、test_get_user_events、test_setup_trigger、test_events_tenant_isolation）
- `ruff check tests/integration/test_marketing_integration.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`tests/integration/test_marketing_integration.py`](../../../tests/integration/test_marketing_integration.py) L{1}-{L220}

```{1}:{30}:tests/integration/test_marketing_integration.py
import uuid
import pytest
from models.marketing import CampaignStatus, CampaignType, TriggerType
from pkg.errors.app_exceptions import NotFoundException
from services.marketing_service import MarketingService
from services.user_service import UserService

@pytest.mark.integration
class TestMarketingServiceIntegration:
    async def _seed_user(self, async_session, tenant_id: int) -> int:
        user_svc = UserService(async_session)
        suffix = uuid.uuid4().hex[:8]
        reg = await user_svc.create_user(
            username=f"mktuser_{suffix}",
            email=f"mkt_{suffix}@example.com",
            password="Test@Pass1234",
            tenant_id=tenant_id,
        )
        return reg.id
```

### 2.2 涉及文件清单

- 要改：
  - [`tests/integration/test_marketing_integration.py`](../../../tests/integration/test_marketing_integration.py) — 新增 test_record_event / test_get_user_events / test_setup_trigger / test_events_tenant_isolation 四个测试方法- 要建：无（新文件）

### 2.3 缺什么

- [ ] `test_record_event` —覆盖 `MarketingService.record_event()`，验证事件写入 event 表并正确更新 campaign.sent_count / open_count / click_count
- [ ] `test_get_user_events` — 覆盖 `MarketingService.get_user_events()`，验证同一个 customer_id 在多 event 时按 created_at 降序返回
- [ ] `test_setup_trigger` — 覆盖 `MarketingService.setup_trigger()`，验证 trigger_type + 可选 trigger_days 写入 campaign 表
- [ ] `test_events_tenant_isolation` — 验证事件记录按 tenant_id 隔离，跨 tenant `get_user_events` 返回空
- [ ] `test_pause_campaign` —覆盖 `MarketingService.pause_campaign()`

---

## 3. 目标产物（终点）

### 3.1 新文件

|路径 | 用途 |
|------|------|
| 无 | 测试全在现有文件内扩展 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/integration/test_marketing_integration.py`](../../../tests/integration/test_marketing_integration.py) | 新增 5 个测试方法完整覆盖 record_event / get_user_events / setup_trigger / pause_campaign / events tenant isolation |

### 3.3 新增能力

- **Test coverage**：`test_record_event` → 验证 event写入并更新 counters
- **Test coverage**：`test_get_user_events` → 验证按 customer_id 过滤 +降序
- **Test coverage**：`test_setup_trigger` → 验证 trigger_type / trigger_days 持久化
- **Test coverage**：`test_events_tenant_isolation` → 验证事件 tenant 隔离
- **Test coverage**：`test_pause_campaign` → 验证 status→paused，get_campaign 取回值一致

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **直接操作 ORM session 而非 HTTP router**：行快、无网络开销、错误定位容易；router 层留专项测试。
- **seed user 而非 seed customer**：campaign.created_by 引用 `users.id`，integration conftest `_seed_customer` 依赖 `customers.id`，而测试中 `record_event(customer_id)` 需要一个有效的 `customers.id` ——因此需要同时 seed user（用于 created_by）和 customer（用于 customer_id）。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）；`get_user_events` 查询 `customer_id + tenant_id`，`record_event` 同时写入 campaign_id+tenant_id(customer 和 event 表都需要)。
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；测试直接访问 `.id`/`.status`/`.event_type` 等属性。
- Service错误抛 `AppException` 子类；测试用 `pytest.raises(NotFoundException)` 验证。
- Integration test conftest 为每个 test function 提供 `async_session`（function-scoped，测试间 TRUNCATE CASCADE）；`tenant_id` fixture 返回随机 int，跨 test 文件独立。

### 4.4 已知坑

1. **Integration conftest 在 module load 时 patch `get_db_session`** → 测试文件 top-level import 时 patch 已生效；不要在测试文件内重复 patch。
2. **customer_id seed 需要先创建 CustomerModel记录** → `record_event(customer_id=int)` 依赖 `customers.id` FK 存在；用 conftest `_seed_customer` fixture 而非直接写死数字。

---

## 5. 实现步骤（按顺序）

### Step 1: 在 test_marketing_integration.py 顶部添加 record_event 相关 imports

确认 `CampaignEventModel` 可从 `db.models.marketing` 获取（与 campaign model 同文件），确认 `pytest.raises` 已 import。

操作：
- a) 检查现有 import已有 `pytest`, `NotFoundException`, `uuid`
- b)确认 `record_event` 的 `customer_id` 参数依赖 `_seed_customer` fixture（需 import `CustomerService`）

完成判定：`ruff check tests/integration/test_marketing_integration.py` → 0 errors

### Step 2: 在 TestMarketingServiceIntegration 类末尾添加 test_record_event

在 `test_list_pagination` 方法后插入：

```python
async def test_record_event(self, db_schema, tenant_id, async_session):
    uid = await self._seed_user(async_session, tenant_id)
    customer_id = await _seed_customer(async_session, tenant_id)
    svc = MarketingService(async_session)
    suffix = uuid.uuid4().hex[:8]
    campaign = await svc.create_campaign(
        name=f"Event Test {suffix}",
        campaign_type=CampaignType.EMAIL,
        content="Body",
        created_by=uid,
        tenant_id=tenant_id,
        subject="Test",
    )
    cid = campaign.id
    assert campaign.sent_count == 0

    # record sent event
    sent_event = await svc.record_event(cid, customer_id, "sent", tenant_id)
    assert sent_event.event_type == "sent"
    assert sent_event.campaign_id == cid
    assert sent_event.customer_id == customer_id
    assert sent_event.tenant_id == tenant_id

    # record opened event
    opened_event = await svc.record_event(cid, customer_id, "opened", tenant_id)
    assert opened_event.event_type == "opened"

    # record clicked event
    clicked_event = await svc.record_event(cid, customer_id, "clicked", tenant_id)
    assert clicked_event.event_type == "clicked"

    # refresh and verify counters
    refreshed = await svc.get_campaign(cid, tenant_id=tenant_id)
    assert refreshed.sent_count == 1
    assert refreshed.open_count == 1
    assert refreshed.click_count == 1
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_marketing_inigration.py::TestMarketingServiceIntegration::test_record_event -v` →1 passed

### Step 3: 添加 _seed_customer helper 函数到文件顶部

在文件顶部 `uuid` import 后、`TestMarketingServiceIntegration` 类定义前添加：

```python
async def _seed_customer(async_session, tenant_id: int) -> int:
    """Create a customer and return its id."""
    customer_svc = CustomerService(async_session)
    result = await customer_svc.create_customer(
        data={"name": "MktCustomer", "email": f"mkt-cust-{uuid.uuid4().hex[:8]}@example.com"},
        tenant_id=tenant_id,
    )
    return result.id
```

并在文件顶部 import 中添加 `from services.customer_service import CustomerService`。

**完成判定**：`ruff check tests/integration/test_marketing_integration.py` →0 errors

### Step 4: 在类末尾添加 test_get_user_events

```python
async def test_get_user_events(self, db_schema, tenant_id, async_session):
    uid = await self._seed_user(async_session, tenant_id)
    customer_id = await _seed_customer(async_session, tenant_id)
    svc = MarketingService(async_session)
    suffix = uuid.uuid4().hex[:8]
    campaign = await svc.create_campaign(
        name=f"Events List Test {suffix}",
        campaign_type=CampaignType.EMAIL,
        content="Body",
        created_by=uid,
        tenant_id=tenant_id,
        subject="Test",
    )
    cid = campaign.id

    # record 3 events for the same customer
    await svc.record_event(cid, customer_id, "sent", tenant_id)
    await svc.record_event(cid, customer_id, "opened", tenant_id)
    await svc.record_event(cid, customer_id, "clicked", tenant_id)

    events = await svc.get_user_events(customer_id, tenant_id)
    assert len(events) == 3
    # must be ordered by created_at desc
    assert events[0].event_type == "clicked"
    assert events[1].event_type == "opened"
    assert events[2].event_type == "sent"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_marketing_integration.py::TestMarketingServiceIntegration::test_get_user_events -v` → 1 passed

### Step 5: 添加 test_setup_trigger

```python
async def test_setup_trigger(self, db_schema, tenant_id, async_session):
    uid = await self._seed_user(async_session, tenant_id)
    svc = MarketingService(async_session)
    suffix = uuid.uuid4().hex[:8]
    campaign = await svc.create_campaign(
        name=f"Trigger Test {suffix}",
        campaign_type=CampaignType.EMAIL,
        content="Body",
        created_by=uid,
        tenant_id=tenant_id,
        subject="Test",
    )
    cid = campaign.id

    updated = await svc.setup_trigger(
        cid,
        tenant_id=tenant_id,
        trigger_type=TriggerType.CUSTOM,
        trigger_days=3,
    )
    assert updated.trigger_type == TriggerType.CUSTOM.value
    assert updated.trigger_days == 3

    fetched = await svc.get_campaign(cid, tenant_id=tenant_id)
    assert fetched.trigger_type == TriggerType.CUSTOM.value
    assert fetched.trigger_days == 3
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_marketing_integration.py::TestMarketingServiceIntegration::test_setup_trigger -v` → 1 passed

### Step 6: 添加 test_events_tenant_isolation 和 test_pause_campaign

```python
async def test_events_tenant_isolation(self, db_schema, tenant_id, async_session):
    uid = await self._seed_user(async_session, tenant_id)
    customer_id = await _seed_customer(async_session, tenant_id)
    svc = MarketingService(async_session)
    suffix = uuid.uuid4().hex[:8]
    campaign = await svc.create_campaign(
        name=f"Isolation {suffix}",
        campaign_type=CampaignType.EMAIL,
        content="Body",
        created_by=uid,
        tenant_id=tenant_id,
        subject="Test",
    )
    cid = campaign.id
    await svc.record_event(cid, customer_id, "sent", tenant_id)

    wrong_tid = tenant_id + 9999
    events_wrong = await svc.get_user_events(customer_id, wrong_tid)
    assert len(events_wrong) == 0

async def test_pause_campaign(self, db_schema, tenant_id, async_session):
    uid = await self._seed_user(async_session, tenant_id)
    svc = MarketingService(async_session)
    suffix = uuid.uuid4().hex[:8]
    campaign = await svc.create_campaign(
        name=f"Pause Test {suffix}",
        campaign_type=CampaignType.EMAIL,
        content="Body",
        created_by=uid,
        tenant_id=tenant_id,
        subject="Test",
    )
    cid = campaign.id
    assert campaign.status == CampaignStatus.DRAFT.value

    paused = await svc.pause_campaign(cid, tenant_id=tenant_id)
    assert paused.status == CampaignStatus.PAUSED.value

    fetched = await svc.get_campaign(cid, tenant_id=tenant_id)
    assert fetched.status == CampaignStatus.PAUSED.value
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_marketing_integration.py::TestMarketingServiceIntegration::test_events_tenant_isolation tests/integration/test_marketing_integration.py::TestMarketingServiceIntegration::test_pause_campaign -v` → 2 passed

### Step 7: 运行完整 test file 并确认全绿

```
PYTHONPATH=src pytest tests/integration/test_marketing_integration.py -v
```

预期：`N passed`（原有6 个 + 新增 5 个 =11 passed）。

**完成判定**：`ruff check tests/integration/test_marketing_integration.py` → 0 errors 且 pytest 输出不含 FAILED

---

## 6. 验收

- [ ] `ruff check tests/integration/test_marketing_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_marketing_integration.py -v` → 11 passed（含新增 5 个 test）
- [ ] 新增 `test_record_event` → passed- [ ] 新增 `test_get_user_events` → passed- [ ] 新增 `test_setup_trigger` → passed
- [ ] 新增 `test_events_tenant_isolation` → passed
- [ ] 新增 `test_pause_campaign` → passed

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `_seed_customer` fixture 在 conftest 中定义，但 test file需直接调用 `_seed_customer`（非 fixture）时找不到 | 低 | 中 | 将 `_seed_customer` 改为文件级普通 async 函数，依赖 `async_session` 参数传入，与现有 `_seed_user` 模式一致 |
| customer_id 在 record_event 时 FK约束失败（customer记录不存在） | 中 | 高 | 在测试 setup阶段确保 `_seed_customer` 在所有 event 测试中首先执行 |
| Docker Postgres 未启动导致测试 skip | 低 | 中 | PR CI 配置 `DATABASE_URL`；本地开发者需先 `docker compose -f configs/docker-compose.test.yml up -d test-db` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/integration/test_marketing_integration.py
git commit -m "test(integration): add missing MarketingService integration tests (#460)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add MarketingService integration tests against real PostgreSQL (#460)" --body "Closes #460"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/integration/test_tickets_integration.py`](../../../tests/integration/test_tickets_integration.py) — `_seed_customer` / `_seed_user` helper模式
- 父 issue / 关联：#450（营销服务完整实现父 issue）、#459（MarketingService CRUD integration tests 基线）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
