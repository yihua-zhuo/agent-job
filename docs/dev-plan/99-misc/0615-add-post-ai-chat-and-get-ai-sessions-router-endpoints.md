# AI Chat · Add POST /ai/chat and GET /ai/sessions router endpoints

| 元数据 | 值 |
|---|---|
| Issue | #615 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [Add ChatService abstraction #614](../99-misc/0614-add-chatservice-abstraction.md) |
| 启用后赋能 | 父 issue #43 AI Chat Assistant 功能 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #43 的父 issue 要求提供 AI 对话功能。当前的 `src/api/routers/ai.py` 只暴露了 `POST /chat`（需先发 conversation 创建请求）和 `GET /conversation/{id}` — 没有办法一步完成「发送消息并获取回复」，也没有现成的「列出当前用户所有会话」的端点。#614 引入 `ChatService` 抽象，为 router 层提供干净的调用入口，本板块则在该基础上架设两个新 endpoint。

### 1.2 做完后

- **用户视角**：POST `/api/v1/ai/chat` 可在一次请求中发送消息并拿到中文回复 + 建议数组（若无 conversation_id 则自动创建）；GET `/api/v1/ai/sessions` 可分页浏览当前用户的会话列表。
- **开发者视角**：`src/api/routers/ai_chat.py` 提供 `ai_chat_router`，内部调用 `ChatService`。新文件不修改已有 `ai.py` 的任何路由。

### 1.3 不做什么（剔除）

- [ ] 本板块不引入 rate limiting（issue 明确"No rate limiting yet"；#614 的 ChatService 本身也无此需求）。
- [ ] 不修改 `src/api/routers/ai.py` 的现有路由或行为。
- [ ] 不创建新的 ORM model 或数据库迁移 — 所有数据结构复用 #614 的 `ChatService` 已封装的部分。

### 1.4 关键 KPI

- `ruff check src/api/routers/ai_chat.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_ai_chat_router.py -v` → ≥ 4 passed（happy path、boundary、error case）
- `PYTHONPATH=src pytest tests/integration/test_ai_chat_integration.py -v` → 全 passed
- 端到端：`POST /api/v1/ai/chat` 返回 `{"success": true, "data": {"reply": "...", "suggestions": [...]}}`
- 端到端：`GET /api/v1/ai/sessions?page=1&page_size=20` 返回 `{"success": true, "data": {"items": [...], "total": N}}`

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口 — `AIService.list_conversations` 已实现会话列表查询：
[`src/services/ai_service.py`](../../../src/services/ai_service.py) L63-L92

```python
63:    async def list_conversations(
64:        self, tenant_id: int, user_id: int, page: int = 1, page_size: int = 20
65:    ) -> tuple[list[AIConversationModel], int]:
66:        """Return paginated conversations for a tenant+user."""
67:        offset = (page - 1) * page_size
68:
69:        count_result = await self.session.execute(
70:            select(func.count(AIConversationModel.id)).where(
71:                and_(
72:                    AIConversationModel.tenant_id == tenant_id,
73:                    AIConversationModel.user_id == user_id,
74:                )
75:            )
76:        )
77:        total = count_result.scalar() or 0
78:
79:        result = await self.session.execute(
80:            select(AIConversationModel)
81:            .where(
82:                and_(
83:                    AIConversationModel.tenant_id == tenant_id,
84:                    AIConversationModel.user_id == user_id,
85:                )
86:            )
87:            .order_by(AIConversationModel.updated_at.desc())
88:            .offset(offset)
89:            .limit(page_size)
90:        )
91:        conversations = result.scalars().all()
92:        return list(conversations), int(total)
```

已有 `ChatRequest` + `ChatResponse` Pydantic 模型（无新建需求）：
[`src/models/ai.py`](../../../src/models/ai.py) L8-L25

```python
 8:class ChatRequest(BaseModel):
 9:    message: str = Field(..., min_length=1, max_length=4000)
10:    context: dict[str, Any] | None = Field(default=None)
11:    conversation_id: int | None = Field(default=None)
12:
13:class ChatResponse(BaseModel):
14:    reply: str
15:    suggestions: list[str] | None = None
16:    actions: list[dict] | None = None
17:
18:    def to_dict(self) -> dict[str, Any]:
19:        return self.model_dump()
```

