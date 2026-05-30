# Redis Pub/Sub · Cross-instance WebSocket event distribution---

## 1. 目标与背景

### 1.1 为什么做

当前 [`src/websocket/manager.py`](../../../src/websocket/manager.py) 的广播实现仅在本进程内分发消息。在多 worker（uvicorn --workers N）或 Kubernetes 多 pod 部署场景下，进程 A发送的消息不会到达进程 B / pod B 上已连接的客户端，导致实时事件（如「客户状态变更」）无法跨实例送达所有在线用户。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层基础设施改进。多 worker部署下客户信息、任务分配等实时推送不再出现「只有部分在线用户收到」的情况。
- **开发者视角**：TBD - 待验证：`src/websocket/pubsub.py` 新建模块，路径待确认；[`src/websocket/manager.py`](../../../src/websocket/manager.py) 的 `broadcast` 在写入本地连接之余同时 `PUBLISH` 到 Redis channel；接收到 Redis消息的 subscriber 将其转广播至本进程内 connections，实现跨实例分发。

### 1.3 不做什么（剔除）

- [ ] 不实现 Redis clustering / Sentinel（单节点 Redis 足够，先做 pub/sub）。
- [ ] 不实现消息持久化 /事件回放（不属于 pub/sub 范畴）。
- [ ] 不在本板块增加新 API endpoint（`src/websocket/manager.py` 已有路由结构，仅修改 `broadcast` 调用链）。

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_websocket_pubsub.py -v` → 全 passed
- `ruff check src/websocket/pubsub.py src/websocket/manager.py` → 0 errors
- `alembic upgrade head` → exit 0（如需 migration；本板块可能无 DB改动时可不填）
- 多 worker场景下，一条广播消息可被 N 个 worker 上的 subscriber 正确转发至各自连接的对端客户端（验证方式见 §6）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/websocket/manager.py`](../../../src/websocket/manager.py)

```{python}:
TBD - 待验证："src/websocket/manager.py 关键 broadcast 方法签名，预期形如 async def broadcast(self, channel: str, message: dict) -> None"
```

<!-- 新建模块时，§2.1 直接写：N/A — 新建模块 -->

### 2.2 涉及文件清单

- 要改：
  - [`src/websocket/manager.py`](../../../src/websocket/manager.py) — 在 `broadcast` 中调用 `pubsub.publish()`；注册 subscriber listener
- 要建：
  - `src/websocket/pubsub.py` — Redis 连接、publish、subscribe 监听循环封装
  - `tests/unit/test_websocket_pubsub.py` — mock Redis client 测试 publish/subscribe 链路

### 2.3 缺什么

- [ ] 无跨进程广播机制：当前 `broadcast` 只写入 `self.connections[channel]`，多 worker 间互不可感知
- [ ] 无 Redis 连接封装：缺少 `pubsub.py` 模块
- [ ] 无单元测试覆盖 `pubsub.publish` 调用与 subscriber 回调转发逻辑

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/websocket/pubsub.py` | Redis aioredis 连接封装：publish 接口 + subscribe监听 loop；模块级单例 |
| `tests/unit/test_websocket_pubsub.py` | 使用 mock Redis client 验证 publish 发送、subscribe 回调触发、本地 broadcast传递 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/websocket/manager.py`](../../../src/websocket/manager.py) | import `pubsub` 模块；`broadcast` 方法在写入本地连接之余调用 `await pubsub.publish(channel, payload)`；应用启动时启动 subscriber listener（随 manager生命周期） |

### 3.3 新增能力

