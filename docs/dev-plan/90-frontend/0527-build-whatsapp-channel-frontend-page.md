# WhatsApp Channel · Build frontend page for WhatsApp messaging

| 元数据 | 值 |
|---|---|
| Issue | #527 |
| 分类 | 90-frontend |
| 优先级 | 推荐 |
| 工作量 | 1-2 工作日 |
| 依赖 | [Build WhatsApp channel backend](../40-campaigns/0526-create-whatsapp-conversation-service.md) |
| 启用后赋能 | [Automate message rules (upstream consumer)](0500-add-developer-documentation-page-and-api-playground.md) — TBD — 待验证：确认自动化规则引擎文档编号 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #527 is a frontend subtask of the WhatsApp channel epic (#71). The backend for WhatsApp conversations is being built in parallel under #526. Without a frontend page, the channel cannot be used — customer service reps have no UI to view conversation history or dispatch outbound messages.

### 1.2 做完后

- **用户视角**：Customer service reps and admins can open `/channels/whatsapp` and see a list of WhatsApp conversations (customer name, last message preview, timestamp, unread badge). Clicking a conversation opens a chat pane with message bubbles, timestamps, and send controls for text, image, and voice.
- **开发者视角**：New frontend page `src/frontend/pages/channels/whatsapp.tsx` is wired to existing REST endpoints (no new backend required). It follows established API client patterns from the codebase.

### 1.3 不做什么（剔除）

- [ ] No new REST endpoints on the backend — wire to endpoints created in #526 only
- [ ] No real-time WebSocket/SSE message streaming — polling is out of scope
- [ ] No WhatsApp Business API credential management UI — separate issue

### 1.4 关键 KPI

- [Page renders: `http://localhost:3000/channels/whatsapp` loads with conversation list and no console errors]
- [Send button: clicking "Send" dispatches a `POST /api/conversations/{id}/messages` with `{text: "...", type: "text"}`]
- [TypeScript: `cd frontend && npx tsc --noEmit` → 0 errors]
- [Existing tests: `cd frontend && npm test` → all pass]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`frontend/src/app/(app)/channels/` directory — existing channel pages to use as structural reference L?

TBD - 待验证：`frontend/src/lib/api/client.ts` or `frontend/src/lib/api/queries.ts` — existing API client patterns (e.g. `useQuery`, `useMutation` from TanStack Query or similar) L?

TBD - 待验证：`frontend/src/app/(app)/automation/rules/page.tsx` or similar list + detail layout — UI pattern to replicate for conversation list + chat split L?

### 2.2 涉及文件清单

- 要改：
  - TBD — likely `frontend/src/app/(app)/layout.tsx` or `frontend/src/app/layout.tsx` — add route /channels/whatsapp
- 要建：
  - `frontend/src/app/(app)/channels/whatsapp/page.tsx` — main page component
  - `frontend/src/app/(app)/channels/whatsapp/_components/ConversationList.tsx` — left panel list
  - `frontend/src/app/(app)/channels/whatsapp/_components/ChatWindow.tsx` — right panel chat pane
  - `frontend/src/app/(app)/channels/whatsapp/_components/MessageBubble.tsx` — individual message bubble
  - `frontend/src/app/(app)/channels/whatsapp/_components/SendControls.tsx` — text/image/voice controls
  - `frontend/src/lib/api/conversations.ts` — API client functions for GET / POST
  - `frontend/src/types/whatsapp.ts` — TypeScript interfaces for Conversation, Message types

### 2.3 缺什么

