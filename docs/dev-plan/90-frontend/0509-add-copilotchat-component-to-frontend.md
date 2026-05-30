# CopilotChat · Add floating AI chat copilot panel to frontend

| 元数据 | 值 |
|---|---|
| Issue | #509 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：0508 backend copilot endpoint board 编号，待确认实际文件名 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently lacks a unified AI chat interface for users to query copilot capabilities while working within customer or opportunity context. Issue #76 defines the overall Copilot feature direction, and #508 adds the backend `POST /copilot/chat` endpoint. Without a frontend panel, the backend endpoint is unreachable and the feature is not usable. This board delivers the interactive chat UI that makes the copilot accessible directly from the CRM workspace.

### 1.2 做完后

- **用户视角**：用户 clicks a floating button (bottom-right of every page) to open a collapsible chat panel. The panel shows a context bar indicating the current customer/opportunity. The user types a message and receives structured tool-call response cards rendered inline. On first open (empty state), suggested prompts are displayed.
- **开发者视角**：A new `CopilotChat` component at `src/frontend/components/CopilotChat.tsx` is available for import. The component reads page context from the store and calls `POST /copilot/chat` via the existing API client pattern.

### 1.3 不做什么（剔除）

- [ ] Backend copilot logic or endpoint implementation — covered by #508
- [ ] Authentication / session management for copilot — assumed to exist from the parent feature
- [ ] Persistent chat history across sessions — messages are session-only for this board
- [ ] Multi-language / i18n of UI strings — all strings are English for now

### 1.4 关键 KPI

- [指标 1：`cd frontend && npx tsc --noEmit` → 0 errors (type-check passes)]
- [指标 2：`cd frontend && npm run lint` → 0 errors]
- [指标 3：E2E — chat window opens via button click, sends a message, and displays a response card; verified via Playwright or manual step]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。No `CopilotChat` component exists yet. The closest existing pattern is the `BulkActionsBar` at [`frontend/src/components/tickets/bulk-actions-bar.tsx`](../../../frontend/src/components/tickets/bulk-actions-bar.tsx), which demonstrates how this project structures collapsible UI panels and uses the API client.

### 2.2 涉及文件清单

- 要改：
  - [`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) — add `sendCopilotMessage` query hook (if not already added by #508)
- 要建：
  - `frontend/src/components/CopilotChat.tsx` — floating button + collapsible chat window + context bar + message list + input + send
  - TBD - 待验证：确认 layout.tsx 路径 — import and mount `<CopilotChat />` in the root app layout (or a specific layout that has page-store context)

### 2.3 缺什么

- [ ] No `CopilotChat` component — the primary deliverable
- [ ] No page-store hook to read current customer/opportunity context — need to determine whether it exists or needs to be stubbed
- [ ] No `POST /copilot/chat` call from the frontend API client — may have been added by #508; needs verification
- [ ] No suggested-prompts empty-state UI in any existing component — new pattern to introduce

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/components/CopilotChat.tsx` | Floating chat panel: button, window, context bar, message list, input, send, suggested prompts |
| `frontend/src/hooks/usePageContext.ts` | Hook to read current customer/opportunity from page store (stub if not yet available) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：确认 layout.tsx 路径 | Import and mount `<CopilotChat />` in the root app layout |
| [`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) | Add `useSendCopilotMessage` mutation hook calling `POST /copilot/chat` |

### 3.3 新增能力

- **Component**：`CopilotChat` — renders floating FAB (bottom-right), expands to chat window, shows context bar, message list, text input, send button
- **API hook**：`useSendCopilotMessage()` — TanStack Query mutation, calls `POST /copilot/chat`
- **UX pattern**：Suggested prompts shown on empty state (first-open)
- **UX pattern**：Tool-call results rendered as structured cards in the message list

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **State management via TanStack Query mutation** (not raw `fetch`) — aligns with the project's established API client pattern in `frontend/src/lib/api/queries.ts`
- **Client-side collapsible state** via React `useState` — no external state library needed; the chat window is ephemeral
- **Context bar reads from `usePageContext` hook** — decouples the component from the store implementation, allowing it to work regardless of whether the store uses Zustand, Redux, or React Context

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react` | `^18.x` (existing) | matches current frontend React version |
| `@tanstack/react-query` | `^5.x` (existing) | existing API client pattern |
| `tailwindcss` | `^3.x` (existing) | existing styling approach |

### 4.3 兼容性约束

- All imports use path aliases or relative paths relative to `frontend/src/`
- API client always reads `tenant_id` from the existing auth context — copilot calls must forward it
- Component is a pure client component (`"use client"` directive) since it calls an API endpoint
- Floating button must use fixed positioning (`position: fixed; bottom: 1.5rem; right: 1.5rem`) and respect `z-index` to sit above the sidebar

### 4.4 已知坑

1. **Z-index stacking with sidebar** → 规避：assign `z-index: 9999` to the chat FAB and ensure the sidebar `z-index` is lower; confirm visually on the `(app)` layout
2. **TanStack Query mutation not invalidated on error** → 规避：handle error state explicitly in the component UI (show red inline message) rather than relying on automatic retry
3. **Context bar shows stale data if page store updates** → 规避：subscribe to the page store via the `usePageContext` hook; if the hook is not yet built, stub it to return `{ customer: null, opportunity: null }` and document the TBD

---

## 5. 实现步骤（按顺序）

### Step 1: Add `useSendCopilotMessage` mutation hook

Add a TanStack Query mutation hook to `frontend/src/lib/api/queries.ts` that calls `POST /copilot/chat`. The hook should accept `{ message: string; context?: Record<string, unknown> }` and return `{ data, isPending, error, mutate }`.

If the hook already exists (added by #508), skip this step and verify it matches the expected signature.

操作：
- a) Open `frontend/src/lib/api/queries.ts`
- b) Add `useSendCopilotMessage` using `useMutation` from `@tanstack/react-query`
- c) POST body: `{ message, context: { customer_id, opportunity_id } }` (forward tenant context)
- d) Return typed response via the existing API client pattern

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

