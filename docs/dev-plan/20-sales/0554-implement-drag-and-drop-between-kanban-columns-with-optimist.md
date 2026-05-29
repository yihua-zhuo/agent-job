# Tickets · 看板卡片支持拖拽换列

| 元数据 | 值 |
|---|---|
| Issue | #554 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [Tickets 看板基础视图](./0553-add-kanban-board-to-tickets-page.md) |
| 启用后赋能 | [看板自动化规则](./TODO-kanban-automation.md), [商机看板拖拽](./TODO-opportunity-kanban-dnd.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 Tickets 看板（`kanban-board.tsx`）是纯静态展示组件，仅按 `status` 分组渲染卡片，鼠标悬停/拖拽均无反应。用户在 CRM 录入工单后，需频繁跨状态列移动工单，完全依赖手动编辑 — 体验远落后于同项目 Tasks 页已实现的 `@dnd-kit` 拖拽方案。

### 1.2 做完后

- **用户视角**：用户可以在 Tickets 看板中直接拖动卡片到相邻或任意列，松手后卡片立即出现在目标列（optimistic UI）；若 API 调用失败，卡片自动弹回原列并显示错误提示。
- **开发者视角**：`KanbanBoard` 组件获得 `onCardDrop` 回调和乐观更新状态管理；`KanbanTicketData` 接口保持不变；后端无需改动 — 复用已有 `PUT /api/v1/tickets/{id}/status` 端点。

### 1.3 不做什么（剔除）

- [ ] 多选批量拖拽（`POST /api/v1/tickets/bulk-update` 暂不接入）
- [ ] 商机（Opportunity）看板拖拽
- [ ] 撤销按钮（revert 即为 undo，无需独立按钮）
- [ ] 看板列顺序拖拽调整（仅支持卡片跨列）
- [ ] 后端新建接口（直接复用现有 `PUT /tickets/{id}/status`）

### 1.4 关键 KPI

- [指标 1：拖拽换列后 UI 立即更新，≤16 ms 无闪烁（`ReactProfiler` 或视觉确认）]
- [指标 2：API 失败时卡片回弹至原列，错误提示出现]
- [指标 3：`ruff check frontend/src/components/tickets/kanban-board.tsx` → 0 errors]
- [指标 4：`PYTHONPATH=src pytest tests/unit/test_ticket_service.py -v` → 已有测试全 passed（回归）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

入口：[`frontend/src/components/tickets/kanban-board.tsx`](../../frontend/src/components/tickets/kanban-board.tsx) L{1}-L{80}

```tsx:frontend/src/components/tickets/kanban-board.tsx
export function KanbanBoard({ tickets, groupBy = "status" }: KanbanBoardProps) {
  if (groupBy === "status") {
    const groups: Record<string, { label: string; color: string }> = {
      open: { label: "Open", color: "bg-blue-500" },
      in_progress: { label: "In Progress", color: "bg-yellow-500" },
      pending: { label: "Pending", color: "bg-yellow-400" },
      resolved: { label: "Resolved", color: "bg-green-500" },
      closed: { label: "Closed", color: "bg-gray-400" },
    };
    const cols = Object.entries(groups).map(([key, { label, color }]) => ({
      key,
      label,
      color,
      tickets: tickets.filter((t) => t.status === key),
    }));
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {cols.map(({ key, label, color, tickets: colTickets }) => (
          <StatusColumn
            key={key}
            title={label}
            colorClass={color}
            tickets={colTickets}
            onTicketClick={handleTicketClick}
          />
        ))}
      </div>
    );
  }
}
```

引用方：[`frontend/src/app/(app)/tickets/page.tsx`](../../frontend/src/app/(app)/tickets/page.tsx) — `viewMode === "kanban"` 时渲染 `<KanbanBoard>`。

### 2.2 涉及文件清单

- 要改：
  - [`frontend/src/components/tickets/kanban-board.tsx`](../../frontend/src/components/tickets/kanban-board.tsx) — 接入 `@dnd-kit`，增加 `onDrop` 乐观更新逻辑
  - [`frontend/src/app/(app)/tickets/page.tsx`](../../frontend/src/app/(app)/tickets/page.tsx) — 将 tickets 数据注入 `KanbanBoard`，管理 optimistic state
- 要建：
  - `frontend/src/components/tickets/draggable-ticket-card.tsx` — 封装 `useSortable` 的可拖拽卡片组件
  - `frontend/src/app/(app)/tickets/kanban-board-dnd.test.tsx` — Vitest 单元测试（拖拽交互 + rollback）

### 2.3 缺什么

- [ ] `KanbanBoard` 无 `@dnd-kit` 上下文包裹，无法响应 `DragEndEvent`]
- [ ] 卡片组件无 `useSortable` hook 调用，DOM 无 `transform` / `transition` 样式]
- [ ] 无 `DnD` sensor 配置（`PointerSensor` 需 `activationConstraint: { distance: 8 }` 防误触发）]
- [ ] tickets page 无 optimistic 状态管理（无 `isPending` / `rollback` 逻辑）]
- [ ] 无 `DragOverlay` 渲染拖拽中的卡片镜像]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/components/tickets/draggable-ticket-card.tsx` | 封装 `@dnd-kit` `useSortable` 的工单卡片，支持 `isDragging` 样式 |
| `frontend/src/app/(app)/tickets/kanban-board-dnd.test.tsx` | Vitest 测试：拖拽换列成功 / API 失败回弹 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`frontend/src/components/tickets/kanban-board.tsx`](../../frontend/src/components/tickets/kanban-board.tsx) | 导出 `KanbanBoard` 增加 `DndContext` + `SortableContext` + `DragOverlay`；每列改用 `<SortableContext>` 包裹；`onDragEnd` 调用 props `onCardDrop` |
| [`frontend/src/app/(app)/tickets/page.tsx`](../../frontend/src/app/(app)/tickets/page.tsx) | 管理本地 optimistic `tickets` 状态；`onCardDrop` 乐观更新 + API 调用 + rollback on error |

### 3.3 新增能力

- **Frontend component**：`DraggableTicketCard` — `useSortable({ id: ticket.id })` + `CSS.Transform.toString(transform)` + `isDragging` opacity
- **Frontend component**：`KanbanBoard` — `DndContext` / `SortableContext` / `DragOverlay`，新增 `onCardDrop` prop
- **Frontend hook logic**：tickets page 内 optimistic update + rollback on `catch`
- **API integration**：`PUT /api/v1/tickets/{id}/status`（已有，无需后端改动）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `@dnd-kit` 而非 `react-beautiful-dnd`**：前者支持 React 18+ SSR / 并发模式，且本项目 Tasks 页已采用同一库，统一技术栈降低维护成本。
- **选 `PUT /tickets/{id}/status` 而非通用 `PUT /tickets/{id}`**：专用端点语义更清晰，body 仅需 `{ new_status }`，减少出错面。
- **不在 `KanbanBoard` 内部调用 API，而在调用方（tickets page）处理**：保持组件纯 UI 逻辑，便于后续复用至商机看板等场景。

### 4.2 版本约束

<!-- 无新增 npm 依赖；@dnd-kit 已由 tasks/page.tsx 引入，此处直接复用 -->

### 4.3 兼容性约束

- `KanbanTicketData` 接口不变，新增字段仅用于内部 optimistic state，不暴露给 API 层
- 多租户：API 调用携带已有 `tenant_id`（继承自 session/auth context）
- API 返回 `{ success, data, message }` envelope，组件只读 `data.status` 验参
- 乐观更新采用本地 `tickets` 数组克隆，不修改 props；rollback 时直接替换回原 props 值

### 4.4 已知坑

1. **Tasks 页 `activationConstraint: { distance: 8 }` 经验证防误触有效** → 直接复用，不另作配置。
2. **乐观更新期间快速连续拖拽** → 第二次 `DragEnd` 时若第一次尚未落库，应 cancel pending 请求再发起新请求；实现上以 `abortController` 取消上一次 mutation。
3. **DragOverlay 卡片样式与原卡片完全一致** → `isDragging` 时原卡片应 `opacity-50` / `pointer-events-none`，防止用户将卡片丢到自身之上造成状态撕裂。
4. **Vitest + `@dnd-kit`**：测试中 `DndContext` 需用 `render(<DndContext ...><KanbanBoard /></DndContext>)` 包裹；mock `fireEvent` 拖拽需 `pointerMove/Up` 序列，不可仅模拟 `dragEnd`。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 DraggableTicketCard 组件

从 Tasks 页 `DraggableTaskCard` 抽取模式，创建 `DraggableTicketCard` 组件。

操作：
- a) 新建 `frontend/src/components/tickets/draggable-ticket-card.tsx`
- b) 导入 `useSortable` from `@dnd-kit/sortable` + `CSS` from `@dnd-kit/utilities`
- c) Props 接收 `ticket: KanbanTicketData` + `onClick` + `isDraggingOverlay`（overlay 专用 flag）
- d) `useSortable({ id: String(ticket.id) })` — 用 `String` 与 Tasks 页保持一致
- e) `isDragging` 时父容器加 `opacity-50 pointer-events-none`；`isDraggingOverlay` 时加 `shadow-xl rotate-2 scale-105`
- f) 导出 `DraggableTicketCard` 命名的 `KanbanTicketData` 接口不变

示例代码：

```tsx:frontend/src/components/tickets/draggable-ticket-card.tsx
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { KanbanTicketData } from "./kanban-board";