现有 `ai_router` 中的 `POST /chat` 需要两次请求（先 create conversation，再 send）：
[`src/api/routers/ai.py`](../../../src/api/routers/ai.py) L73-L108

```python
73:@ai_router.post("/chat")
74:async def chat(
75:    request: ChatRequest,
76:    ctx: AuthContext = Depends(require_auth),
77:    session: AsyncSession = Depends(get_db),
78:) -> dict:
79:    _check_rate_limit(ctx.tenant_id, ctx.user_id)
80:
81:    svc = AIService(session)
82:
83:    if request.conversation_id is None:
84:        conversation = await svc.create_conversation(
85:            tenant_id=ctx.tenant_id, user_id=ctx.user_id, title=None
86:        )
87:        conversation_id = conversation.id
88:    else:
89:        conversation_id = request.conversation_id
90:
91:    result = await svc.send_message(
92:        conversation_id=conversation_id,
93:        message=request.message,
94:        tenant_id=ctx.tenant_id,
95:        user_id=ctx.user_id,
96:    )
97:
98:    response = ChatResponse(
99:        reply=result.reply,
100:        suggestions=result.suggestions,
101:        actions=result.actions,
102:    )
103:    return _success(response.to_dict(), message=result.reply or "")
```

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 在 `include_router` 中注册 `ai_chat_router`（如尚未注册）
- 要建：
  - `src/api/routers/ai_chat.py` — 新路由文件，暴露 `POST /ai/chat` 和 `GET /ai/sessions`
  - `tests/unit/test_ai_chat_router.py` — 单元测试（4 个测试用例）
  - `tests/integration/test_ai_chat_integration.py` — 集成测试

### 2.3 缺什么

- [ ] 没有 `ai_chat.py` 独立路由文件 — 所有逻辑堆在 `ai.py` 中无法解耦
- [ ] 没有 `GET /ai/sessions` 端点 — 用户无法列出自己所有会话，必须先知道 conversation_id
- [ ] `POST /ai/chat` 在 `ai.py` 中需要先 create conversation 再 send_message，两步合并后才能一次完成
- [ ] `ChatService` 抽象（#614）尚未就位，本板块依赖其返回的 service 实例

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/ai_chat.py` | 新路由：POST /ai/chat（一步完成聊天）和 GET /ai/sessions（分页会话列表） |
| `tests/unit/test_ai_chat_router.py` | 单元测试：验证端点响应格式、错误处理、auth 校验 |
| `tests/integration/test_ai_chat_integration.py` | 集成测试：真实 DB 场景，验证 router 与 service 联动 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/main.py` | 新增 `app.include_router(ai_chat_router)` 注册（若尚未注册） |

### 3.3 新增能力

- **API endpoint**：`POST /api/v1/ai/chat` → 接受 `{message, context?, conversation_id?}` → 返回 `{success: true, data: {reply: str, suggestions: list[str]?, actions: list?}`
- **API endpoint**：`GET /api/v1/ai/sessions` → 接受 `page`, `page_size` 查询参数 → 返回 `{success: true, data: {items: [], total: int, page: int, page_size: int}}`
- **Router file**：`src/api/routers/ai_chat.py` — 独立于现有 `ai.py`，可直接被 `main.py` 挂载
- **Response schemas**：复用 `src/models/ai.py` 已有 `ChatRequest` / `ChatResponse`（无需新建）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **新文件 `ai_chat.py` 而非修改 `ai.py`**：遵循单一职责，ai.py 专注 conversation 管理，ai_chat.py 专注 chat/sessions 对外 API。修改现有 ai.py 会增加 regression 风险，且 ai_chat.py 可以独立挂载。
- **复用 `AIService` 而非引入 `ChatService`（#614 完成后）**：在 #614 落地前，直接调用已存在的 `AIService`，确保本板块可以独立开发和测试。#614 的 ChatService 注入后，本文件仅需修改 import。
- **复用 `ChatRequest` / `ChatResponse` from `models/ai.py`**：无需新建 schema，两个模型完全符合需求（message→reply+suggestions）。

