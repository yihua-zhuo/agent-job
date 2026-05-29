# AI 自动化板块 · 将 AIService 接入 Agent Framework 并增强 Rate Limiting

| 元数据 | 值 |
|---|---|
| Issue | #617 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0625](0625-add-baseagent-abstract-class-and-agentregistry-singleton.md)（BaseAgent + AgentRegistry 基础设施）, [0627](0627-add-llmservice-with-multi-provider-support.md)（LLMService 多 provider 接口） |
| 启用后赋能 | 无（本次为终态实现） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `AIService.send_message` 调用的是确定性 stub `AIChatGateway._call_gateway`，没有真实 AI 推理能力。`src/agents/` 中已有 `BaseAgent` / `AgentRegistry` / `CoordinatorAgent`（#625/#626），`src/services/llm_service.py`（#627）即将提供统一的多 provider chat 接口。本次 issue 将两者接入 `AIService`，并增强速率限制——从进程内 in-memory dict 升级为 Redis-backed 分布式限流，支持多实例部署。

### 1.2 做完成后

- **用户视角**：`POST /api/v1/ai/chat` 背后由真实 LLM provider（OpenAI/Anthropic/MiniMax）驱动回复，回复质量显著提升；Rate limit 由 30 req/min 提升至可配置阈值并支持 Redis 分布式一致性。
- **开发者视角**：`AIService` 已接入 `LLMService`（via `AIChatGateway` 重构）和 `CoordinatorAgent`（via 新 agent 端点）；新增 `RateLimitService` 提供 `check_and_record(tenant_id, user_id, action)` 方法，返回剩余配额。

### 1.3 不做什么（剔除）

