# 存在感知服务 · Presence tracking service and WebSocket events

| 元数据 | 值 |
|---|---|
| Issue | #491 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0490 — WebSocket 连接管理器](./0490-add-redis-pub-sub-integration-for-cross-instance-event-distr.md) |
| 启用后赋能 | 所有业务服务（CustomerService、OpportunityService、TicketService 等） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

实时协作应用需要在用户浏览或修改资源时向其他在线用户广播存在感知（presence）信息。当前的 CRM 平台缺少这一层：用户无法感知谁正在同时查看或编辑某条客户/商机/工单记录。缺少存在感知导致并发编辑冲突无法被提前检测，影响数据一致性和协作体验。

这是 #80 的子任务，依赖 #490 提供的底层 WebSocket 连接管理器。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层设施，为将来实时协作功能（如"张三正在编辑此客户"）提供事件源。
- **开发者视角**：`src/websocket/events.py` 提供 `UserPresenceEvent` 模型和 `PresenceEventEmitter`；`ConnectionManager` 已就绪可直接使用；业务服务（CustomerService 等）在每次 mutation 后自动 emit presence join/leave 事件。

### 1.3 不做什么（剔除）

- [ ] 前端 WebSocket 消费层（订阅 UI 组件）— 由后续板块处理
- [ ] 持久化 presence 状态到数据库 — 仅存储于内存 dict（见 §4）
- [ ] 分布式多进程 presence 同步 — 单进程内存 dict + future Redis pub/sub
- [ ] 锁机制（乐观锁 / 悲观锁）— 不在本板块范围内
- [ ] 连接超时保活（heartbeat）— 由 #490 的 ConnectionManager 处理

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_presence_events.py -v` → ≥ 5 passed]
- [指标 2：`ruff check src/websocket/events.py src/services/customer_service.py` → 0 errors]
- [指标 3：3 个 service 文件（customer/ticket/opportunity）mutation 后均调用 `PresenceEventEmitter.emit()`，通过 mock 验证]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/customer_service.py` L? — 现有 CustomerService.mutation 方法，需在 return 前插入 emit 调用

TBD - 待验证：`src/services/ticket_service.py` L? — 同上

TBD - 待验证：`src/services/opportunity_service.py` L? — 同上

TBD - 待验证：`src/websocket/connection_manager.py` L? — #490 预期产出，ConnectionManager 应已有 `broadcast` / `send_personal` 方法

### 2.2 涉及文件清单

- 要改：
  - `src/services/customer_service.py` — 在 mutation 方法末尾插入 `PresenceEventEmitter.emit_join()`
  - `src/services/ticket_service.py` — 同上
  - `src/services/opportunity_service.py` — 同上
- 要建：
  - `src/websocket/events.py` — UserPresenceEvent 数据类 + PresenceEventEmitter
  - `src/models/presence.py` — Pydantic event schema（如采用 pydantic 序列化）
  - `tests/unit/test_presence_events.py` — 单元测试

### 2.3 缺什么

- [ ] `UserPresenceEvent` 模型：定义 join/leave 事件结构（user_id、resource_type、resource_id、tenant_id、action）
- [ ] `PresenceEventEmitter`：持有 `ConnectionManager` 引用，根据 resource+tenant 分发事件到对应 room
- [ ] In-memory presence dict：按 `resource_type:resource_id` 索引，记录当前在线用户列表
- [ ] CRUD service 集成：CustomerService / OpportunityService / TicketService 的 mutation 方法需 emit presence 事件
- [ ] 单元测试：验证 service mutation 调用正确的 emit 方法（使用 Mock）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/websocket/events.py` | UserPresenceEvent 数据类 + PresenceEventEmitter，单进程内存 room 管理，broadcast via ConnectionManager |
| `src/websocket/__init__.py` | events 模块导出 |
| `tests/unit/test_presence_events.py` | 验证 emit 调用、room 注册、broadcast 过滤的单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/customer_service.py` | mutation 方法末尾调用 `presence_emitter.emit_join(resource="customer", resource_id=id, ...)` |
| `src/services/ticket_service.py` | 同上，resource="ticket" |
| `src/services/opportunity_service.py` | 同上，resource="opportunity" |
| `src/websocket/connection_manager.py` | 如 #490 已提供基础实现，确认接口匹配（如需补充 `join_room`/`leave_room`） |

### 3.3 新增能力

- **Data class**：`UserPresenceEvent(action: Literal["join", "leave"], user_id: int, resource_type: str, resource_id: int, tenant_id: int, timestamp: datetime)`
- **Emitter**：`PresenceEventEmitter(connection_manager: ConnectionManager)` — `emit_join()` / `emit_leave()` 方法
- **In-memory state**：`dict[f"{resource_type}:{resource_id}", set[int]]` — 在线用户集合（单进程）
- **Service integration**：3 个 service 的 mutation 方法 emit presence 事件，router 层无感知
- **Unit test**：`test_presence_events.py` 覆盖 emit 调用、room 分组、tenant 隔离

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 in-memory dict 不选 Redis**：当前阶段单进程运行，presence 为"最佳努力"而非强一致；Redis 同步在后续分布式阶段再引入，避免过早复杂度
- **选 data class 不选 pydantic model**：presence event 是内部数据结构，无需 HTTP validation，用 `dataclasses` 减少依赖
- **选 ConnectionManager broadcast 不选逐个 send**：room 广播语义更清晰，O(N) 推送一次完成，避免遗漏

