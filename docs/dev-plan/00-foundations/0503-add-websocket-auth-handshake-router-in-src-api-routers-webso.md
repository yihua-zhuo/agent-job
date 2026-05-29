# WebSocket 认证握手路由 · 添加 JWT 验证的 WebSocket 路由

| 元数据 | 值 |
|---|---|
| Issue | #503 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [WebSocket ConnectionManager #502](../50-automation/0502-add-websocket-connectionmanager.md) |
| 启用后赋能 | [实时工单频道 #504](../50-automation/0504-real-time-ticket-updates-via-websocket.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 需要支持客户端（如前端看板）通过 WebSocket 订阅实时事件。当前没有任何 WebSocket 端点，客户端无法建立持久连接以接收推送。WebSocket 连接受到无保护的威胁，必须在握手阶段完成 JWT 校验，拒绝未授权连接，否则任何人都能接入实时通道窃听租户数据。

### 1.2 做完后

- **用户视角**：前端可通过 `ws://host/ws/{resource_type}/{resource_id}` 建立已认证的实时连接；无效 token 直接被拒绝，连接不会建立。
- **开发者视角**：新增 `src/api/routers/websocket.py` 提供标准化 WebSocket 入口；后续板块只需引用 `ConnectionManager`（#502）即可在对应 channel 上广播事件，无需重复鉴权逻辑。

### 1.3 不做什么（剔除）

- [ ] 广播逻辑（broadcast 事件写入 ConnectionManager 后由下游板块负责）
- [ ] 频道订阅持久化（连接断开即清理，不写 DB）
- [ ] 二进制帧处理（仅处理 text JSON 帧）
- [ ] WebSocket 重连策略（客户端行为，不在服务端范围内）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_websocket.py -v` → 所有 case passed]
- [指标 2：`ruff check src/api/routers/websocket.py src/api/routers/__init__.py` → 0 errors]
- [指标 3：`ruff check src/main.py` → 0 errors（如 main.py 有变更）]
- [指标 4：`ruff format --check src/api/routers/websocket.py tests/unit/test_websocket.py` → 0 diffs]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/internal/middleware/fastapi_auth.py` — 现有 JWT 验证逻辑（含 `require_auth` / `AuthContext`），WebSocket 认证握手需复用其中 token 解析部分

```{1}:50:src/internal/middleware/fastapi_auth.py
# TBD — 待确认实际行号和导出符号
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer

# 安全方案：HTTPBearer 用于从 Authorization header 提取 Bearer token
security = HTTPBearer()

async def require_auth(request: Request) -> AuthContext:
    # 解析 JWT，返回 tenant_id / user_id 等上下文
    ...
```

TBD - 待验证：`src/main.py` — 现有 `app = FastAPI()` 实例，路由通过 `app.include_router(...)` 挂载

TBD - 待验证：`src/services/connection_manager.py` 或 `src/api/routers/` 下某处 — #502 的 ConnectionManager 产出位置（须在 #502 合并后才能开始本板块）

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 新增 `app.include_router(websocket_router, prefix="/ws")` 挂载
- 要建：
  - `src/api/routers/websocket.py` — WebSocket 认证握手路由
  - `tests/unit/test_websocket.py` — 握手单元测试（valid/missing/invalid token 三场景）
  - `src/api/routers/__init__.py` — 如已有则追加导出，如无则新建

### 2.3 缺什么

- [ ] `src/api/routers/websocket.py` — WebSocket 端点，尚不存在
- [ ] `src/api/routers/__init__.py` — websocket 模块是否需要显式导出 router（视项目结构而定）
- [ ] WebSocket 场景下的 JWT 解析逻辑（现有 `require_auth` 依赖 `Request` 对象，WebSocket 用 `WebSocket` 对象，需确认是否可直接复用或需提取公共函数）
- [ ] ConnectionManager 的 `join` / `leave` 方法签名（来自 #502，须确认后方可写调用代码）
- [ ] `tests/unit/test_websocket.py` — 针对握手行为的单元测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/websocket.py` | WebSocket 路由：握手时 JWT 校验，成功后调 ConnectionManager.join，断开时调 leave |
| `tests/unit/test_websocket.py` | 握手单元测试：valid token → accept，missing token → reject，invalid token → 401 |
| `src/api/routers/__init__.py` | 视现有结构决定是否新建（如已有则合并导出） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | 挂载 `websocket_router` 至 `/ws` 前缀：`app.include_router(websocket_router, prefix="/ws", tags=["websocket"])` |

### 3.3 新增能力

- **Router**：`websocket_router` — `WebSocket("/ws/{resource_type}/{resource_id}")`，握手阶段校验 JWT
- **Service / Util**：`verify_ws_token(websocket: WebSocket) -> AuthContext` — 从 query param `token` 或 header 提取 JWT 并校验，与 `require_auth` 逻辑一致
- **Model**：无新增 ORM model（ConnectionManager 无持久化）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **从 query param 接受 token 而非强制 header**：客户端 JavaScript `new WebSocket(url, protocols)` 无法在握手时自定义 HTTP header，只能通过 `?token=...` 传参。Header 方式作为可选备用（如客户端可通过包装方式传递）。
- **不在 router 层缓存 AuthContext**：每次消息到达时从 token 重新解析，而非握手时存入 WebSocket session（Starlette 本身不支持 `.state` 跨协程共享，需要显式写入 `websocket.state`）
- **复用现有 `require_auth` 的 JWT 逻辑**：不重新实现 JWT decode，而是抽取公共函数 `decode_token(raw_token: str) -> AuthContext`，供 FastAPI router 和 WebSocket router 共用

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `fastapi` | `>=0.110` | WebSocket 支持（已有） |
| `python-jose[cryptography]` | 现有约束 | JWT 解析（已有） |

### 4.3 兼容性约束

- 多租户：WebSocket 连接须携带 `tenant_id`（从 JWT claim 解析），Channel key 须包含 `tenant_id`，避免跨租户消息泄漏
- Service 层错误抛 `AppException`；WebSocket 不走 HTTP 响应，握手失败直接 `await websocket.close(code=1008)` 并附 reason string
- 连接断开后 ConnectionManager.leave 必须同步清理注册记录，不能留 dangling 引用
- PYTHONPATH=src，import 写 `from internal.middleware.fastapi_auth import ...` 而不是 `from src.internal...`

### 4.4 已知坑

1. **FastAPI WebSocket 不支持 `Depends()` 注入 auth** → 规避：手动在 WebSocket endpoint 内调用 token 解析函数，不走 DI
2. **Starlette WebSocket `.accept()` 前不能 set headers / 不能提前关闭** → 规避：先校验 token，校验通过再 `.accept()`，校验失败直接 `.close(1008)` 不调用 `.accept()`
3. **ConnectionManager 尚未存在（依赖 #502）** → 规避：本板块须等 #502 合并后再合入；单元测试 mock ConnectionManager（不依赖真实实现）
4. **Alembic** — 本板块无 migration，N/A

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/websocket.py` — 骨架与依赖导入

新建 `src/api/routers/websocket.py`，导入必要依赖：

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from internal.middleware.fastapi_auth import decode_token, AuthContext
from services.connection_manager import ConnectionManager  # type: ignore — #502 产出
# 或 TBD — 待确认 #502 的实际 import 路径

router = APIRouter()

# 握手阶段 token 来源优先级：query param "token" > header "Authorization: Bearer ..."
async def verify_ws_token(websocket: WebSocket) -> AuthContext | None:
    # 从 websocket.query_params["token"] 取原始 JWT 字符串
    # 备选：websocket.headers.get("authorization", "").replace("Bearer ", "")
    # 调用 decode_token(raw_token) 返回 AuthContext，失败返回 None
    pass
```

**完成判定**：`ruff check src/api/routers/websocket.py` → 0 errors（语法/import 正确）

---

### Step 2: 实现 `verify_ws_token` 辅助函数

在 `websocket.py` 中实现 token 提取与校验逻辑：

```python
async def verify_ws_token(websocket: WebSocket) -> AuthContext | None:
    # 1. 优先取 query param token
    raw_token = websocket.query_params.get("token")
    if not raw_token:
        # 2. 备选：从 Authorization header 提取
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:]

    if not raw_token:
        return None

    try:
        return decode_token(raw_token)  # 复用现有 JWT 工具
    except Exception:
        return None
