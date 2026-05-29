# WebSocket 前端客户端与在线状态 UI

| 元数据 | 值 |
|---|---|
| Issue | #494 |
| 分类 | 90-frontend |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0493-add-websocket-backend-manager-and-event-bus](../50-automation/0493-add-websocket-backend-manager-and-event-bus.md) |
| 启用后赋能 | [客户详情实时协作](../10-customers/板块名), [商机详情实时协作](../20-sales/板块名), [工单详情实时协作](../30-tickets/板块名) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

目前 CRM 各详情页（客户、商机、工单）完全依赖用户手动刷新页面才能感知数据变更，协作场景下用户不知道其他人正在查看或编辑同一条记录。Issue #80（实时协作功能）要求在不刷新页面的情况下推送数据变更并显示在线用户，而 #493 已完成 WebSocket 服务端基础设施（manager + event bus），本板块负责前端客户端接入和 UI 层呈现。

### 1.2 做完后

- **用户视角**：进入客户、商机、工单详情页时，页面右上角显示"N 人在浏览此页面"徽标；当其他用户对当前记录执行创建/更新/删除操作时，页面顶部弹出 toast 通知（"王五更新了这条商机"）；切换页面时自动发送 join/leave presence 事件。
- **开发者视角**：可通过 `src/realtime/websocket_client.py` 统一管理所有 WebSocket 连接；每个详情页仅需调用 `subscribe(entityType, entityId)` 即可完成频道订阅；接收到的事件通过 `onMutationEvent` 回调注入，开发者可按需扩展通知逻辑。

### 1.3 不做什么（剔除）

- [ ] 不实现 WebSocket 服务端逻辑（由 #493 负责）
- [ ] 不实现频道级别的权限校验（服务端已在 #493 处理）
- [ ] 不在列表页（/customers、/opportunities、/tickets）添加 presence 指示器（仅详情页）
- [ ] 不支持移动端 WebSocket 降级为轮询（本期仅实现 WebSocket 优先）

### 1.4 关键 KPI

- [指标 1：页面 A 打开后 `presence_join` 事件在 2s 内发送到服务端；用浏览器 Network 面板确认 WebSocket 帧发出]
- [指标 2：两个浏览器 Tab 打开同一记录，presence count 显示为 2；切换 Tab 时计数正确增减]
- [指标 3：`ruff check src/realtime/websocket_client.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - [`frontend/src/app/(app)/customers/[id]/page.tsx`](../../frontend/src/app/(app)/customers/[id]/page.tsx) — 添加 presence 订阅和指示器
  - [`frontend/src/app/(app)/opportunities/[id]/page.tsx`](../../frontend/src/app/(app)/opportunities/[id]/page.tsx) — 添加 presence 订阅和指示器
  - [`frontend/src/app/(app)/tickets/[id]/page.tsx`](../../frontend/src/app/(app)/tickets/[id]/page.tsx) — 添加 presence 订阅和指示器
- 要建：
  - `src/realtime/websocket_client.py` — WebSocket 客户端封装（connect/reconnect/channel subscribe/event handlers）
  - `frontend/src/lib/websocket/client.ts` — 前端 WebSocket 客户端（TypeScript）
  - `frontend/src/components/presence/PresenceIndicator.tsx` — N 人在浏览指示器组件
  - `frontend/src/components/presence/MutationToast.tsx` — 实时变更 toast 通知组件
  - `frontend/src/hooks/usePresence.ts` — presence 订阅 React Hook
  - `frontend/src/hooks/useMutationToast.ts` — toast 通知 Hook
  - `tests/unit/test_websocket_client.py` — WebSocket 客户端单元测试

### 2.3 缺什么

- [ ] 前端无 WebSocket 客户端基础设施，无法与服务端 #493 的 manager 建立连接
- [ ] 详情页未订阅 presence 频道，用户不知道其他人正在查看
- [ ] 数据变更无实时推送，用户需要手动刷新页面才能看到更新
- [ ] 无 reconnect 逻辑；网络抖动后连接永久断开
- [ ] 无前端 toast 通知组件，无法展示实时变更事件

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/realtime/websocket_client.py` | Python WebSocket 客户端工具（后端测试用，模拟前端行为） |
| `frontend/src/lib/websocket/client.ts` | 前端 TypeScript WebSocket 客户端封装，含重连指数退避 |
| `frontend/src/components/presence/PresenceIndicator.tsx` | 渲染"N 人在浏览此页面"徽标 |
| `frontend/src/components/presence/MutationToast.tsx` | 实时变更 toast 通知组件（支持队列） |
| `frontend/src/hooks/usePresence.ts` | React Hook：挂载时订阅 presence，卸载时取消订阅 |
| `frontend/src/hooks/useMutationToast.ts` | React Hook：监听 mutation 事件并触发 toast |
| `tests/unit/test_websocket_client.py` | Python WebSocket 客户端单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`frontend/src/app/(app)/customers/[id]/page.tsx`](../../frontend/src/app/(app)/customers/[id]/page.tsx) | 挂载时调用 `usePresence({ type: 'customer', id })`，渲染 `<PresenceIndicator>` |
| [`frontend/src/app/(app)/opportunities/[id]/page.tsx`](../../frontend/src/app/(app)/opportunities/[id]/page.tsx) | 同上，type 为 `opportunity` |
| [`frontend/src/app/(app)/tickets/[id]/page.tsx`](../../frontend/src/app/(app)/tickets/[id]/page.tsx) | 同上，type 为 `ticket` |