- [ ] 不在本次实现 `AgentRegistry` 的注册逻辑（#625 已落地，本次只调用已注册 agent）
- [ ] 不实现 `embed()` 方法（属于 #627）
- [ ] 不修改 `AIConversationModel` / `AIMessageModel` 的 schema（ORM 层保持不变）
- [ ] 不实现 API key 轮换或 provider fallback 逻辑（future issue）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ai_service.py -v` → ≥ 12 passed（含新增 WiredAgent 测试）
- `PYTHONPATH=src pytest tests/unit/test_ai_router.py -v` → ≥ 10 passed（含 Redis rate limit 测试）
- `ruff check src/services/ai_service.py src/internal/ai_gateway.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如需 migration）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/ai_service.py`](../../src/services/ai_service.py) L115-L163

```python
115:    async def send_message(
116:        self,
117:        conversation_id: int,
118:        message: str,
119:        tenant_id: int,
120:        user_id: int,
121:    ) -> AIResponse:
122:        """Store user message, call AI gateway with CRM context, store & return reply."""
123:        await self.get_conversation(conversation_id, tenant_id, user_id)
124:        now = datetime.now(UTC)
125:        user_msg = AIMessageModel(conversation_id=..., tenant_id=..., role="user", content=message, created_at=now)
126:        self.session.add(user_msg)
127:        await self.session.flush()
128:        messages = await self._build_message_history(conversation_id, tenant_id)
129:        context = await self._enrich_context(tenant_id, user_id)
130:        reply_response = await self.gateway.chat(messages, context)  # ← stub，替换为 LLMService
131:        assistant_msg = AIMessageModel(conversation_id=..., tenant_id=..., role="assistant", content=reply_response.reply, ...)
132:        self.session.add(assistant_msg)
133:        await self.session.flush()
134:        return reply_response
```

现有 Rate Limiter（进程内 in-memory）：[`src/api/routers/ai.py`](../../src/api/routers/ai.py) L28-L46

```python
28: _rate_limit_store: defaultdict[tuple[int, int], list[float]] = defaultdict(list)
29: _RATE_LIMIT_WINDOW = 60  # seconds
30: _RATE_LIMIT_MAX = 30  # requests
31:
32: def _check_rate_limit(tenant_id: int, user_id: int) -> None:
33:     now = time.time()
34:     window = _rate_limit_store[(tenant_id, user_id)]
35:     window[:] = [ts for ts in window if now - ts < _RATE_LIMIT_WINDOW]
36:     if len(window) >= _RATE_LIMIT_MAX:
37:         raise ValidationException("Rate limit exceeded")
38:     window.append(now)
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/ai_service.py`](../../src/services/ai_service.py) — 将 `gateway.chat()` 替换为调用 `LLMService`，注入 `CoordinatorAgent` 用于 agent 任务分发
  - [`src/internal/ai_gateway.py`](../../src/internal/ai_gateway.py) — 重构为 `LLMGateway`，调用 `LLMService.chat()` 而非 stub
  - [`src/api/routers/ai.py`](../../src/api/routers/ai.py) — 替换 in-memory rate limit 为 `RateLimitService`（Redis-backed），新增 agent 端点
  - [`tests/unit/test_ai_service.py`](../../tests/unit/test_ai_service.py) — 新增 WiredAgent 测试用例
  - [`tests/unit/test_ai_router.py`](../../tests/unit/test_ai_router.py) — 新增 Redis rate limit 测试用例
- 要建：
  - `src/services/rate_limit_service.py` — Redis-backed 速率限制 service
  - `tests/unit/test_rate_limit_service.py` — 单元测试
 - `alembic/versions/<id>_add_ai_rate_limit_indexes.py` — 可选，按需

### 2.3 缺什么

- [ ] `AIService` 未接入真实 LLM — `AIChatGateway` 是 stub，替换为 `LLMService` 需要依赖 #627 完成
- [ ] 无 Agent 接入点 — `CoordinatorAgent` 已存在于 `src/agents/coordinator.py`，但 AIService 无法调度它
- [ ] Rate limit 为进程内 in-memory — 多实例部署时不一致，且进程重启后状态丢失
- [ ] Rate limit 无法配置 per-tenant/per-action — 当前全局 30 req/min

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/rate_limit_service.py` | `RateLimitService`：Redis-backed sliding window rate limit，支持 per-tenant 配置，返回剩余配额 |
| `tests/unit/test_rate_limit_service.py` | 单元测试：mock Redis client，覆盖 happy-path、limit-exceeded、Redis-unavailable 三类场景 |
| `docs/dev-plan/50-automation/0617-wire-aiservice-to-agent-framework-and-add-rate-limiting.md` | 本文档 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/ai_service.py`](../../src/services/ai_service.py) | `__init__` 新增 `agent_registry: AgentRegistry | None` 参数；`send_message` 调用 `LLMGateway`（重构自 `AIChatGateway`），注入 CRM context；新增 `run_agent_task(task_type, params)` 方法 |
| [`src/internal/ai_gateway.py`](../../src/internal/ai_gateway.py) | 重构成 `LLMGateway`：持有 `LLMService` 实例（延迟初始化），`chat()` 方法调用 `llm_service.chat(messages, tenant_id, model?)`；保留 `AIResponse` dataclass |
| [`src/api/routers/ai.py`](../../src/api/routers/ai.py) | 替换 `_check_rate_limit` + `_rate_limit_store` 为 `RateLimitService` 实例；新增 `POST /api/v1/ai/agent` 端点（调度 CoordinatorAgent）；保留现有 `/chat`、`/conversation` 端点 |
| [`tests/unit/test_ai_service.py`](../../tests/unit/test_ai_service.py) | 新增 `TestWiredAgent` 测试类：mock `AgentRegistry`，验证 `run_agent_task` 正确 dispatch |
| [`tests/unit/test_ai_router.py`](../../tests/unit/test_ai_router.py) | 更新 rate limit 测试：mock `RateLimitService`；新增 `TestAgentEndpoint` 测试类 |

### 3.3 新增能力

- **Service method**：`AIService.__init__(self, session, gateway?, agent_registry?)` — 可选参数向后兼容
- **Service method**：`AIService.run_agent_task(self, task_type: str, params: dict, tenant_id: int) -> dict` — 通过 `AgentRegistry` 调度已注册 agent
- **Service method**：`RateLimitService.check_and_record(self, tenant_id: int, user_id: int, action: str) -> dict` — 返回 `{"allowed": bool, "remaining": int, "reset_at": float}`
- **API endpoint**：`POST /api/v1/ai/agent` → `{"task_type": "...", "params": {...}}` → `{"success": true, "data": {...}}`
- **重构**：`AIChatGateway` → `LLMGateway`，调用 `LLMService.chat()`（依赖 #627）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Redis sliding window 而不选 Token Bucket** — sliding window 提供更精确的瞬时并发控制；Token Bucket 更适合 burst 场景但实现更复杂。对于 CRM AI chat，sliding window 已足够。
- **选在 `RateLimitService` 中 handle Redis unavailable 为"allow through"（fail open）** — 下游 AI 服务的 rate limit 是保护层，不是业务正确性约束；Redis 故障时拒绝所有请求会导致所有用户不可用，而 allowed-through 只在短时间内失去保护。
- **选 `AIChatGateway` 重构为 `LLMGateway`（同一文件替换）而非新文件** — `AIChatGateway` 目前只有 `ai.py` 引用，重构成本低；`AIResponse` dataclass 保持不变，向后兼容已有测试。
- **选 agent 端点独立 `POST /api/v1/ai/agent` 而不扩展 `POST /chat`** — `/chat` 是面向终端用户的会话接口，agent dispatch 是内部操作，分离避免语义混淆。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `redis` (Python client) | `≥ 5.0` | async `redis.asyncio.Redis` 支持异步 sliding window；5.0 以下无 first-class async 支持 |
| `aioredis` / `redis.asyncio` | 内置于 `redis ≥ 5.0` | 不再需要独立 `aioredis` 包 |

### 4.3 兼容性约束

- Service Constructor：`AIService.__init__(self,session:AsyncSession,gateway?,agent_registry?)` — `gateway` 和 `agent_registry` 默认为 `None`，保持向后兼容
- Service错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），不返回 `ApiResponse.error()`
- Service 不调用 `.to_dict()`，序列化由 router 负责
- Multi-tenant：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`（已有，勿破坏）
- Rate limit key = `(tenant_id, user_id, action)` — 与现有 `(tenant_id, user_id)` 兼容，action 字段可选