- [ ] No WhatsApp channel page at `/channels/whatsapp` — page component missing
- [ ] No conversation list component with customer name, last message, timestamp, unread badge
- [ ] No chat window with message bubbles, timestamps
- [ ] No send controls supporting text / image / voice message types
- [ ] No API client functions for `GET /api/conversations` and `POST /api/conversations/{id}/messages`
- [ ] No TypeScript types for Conversation and Message domain objects

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/app/(app)/channels/whatsapp/page.tsx` | Main page: layout with conversation list + chat window split |
| `frontend/src/app/(app)/channels/whatsapp/_components/ConversationList.tsx` | Left panel: scrollable list of conversations with preview data |
| `frontend/src/app/(app)/channels/whatsapp/_components/ChatWindow.tsx` | Right panel: chat pane with messages + send controls |
| `frontend/src/app/(app)/channels/whatsapp/_components/MessageBubble.tsx` | Single message bubble, inbound/outbound variants |
| `frontend/src/app/(app)/channels/whatsapp/_components/SendControls.tsx` | Input bar with text input, image attach, voice record buttons |
| `frontend/src/lib/api/conversations.ts` | API client: `fetchConversations()`, `sendMessage(convId, payload)` |
| `frontend/src/types/whatsapp.ts` | TypeScript interfaces: `Conversation`, `Message`, `SendMessagePayload` |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD — likely `frontend/src/app/(app)/channels/page.tsx` or `frontend/src/app/page.tsx` | Add WhatsApp link in channel navigation (if existing nav exists) |
| TBD — `frontend/package.json` | Add any new dependencies (TanStack Query, date utility libs) if not already present |

### 3.3 新增能力

- **Page route**：`/channels/whatsapp` — accessible after login
- **API client functions**：`fetchConversations(tenantId)` → `Conversation[]`, `sendMessage(convId, payload)` → `Message`
- **TypeScript types**：`Conversation { id, customer_id, customer_name, last_message, last_timestamp, unread_count }`, `Message { id, conversation_id, sender, body, type, timestamp }`
- **UI components**：Responsive split-pane layout (conversation list left, chat window right); message bubbles with inbound (left) / outbound (right) alignment; send controls with text input, image upload button, voice record button

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use Next.js App Router (`frontend/src/app/(app)/channels/whatsapp/page.tsx`) over Pages Router** — codebase already uses App Router (inferred from `frontend/src/app/(app)/automation/rules/page.tsx`); consistent file-based routing and Server Components support.
- **Use TanStack Query (or similar) for data fetching over raw `fetch`** — existing API client patterns in `frontend/src/lib/api/queries.ts` suggest this; enables caching, loading/error states, optimistic updates for send.
- **No new backend endpoints** — #526 delivers the backend; this page only wires to existing REST endpoints. Avoids scope creep.

### 4.2 版本约束

<!-- No new npm dependencies anticipated. If TanStack Query is not yet present, pin to latest stable. -->

| 依赖 | 版本 | 理由 |
|------|------|------|
| TanStack Query | `^5.x` | If added — matches modern App Router patterns; pin minor for stability |

### 4.3 兼容性约束

- All API calls must include tenant context (from auth session / context provider)
- Message payload shape must match `SendMessagePayload` as defined in `frontend/src/types/whatsapp.ts`
- TypeScript strict mode enabled — no `any` casts to silence errors
- Components must be client components (`"use client"`) if using hooks (useState, useEffect, TanStack Query hooks)

### 4.4 已知坑

1. **Next.js App Router `"use client"` directive required** → 规避：Mark all interactive components with `"use client"` at the top; page-level server component can import client components normally
2. **API response shape mismatches TypeScript types** → 规避：Align `Conversation` / `Message` interfaces with actual backend response from #526 before wiring; add `console.log` in dev to catch shape drift
3. **Unread badge flicker on initial load** → 规避：Initialize unread count in component state from API data; avoid client-side-only counter that differs from server truth

---

## 5. 实现步骤（按顺序）

### Step 1: Define TypeScript interfaces

Add `frontend/src/types/whatsapp.ts` with all domain types needed for the page.

```typescript
// frontend/src/types/whatsapp.ts
export type MessageType = "text" | "image" | "voice";

export interface Message {
  id: number;
  conversation_id: number;
  sender: "customer" | "agent";
  body: string;         // text content or URL for image/voice
  type: MessageType;
  timestamp: string;    // ISO 8601
}

export interface Conversation {
  id: number;
  customer_id: number;
  customer_name: string;
  last_message: string;
  last_timestamp: string;
  unread_count: number;
}