```

**完成判定**：`ruff check src/api/routers/websocket.py` → 0 errors

---

### Step 3: 实现 WebSocket endpoint — 握手校验 + join/leave

```python
@router.websocket("/{resource_type}/{resource_id}")
async def ws_channel(
    websocket: WebSocket,
    resource_type: str,
    resource_id: str,
):
    # 1. 校验 token
    ctx = await verify_ws_token(websocket)
    if ctx is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # 2. 接受连接
    await websocket.accept()

    # 3. 构建 channel key（含 tenant_id 防跨租户）
    channel = f"{ctx.tenant_id}:{resource_type}:{resource_id}"

    # 4. 加入 Channel
    await ConnectionManager.join(websocket, channel, ctx.tenant_id)

    try:
        while True:
            data = await websocket.receive_text()
            # 本板块无 broadcast 逻辑；data 可记录或忽略
    except WebSocketDisconnect:
        await ConnectionManager.leave(websocket, channel, ctx.tenant_id)
```

**完成判定**：`ruff check src/api/routers/websocket.py` → 0 errors；类型检查 `PYTHONPATH=src mypy src/api/routers/websocket.py` → 0 errors

---

### Step 4: 挂载路由到 `src/main.py`

在 `src/main.py` 中现有 `app = FastAPI()` 定义后添加：

```python
from api.routers import websocket as ws_router