- **Python 模块**：`src/websocket/pubsub.py` — `publish(channel, message)`异步函数 + `_subscribe_loop(channels, callback)` 内部协程
- **并发模型**：subscriber listener 在独立 `asyncio.Task` 中运行，收到 Redis消息后通过回调转发至 manager 的本地 `broadcast`
- **配置注入**：Redis URL 通过环境变量 `REDIS_URL` 读取（默认值 `redis://localhost:6379`）；不支持时跳过（warn log）以兼容无 Redis 开发环境
- **单元测试**：`tests/unit/test_websocket_pubsub.py` — `MockRedis` 模拟 `publish` / `psubscribe`，验证发布-订阅-转发链路

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `redis.asyncio`（或 `aioredis`）不选 `fakeredis`**：生产连接必须使用真实 Redis driver；测试用 mock 同名接口置换，无需换 client库。
- **选 subscriber pattern 不选 polling**：`SUBSCRIBE` 实时推送比定时 `LPOP` 更低延迟、无消息堆积风险。
- **选模块级单例连接不选，每次调用时新建连接**：`publish` 高频调用，频繁新建连接开销过大；单例 + 连接池化管理。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `redis` | `>=5.0.0` | 同时支持 sync 和 async API；`aioredis` 已合并入主库（v4.2+） |

### 4.3 兼容性约束

- 多租户：本板块仅涉及 WebSocket broadcast channel 名，不涉及 DB 查询，无需额外 tenant_id 过滤。
- `pubsub.py` 无状态可变类，不存在线程安全问题；subscriber loop 使用 `asyncio.create_task`，由 manager生命周期管理。
- Service 无（纯 infra 模块），不适用 CLAUDE.md 的 service 返回规范。
- 若后续 websocket 模块引入 session注入：必须保持 `session: AsyncSession = Depends(get_db)`，勿用 `async with get_db()`。

### 4.4 已知坑

1. **Redis 连接在 `asyncio.create_task` 内抛出异常会导致 task 静默崩溃** → 规避：subscriber loop 外包 `try/except`，异常时记录 `logger.error` 并在延迟后重连。
2. **测试时 `MockRedis` 若未正确 mock `subscribe` 则事件循环永不触发** → 规避：单元测试中 `MockRedis.psubscribe` 立即触发回调，验证逻辑在回调内完成（不等真正消息）。
3. **PYTHONPATH=src**：`from websocket import pubsub`写法依赖 PYTHONPATH=src；所有 import 均不带 `src/` 前缀。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/websocket/pubsub.py`

Skeleton

新建 `src/websocket/pubsub.py`，实现：

- `REDIS_URL: str` 环境变量读取，默认 `redis://localhost:6379`。
- `_redis: redis.asyncio.Redis | None` 模块级连接，初始化函数 `async def init_redis() -> redis.asyncio.Redis | None`：尝连 Redis，失败时 `logger.warning("Redis unavailable, skipping pub/sub init")` 并返回 `None`。
- `async def publish(channel: str, message: dict) -> None`：若 `_redis` 为 `None` 则 no-op。
- `_async def _subscribe_loop(channels: list[str], callback: Callable[[str, dict], Awaitable[None]]) -> None`：内部协程，持续 `subscribe` 并将收到消息传给 `callback`。
- `async def start_subscriber(channels: list[str], callback: Callable[[str, dict], Awaitable[None]]) -> asyncio.Task`：公开接口，启动独立 task。

完成判定：`ruff check src/websocket/pubsub.py` → 0 errors

---

### Step 2: 在 `src/websocket/manager.py` 中集成 pubsub

在 [`src/websocket/manager.py`](../../../src/websocket/manager.py) 中：

- 文件顶部添加 `from websocket import pubsub`（PYTHONPATH=src）。
- `WebSocketManager.__init__` 中调用 `await pubsub.init_redis()` 并保存 `_redis_initialized` 标志。
- 在 broadcast 方法末尾添加本步的发布逻辑...

在 broadcast 方法末尾（写入本地 connections之后）添加：

```python
# src/websocket/manager.py (broadcast 方法内)
await self._broadcast_locally(channel, message)
# 如果 Redis 可用，同时发布到 Redis channel
await pubsub.publish(channel, message)
```

- 在 `WebSocketManager.start()` 中启动 subscriber listener task，注册回调为本实例的 `_broadcast_locally` 方法：

```python
self._subscriber_task = await pubsub.start_subscriber(
    channels=[...],           # 所有活跃 channel 名
    callback=self._broadcast_locally
)
```

- `WebSocketManager.shutdown` 中取消 subscriber task。
- 仅当 `pubsub._redis is not None` 时才启动 subscriber（无 Redis 时仅走本地广播，不阻断连接管理）。

