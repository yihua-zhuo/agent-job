No page store exists. The dev-plan board explicitly notes this may be stubbed. I now have enough to write the plan. Here's the output:

# Implementation Plan — Issue #509

## Goal
Create a `CopilotChat` floating panel component in the frontend that calls the already-merged `POST /copilot/chat` backend endpoint (from #508). The panel shows a floating button (bottom-right), expands to a collapsible chat window with a context bar (current customer/opportunity), a scrollable message list, a text input with send button, and suggested prompts on the empty state. Tool-call results are rendered as structured cards inline in the message list.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0509-add-copilotchat-component-to-frontend.md`
Template depth: `medium`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-medium.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0509-add-copilotchat-component-to-frontend.md`

## Affected Files
- `frontend/src/components/CopilotChat.tsx` — new file: floating button, collapsible chat window, context bar, message list, input, send, suggested prompts, tool-call cards
- `frontend/src/hooks/usePageContext.ts` — new file: stub hook returning `{ customer_id, opportunity_id }` (returns nulls; no page store exists yet — see §2.3 of the dev-plan board)
- `frontend/src/lib/api/queries.ts` — add `useSendCopilotMessage` mutation hook calling `POST /copilot/chat?message=...`
- `frontend/src/app/(app)/layout.tsx` — mount `<CopilotChat />` alongside the existing `<AIPanel />` (L79)

## Implementation Steps

1. **Add `useSendCopilotMessage` mutation hook to `queries.ts`**. The backend endpoint is `POST /copilot/chat?message=<text>` (query-param, not JSON body — see `src/api/routers/copilot.py` L13-L35). The hook must use `apiClient.post` with an empty body and append `?message=<encoded text>` to the path. It must read the token from `useAuthStore` (same pattern as every other hook in the file, e.g. `useCreateTask` L355-L363). Response shape is `{ success: true, data: { response, conversation_id, tool_calls } }`. Add a type alias for the response data and return `mutate`/`mutateAsync`/`isPending`/`error` from the hook.

2. **Create `frontend/src/hooks/usePageContext.ts`**. No page store exists in `frontend/src/lib/store/` (only `auth-store.ts`, `task-store.ts`, `theme-store.ts`), so the hook is a thin stub for this board. Export `usePageContext(): { customer_id: number | null; opportunity_id: number | null }` returning `{ customer_id: null, opportunity_id: null }`. The dev-plan §4.4 risk #3 explicitly tolerates this: "Stub `usePageContext` returns nulls; context bar shows 'No context'". Add a brief comment that this should be wired to the page store once it exists.

3. **Create `frontend/src/components/CopilotChat.tsx` as a client component**. Add `"use client"` directive (required: it calls an API endpoint and uses `useState`). The component uses: `useState` for `isOpen`, `messages` (array of `{ role, content }`), `input`, and `isLoading`; `usePageContext` for the context bar; `useSendCopilotMessage` for the API call. The FAB button is fixed-position bottom-right (`fixed bottom-6 right-6 z-[9999]` per dev-plan §4.3). The chat window is a panel anchored above the FAB (`bottom-24 right-6`) with the same width/height pattern as the existing `AIPanel` in `frontend/src/lib/components/ai-panel.tsx` L82-L87. The context bar at the top shows `"Chatting about: Customer #{N}"` when `customer_id` is set, otherwise `"No context"` (also reflects `opportunity_id` when set). The message list renders user messages right-aligned (primary background) and assistant messages left-aligned (muted background). Suggested prompts (e.g. "Show my top leads", "Summarize this ticket", "What's new today?") are shown only when `messages.length === 0`. On send: append the user message, call `mutate`, on success append the assistant response, clear the input. On error: append a red inline error message ("Copilot unavailable") — matches dev-plan §7 fallback. For tool-call rendering: when a message's response includes non-empty `tool_calls`, render each as a structured card (bordered, rounded, with tool name and a summary of arguments/result) below the assistant message bubble.

4. **Mount `<CopilotChat />` in `frontend/src/app/(app)/layout.tsx`**. The dev-plan lists this as TBD-verification but the path is already identified: `frontend/src/app/(app)/layout.tsx` exists and already mounts `<AIPanel />` at L79. Add `import { CopilotChat } from "@/components/CopilotChat"` and place `<CopilotChat />` next to `<AIPanel />` (both are global, client-side floating panels rendered inside `<AuthGuard>`).

5. **Verify build, lint, and type-check**. Run `cd frontend && npx tsc --noEmit` (dev-plan §6 acceptance), `cd frontend && npm run lint` (dev-plan §6 acceptance), and `cd frontend && npm run build` (dev-plan §6 acceptance). All must exit 0.

6. **Manual E2E verification** (dev-plan Step 6). `cd frontend && npm run dev`, navigate to an authenticated page, click the FAB, type a message, press Send, confirm: (a) the user message appears in the list, (b) a loading indicator shows, (c) the assistant response renders from the API, (d) no unhandled errors in the browser console.

## Test Plan
- Unit tests in `tests/unit/`: none required. The dev-plan board does not list unit tests for this frontend component (the `AIPanel` precedent at `frontend/src/lib/components/ai-panel.tsx` has no test file either). Frontend tests in this repo use `vitest run` (see `frontend/package.json` L9), but no test file exists for the analogous `ai-panel.tsx`. The dev-plan §6 acceptance criteria are `npx tsc --noEmit` + `npm run lint` + `npm run build` — all type/lint checks, not unit tests.
- Integration tests in `tests/integration/`: not applicable. This board is frontend-only; the backend `POST /copilot/chat` endpoint is covered by `tests/unit/test_copilot_service.py` (already merged in #508).
- Dev-plan verification: dev-plan §6 lists five commands — `npx tsc --noEmit`, `npm run lint`, `npm run build`, `git diff --stat` showing the new file, and a manual E2E (chat opens, message sent, response displayed). Steps 5 and 6 above cover all five.

## Acceptance Criteria
- `cd frontend && npx tsc --noEmit` exits 0 (no type errors in `CopilotChat.tsx`, `usePageContext.ts`, or the added hook in `queries.ts`).
- `cd frontend && npm run lint` exits 0.
- `cd frontend && npm run build` exits 0.
- `frontend/src/components/CopilotChat.tsx` exists as a new file and `frontend/src/app/(app)/layout.tsx` is modified to import and mount `<CopilotChat />` (verifiable via `git diff --stat`).
- Manual: clicking the floating button (bottom-right) opens the chat panel; typing a message and pressing Send displays the user message in the list followed by an assistant response from `POST /copilot/chat?message=...`.

## Risks / Open Questions
- The `POST /copilot/chat` backend endpoint takes `message` as a **query parameter** (not a JSON body), confirmed at `src/api/routers/copilot.py` L15. The `useSendCopilotMessage` hook must build the URL as `/api/v1/copilot/chat?message=<encoded>` and POST with an empty body, not send JSON. This differs from the dev-plan board's Step 1 example which suggests a JSON body — the plan must follow the actual backend contract.
- No page store exists for reading current customer/opportunity context (confirmed: `frontend/src/lib/store/` contains only `auth-store.ts`, `task-store.ts`, `theme-store.ts`). `usePageContext` is a stub returning nulls, matching dev-plan §4.4 risk #3. The context bar will show "No context" until a page store is implemented in a future board.
- The existing `<AIPanel />` at `frontend/src/app/(app)/layout.tsx` L79 is a UI-only mock (no API calls — see `ai-panel.tsx` L48-L55: "Simulated AI response — replace with real API call when backend is wired"). The new `<CopilotChat />` and the existing `<AIPanel />` will both appear in the layout. This is acceptable per the issue body (the boards are independent), but a future board may need to consolidate them.