### 3.3 新增能力

- **Python WebSocket client**：`WebSocketClient.connect()`, `.subscribe(channel)`, `.on(event, handler)`, `.close()`
- **TypeScript WebSocket client**：`connect(url)`, `subscribe(channel)`, exponential backoff reconnect
- **React Hook**：`usePresence({ type, id })` → 自动处理 join/leave 生命周期
- **React Hook**：`useMutationToast()` → 监听 mutation 事件并渲染 toast
- **UI Component**：`<PresenceIndicator count={n} />` → 显示在线人数

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选指数退避（exponential backoff）重连，不选定时心跳轮询**：WebSocket 是长连接，重连应基于连接断开事件触发；心跳仅用于保活，不应用于重连决策。
- **选单例 WebSocket 客户端（单 global 实例），不选 per-component 实例**：同一浏览器 Tab 多次打开同一页面时不应建立多个 WebSocket 连接；同一 Tab 切换页面时复用一个连接，只切换订阅频道。
- **选 React Hook 封装 presence 逻辑，不选直接在各 page.tsx 内调用**：避免重复代码；确保 join/leave 事件在正确的时机（useEffect cleanup）发出。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `websockets` (Python) | `>=12.0` | Python 端测试客户端，与 FastAPI 生态兼容 |

### 4.3 兼容性约束

- 前端 WebSocket URL 通过环境变量 `NEXT_PUBLIC_WS_URL` 配置（默认为 `ws://localhost:8000/ws`），支持不同环境切换
- 所有 WebSocket 消息 payload 为 JSON，遵循 #80 定义的事件 schema
- 组件使用 React 18，`use client` 指令已标注（Next.js App Router）
- 不修改任何现有 API router 的 HTTP 接口

### 4.4 已知坑

1. **WebSocket 连接在 Next.js 热更新后断连** → 规避：客户端注册 `window.addEventListener('beforeunload', () => client.close())`，确保页面卸载时主动关闭；开发环境热更新触发 cleanup 后自动重连。
2. **同一 Tab 快速切换两个详情页导致 presence leave 事件晚发** → 规避：`usePresence` 在订阅新频道前先退订旧频道（send `presence_leave`），再订阅新频道（send `presence_join`），在同一个 useEffect cleanup 中顺序执行。
3. **toast 通知并发：多个 mutation 事件短时间到达导致多个 toast 堆叠遮挡页面内容** → 规避：`MutationToast` 组件内部维护事件队列（max 3 条可见），超出排队，超时自动消失（5s）。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建前端 WebSocket 客户端 `frontend/src/lib/websocket/client.ts`

实现 TypeScript 单例客户端，含 connect、subscribe、指数退避重连（max 5 次，base 1s × 2^n）、事件订阅机制（Map event→handlers）。连接 URL 从 `NEXT_PUBLIC_WS_URL` 环境变量读取，默认为 `ws://localhost:8000/ws`。