---

### Step 2: Create `usePageContext` hook

Create `frontend/src/hooks/usePageContext.ts` as a thin wrapper that reads the current customer and opportunity from whatever page store exists. If no store is available yet, stub the return value so the component compiles and can be finished once the store is implemented.

操作：
- a) Create `frontend/src/hooks/usePageContext.ts`
- b) Export `usePageContext(): { customer_id: number | null; opportunity_id: number | null }`
- c) If the page store pattern is unknown, stub with `{ customer_id: null, opportunity_id: null }` and add a `// TODO: wire to page store after #508 lands` comment

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

---

### Step 3: Build `CopilotChat` component shell

Create `frontend/src/components/CopilotChat.tsx` with the fixed-position floating button. The button toggles `isOpen: boolean` state. Import and render the component stub from `Step 4`.

操作：
- a) Create `frontend/src/components/CopilotChat.tsx`
- b) Add `"use client"` directive
- c) Add `isOpen` state, FAB button with fixed positioning, conditional render of chat window container (empty for now)
- d) Style with Tailwind: `fixed bottom-6 right-6 z-[9999]`

```tsx
"use client";

import { useState } from "react";

export function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-[9999] ..."
      >
        {isOpen ? "✕" : "💬"}
      </button>
      {isOpen && <div className="fixed bottom-24 right-6 ...">...</div>}
    </>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

---

### Step 4: Implement chat window — context bar, message list, input, suggested prompts

Extend the `CopilotChat` component from Step 3 to include all interior UI elements: context bar at top (shows current customer/opportunity from `usePageContext`), scrollable message list, text input with send button, and suggested prompt chips when the message list is empty.

操作：
- a) In `CopilotChat.tsx`, add imports: `useSendCopilotMessage`, `usePageContext`
- b) Add `messages: Array<{role: 'user'|'assistant'; text: string}>` state
- c) Add `input: string` state for the text field
- d) On send: call `mutate({ message: input, context: { customer_id, opportunity_id } })`, append user message to list, on success append assistant response, clear input
- e) Render context bar: `"Chatting about: Customer #N" | "No context"`
- f) Render suggested prompts only when `messages.length === 0` (e.g. "Show my top leads", "Summarize this ticket")

示例代码（message list fragment）：

```tsx
<div className="flex-1 overflow-y-auto space-y-3 p-4">
  {messages.length === 0 && (
    <div className="flex flex-wrap gap-2">
      {["Show my top leads", "Summarize this ticket", "What's new today?"].map((p) => (
        <button key={p} onClick={() => setInput(p)} className="chip">
          {p}
        </button>
      ))}
    </div>
  )}
  {messages.map((m, i) => (
    <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
      <span className={`inline-block px-3 py-2 rounded-lg ${m.role === "user" ? "bg-blue-500 text-white" : "bg-gray-100"}`}>
        {m.text}
      </span>
    </div>
  ))}