export interface SendMessagePayload {
  type: MessageType;
  text?: string;
  media_url?: string;
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/types/whatsapp.ts` → exit 0

### Step 2: Add API client functions

Create `frontend/src/lib/api/conversations.ts` using existing patterns (e.g. `get` / `post` helpers from `frontend/src/lib/api/queries.ts`).

```typescript
// frontend/src/lib/api/conversations.ts
import { Conversation, Message, SendMessagePayload } from "@/types/whatsapp";

export async function fetchConversations(tenantId: number): Promise<Conversation[]> {
  const res = await fetch(`/api/conversations?tenant_id=${tenantId}&channel=whatsapp`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  const json = await res.json();
  return json.data?.items ?? json.data ?? [];
}

export async function sendMessage(
  conversationId: number,
  payload: SendMessagePayload
): Promise<Message> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to send message");
  const json = await res.json();
  return json.data;
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/lib/api/conversations.ts` → exit 0

### Step 3: Build ConversationList component

Create `frontend/src/app/(app)/channels/whatsapp/_components/ConversationList.tsx`.

- Uses TanStack Query `useQuery` to call `fetchConversations(tenantId)`
- Renders scrollable list: customer name, last message preview (truncated), relative timestamp, unread badge (red dot + count)
- Clicking a conversation calls `onSelect(conversation)` prop
- Shows loading skeleton while fetching, empty state if no conversations

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors；component renders without runtime errors in dev

### Step 4: Build MessageBubble component

Create `frontend/src/app/(app)/channels/whatsapp/_components/MessageBubble.tsx`.

- Props: `message: Message`
- If `sender === "customer"`: left-aligned bubble, light gray background
- If `sender === "agent"`: right-aligned bubble, brand-color background, white text
- For `type === "image"`: renders `<img src={body} />`
- For `type === "voice"`: renders `<audio controls src={body} />`
- Shows timestamp below bubble in small gray text

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

### Step 5: Build SendControls component

Create `frontend/src/app/(app)/channels/whatsapp/_components/SendControls.tsx`.

- Text input (controlled, Enter or Send button submits)
- Image attach button (opens file picker, sets `media_url` in payload)
- Voice button (uses `navigator.mediaDevices.getUserMedia` for recording; on stop, uploads blob and sets `media_url` — or falls back to a placeholder noting voice upload is stubbed)
- Calls `onSend(payload: SendMessagePayload)` prop on submit
- Disabled state while sending (prevents double-submit)

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

### Step 6: Build ChatWindow component

Create `frontend/src/app/(app)/channels/whatsapp/_components/ChatWindow.tsx`.

- Composes `MessageBubble` list + `SendControls`
- On mount, fetches messages for selected conversation via `useQuery` (endpoint TBD — likely `GET /api/conversations/{id}/messages`)
- Auto-scrolls to bottom on new messages
- Shows "Select a conversation" empty state when no conversation is selected
- After send success, prepends new message to list optimistically

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors

### Step 7: Build main page and wire everything

Create `frontend/src/app/(app)/channels/whatsapp/page.tsx`.

- `"use client"` at top
- Layout: flex row — `<ConversationList>` (fixed width ~320px) + `<ChatWindow>` (flex-1)
- Owns selected conversation state: `selectedConversation: Conversation | null`
- Passes `onSelect` to ConversationList; passes selected conversation to ChatWindow
- Gets `tenantId` from auth context (TBD — likely from existing auth provider / session hook)

```typescript
// frontend/src/app/(app)/channels/whatsapp/page.tsx
"use client";

import { useState } from "react";
import ConversationList from "./_components/ConversationList";
import ChatWindow from "./_components/ChatWindow";
import type { Conversation } from "@/types/whatsapp";
import { useAuth } from "@/lib/auth";  // TBD — verify path

export default function WhatsAppChannelPage() {
  const { tenantId } = useAuth();
  const [selected, setSelected] = useState<Conversation | null>(null);

  return (
    <div className="flex h-screen">
      <ConversationList tenantId={tenantId} onSelect={setSelected} />
      <ChatWindow conversation={selected} />
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors；page renders at `/channels/whatsapp`

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 errors
- [ ] `cd frontend && npm run lint` (or `next lint`) → 0 errors and 0 warnings
- [ ] `cd frontend && npm test` → all pass
- [ ] Page loads at `http://localhost:3000/channels/whatsapp` without console errors
- [ ] Conversation list renders (or empty state if no data)
- [ ] Selecting a conversation opens chat window with messages
- [ ] Send button dispatches `POST /api/conversations/{id}/messages` with correct JSON payload
- [ ] No TypeScript `any` casts used to silence errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #526 backend not ready when frontend is tested — API calls fail with 404 | 中 | 低 | Mock API responses in development using MSW (Mock Service Worker) or Next.js route handlers; frontend work is not blocked by backend completion |
| TanStack Query version conflict with existing codebase version | 低 | 中 | Pin to the version already used in `frontend/package.json`; skip adding as new dependency |
| Voice recording requires browser permissions and HTTPS — fails in dev without secure context | 低 | 中 | Gracefully degrade: voice button shows tooltip "Available over HTTPS only" and does not crash the component; text and image send still work |
| Auth context / `tenantId` not available in page component (auth provider not set up in this region) | 中 | 高 | Use a `tenantId` prop passed from a parent layout that has auth; document the assumption in a `// TODO` comment — unblock other work while auth wiring is finalized separately |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/app/\(app\)/channels/whatsapp/
git commit -m "feat(frontend): add WhatsApp channel page with conversation list and chat window"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): build WhatsApp channel page (#527)" --body "Closes #527

## Summary
- Add WhatsApp channel page at \`/channels/whatsapp\`
- Conversation list with customer name, last message, timestamp, unread badge
- Chat window with message bubbles (text/image/voice) and send controls
- Wire to existing REST endpoints from #526 backend

## Test plan
- [ ] \`cd frontend && npx tsc --noEmit\` → 0 errors
- [ ] \`cd frontend && npm run lint\` → 0 errors
- [ ] \`cd frontend && npm test\` → all pass
- [ ] Page renders at /channels/whatsapp
- [ ] Send button dispatches POST to /api/conversations/{id}/messages

🤖 Generated with [Claude Code](https://claude.ai/code)"

# 2. Update dev-plan board
# - Mark this board as completed in docs/dev-plan/README.md §1.1 AUTO-INDEX
# - No manual Changelog entry needed — generator auto-updates on merge
```

---

## 9. 参考

- Subtask parent: [#71 — WhatsApp channel epic](https://github.com/search?q=repo%3A*%2F*+%2371+whatsapp)
- Backend dependency: [#526 — Build WhatsApp channel backend API](../40-campaigns/0526-create-whatsapp-conversation-service.md)
- Existing frontend patterns: TBD — `frontend/src/lib/api/queries.ts` — verify API client conventions
- Existing frontend layout pattern: TBD — `frontend/src/app/(app)/automation/rules/page.tsx` — verify split-pane list/detail layout
- TanStack Query docs: [TanStack Query](https://tanstack.com/query/latest)
- Next.js App Router: [Next.js Docs](https://nextjs.org/docs/app)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---