```typescript
// frontend/src/lib/websocket/client.ts（≤30 行核心结构）
type WsEvent = { type: string; payload: Record<string, unknown> };

class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<(payload: unknown) => void>>();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingSubscriptions = new Set<string>();

  connect(): void { /* 建立 WebSocket 连接，注册 onopen/onclose/onmessage */ }
  subscribe(channel: string): void { /* 发送 subscribe 帧，加入 pendingSubscriptions */ }
  on(event: string, handler: (payload: unknown) => void): () => void { /* 注册 handler，返回取消订阅函数 */ }
  private scheduleReconnect(): void { /* 指数退避：1s, 2s, 4s, 8s, 16s */ }
  close(): void { /* 清理定时器，关闭连接 */ }
}

export const wsClient = new WebSocketClient();
```

**完成判定**：`ruff check src/realtime/websocket_client.py` exit 0（如同时涉及 Python 端）；`npx tsc --noEmit frontend/src/lib/websocket/client.ts` exit 0（如 TS 项目有 tsc 配置）

### Step 2: 创建 React Hook `frontend/src/hooks/usePresence.ts`

接收 `{ type: 'customer'|'opportunity'|'ticket', id: string|number }`，在 useEffect 回调中：
1. 调用 `wsClient.connect()` 确保连接已建立
2. 发送 `presence_join` 事件（payload 含 userId、entityType、entityId、timestamp）
3. 监听 `presence_update` 事件，解析当前频道在线人数，更新 state
4. cleanup 函数发送 `presence_leave` 事件

```typescript
// frontend/src/hooks/usePresence.ts（≤25 行）
export function usePresence(opts: { type: string; id: string | number }) {
  const [viewerCount, setViewerCount] = useState(0);
  useEffect(() => {
    const channel = `${opts.type}:${opts.id}`;
    wsClient.connect();
    wsClient.subscribe(channel);
    wsClient.emit('presence_join', { entityType: opts.type, entityId: opts.id });
    const off = wsClient.on('presence_update', (payload: any) => {
      if (payload.channel === channel) setViewerCount(payload.count);
    });
    return () => {
      wsClient.emit('presence_leave', { entityType: opts.type, entityId: opts.id });
      off();
    };
  }, [opts.type, opts.id]);
  return { viewerCount };
}
```

**完成判定**：`ls frontend/src/hooks/usePresence.ts` 文件存在

### Step 3: 创建 PresenceIndicator 和 MutationToast 组件

`PresenceIndicator.tsx`：接收 `count: number`，count == 1 显示"1 人在浏览"，count > 1 显示"N 人在浏览"，count == 0 不渲染。

`MutationToast.tsx`：维护队列 `notifications: Array<{id, message, type}>`，每次新增时设置 5s auto-dismiss timeout；支持 `dismiss(id)` 手动关闭；最多同时显示 3 条。

```typescript
// frontend/src/components/presence/MutationToast.tsx（≤30 行核心逻辑）
export function MutationToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  useEffect(() => {
    const off = wsClient.on('mutation', (payload: any) => {
      const toast: Toast = { id: crypto.randomUUID(), message: formatMutation(payload), type: payload.operation };
      setToasts(prev => [...prev.slice(-2), toast]); // max 3
      setTimeout(() => dismiss(toast.id), 5000);
    });
    return off;
  }, []);
  const dismiss = (id: string) => setToasts(prev => prev.filter(t => t.id !== id));
  return ( <> {children} <ToastContainer toasts={toasts} onDismiss={dismiss} /> </> );
}
```

**完成判定**：`ls frontend/src/components/presence/PresenceIndicator.tsx frontend/src/components/presence/MutationToast.tsx` 文件存在

### Step 4: 创建 useMutationToast Hook 并包装 App Layout

创建 `useMutationToast.ts` Hook 封装 `MutationToast` 的事件监听逻辑；在 `frontend/src/app/(app)/layout.tsx` 外层包 `<MutationToastProvider>`，使 toast 覆盖全页面。