interface Props {
  ticket: KanbanTicketData;
  onClick: (id: number) => void;
  isDraggingOverlay?: boolean;
}

export function DraggableTicketCard({ ticket, onClick, isDraggingOverlay = false }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: String(ticket.id) });

  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50 pointer-events-none" : ""}`}
    >
      <div className={`rounded bg-white p-3 shadow ${isDraggingOverlay ? "shadow-xl rotate-2 scale-105" : ""}`}>
        {/* existing card content — subject, priority badge, etc. */}
        <p className="text-sm font-medium truncate">{ticket.subject}</p>
        <button onClick={() => onClick(ticket.id)} className="mt-1 text-xs text-blue-600 hover:underline">
          View
        </button>
      </div>
    </div>
  );
}
```

**完成判定**：`ls frontend/src/components/tickets/draggable-ticket-card.tsx` → 文件存在；`npx tsc --noEmit frontend/src/components/tickets/draggable-ticket-card.tsx` → 0 errors

---

### Step 2: 重构 KanbanBoard — 接入 DndContext + SortableContext

将 `KanbanBoard` 改造为可接收 `onCardDrop` 回调的受控组件，内部包裹 `@dnd-kit` 上下文。

操作：
- a) 导入 `DndContext`, `DragOverlay`, `PointerSensor`, `useSensor`, `useSensors`, `type DragEndEvent`, `type DragStartEvent` from `@dnd-kit/core`；`SortableContext`, `verticalListSortingStrategy` from `@dnd-kit/sortable`
- b) Props 增加 `onCardDrop: (ticketId: number, newStatus: string) => void`
- c) 每列改用 `<SortableContext items={colTickets.map(t => String(t.id))} strategy={verticalListSortingStrategy}>` 包裹
- d) 每张卡片替换为 `<DraggableTicketCard ticket={ticket} onClick={onTicketClick} />`（拖拽层已封装）
- e) `DndContext` 包裹全部列，sensor 配置 `useSensor(PointerSensor, { activationConstraint: { distance: 8 } })`
- f) `onDragStart` 回调：设置 `activeTicketId = event.active.id as string` 到 state
- g) `onDragEnd` 回调：从 `event.over?.id` 读取目标列 `newStatus`，调用 `onCardDrop(ticketId, newStatus)`
- h) `DragOverlay` 渲染 `<DraggableTicketCard ticket={activeTicket} onClick={() => {}} isDraggingOverlay />`

示例代码（核心变更）：

```tsx:frontend/src/components/tickets/kanban-board.tsx
// 新增 import（保留原有 import）
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { DraggableTicketCard } from "./draggable-ticket-card";