### 4.4 已知坑

1. **Redis `SLINCR` command is not atomic on all Redis versions** → 规避：使用 Lua script 保证 check-and-increment 的原子性（单条 EVAL 命令），避免 race condition。
2. **`LLMService` is not yet merged when this issue is being implemented** → 规避：Step 1 中 `LLMGateway` 保留对 `AIChatGateway` stub 的 fallback；只有当 `LLMService` 导入成功时才使用它，否则 log warning 并回退到 stub。
3. **In-memory rate limit store is imported in router and tested via `test_ai_router.py`** → 规避：移除 `_rate_limit_store` 和 `_check_rate_limit` 后，`test_ai_router.py` 中的 `clear_rate_limit_store` fixture 和 `TestRateLimitHelper` / `TestRateLimitIntegration` 测试类需要同步更新或删除。

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold `RateLimitService` with Redis sliding window

在 `src/services/rate_limit_service.py` 创建 `RateLimitService` 类：

```
__init__(self, session: AsyncSession, redis_client: redis.asyncio.Redis)
async def check_and_record(self, tenant_id: int, user_id: int, action: str = "default") -> dict
```

- key = `f"ratelimit:{tenant_id}:{user_id}:{action}"`
- window = 60s，max = 从 `settings.RATE_LIMIT_MAX` 读取，expiry = window + 10
- 使用 Lua script 执行 sliding window check-and-increment（原子性）：

```python
LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local expiry = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, expiry)
    return {1, limit - count - 1, now + window}
else
    return {0, 0, now + window}
end
"""
```

- Redis unavailable 时 log warning 并返回 `{"allowed": True, "remaining": 0, "reset_at": 0}`（fail open）
- 在 `src/configs/settings.py` 新增 `RATE_LIMIT_MAX = 30` 和 `RATE_LIMIT_LIMIT_WINDOW = 60`

操作：
- 创建 `src/services/rate_limit_service.py`
- 在 `src/configs/settings.py` 新增配置项

完成判定：`ruff check src/services/rate_limit_service.py` →0 errors；`PYTHONPATH=src python -c "from services.rate_limit_service import RateLimitService; print('OK')"` → silent---

### Step 2: Wire AIService to Agent Framework

修改 `src/services/ai_service.py`：

- `__init__` 新增可选参数 `agent_registry: AgentRegistry | None = None`
- 新增 `async def run_agent_task(self, task_type: str, params: dict, tenant_id: int, user_id: int) -> dict`

```python
async def run_agent_task(
    self,
    task_type: str,
    params: dict,
    tenant_id: int,
    user_id: int,
) -> dict:
    if self._agent_registry is None:
        raise ValidationException("Agent registry not configured")
    agent = self._agent_registry.get(task_type)
    if agent is None:
        raise NotFoundException(f"Agent '{task_type}' not found in registry")
    result = await agent.execute(params, tenant_id=tenant_id, user_id=user_id)
    return result if isinstance(result, dict) else result.model_dump()
```

操作：
- 在 `AIService.__init__` 第 1 行后插入 `self._agent_registry = agent_registry`
- 在 `send_message` 之后插入 `run_agent_task` 方法

完成判定：`ruff check src/services/ai_service.py` →0 errors

---

### Step 3: Refactor `AIChatGateway` → `LLMGateway`

修改 `src/internal/ai_gateway.py`：

- 重命名 `AIChatGateway` → `LLMGateway`，保留别名 `AIChatGateway = LLMGateway` 向后兼容
- `__init__` 中延迟初始化 `self._llm_service: LLMService | None = None`
- `chat()` 方法优先调用 `self._llm_service.chat(messages, tenant_id=tenant_id)`；若 `_llm_service` 为 `None`，回退到 `_stub_chat()`（log warning）

