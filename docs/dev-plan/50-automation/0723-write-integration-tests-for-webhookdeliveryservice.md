# WebhookDeliveryService · 编写集成测试

| 元数据 | 值 |
|---|---|
| Issue | #723 |
| 分类 | 10-test |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0722-write-webhook-service](0722-write-webhook-service.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

WebhookDeliveryService 已由 #722 实现完毕，但目前仅有单元测试覆盖，缺乏真实的端到端数据库交互验证。集成测试需要覆盖 webhook 注册→列表→删除的生命周期、投递成功/失败重试逻辑、最大重试次数永久失败判定、以及多租户隔离——这些行为无法在纯 mock 的单元测试环境中充分验证。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯测试补充
- **开发者视角**：获得 `tests/integration/test_webhook_service_integration.py`，覆盖 WebhookDeliveryService 的所有关键数据库交互路径；CI gate 确保所有集成测试通过后才允许合入

### 1.3 不做什么（剔除）

- [ ] 不实现新的 WebhookDeliveryService 方法（由 #722 完成）
- [ ] 不做性能/负载测试
- [ ] 不做真实的 HTTP 外发（httpx.AsyncClient.post 统一 mock）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → `5 passed`（或更多）
- `ruff check src/services/webhook_service.py` → 0 errors
- 所有 5 个测试场景均覆盖：CRUD、投递成功、投递失败重试、最大重试永久失败、租户隔离

---

## 2. 当前现状（起点）

### 2.1 现有实现

WebhookDeliveryService 已由 #722 交付，位于 `src/services/webhook_service.py`。其核心方法包括：

- `register_webhook(session, tenant_id, url, event_type, secret)` → 注册新 webhook
- `list_webhooks(session, tenant_id, page, page_size)` → 列表查询
- `delete_webhook(session, webhook_id, tenant_id)` → 删除
- `deliver_webhook(session, webhook_id, payload)` → 执行投递（含重试逻辑）

关键 ORM 模型：`WebhookDeliveryAttempt` / `WebhookDeliveryRecord`（见 `src/db/models/webhook.py`，具体文件名待验证）。

### 2.2 涉及文件清单

- 要改：
  - 无（本次仅新增测试文件，不修改已有代码）
- 要建：
  - `tests/integration/test_webhook_service_integration.py` — WebhookDeliveryService 集成测试
  - `tests/integration/conftest.py` — 若需补充 webhook 相关 fixture（待确认是否已有）

### 2.3 缺什么

- [ ] 缺少 `tests/integration/test_webhook_service_integration.py` — WebhookDeliveryService 集成测试文件
- [ ] 缺少对 `WebhookDeliveryService.deliver_webhook` 在真实 DB session 下的重试逻辑验证
- [ ] 缺少多租户隔离的集成测试覆盖
- [ ] CI 缺少 webhook service 集成测试 gate

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_webhook_service_integration.py` | WebhookDeliveryService 集成测试（5 个场景） |
| `tests/integration/conftest.py` | 若 webhook 专用 seed fixture 缺失则新建；否则复用现有 |

### 3.2 修改文件

无修改文件 — 本次为纯新增测试文件。

### 3.3 新增能力

- **集成测试**：`test_webhook_crud` — register → list → delete → verify gone
- **集成测试**：`test_deliver_success_inserts_record` — mock httpx 返回 200，验证 DB 记录写入
- **集成测试**：`test_deliver_failure_sets_next_retry_at` — mock httpx 返回 500 或抛异常，验证 `next_retry_at` 被设置
- **集成测试**：`test_deliver_max_retries_sets_permanent_failure` — 验证达到最大重试次数后 `status=permanent_failure`
- **集成测试**：`test_tenant_isolation` — 两个 tenant 的 webhook 互不可见
- **CI gate**：`pytest tests/integration/test_webhook_service_integration.py` 进入 CI 流程

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `unittest.mock.patch` 统一 mock httpx.AsyncClient.post，不选 pytest-https彼岸**：原因：`httpx.AsyncClient.post` 是在 service 方法内部实例化的，必须在调用路径上 patch；pytest-https彼岸 适合端到端测试，不适合单 service 级别的集成测试
- **选 `db_schema` fixture 而非手动 create_all/drop_all**：原因：`db_schema` 由 `tests/integration/conftest.py` 提供，自动管理 truncate cascade，隔离性好

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | `>=0.25.0` | #722 已引入，测试环境需同版本 |
| `pytest` | `>=7.4.0` | 支持 `pytest.mark.integration` |

### 4.3 兼容性约束

- 多租户：每个查询必须 `WHERE tenant_id = :tenant_id`（测试 `test_tenant_isolation` 验证此约束）
- Service 返回 ORM 对象；测试断言依赖 `.to_dict()` 序列化结果与 DB 记录对比
- 测试中不得直接 import 尚未定义的模型；若 `webhook.py` 模型名不确定，引用时写 `WebhookDeliveryAttempt` 并在测试文件顶部注明「模型名待与 #722 确认」

### 4.4 已知坑

1. **httpx.AsyncClient 在 service 内实例化导致 patch 失效** → 规避：`with unittest.mock.patch("httpx.AsyncClient.post") as mock_post:`，patch 路径为 `src.services.webhook_service.AsyncClient.post`（具体 import 路径待与 #722 确认）
2. **多租户 fixture 隔离** → 规避：每个测试函数接收 `tenant_id` fixture，第二个 tenant 通过 `async_session` 注入不同 tenant_id 创建 webhook；`list_webhooks` 验证 A tenant 不含 B tenant 的记录
3. **DB truncate cascade 与 FK 顺序** → 规避：`db_schema` fixture 已处理 cascade；测试中手动 `await session.execute(text("DELETE FROM webhook_delivery_attempts"))` 仅作额外安全清理，不依赖删除顺序

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `tests/integration/test_webhook_service_integration.py`

创建测试文件，从 `tests/integration/conftest.py` 导入 `db_schema`、`tenant_id`、`async_session` fixtures。导入 `WebhookDeliveryService`（路径待与 #722 确认，预期为 `src.services.webhook_service`）。

定义 5 个测试方法，全部标记 `@pytest.mark.integration`：

```python
import pytest
from unittest.mock import AsyncMock, patch

from src.services.webhook_service import WebhookDeliveryService

@pytest.mark.integration
class TestWebhookServiceIntegration:
    async def test_webhook_crud(self, db_schema, tenant_id, async_session):
        svc = WebhookDeliveryService(async_session)
        webhook = await svc.register_webhook(tenant_id, "https://example.com/hook", "deal.created", "secret123")
        assert webhook.id is not None

        webhooks, total = await svc.list_webhooks(tenant_id)
        assert total >= 1

        await svc.delete_webhook(webhook.id, tenant_id)

        with pytest.raises(NotFoundException):
            await svc.get_webhook(webhook.id, tenant_id)
```

**完成判定**：`ls tests/integration/test_webhook_service_integration.py` → 文件存在 / `ruff check tests/integration/test_webhook_service_integration.py` → 0 errors

### Step 2: 实现 `test_deliver_success_inserts_record`

```python
    async def test_deliver_success_inserts_record(self, db_schema, tenant_id, async_session):
        svc = WebhookDeliveryService(async_session)
        webhook = await svc.register_webhook(tenant_id, "https://example.com/hook", "deal.created", "secret123")

        with patch("src.services.webhook_service.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = AsyncMock(status_code=200)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await svc.deliver_webhook(webhook.id, {"event": "deal.created"}, tenant_id)

        assert result.status == "success"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py::TestWebhookServiceIntegration::test_deliver_success_inserts_record -v` → `1 passed`

### Step 3: 实现 `test_deliver_failure_sets_next_retry_at`

```python
    async def test_deliver_failure_sets_next_retry_at(self, db_schema, tenant_id, async_session):
        svc = WebhookDeliveryService(async_session)
        webhook = await svc.register_webhook(tenant_id, "https://example.com/hook", "deal.created", "secret123")

        with patch("src.services.webhook_service.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = AsyncMock(status_code=500)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await svc.deliver_webhook(webhook.id, {"event": "deal.created"}, tenant_id)

        assert result.status == "failed"
        assert result.next_retry_at is not None
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py::TestWebhookServiceIntegration::test_deliver_failure_sets_next_retry_at -v` → `1 passed`

### Step 4: 实现 `test_deliver_max_retries_sets_permanent_failure`

模拟连续 5 次失败（第 5 次后永久失败），通过 patch 控制 `httpx.AsyncClient.post` 始终返回 500：

```python
    async def test_deliver_max_retries_sets_permanent_failure(self, db_schema, tenant_id, async_session):
        svc = WebhookDeliveryService(async_session)
        webhook = await svc.register_webhook(tenant_id, "https://example.com/hook", "deal.created", "secret123")

        with patch("src.services.webhook_service.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = AsyncMock(status_code=500)
            mock_client.return_value.__aenter__.return_value = mock_instance

            for i in range(5):
                await svc.deliver_webhook(webhook.id, {"event": "deal.created"}, tenant_id)

        records, _ = await svc.list_delivery_records(webhook.id, tenant_id)
        final_record = records[-1]
        assert final_record.status == "permanent_failure"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py::TestWebhookServiceIntegration::test_deliver_max_retries_sets_permanent_failure -v` → `1 passed`

### Step 5: 实现 `test_tenant_isolation`

使用两个不同 tenant_id 创建各自的 webhook，验证 `list_webhooks` 互不可见：

```python
    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        svc = WebhookDeliveryService(async_session)

        webhook_a = await svc.register_webhook(tenant_id, "https://a.com/hook", "deal.created", "secret")
        webhook_b = await svc.register_webhook(tenant_id + 1000, "https://b.com/hook", "deal.created", "secret")

        list_a, _ = await svc.list_webhooks(tenant_id)
        ids_a = [w.id for w in list_a]

        list_b, _ = await svc.list_webhooks(tenant_id + 1000)
        ids_b = [w.id for w in list_b]

        assert webhook_a.id in ids_a
        assert webhook_a.id not in ids_b
        assert webhook_b.id in ids_b
        assert webhook_b.id not in ids_a
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py::TestWebhookServiceIntegration::test_tenant_isolation -v` → `1 passed`

### Step 6: 验证全量通过

运行完整测试文件：

```bash
PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v
```

期望：`5 passed`（test_webhook_crud、test_deliver_success_inserts_record、test_deliver_failure_sets_next_retry_at、test_deliver_max_retries_sets_permanent_failure、test_tenant_isolation）。

同时运行 lint：

```bash
ruff check tests/integration/test_webhook_service_integration.py
```

**完成判定**：`pytest -v` → `5 passed` + `ruff check` exit 0

---

## 6. 验收

- [ ] `ruff check tests/integration/test_webhook_service_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v` → `5 passed`
- [ ] `test_webhook_crud` 覆盖 register→list→delete→verify gone 全路径
- [ ] `test_deliver_success_inserts_record` 验证 mock 200 时 DB 记录 status=success
- [ ] `test_deliver_failure_sets_next_retry_at` 验证 mock 500 时 next_retry_at 非空
- [ ] `test_deliver_max_retries_sets_permanent_failure` 验证第 5 次失败后 status=permanent_failure
- [ ] `test_tenant_isolation` 验证两个 tenant 的 webhook 互不可见

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| WebhookDeliveryService 的 patch 路径不正确（service 内 import 方式与预期不符） | 低 | 中 | 在测试文件顶部尝试多种 patch 路径（`httpx.AsyncClient.post`、`src.services.webhook_service.AsyncClient.post`），优先 CI 中确定正确路径；不影响其他功能 |
| #722 未完成导致 service 方法名/签名不确定 | 中 | 高 | 本次 PR 依赖 #722 合入；若 #722 交付延迟，在 0722 完成后重新生成测试文件 |
| DB migration 未包含 webhook 表（alembic 版本落后） | 低 | 高 | 运行 `alembic upgrade head` 确认；如失败则在 0722 或本板块补做 migration |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/integration/test_webhook_service_integration.py
git commit -m "test(integration): add webhook service integration tests"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#723): integration tests for WebhookDeliveryService" --body "Closes #723

## Summary
- Add 5 integration test cases for WebhookDeliveryService using db_schema/tenant_id/async_session fixtures
- test_webhook_crud: register→list→delete→verify gone
- test_deliver_success_inserts_record: mock httpx 200
- test_deliver_failure_sets_next_retry_at: mock httpx 500
- test_deliver_max_retries_sets_permanent_failure: 5 failures → permanent_failure
- test_tenant_isolation: two tenants cannot see each other's webhooks

## Test plan
- [x] ruff check tests/integration/test_webhook_service_integration.py
- [x] PYTHONPATH=src pytest tests/integration/test_webhook_service_integration.py -v → 5 passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在 docs/dev-plan/50-automation/0723-write-integration-tests-for-webhookdeliveryservice.md Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/integration/`](../../tests/integration/) — 现有集成测试文件结构参考
- 父 issue / 关联：#722（WebhookDeliveryService 实现）、#496（Webhook 功能总览）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