// Props 新增 onCardDrop
interface KanbanBoardProps {
  tickets: KanbanTicketData[];
  groupBy?: "status" | "priority" | "assignee";
  onTicketClick?: (id: number) => void;
  onCardDrop: (ticketId: number, newStatus: string) => void;
}

export function KanbanBoard({ tickets, groupBy = "status", onTicketClick, onCardDrop }: KanbanBoardProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null);
  const activeTicket = tickets.find((t) => String(t.id) === activeTicketId) ?? null;

  function handleDragStart(event: DragStartEvent) {
    setActiveTicketId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveTicketId(null);
    const overId = event.over?.id;
    if (!overId || !activeTicketId) return;
    const ticketId = Number(activeTicketId);
    onCardDrop(ticketId, overId as string);
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {/* columns unchanged — but wrap each card with SortableContext */}
      </div>
      <DragOverlay>
        {activeTicket && (
          <DraggableTicketCard ticket={activeTicket} onClick={() => {}} isDraggingOverlay />
        )}
      </DragOverlay>
    </DndContext>
  );
}
```

**完成判定**：`npx tsc --noEmit frontend/src/components/tickets/kanban-board.tsx` → 0 errors；`ruff check frontend/src/components/tickets/kanban-board.tsx` → 0 errors

---

### Step 3: 在 Tickets Page 接入乐观更新 + rollback 逻辑

`tickets/page.tsx` 管理 optimistic tickets state，`onCardDrop` 调用 API，失败时回弹。

操作：
- a) 导入 `useState`, `useCallback`, `useRef` from React；`MutationFunction` from `@tanstack/react-query`（tasks page 已引入）
- b) 新增 state：`const [optimisticTickets, setOptimisticTickets] = useState<KanbanTicketData[]>(tickets)`
- c) 当父组件 `tickets` prop 更新时同步 `setOptimisticTickets(tickets)`
- d) 定义 `changeTicketStatus` mutation：调用 `PUT /api/v1/tickets/${id}/status`，body `{ new_status: newStatus }`
- e) `onCardDrop` 回调：
  - 克隆当前 `optimisticTickets`，找出被拖卡片的 `originalStatus`
  - 立即更新本地 state（optimistic）
  - `try { await changeTicketStatus.mutateAsync(...) }` — 成功则直接落库
  - `catch { setOptimisticTickets(rollbackTickets) }` — 回弹 + toast error
- f) 用 `useRef` 存储 `originalTicketSnapshot`，确保 rollback 取到最新快照而非闭包旧值
- g) 透传 `<KanbanBoard tickets={optimisticTickets} onCardDrop={handleCardDrop} ...>`

示例代码：

```tsx:frontend/src/app/(app)/tickets/page.tsx
const [optimisticTickets, setOptimisticTickets] = useState<KanbanTicketData[]>(tickets);
const snapshotRef = useRef<KanbanTicketData[]>([]);