```python
class LLMGateway:
    async def chat(self, messages, context=None, tenant_id=None):
        if self._llm_service is None:
            warnings.warn("LLMService not configured, using stub fallback")
            return await self._stub_chat(messages, context)
        reply = await self._llm_service.chat(messages, tenant_id=tenant_id)
        return AIResponse(reply=reply, suggestions=[], actions=[])

    async def _stub_chat(self, messages, context=None):
        # existing stub implementation, unchanged
        ...

AIChatGateway = LLMGateway  # backward compat alias
```

操作：
- 在 `src/internal/ai_gateway.py` 第 1 行后插入 `import warnings`
- 将 `AIChatGateway` class 重命名为 `LLMGateway`，在文件末尾添加 `AIChatGateway = LLMGateway`
- 新增 `__init__` 参数 `llm_service: LLMService | None = None` 和 fallback逻辑

完成判定：`ruff check src/internal/ai_gateway.py` → 0 errors；`PYTHONPATH=src python -c "from internal.ai_gateway import LLMGateway, AIChatGateway, AIResponse; print('import OK')"` → silent

---

### Step 4: Replace in-router rate limit with `RateLimitService`

修改 `src/api/routers/ai.py`：

- 删除 `_rate_limit_store`（L28）、`_RATE_LIMIT_WINDOW`（L29）、`_RATE_LIMIT_MAX`（L30）、`_check_rate_limit`（L32-L38）
- 顶部 import 新增 `from services.rate_limit_service import RateLimitService`
- 每个端点的 rate limit 检查替换为 `RateLimitService` 实例调用：

```python
redis_url = settings.REDIS_URLredis_client = redis.asyncio.from_url(redis_url)

@ai_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    rl = RateLimitService(session, redis_client)
    limit = await rl.check_and_record(ctx.tenant_id, ctx.user_id, "ai_chat")
    if not limit["allowed"]:
        raise ValidationException("Rate limit exceeded")
    svc = AIService(session)
    ...
```

操作：
- 删除 `src/api/routers/ai.py` L28-L38 的进程内 rate limit 实现
-替换所有 `_check_rate_limit(ctx.tenant_id, ctx.user_id)` 为 `RateLimitService` 调用

完成判定：`ruff check src/api/routers/ai.py` → 0 errors

---

### Step 5: Add `POST /api/v1/ai/agent` endpoint

在 `src/api/routers/ai.py` 新增 `AgentTaskRequest` Pydantic schema 和端点：

```python
from typing import Any
from pydantic import BaseModel, Field

class AgentTaskRequest(BaseModel):
    task_type: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

@ai_router.post("/agent")
async def dispatch_agent_task(
    request: AgentTaskRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rl = RateLimitService(session, redis_client)
    limit = await rl.check_and_record(ctx.tenant_id, ctx.user_id, "ai_agent")
    if not limit["allowed"]:
        raise ValidationException("Rate limit exceeded")
    from agents import AgentRegistry
    svc = AIService(session, agent_registry=AgentRegistry())
    result = await svc.run_agent_task(
        task_type=request.task_type,
        params=request.params,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
    )
    return {"success": True, "data": result}
```

操作：
- 在 `src/api/routers/ai.py`顶部 import 区添加 `AgentTaskRequest`
- 在 router末尾新增 `/agent` 端点

完成判定：`ruff check src/api/routers/ai.py` → 0 errors；端点注册 FastAPI app 不报错

---

### Step 6: Write unit tests for `RateLimitService`

创建 `tests/unit/test_rate_limit_service.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.rate_limit_service import RateLimitService


class TestRateLimitService:
    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_allowed_under_limit(self, mock_session, mock_redis):
        svc = RateLimitService(mock_session, mock_redis)
        mock_redis.evalsha = AsyncMock(return_value=[1, 29, 1234567890.0])
        result = await svc.check_and_record(tenant_id=1, user_id=99, action="ai_chat")
        assert result["allowed"] is True
        assert result["remaining"] == 29

    @pytest.mark.asyncio
    async def test_rejected_over_limit(self, mock_session, mock_redis):
        svc = RateLimitService(mock_session, mock_redis)
        mock_redis.evalsha = AsyncMock(return_value=[0, 0, 1234567890.0])
        result = await svc.check_and_record(tenant_id=1, user_id=99, action="ai_chat")
        assert result["allowed"] is False
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, mock_session, mock_redis):
        mock_redis.evalsha = AsyncMock(side_effect=ConnectionError("Redis down"))
        svc = RateLimitService(mock_session, mock_redis)
        result = await svc.check_and_record(tenant_id=1, user_id=99, action="ai_chat")
        assert result["allowed"] is True  # fail open
```