app.include_router(ws_router.router, prefix="/ws", tags=["websocket"])
```

TBD - 待验证：在 `src/main.py` 中找到合适的 include_router 位置（通常在所有其他 router 之后或与 APIRouter 同一区域）

**完成判定**：`ruff check src/main.py` → 0 errors；运行 `PYTHONPATH=src uvicorn src.main:app --reload --port 8000` 不报导入错误

---

### Step 5: 编写单元测试 `tests/unit/test_websocket.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestWebSocket
# 注意：FastAPI TestClient 支持 websocket 属性，无需完整 asyncio client

from api.routers.websocket import verify_ws_token, router

@pytest.fixture
def valid_token() -> str:
    # 使用 conftest.py 中的 mock_jwt_token fixture 或内联生成
    return make_jwt_token(tenant_id=1, user_id=1)

@pytest.fixture
def mock_connection_manager(monkeypatch):
    cm = AsyncMock()
    cm.join = AsyncMock()
    cm.leave = AsyncMock()
    monkeypatch.setitem(sys.modules, "services.connection_manager", MagicMock(get=AsyncMock(return_value=cm)))
    return cm

class TestVerifyWsToken:
    async def test_valid_token_returns_context(self, valid_token):
        ws = MagicMock()
        ws.query_params.get.return_value = valid_token
        ctx = await verify_ws_token(ws)
        assert ctx is not None
        assert ctx.tenant_id == 1

    async def test_missing_token_returns_none(self):
        ws = MagicMock()
        ws.query_params.get.return_value = None
        ws.headers.get.return_value = ""
        ctx = await verify_ws_token(ws)
        assert ctx is None

    async def test_invalid_token_returns_none(self):
        ws = MagicMock()
        ws.query_params.get.return_value = "not.a.valid.jwt.token"
        ctx = await verify_ws_token(ws)
        assert ctx is None
```

完整测试覆盖：
- valid token → `ctx` 非 None，`ConnectionManager.join` 被调用
- missing token → `ctx` 为 None，`websocket.close(code=1008)` 被调用，无 `.accept()`
- invalid token → 同 missing，close reason 含 "Unauthorized"

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_websocket.py -v` → 所有 case passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/websocket.py src/main.py` → 0 errors
- [ ] `ruff format --check src/api/routers/websocket.py tests/unit/test_websocket.py` → 0 diffs
- [ ] `PYTHONPATH=src pytest tests/unit/test_websocket.py -v` → 全 passed
- [ ] `PYTHONPATH=src mypy src/api/routers/websocket.py` → 0 errors（如 mypy 已配置）
- [ ] `PYTHONPATH=src python -c "from api.routers.websocket import router; print('import ok')"` → 无 ImportError（确保模块可独立导入）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #502 ConnectionManager 尚未合并，导致 import 失败 | 中 | 高（阻塞编译） | 用 `TYPE_CHECKING` + mock 写测试，主流程等 #502 合入后再集成；不阻塞测试写完 |
| 复用 `decode_token` 需要从 `Request` 改为兼容 `WebSocket`，需调整签名 | 低 | 中（运行时 401） | 若 `decode_token` 无法直接复用，提取公共 JWT decode 函数供两者调用 |
| WebSocket 端点在某些代理/负载均衡下需要特定 header（X-Forwarded-Proto） | 低 | 中（连接建立失败） | 在 accept 前记录连接元数据；后续在 ConnectionManager 中扩展支持 |
| JWT token 通过 query param 明文暴露在日志中 | 低 | 中（安全） | 确保生产环境日志不记录 query string；若需要可改用 subprotocol 传递 token |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/websocket.py src/main.py tests/unit/test_websocket.py
git commit -m "feat(websocket): add JWT-authenticated WebSocket handshake router

- websocket router at /ws/{resource_type}/{resource_id}
- validates JWT from query param or Authorization header on handshake
- joins/leaves ConnectionManager channel on connect/disconnect
- Closes #503"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(websocket): JWT auth handshake router (#503)" --body "## Summary
- 新增 `src/api/routers/websocket.py` WebSocket 路由
- 握手阶段 JWT 校验（query token / Authorization header）
- 成功握手后调用 ConnectionManager.join，断开调用 leave
- 挂载至 `/ws` 前缀

## Test plan
- [ ] \`pytest tests/unit/test_websocket.py -v\` 全 passed
- [ ] \`ruff check src/api/routers/websocket.py src/main.py\` 0 errors

Closes #503
Subtask of #489"

# 2. 更新进度
# PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/internal/middleware/fastapi_auth.py` — JWT decode 复用源
- 父 issue / 关联：#489（父任务，实时通信基础设施整体规划）、#502（依赖：ConnectionManager join/leave API）
- 第三方文档：[FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/) — 官方端点写法参考

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