useEffect(() => { setOptimisticTickets(tickets); }, [tickets]);

async function handleCardDrop(ticketId: number, newStatus: string) {
  const snapshot = [...optimisticTickets];
  snapshotRef.current = snapshot;

  // optimistic update
  setOptimisticTickets((prev) =>
    prev.map((t) => (t.id === ticketId ? { ...t, status: newStatus } : t))
  );

  try {
    await changeTicketStatus.mutateAsync({ id: ticketId, data: { new_status: newStatus } });
  } catch {
    // rollback
    setOptimisticTickets(snapshotRef.current);
    toast.error("Failed to move ticket. Reverted.");
  }
}
```

**完成判定**：`npx tsc --noEmit frontend/src/app/(app)/tickets/page.tsx` → 0 errors；页面在 kanban 模式下渲染正常（手动验证）

---

### Step 4: 编写 Vitest 单元测试

操作：
- a) 新建 `frontend/src/app/(app)/tickets/kanban-board-dnd.test.tsx`
- b) 测试 1 — 拖拽成功：mock `onCardDrop`；触发 `DndContext.onDragEnd`；验证 `setOptimisticTickets` 被调用一次且新 status 正确
- c) 测试 2 — API 失败 rollback：mock `mutateAsync` throw；验证 `setOptimisticTickets` 还原为原始 snapshot
- d) 测试 3 — `isDragging` 样式切换：drag start 后原卡片 `opacity-50` 出现
- e) `vitest run kanban-board-dnd.test.tsx` → 3 passed

**完成判定**：`npx vitest run frontend/src/app/(app)/tickets/kanban-board-dnd.test.tsx` → `3 passed`

---

### Step 5: lint + typecheck 全链路

操作：
- a) `ruff check frontend/src/components/tickets/kanban-board.tsx frontend/src/components/tickets/draggable-ticket-card.tsx` → 0 errors
- b) `npx tsc --noEmit`（项目级） → 0 errors
- c) `PYTHONPATH=src pytest tests/unit/test_ticket_service.py -v` → 回归测试全 passed

**完成判定**：三条命令全部 exit 0 / passed

---

## 6. 验收

- [ ] `ruff check frontend/src/components/tickets/kanban-board.tsx frontend/src/components/tickets/draggable-ticket-card.tsx` → 0 errors
- [ ] `npx tsc --noEmit` → 0 errors
- [ ] `npx vitest run frontend/src/app/(app)/tickets/kanban-board-dnd.test.tsx` → 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_ticket_service.py -v` → 回归 passed
- [ ] 端到端（手动）：切换 tickets page 至 kanban 视图，拖拽一张卡片至相邻列，松手后卡片出现在目标列；再拖一次并故意网络断连，卡片回弹原列并出现错误提示

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 乐观更新期间 `tickets` prop 从父级刷新，导致 optimistic state 被外部覆盖 | 低 | 中 | `useEffect` 依赖 `[tickets]` 时判断当前是否有 pending mutation，若有则跳过同步 |
| `@dnd-kit` 与项目现有 React 版本不兼容导致运行时警告 | 低 | 低 | 参照 tasks/page.tsx 的相同版本来固定依赖版本 |
| 快速连续拖拽（第一次请求未完成第二次开始）导致最终状态不确定 | 中 | 中 | 用 `useRef<AbortController>` 取消上一次 pending mutation，保证最终只以最后一次 drop 为准 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/components/tickets/kanban-board.tsx \
        frontend/src/components/tickets/draggable-ticket-card.tsx \
        frontend/src/app/\(app\)/tickets/page.tsx \
        frontend/src/app/\(app\)/tickets/kanban-board-dnd.test.tsx
git commit -m "feat(tickets): drag-and-drop between kanban columns with optimistic UI"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(tickets): kanban drag-and-drop with optimistic UI" --body "Closes #554"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现（拖拽+乐观更新模式）：[`frontend/src/app/(app)/tasks/page.tsx`](../../frontend/src/app/(app)/tasks/page.tsx)
- 静态看板入口：[`frontend/src/components/tickets/kanban-board.tsx`](../../frontend/src/components/tickets/kanban-board.tsx)
- 已有 PATCH 端点（后端无需改动）：[`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) — `PUT /tickets/{ticket_id}/status`
- 父 issue：#54
- 依赖板块：#553

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