### 4.2 版本约束

无新增外部依赖（Python 内置 `dataclasses`、`datetime`、`enum`）。如后续引入 `aioprometheus` 等监控库，再补此表。

### 4.3 兼容性约束

- 多租户：presence room key 必须包含 `tenant_id`（格式 `f"{tenant_id}:{resource_type}:{resource_id}"`），确保跨租户隔离
- Service 错误：presence emit 失败（如 ConnectionManager 未就绪）应 **静默**（log+return，不抛异常，不阻塞业务逻辑）
- ConnectionManager 接口：要求 #490 提供 `broadcast(room: str, event: dict)` 方法

### 4.4 已知坑

1. **CRUD service mutation 内 raise 异常后 emit 未执行** → 规避：emit 调用放在 `try` 块之后（正常路径），异常由 router 全局 handler 处理，presence 事件在数据已提交后发送（最终一致性可接受）
2. **SQLAlchemy Base 子类列名不能用 `metadata`** → 规避：如 `UserPresenceEvent` 中需存储额外信息，字段命名用 `event_metadata` 而非 `metadata`（与 `Base.metadata` 冲突）
3. **Alembic autogen 会把 JSONB 写成 JSON、TIMESTAMPTZ 写成 DateTime** → 本板块不涉及 migration（presence 存内存），如后续需持久化则手动改 `sa.JSONB()` / `timezone=True`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 UserPresenceEvent 数据类和 PresenceEventEmitter

在 `src/websocket/events.py` 中定义事件模型和 emitter 类。

操作：
- a) 创建 `src/websocket/events.py`
- b) 定义 `UserPresenceEvent` dataclass（action: join/leave, user_id, resource_type, resource_id, tenant_id, timestamp）
- c) 定义 `PresenceEventEmitter` 类：持有 `_rooms: dict[str, set[int]]` 内存状态，注入 `ConnectionManager`
- d) 实现 `emit_join()` / `emit_leave()`：更新内存 room + 调用 `connection_manager.broadcast()`
- e) 创建 `src/websocket/__init__.py` 导出上述类
- f) 在 `src/websocket/connection_manager.py` 中确认 `broadcast(room: str, event: dict)` 方法存在，如缺失则补充

完成判定：`ruff check src/websocket/events.py` → 0 errors；文件 `src/websocket/events.py` 存在且含 `PresenceEventEmitter` 类定义

---

### Step 2: 在 CustomerService 中集成 presence emit

找到 CustomerService 的 mutation 方法（create/update/delete），在成功返回前插入 `presence_emitter.emit_join(...)` 调用。

操作：
- a) 在 `src/services/customer_service.py` 顶部 import `PresenceEventEmitter`（from src.websocket.events import PresenceEventEmitter）
- b) 在 `CustomerService.__init__` 中注入 emitter：`self.presence_emitter = PresenceEventEmitter(connection_manager)`（connection_manager 从外部传入或从全局工厂获取）
- c) 在 `create_customer`、`update_customer`、`delete_customer` 方法成功路径末尾添加 emit 调用
- d) emit 调用包裹在 `try/except` 中，失败时 log warning 不抛异常

示例代码（如有）：

```python
from src.websocket.events import PresenceEventEmitter

class CustomerService:
    def __init__(self, session: AsyncSession, connection_manager: ConnectionManager):
        self.session = session
        self.presence_emitter = PresenceEventEmitter(connection_manager)

    async def create_customer(self, tenant_id: int, data: CreateCustomerSchema) -> CustomerModel:
        customer = CustomerModel(...)
        self.session.add(customer)
        await self.session.flush()
        try:
            await self.presence_emitter.emit_join(
                user_id=data.owner_id,
                resource_type="customer",
                resource_id=customer.id,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.warning(f"Presence emit failed: {e}")
        return customer
```

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors；mock 测试 `test_presence_emitted_on_create` 验证 emit 被调用

---

### Step 3: 在 TicketService 中集成 presence emit

同上，在 `src/services/ticket_service.py` 的 mutation 方法（create_ticket / update_ticket / close_ticket）中添加 emit。

操作：
- a) Import `PresenceEventEmitter`
- b) 修改 `TicketService.__init__` 签名添加 `connection_manager: ConnectionManager` 参数（无默认值，遵循 CLAUDE.md 规则）
- c) 在 mutation 方法成功路径末尾 emit presence