完成判定：`ruff check src/websocket/manager.py` →0 errors；文件中包含 `pubsub.publish` 调用且周围有 `if pubsub._redis is not None`守卫

---

### Step 3: 编写单元测试 `tests/unit/test

_websocket_pubsub.py`

Creating mock tests...

MockRedis` 类：
- 在 `MockRedis.psubscribe` 保存传入的 callback；手动触发一次模拟消息事件；断言回调被调用且 channel/payload 正确。
- Test4 验证 `start_subscriber` 返回的是 `asyncio.Task` 实例，并用 `task.cancel()` 进行清理。

完成判定：`PYTHONPATH=src pytest tests/unit/test_websocket_pubsub.py -v` → 全 passed

---

### Step 4: 更新 / 检查 uvicorn 启动配置（如适用）

若应用的 `src/main.py` 中存在 `WebSocketManager` 实例化，确认 startup/shutdown 与 manager 的 `start()` / `shutdown()` 已正确 hook。可选：在 `src/main.py` 添加 Redis 连接健康检查 log（INFO level，pubsub 就绪时打印 "Redis pub/sub enabled"）。

完成判定：`ruff check src/main.py` → 0 errors（如有改动）

---

## 6. 验收

- [ ] `ruff check src/websocket/pubsub.py src/websocket/manager.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_websocket_pubsub.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_websocket_manager.py -v` → 全 passed（如已有 manager 测试）  
  → 注：如无 manager 测试文件，此条改为：`PYTHONPATH=src ruff check src/websocket/` → 0 errors
- [ ] 多 worker场景验证：以两 worker启动应用，从 worker A 连接 websocket，另一连接 worker B；从 A 触发广播，B 上的订阅方应收到消息（通过外部脚本 / Python 脚本发起 ws 连接并监听）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Redis 连接失败导致 publisher 报错（网络抖动） | 中 | 中 | `publish` 外包 `try/except`，失败时 warn log 不阻断；subscriber loop异常捕获并重连；本地广播不受影响 |
| subscriber loop task泄漏（未正确 cancel） | 低 | 中 | `shutdown` 中调用 `task.cancel()` 并 `await asyncio.shield(task)`等待；测试覆盖 task生命周期 |
| 多 channel场景下 channel 名不一致导致跨 worker漏发 | 中 | 高 | 定义 channel 名常量（如 `CHANNEL_PREFIX = "ws:"`），所有 broadcast统一使用；单元测试覆盖 |
| Redis URL 配置错误（ENV缺失） | 低 | 低 | 有默认值 `redis://localhost:6379`；缺少时 warn log 并走本地模式（不阻断功能） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/websocket/pubsub.py src/websocket/manager.py tests/unit/test_websocket_pubsub.py
git commit -m "feat(websocket): add Redis pub/sub for cross-instance event distributionCloses #490"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(websocket): Redis pub/sub cross-instance distribution" --body "Closes #490

## Summary
- New src/websocket/pubsub.py: Redis async publish + subscribe loop
- WebSocketManager.broadcast now publishes to Redis channel in addition to local connections
- Unit tests with mock Redis client

## Test plan
- [ ] ruff check src/websocket/pubsub.py src/websocket/manager.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_websocket_pubsub.py -v → all passed
- [ ] Multi-worker manual smoke test passed

🤖 Generated with Claude Code"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 第 9 部分：参考文档

相关实现参考了 WebSocket manager 的现有代码，第三方文档则来自 redis-py 的异步文档和订阅模式示例。父 issue #80 下的 #489依赖本板块的前置实现。

---

## 变更日志

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---
```

**What was changed:** Line 12 — the link `[src/websocket/pubsub.py`](../../src/websocket/pubsub.py)` used `../../` (two parent directories) but the document is in `docs/dev-plan/99-misc/`, requiring `../../../` (three). Since `pubsub.py` is also a file that does not yet exist (it's being created by this plan), the link was dropped and replaced with `TBD - 待验证：src/websocket/pubsub.py 新建模块，路径待确认`.