**完成判定**：`ls frontend/src/hooks/useMutationToast.ts` 文件存在

### Step 5: 在各详情页集成 presence 订阅

修改 `frontend/src/app/(app)/customers/[id]/page.tsx`、`opportunities/[id]/page.tsx`、`tickets/[id]/page.tsx`，各文件顶部导入 `usePresence` 和 `PresenceIndicator`，在页面组件内调用 `const { viewerCount } = usePresence({ type: 'customer', id: params.id })`，在页面右上角（或 Header 区域）渲染 `<PresenceIndicator count={viewerCount} />`。

**完成判定**：三个文件各自的 diff 中均包含 `usePresence` 的导入和调用

### Step 6: 创建 Python WebSocket 客户端及单元测试 `src/realtime/websocket_client.py`

实现 `WebSocketClient` Python 类，供后端测试使用（模拟前端行为）。支持 context manager 协议。

```python
# src/realtime/websocket_client.py
import asyncio, json, websockets
from typing import Callable

class WebSocketClient:
    def __init__(self, url: str):
        self.url = url
        self._conn = None
        self._handlers: dict[str, list[Callable]] = {}

    async def __aenter__(self):
        self._conn = await websockets.connect(self.url)
        return self

    async def __aexit__(self, *args):
        if self._conn:
            await self._conn.close()

    async def send(self, event: str, payload: dict) -> None:
        if self._conn:
            await self._conn.send(json.dumps({"type": event, "payload": payload}))

    def on(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)
```

在 `tests/unit/test_websocket_client.py` 中 mock `websockets.connect`，验证 connect/send/subscribe 流程。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_websocket_client.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/realtime/websocket_client.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_websocket_client.py -v` → 全 passed
- [ ] `ls frontend/src/lib/websocket/client.ts frontend/src/hooks/usePresence.ts frontend/src/hooks/useMutationToast.ts frontend/src/components/presence/PresenceIndicator.tsx frontend/src/components/presence/MutationToast.tsx` → 5 个文件均存在
- [ ] `frontend/src/app/(app)/customers/[id]/page.tsx` diff 包含 `usePresence` 导入和 `<PresenceIndicator` 调用
- [ ] `frontend/src/app/(app)/opportunities/[id]/page.tsx` diff 包含 `usePresence` 导入和 `<PresenceIndicator` 调用
- [ ] `frontend/src/app/(app)/tickets/[id]/page.tsx` diff 包含 `usePresence` 导入和 `<PresenceIndicator` 调用

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #493 WebSocket 服务端未按时完成，前端无服务端可连 | 中 | 高 | 前端 client 已实现指数退避，网络不可达时静默重连；不影响现有 HTTP 功能；本板块 PR 合并后 presence UI 在 #493 合并前显示 count=0 |
| 多 Tab 同时打开同一记录，presence count 计算错误 | 低 | 中 | 服务端 #493 在频道消息中下发 count；前端仅做展示，不做计数逻辑；修复服务端即可 |
| toast 通知在短时间大量 mutation 时淹没页面 | 低 | 中 | MutationToast 组件已实现 max 3 可见、5s auto-dismiss；可进一步通过 feature flag 关闭 toast |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/realtime/websocket_client.py \
        frontend/src/lib/websocket/client.ts \
        frontend/src/hooks/usePresence.ts \
        frontend/src/hooks/useMutationToast.ts \
        frontend/src/components/presence/PresenceIndicator.tsx \
        frontend/src/components/presence/MutationToast.tsx \
        frontend/src/app/\(app\)/customers/\[id\]/page.tsx \
        frontend/src/app/\(app\)/opportunities/\[id\]/page.tsx \
        frontend/src/app/\(app\)/tickets/\[id\]/page.tsx \
        tests/unit/test_websocket_client.py
git commit -m "feat(realtime): add frontend WebSocket client and presence UI"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(realtime): WebSocket frontend client and presence indicator" --body "Closes #494"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 子任务父 issue：#80
- 前置依赖：#493（WebSocket backend manager + event bus）
- 关联参考：#494 依赖 #493 中定义的 WebSocket 事件 schema（`presence_join`、`presence_leave`、`presence_update`、`mutation`）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