**完成判定**：`ruff check src/services/ticket_service.py` → 0 errors

---

### Step 4: 在 OpportunityService 中集成 presence emit

同上，在 `src/services/opportunity_service.py` 中添加 emit。

操作：
- a) Import `PresenceEventEmitter`
- b) 修改 `OpportunityService.__init__` 添加 `connection_manager` 参数
- c) 在 mutation 方法成功路径末尾 emit

**完成判定**：`ruff check src/services/opportunity_service.py` → 0 errors

---

### Step 5: 编写单元测试 test_presence_events.py

在 `tests/unit/test_presence_events.py` 中编写覆盖率≥5 个测试用例的单元测试。

操作：
- a) 创建 `tests/unit/test_presence_events.py`
- b) 定义 `MockConnectionManager`（含 `broadcast` mock 方法）
- c) 测试 `PresenceEventEmitter.emit_join()` 更新内存 room 并调用 broadcast
- d) 测试 `emit_leave()` 从 room 中移除用户
- e) 测试 tenant 隔离：不同 tenant 的 room 互不干扰
- f) 测试 emit 失败（broadcast 抛异常）不传播到调用方
- g) 测试 CustomerService.create_customer 调用 emit_join（mock session + mock emitter）

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.websocket.events import UserPresenceEvent, PresenceEventEmitter

class TestPresenceEventEmitter:
    def test_emit_join_adds_user_to_room(self):
        conn_mgr = MagicMock()
        emitter = PresenceEventEmitter(conn_mgr)
        emitter.emit_join(user_id=1, resource_type="customer", resource_id=100, tenant_id=10)
        assert "10:customer:100" in emitter._rooms
        assert 1 in emitter._rooms["10:customer:100"]
        conn_mgr.broadcast.assert_called_once()

    def test_emit_leave_removes_user_from_room(self):
        conn_mgr = MagicMock()
        emitter = PresenceEventEmitter(conn_mgr)
        emitter.emit_join(user_id=1, resource_type="customer", resource_id=100, tenant_id=10)
        emitter.emit_leave(user_id=1, resource_type="customer", resource_id=100, tenant_id=10)
        assert emitter._rooms.get("10:customer:100", set()) == set()

    def test_tenant_isolation(self):
        conn_mgr = MagicMock()
        emitter = PresenceEventEmitter(conn_mgr)
        emitter.emit_join(user_id=1, resource_type="customer", resource_id=100, tenant_id=10)
        emitter.emit_join(user_id=2, resource_type="customer", resource_id=100, tenant_id=20)
        assert emitter._rooms["10:customer:100"] == {1}
        assert emitter._rooms["20:customer:100"] == {2}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_presence_events.py -v` → ≥ 5 passed

---

## 6. 验收

- [ ] `ruff check src/websocket/events.py src/services/customer_service.py src/services/ticket_service.py src/services/opportunity_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_presence_events.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed（如已有 CustomerService 单元测试，新增 mock 覆盖）
- [ ] 所有 service 的 `__init__` 签名包含 `connection_manager: ConnectionManager` 参数且无默认值
- [ ] `ruff check src/services/customer_service.py src/services/ticket_service.py src/services/opportunity_service.py` 无新增 lint 警告

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #490 的 ConnectionManager 接口与预期不符（broadcast 方法签名不同） | 中 | 中 | 在 `src/websocket/events.py` 中适配实际接口；或在 emitter 中添加 shim 层隔离差异，不修改 service 层 |
| service 层注入 connection_manager 导致大量调用处需传参（破坏性接口变更） | 中 | 高 | 改用全局单例 `get_connection_manager()` 工厂函数，service 内调用 `get_connection_manager()` 获取实例，避免修改所有 router 调用点 |
| presence emit 失败导致业务逻辑回滚（如 emit 在 flush 后但 router raise 前） | 低 | 低 | emit 包裹在 try/except 中，失败只 log 不抛异常；业务数据已在 DB 中，不受影响 |
| 单进程内存 dict 在多 worker（gunicorn --workers N）下不共享 | 高 | 中 | 记录为已知限制，后续引入 Redis pub/sub 前使用 sticky session 或 local-only 模式；不影响本板块验收 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/websocket/events.py src/websocket/__init__.py
git add src/services/customer_service.py src/services/ticket_service.py src/services/opportunity_service.py
git add tests/unit/test_presence_events.py
git commit -m "feat(platform): add presence tracking service and WebSocket events

- Add UserPresenceEvent model and PresenceEventEmitter in src/websocket/events.py
- Integrate presence emit into CustomerService, TicketService, OpportunityService
- Add unit tests for presence event emitter

Closes #491"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(platform): presence tracking service and WebSocket events" --body "Closes #491"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/websocket/connection_manager.py` — #490 产出，PresenceEventEmitter 依赖其 broadcast 接口
- 父 issue / 关联：#80（父）, #490（依赖）
- 第三方文档：[FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)（如需补充 broadcast 实现细节）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