### 4.2 版本约束

无新依赖引入，沿用项目现有依赖版本。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（已有 `AIService.list_conversations` 已遵守）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- 所有端点使用 `AuthContext = Depends(require_auth)` 注入认证上下文，使用 `session: AsyncSession = Depends(get_db)` 注入 DB session
- 返回格式：`{"success": true, "data": {...}, "message": "..."}`（复用 `ai.py` 的 `_success` 辅助函数）

### 4.4 已知坑

1. **`message` 为空字符串时 Pydantic 拦截** → 规避：`ChatRequest` 定义 `message: str = Field(..., min_length=1)`，FastAPI 自动返回 422，无需在 handler 中手动校验。
2. **`page` 或 `page_size` 无效值时 Pydantic 拦截** → 规避：`Query(1, ge=1)` / `Query(20, ge=1, le=100)` — 超出范围自动 422。
3. **`AIService.list_conversations` 返回 `(list, int)` 元组** → 规避：router 层直接解包使用，与 `CustomerService.list_customers` 模式一致。
4. **#614 尚未合入时 `ChatService` 不存在** → 规避：本板块在实现时直接 import `AIService`（已存在），#614 合入后将 `AIService` 替换为 `ChatService`，本文件改动最小化。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/ai_chat.py` 文件结构

在 `src/api/routers/` 下新建 `ai_chat.py`，定义 `ai_chat_router`（prefix `/api/v1/ai`，与 `ai_router` 共享同一 prefix 不会冲突），引入必要的依赖：AuthContext、get_db、ChatRequest、ChatResponse、AIService。

```python
"""AI Chat router — /api/v1/ai/chat and /api/v1/ai/sessions endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.ai import ChatRequest, ChatResponse
from services.ai_service import AIService

ai_chat_router = APIRouter(prefix="/api/v1/ai", tags=["ai-chat"])


def _success(data: dict, message: str = "") -> dict:
    return {"success": True, "data": data, "message": message}
```

**完成判定**：`ruff check src/api/routers/ai_chat.py` → 0 errors

---

### Step 2: 实现 `POST /api/v1/ai/chat` 端点

复用 `AIService.create_conversation`（无 conversation_id 时）和 `AIService.send_message`（已有逻辑），返回 `ChatResponse.to_dict()` 包装在 `_success` 中。

```python
@ai_chat_router.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Send a message and get a reply in one request.

    Creates a new conversation if conversation_id is absent.
    """
    svc = AIService(session)

    if request.conversation_id is None:
        conversation = await svc.create_conversation(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id, title=None
        )
        conversation_id = conversation.id
    else:
        conversation_id = request.conversation_id

    result = await svc.send_message(
        conversation_id=conversation_id,
        message=request.message,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
    )

    response = ChatResponse(
        reply=result.reply,
        suggestions=result.suggestions,
        actions=result.actions,
    )
    return _success(response.to_dict(), message=result.reply or "")
```

**完成判定**：`ruff check src/api/routers/ai_chat.py` → 0 errors

---

### Step 3: 实现 `GET /api/v1/ai/sessions` 端点

调用 `AIService.list_conversations`，分页返回会话列表。复用 `ai.py` 中的 `_paginated_response` 模式（不含 rate limit）。

```python
def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@ai_chat_router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of AI conversations (sessions) for the current user."""
    svc = AIService(session)
    conversations, total = await svc.list_conversations(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        page=page,
        page_size=page_size,
    )
    return _paginated_response(
        items=[c.to_dict() for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )
```

**完成判定**：`ruff check src/api/routers/ai_chat.py` → 0 errors

---

### Step 4: 在 `src/main.py` 注册 `ai_chat_router`

查找 `src/main.py` 中 `app.include_router(ai_router` 的位置，在其后或同区域添加 `app.include_router(ai_chat_router)`，确保路由被正确挂载。