操作：
- 创建 `tests/unit/test_rate_limit_service.py`

完成判定：`PYTHONPATH=src pytest tests/unit/test_rate_limit_service.py -v` →3 passed

---

### Step 7: Update existing router and service tests

修改 `tests/unit/test_ai_service.py`：

- 删除原有 `TestRateLimitHelper` / `TestRateLimitIntegration` 测试类（进程内实现已移除）
- 新增 `TestWiredAgent`：

```python
class TestWiredAgent:
    @pytest.mark.asyncio
    async def test_run_agent_task_dispatches(self, mock_db_session, mock_state):
        mock_registry = MagicMock()
        mock_agent = AsyncMock(return_value={"result": "ok"})
        mock_registry.get.return_value = mock_agent
        svc = AIService(mock_db_session, agent_registry=mock_registry)
        result = await svc.run_agent_task("coordinator", {"query": "test"}, tenant_id=1, user_id=99)
        mock_registry.get.assert_called_once_with("coordinator")
        mock_agent.execute.assert_called_once()
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_run_agent_task_unknown_agent(self, mock_db_session, mock_state):
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        svc = AIService(mock_db_session, agent_registry=mock_registry)
        with pytest.raises(NotFoundException):
            await svc.run_agent_task("unknown", {}, tenant_id=1, user_id=99)
```

修改 `tests/unit/test_ai_router.py`：
- `TestRateLimitHelper` / `TestRateLimitIntegration` 替换为 mock `RateLimitService` 的测试

操作：
- 修改 `tests/unit/test_ai_service.py`
- 修改 `tests/unit/test_ai_router.py`

完成判定：`PYTHONPATH=src pytest tests/unit/test_ai_service.py tests/unit/test_ai_router.py -v` →全部 passed

---

## 6. 验收

- [ ] `ruff check src/services/rate_limit_service.py src/services/ai_service.py src/internal/ai_gateway.py src/api/routers/ai.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/services/rate_limit_service.py src/services/ai_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_rate_limit_service.py -v` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_service.py -v` → ≥ 12 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_router.py -v` → ≥ 10 passed
- [ ] `ruff format --check src/services/rate_limit_service.py src/services/ai_service.py src/internal/ai_gateway.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/integration/test_ai_integration.py -v` → 全 passed（如已存在 integration 测试）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #627（LLMService）未按时完成导致 `LLMGateway` 仍有 stub 依赖 | 中 | 中 | Step 3 已设计 fallback；stub 在无 LLMService 时仍可正常工作，不阻塞本次 router/rate-limit 改动 |
| Redis 可用性导致 fail-open 策略使 rate limit 在 Redis 故障期间失效 | 低 | 低 | 短期（<5min）Redis 故障仅导致限流失效，不影响业务；监控可检测 Redis 可用性并告警 |
| Lua script 在 Redis Cluster 模式下不支持 EVALSHA（需要 EVAL） | 低 | 中 | 使用 `EVAL` 而非 `EVALSHA`；或在检测到 Cluster 模式时降级到 pipeline+watch 方案 |
| `test_ai_router.py` 的 `TestRateLimitHelper` 使用进程内实现，移除后测试失效 | 高 | 中 | Step 7 同步更新测试文件，将进程内测试替换为 Redis-mock 测试；不保留已移除的实现 |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/services/rate_limit_service.py src/services/ai_service.py src/internal/ai_gateway.py src/api/routers/ai.py src/models/ai.py tests/unit/test_rate_limit_service.py tests/unit/test_ai_service.py tests/unit/test_ai_router.py
git commit -m "feat(automation): wire AIService to Agent Framework and add Redis-backed rate limiting (#617)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "#617 feat: wire AIService to Agent Framework + Redis rate limiting" --body "Closes #617"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/ai_service.py`](../../src/services/ai_service.py) — AIService 现有实现，Step 2 扩展它
- 同类参考实现：[`src/api/routers/ai.py`](../../src/api/routers/ai.py) — 现有 in-memory rate limit，Step 4 替换它
- 同类参考实现：[`src/agents/coordinator.py`](../../src/agents/coordinator.py) — #626 的产物，`run_agent_task` 通过 `AgentRegistry` 调度它
- 同类参考实现：[`src/services/llm_service.py`](../../src/services/llm_service.py) — #627 的产物，Step 3 接入它（fallback 设计保证顺序无关）
- 依赖 issue / 关联：#625（BaseAgent + AgentRegistry）, #627（LLMService）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