</div>
```

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors && `cd frontend && npm run lint` → 0 errors

---

### Step 5: Mount `CopilotChat` in the app layout

Add `<CopilotChat />` to TBD - 待验证：确认 layout.tsx 路径 (or the appropriate root layout for authenticated pages) so it is globally available. Confirm the import path is correct relative to the layout file.

操作：
- a) Open TBD - 待验证：确认 layout.tsx 路径
- b) Add `import { CopilotChat } from "@/components/CopilotChat"` (or relative path)
- c) Insert `<CopilotChat />` before the closing `</div>` of the layout root

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

---

### Step 6: Manual E2E verification

Run the frontend dev server and verify the chat window opens, sends a message, and displays a response. This step is manual but documented with exact steps.

操作：
- a) `cd frontend && npm run dev`
- b) Navigate to any authenticated page (e.g. `/tasks`)
- c) Click the floating button (bottom-right) — chat window opens
- d) Type a message and press Send — message appears in list, loading spinner shown
- e) Response from `POST /copilot/chat` appears as assistant message

**完成判定**：Manual confirmation that the chat window opens, sends, and displays a response — no crash, no unhandled error in console

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 errors
- [ ] `cd frontend && npm run lint` → 0 errors
- [ ] `cd frontend && npm run build` → 0 errors (next build passes)
- [ ] `git diff --stat` shows `frontend/src/components/CopilotChat.tsx` as a new file and `frontend/src/app/(app)/layout.tsx` modified
- [ ] Chat window opens via floating button click (manual E2E)
- [ ] Sending a message renders a user message in the list and an assistant response (manual E2E)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #508 backend not ready when this board ships | 中 | 中 | Component calls `/copilot/chat` which returns 404; `useSendCopilotMessage` catches error and displays "Copilot unavailable" message inline — no crash |
| Page store context hook not implemented yet | 低 | 低 | Stub `usePageContext` returns nulls; context bar shows "No context" — feature is still functional, just without pre-filled context |
| Z-index collision with sidebar or modals | 低 | 低 | CSS `z-index: 9999` on FAB; if collision occurs, adjust `bottom`/`right` values or wrap in a portal (`ReactDOM.createPortal`) — isolated CSS change, no logic impact |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/components/CopilotChat.tsx \
       frontend/src/hooks/usePageContext.ts \
       frontend/src/app/\(app\)/layout.tsx \
       frontend/src/lib/api/queries.ts
git commit -m "feat(frontend): add CopilotChat floating panel component

- Floating button (bottom-right) opens collapsible chat window
- Context bar shows current customer/opportunity from page store
- Suggested prompts on empty state
- Calls POST /copilot/chat via TanStack Query mutation
- Closes #509"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): CopilotChat component" --body "Closes #509

## Summary
- Add \`CopilotChat\` component: floating button + collapsible chat window + context bar + message list + input + suggested prompts
- Add \`usePageContext\` hook (stubbed until page store is wired)
- Add \`useSendCopilotMessage\` mutation hook
- Mount in \`(app)\` layout

## Test plan
- [ ] \`cd frontend && npx tsc --noEmit\` → 0 errors
- [ ] \`cd frontend && npm run lint\` → 0 errors
- [ ] \`cd frontend && npm run build\` → 0 errors
- [ ] Manual: chat window opens, message sent, response displayed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. Update this board
# - Mark §状态 = ✅ 已完成
# - Add entry to Changelog table