操作：
- a) 读取 `src/main.py`
- b) 在 `app.include_router` 区域添加 `app.include_router(ai_chat_router, prefix="/api/v1")`（检查 prefix 是否已由 router 自身处理，避免双重 prefix）

**完成判定**：`grep -n "ai_chat_router" src/main.py` → 找到注册行

---

### Step 5: 编写 `tests/unit/test_ai_chat_router.py`

在 `tests/unit/` 下新建测试文件，参考 `tests/unit/test_ai_router.py` 的 fixture 模式（TestClient + mock AIService）。覆盖：
1. `POST /chat` — 正常返回 reply + suggestions
2. `POST /chat` — 无 conversation_id 时自动创建
3. `POST /chat` — 空消息返回 422（由 ChatRequest min_length=1 触发）
4. `GET /sessions` — 返回分页 items + total
5. `GET /sessions` — page/page_size boundary（page=0 返回 422，page_size=101 返回 422）

```python
@pytest.fixture
def client_with_service(monkeypatch, mock_db_session):
    """Return a TestClient with AIService fully mocked."""
    mock_service = MagicMock()
    monkeypatch.setattr(
        "api.routers.ai_chat.AIService",
        lambda session: mock_service,
    )
    app = FastAPI()
    app.include_router(ai_chat_router)
    app.dependency_overrides[require_auth] = lambda: _make_auth_ctx()
    app.dependency_overrides[get_db] = lambda: mock_db_session
    # exception handler...
    return TestClient(app, raise_server_exceptions=False), mock_service
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_chat_router.py -v` → ≥ 4 passed

---

### Step 6: 编写 `tests/integration/test_ai_chat_integration.py`

在 `tests/integration/` 下新建测试文件，使用 `db_schema`、`tenant_id`、`async_session` fixtures。验证端到端行为：
1. `POST /chat` → 201，创建 conversation + message，reply 非空
2. `GET /sessions` → 返回 items 包含刚才创建的 session，total ≥ 1
3. `GET /sessions` → 分页参数正常（page=1, page_size=5）

操作：
- a) 在 `tests/integration/` 下创建 `test_ai_chat_integration.py`
- b) 使用真实 DB session + AIService 组合验证

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_ai_chat_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/ai_chat.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors（如有修改）
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_chat_router.py -v` → ≥ 4 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_ai_chat_integration.py -v` → 全 passed
- [ ] 端到端：`POST http://localhost:8000/api/v1/ai/chat` with `{"message": "你好"}` → `{"success": true, "data": {"reply": "...", "suggestions": [...]}}`
- [ ] 端到端：`GET http://localhost:8000/api/v1/ai/sessions?page=1&page_size=20` → `{"success": true, "data": {"items": [...], "total": N}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #614 未完成导致 ChatService 不可用 | 中 | 中 | 本板块直接依赖已存在的 AIService，#614 合入后只需将 import 替换为 ChatService，改动 ≤ 3 行 |
| `ai_chat_router` 与 `ai_router` prefix 冲突导致路由匹配错误 | 低 | 高 | 在 main.py 中使用不同的 prefix（如 `/api/v1/ai-chat`），或通过 `router.include_router(ai_chat_router)` 嵌套合并 prefix；不阻塞下游 |
| 新文件 ruff 报错（import 未使用、unused variable） | 中 | 低 | `ruff check` 失败即修改；无回退需求 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/ai_chat.py src/main.py tests/unit/test_ai_chat_router.py tests/integration/test_ai_chat_integration.py
git commit -m "feat(ai): add POST /ai/chat and GET /ai/sessions endpoints

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ai): add POST /ai/chat and GET /ai/sessions router endpoints" --body "Closes #615"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/ai.py`](../../../src/api/routers/ai.py) — `POST /chat` 现有实现（复用其 `_success` / `_paginated_response` 辅助函数和 AIService 调用模式）
- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 分页端点的标准模式（Query 参数、_paginated 辅助函数）
- 父 issue / 关联：#43（AI Chat Assistant 父 issue）
- 依赖 issue：#614（Add ChatService abstraction — 提供 service 层抽象，本板块在其完成后替换 AIService import）
