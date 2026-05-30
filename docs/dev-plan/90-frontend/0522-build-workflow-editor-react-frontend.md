# Workflow Editor · Visual automation workflow editor React frontend

| 元数据 | 值 |
|---|---|
| Issue | #522 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [#521](0501-build-workflow-data-models-api-routes.md) |
| 启用后赋能 | #524, #525, #526 — TBD |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #521 provides the data models, service layer, and API routers for automation rules. The backend is ready, but end users have no way to visually author, wire, and configure automation workflows — they can only hit the API directly or via raw JSON. A graph-based visual editor is the standard UX surface for workflow automation products (Zapier, Make, n8n, AWS Step Functions). Without a frontend editor, the automation rule engine cannot be shipped as a complete user-facing feature.

### 1.2 做完后

- **用户视角**: A non-technical admin opens `/automation/rules` in the CRM and can drag Trigger/Condition/Action/Approval/Loop node types from a sidebar palette onto a pan-and-zoom canvas, wire them together by dragging from output ports to input ports, click any node to open a side-config panel with a JSON form, and save the resulting rule graph back to the API.
- **开发者视角**: A new `src/workflow/editor/` component tree provides `WorkflowCanvas`, `NodePalette`, `NodeWrapper`, `ConnectionLine`, and `ConfigPanel`. The editor accepts a serialized rule payload from the API, renders it with React Flow, and serializes mutations back for `PUT /api/automation/rules/{id}` / `POST /api/automation/rules`.

### 1.3 不做什么（剔除）

- [ ] No new API endpoints or backend service logic — those are supplied by #521.
- [ ] No manual test files (`tests/unit/` / `tests/integration/`) — issue states manual browser verification only.
- [ ] No backend persistence, DB schema, or Alembic migration — #521 owns that.
- [ ] No mobile-optimised layout — desktop-first (1024 px minimum viewport).
- [ ] No shareable/public workflow templates gallery — only the palette-baked default node set.

### 1.4 关键 KPI

- [指标1：`ruff check src/workflow/editor/` → 0 errors]
- [指标 2：`cd frontend && npx tsc --noEmit` → 0 type errors]
- [指标 3：Manual — page `/automation/rules` renders canvas + palette without console errors]
- [指标 4：Manual — drag a Trigger node onto canvas, open ConfigPanel, edit JSON, save → API returns updated rule]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块 (`src/workflow/editor/` is net-new; this is the first frontend piece for the automation subsystem).

### 2.2 涉及文件清单

- 要改：
  - `frontend/src/app/(app)/automation/rules/page.tsx` — TBD - 待验证：确认前端页面实际路径
  - [`frontend/src/components/layout/app-sidebar.tsx`](../../../frontend/src/components/layout/app-sidebar.tsx) — add nav link to `/automation/rules`
  - [`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) — add RTK Query endpoints for rule fetch/create/update
- 要建：
  - `frontend/src/workflow/editor/Canvas.tsx` — root React Flow canvas with pan/zoom/grid
  - `frontend/src/workflow/editor/NodePalette.tsx` — draggable node type sidebar
  - `frontend/src/workflow/editor/nodes/TriggerNode.tsx` — custom trigger node component
  - `frontend/src/workflow/editor/nodes/ConditionNode.tsx` — custom condition node
  - `frontend/src/workflow/editor/nodes/ActionNode.tsx` — custom action node
  - `frontend/src/workflow/editor/nodes/ApprovalNode.tsx` — custom approval gate node
  - `frontend/src/workflow/editor/nodes/LoopNode.tsx` — custom loop/iteration node
  - `frontend/src/workflow/editor/NodeWrapper.tsx` — wrapper that maps rule node type to the right custom node component
  - `frontend/src/workflow/editor/ConnectionLine.tsx` — custom SVG connection line renderer
  - `frontend/src/workflow/editor/ConfigPanel.tsx` — slide-in side panel with JSON config form for selected node
  - `frontend/src/workflow/editor/types.ts` — TypeScript interfaces for graph nodes, edges, and rule payload
  - `frontend/src/workflow/editor/utils.ts` — helpers: serialise rule JSON ↔ React Flow state - `frontend/src/workflow/editor/WorkflowEditor.tsx` — top-level component that composes Canvas + Palette + ConfigPanel

### 2.3 缺什么

- [ ] No visual canvas component — `reactflow` / `@xyflow/react` not yet installed in `frontend/`
- [ ] No automation rule graph data model on the frontend (`WorkflowGraph`, `RuleNode`, `RuleEdge` types)
- [ ] No sidebar palette with automation node type icons
- [ ] No node config side panel with JSON schema rendering (Monaco Editor or textarea fallback)
- [ ] No wiring from the React Flow graph state to the API routers exposed by #521
- [ ] No entry route `/automation/rules/[id]/editor` or sub-route under the rules page
- [ ] RTK Query definitions for `GET /automation/rules/:id`, `PUT /automation/rules/:id` do not yet exist in `frontend/src/lib/api/queries.ts`

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/workflow/editor/Canvas.tsx` | Root `<ReactFlow>` wrapper with pan/zoom/grid and node/edge registration |
| `frontend/src/workflow/editor/NodePalette.tsx` | Left-sidebar with draggable node-type tiles (Trigger/Condition/Action/Approval/Loop) |
| `frontend/src/workflow/editor/nodes/TriggerNode.tsx` | Custom React Flow node for trigger type |
| `frontend/src/workflow/editor/nodes/ConditionNode.tsx` | Custom React Flow node for condition type |
| `frontend/src/workflow/editor/nodes/ActionNode.tsx` | Custom React Flow node for action type |
| `frontend/src/workflow/editor/nodes/ApprovalNode.tsx` | Custom React Flow node for approval gate type |
| `frontend/src/workflow/editor/nodes/LoopNode.tsx` | Custom React Flow node for loop type |
| `frontend/src/workflow/editor/NodeWrapper.tsx` | Dispatches `ruleNode.type` → corresponding custom node component |
| `frontend/src/workflow/editor/ConnectionLine.tsx` | Custom `ConnectionLineComponent` for smooth SVG bezier output→input ports |
| `frontend/src/workflow/editor/ConfigPanel.tsx` | Right slide-in panel; renders JSON config form for the selected node |
| `frontend/src/workflow/editor/types.ts` | TypeScript interfaces: `RuleGraph`, `RuleNode`, `RuleEdge`, `WorkflowNodeType` |
| `frontend/src/workflow/editor/utils.ts` | `ruleGraphToFlow(n: RuleGraph) → {nodes, edges}` and inverse `flowToRuleGraph` |
| `frontend/src/workflow/editor/WorkflowEditor.tsx` | Composes `Canvas` + `NodePalette` + `ConfigPanel`; owns `nodes`, `edges`, `onNodesChange` state |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `frontend/src/app/(app)/automation/rules/page.tsx` | TBD - 待验证：确认前端页面实际路径 |
| [`frontend/src/components/layout/app-sidebar.tsx`](../../../frontend/src/components/layout/app-sidebar.tsx) | Add `<Link href="/automation/rules/new">` entry to Automation section |
| [`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) | Add `useGetRule`, `useUpdateRule` RTK Query endpoints wired to `/automation/rules/:id` |

### 3.3 新增能力

- **React component**: `<WorkflowEditor ruleId={number} />` — self-contained editor shell
- **Custom React Flow nodes**: `TriggerNode`, `ConditionNode`, `ActionNode`, `ApprovalNode`, `LoopNode` — each with typed handles (input/output ports)
- **Connection line**: smooth bezier SVG from source handle (right) → target handle (left)
- **Config panel**: JSON textarea (Monaco Editor for Pro tier, plain `<textarea>` fallback) bound to selected node's `data.config`
- **Graph ↔ API translation**: bidirectional transform between React Flow `{nodes, edges}` and the rule JSON payload accepted by #521's API routes

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `@xyflow/react`（React Flow v11）不选 custom canvas**: React Flow handles pan/zoom, drag-and-drop, connection validation, minimap, and edge routing out of the box. Implementing these from scratch would easily eat 3× the estimated workload.
- **选 plain `<textarea>` for JSON config panel initially, Monaco Editor as follow-up**: Keep cognitive load low for v1. Monaco Editor adds ~800 kB bundle. The textarea with JSON preview satisfies "JSON config form" without over-engineering.
- **选 React Flow `addEdge` / `onNodesChange` from `useNodesState` / `useEdgesState` hooks**: Each node mutation is recorded in React Flow state; on save, `flowToRuleGraph(nodes, edges)` serialises back to the wire payload. No external state library needed for a single-editor instance.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `@xyflow/react` | `^11` | React Flow v11 ships TypeScript types built-in and supports React 18 |
| `react` | `^18` | Project minimum per `frontend/package.json` |

### 4.3 兼容性约束

- Node `data` objects must be JSON-serialisable (no class instances or React component refs) since they are serialised to the API and stored in the DB `rule_graph` JSONB column.
- Each custom node component must include `<Handle type="target" position={Position.Left} />` and `<Handle type="source" position={Position.Right} />` so the connection line can operate.
- All node type identifiers in the React Flow graph must match the string enum values expected by #521's service layer (`trigger`, `condition`, `action`, `approval`, `loop`).
- Node config panel must reflect changes in real-time to the React Flow node `data` object — do NOT clone/copy node data that escapes React Flow's managed state.

### 4.4 已知坑

1. **React Flow node data must be plain JSON objects** — storing non-serialisable values (e.g. class instances, closures) in node `data` will cause `flowToRuleGraph` to produce invalid JSON on save. → Avoidance: initialise `data` as a plain object `{ type, config: {} }` and treat it as immutable after creation.
2. **Lazy-loaded node components cause SSR issues in Next.js** — custom node components (`TriggerNode`, etc.) must use the `ParentSize` pattern or be registered via `nodeTypes` prop on `<ReactFlow>` at render time (not asynchronously). → If the editor page500s on first load, ensure node types are module-level imports, not dynamic `import()` calls.
3. **React Flow `useNodesState` does not deep-merge `data` on partial updates** — calling `updateNodeData(id, { config: newConfig })` replaces `data` entirely if not spread correctly. → Pattern: `updateNodeData(id, { ...nodes.find(n => n.id === id)?.data, ...partialUpdate })`.

---

## 5. 实现步骤（按顺序）

### Step 1: Install `@xyflow/react` and create `src/workflow/editor/` directory layout

Install the React Flow package, create the directory tree, and export barrel files so imports are consistent.

操作：
- a) `cd frontend && npm install @xyflow/react`
- b) `mkdir -p frontend/src/workflow/editor/nodes`
- c) Create `frontend/src/workflow/editor/types.ts` with the core interfaces- d) Create `frontend/src/workflow/editor/utils.ts` with stub `ruleGraphToFlow` and `flowToRuleGraph` identity functions
- e) Create `frontend/src/workflow/editor/index.ts` barrel re-exporting all public members

```typescript
// frontend/src/workflow/editor/types.ts
export type WorkflowNodeType = 'trigger' | 'condition' | 'action' | 'approval' | 'loop';

export interface RuleNodeData {
  type: WorkflowNodeType;
  label: string;
  config: Record<string, unknown>;
}

export interface RuleNode {
  id: string;
  data: RuleNodeData;
  position: { x: number; y: number };
}

export interface RuleEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface RuleGraph {
  nodes: RuleNode[];
  edges: RuleEdge[];
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/workflow/editor/types.ts` →0 type errors / `ls frontend/src/workflow/editor/` shows all directories

### Step 2: Build custom node components (`TriggerNode`, `ConditionNode`, `ActionNode`, `ApprovalNode`, `LoopNode`)

Each node is a styled card with a type badge, a label, fixed left target handle, and right source handle.

操作：
- a) In `frontend/src/workflow/editor/nodes/TriggerNode.tsx`, create a component that renders `<Card>` from the existing UI library with a "⚡ Trigger" badge- b) Add `<Handle type="target" position={Position.Left} id="in" />` and `<Handle type="source" position={Position.Right} id="out" />`
- c) Repeat for `ConditionNode` ("⚖ Condition"), `ActionNode` ("⚙ Action"), `ApprovalNode` ("✅ Approval"), `LoopNode` ("🔄 Loop")
- d) Create `frontend/src/workflow/editor/nodes/index.ts` exporting all five

```typescript
// frontend/src/workflow/editor/nodes/TriggerNode.tsx
import { Handle, Position, NodeProps } from '@xyflow/react';
import { RuleNodeData } from '../types';

export function TriggerNode({ data, selected }: NodeProps<RuleNodeData>) {
  return (
    <div style={{ border: selected ? '2px solid #3b82f6' : '1px solid #e5e7eb', borderRadius: 8, padding: 12, background: '#fff', minWidth: 160 }}>
      <Handle type="target" position={Position.Left} id="in" />
      <div style={{ fontWeight: 600, fontSize: 13 }}>⚡ {data.label || 'Trigger'}</div>
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  );
}
```

**完成判定**：`ruff check frontend/src/workflow/editor/nodes/` → 0 errors / `cd frontend && npx tsc --noEmit` → 0 errors in those files

### Step 3: Create `NodeWrapper` (type-to-component dispatcher) and `ConnectionLine`

`NodeWrapper` accepts a rule node, looks up its `data.type`, and renders the matching custom node component. `ConnectionLine` renders a smooth SVG bezier between ports.

操作：
- a) Write `frontend/src/workflow/editor/NodeWrapper.tsx` with a `NODE_TYPE_MAP` object mapping `WorkflowNodeType → component`
- b) Create `frontend/src/workflow/editor/ConnectionLine.tsx` using `ConnectionLineComponent` from `@xyflow/react`
- c) Create `nodeTypes` and `edgeTypes` maps in `WorkflowEditor.tsx` skeleton

```typescript
// frontend/src/workflow/editor/NodeWrapper.tsx
import { NodeProps } from '@xyflow/react';
import { TriggerNode } from './nodes/TriggerNode';
import { ConditionNode } from './nodes/ConditionNode';
import { ActionNode } from './nodes/ActionNode';
import { ApprovalNode } from './nodes/ApprovalNode';
import { LoopNode } from './nodes/LoopNode';
import { RuleNodeData } from './types';

const NODE_TYPE_COMPONENTS = {
  trigger: TriggerNode,
  condition: ConditionNode,
  action: ActionNode,
  approval: ApprovalNode,
  loop: LoopNode,
};

export function NodeWrapper(props: NodeProps<RuleNodeData>) {
  const Comp = NODE_TYPE_COMPONENTS[props.data?.type];
  if (!Comp) return <div>Unknown node type: {props.data?.type}</div>;
  return <Comp {...props} />;
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/workflow/editor/NodeWrapper.tsx` →0 errors / `ruff check frontend/src/workflow/editor/` → 0 errors

### Step 4: Build `WorkflowEditor.tsx` (top-level shell) and `Canvas.tsx`

`WorkflowEditor` owns the `useNodesState` / `useEdgesState` React Flow state and composes Canvas + Palette + ConfigPanel.

操作：
- a) Write `frontend/src/workflow/editor/WorkflowEditor.tsx` — wire `useNodesState`, `useEdgesState`, `onConnect`, `onNodesChange`, `onEdgesChange` from `@xyflow/react`
- b) Inside the component, accept `ruleId?: number` prop and call the RTK Query `useGetRule(ruleId)` on mount
- c) Pass `ruleGraphToFlow(existingGraph)` result to initial `nodes` / `edges` state
- d) `onSave` calls `flowToRuleGraph(nodes, edges)` and dispatches `useUpdateRule({ id: ruleId, body })`
- e) Write `frontend/src/workflow/editor/Canvas.tsx` as a thin wrapper exposing the `<ReactFlow>` element with `nodeTypes` / `edgeTypes` props and a background dot grid

**完成判定**：`cd frontend && npx tsc --noEmit src/workflow/editor/WorkflowEditor.tsx src/workflow/editor/Canvas.tsx` → 0 type errors / `ruff check frontend/src/workflow/editor/` →0 lint errors

### Step 5: Build `NodePalette.tsx` (sidebar) and `ConfigPanel.tsx` (slide-in editor)

`NodePalette` shows draggable tile buttons for each node type; dragging exports `ruleNode` data via React Flow's `onDragStart` + `onDrop`. `ConfigPanel` shows a textarea pre-filled with the selected node's `data.config` JSON; on change it calls `updateNodeData`.

操作：
- a) Write `frontend/src/workflow/editor/NodePalette.tsx` — render `<div className="palette">` with five `<button>` tiles listing type and icon- b) Wire `onDragStart` to set `dataTransfer.setData('application/reactflow', JSON.stringify({ type, label, config }))`
- c) Write `frontend/src/workflow/editor/ConfigPanel.tsx` — `useEffect` watches selected node id; renders `<textarea>` bound to `JSON.stringify(selectedNode?.data?.config, null, 2)`
- d) On `<textarea>` change, `updateNodeData(selectedNodeId, { ...data, config: JSON.parse(newValue) })`
- e) Add a "Save Rule" `<button>` in `WorkflowEditor` that calls the on-save handler

**完成判定**：`ruff check frontend/src/workflow/editor/` → 0 errors / `ls frontend/src/workflow/editor/NodePalette.tsx frontend/src/workflow/editor/ConfigPanel.tsx` → both files exist

### Step 6: Integrate into app route and sidebar nav

操作：
- a) In `frontend/src/app/(app)/automation/rules/page.tsx`, replace the static list (or add a tab/button) to route to `/automation/rules/[id]/page.tsx` where the editor mounts — TBD - 待验证：确认前端页面实际路径
- b) Add to `frontend/src/components/layout/app-sidebar.tsx`:
  ```tsx<SidebarItem href="/automation/rules" label="Automation" icon={<AutomationIcon />} />
  ```
- c) Add RTK Query hooks to `frontend/src/lib/api/queries.ts`:
  - `useGetRule` → `GET /automation/rules/:id`
  - `useUpdateRule` → `PUT /automation/rules/:id`

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors / `ruff check frontend/src/lib/api/queries.ts` → 0 errors

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 type errors
- [ ] `ruff check frontend/src/workflow/editor/` → 0 errors
- [ ] Manual: visit `/automation/rules` — sidebar shows "Automation" nav item; page renders without crash or unhandled Promise rejection
- [ ] Manual: click "New Rule" / open an existing rule — canvas appears with pan/zoom dot grid
- [ ] Manual: drag a Trigger tile from the palette onto the canvas — a TriggerNode card appears at the dropped position
- [ ] Manual: click the node → ConfigPanel opens on the right with a JSON textarea pre-filled with `{}`
- [ ] Manual: edit the JSON textarea, click "Save Rule" → no console Error (RTK Query dispatches PUT, ignores return value for now)

---

## 7. 风险与回退

|风险 | 概率 | 影响 |降级方案 |
|------|------|------|---------|
| React Flow v11 breaking changes in a future minor release | 低 | 中 | Pin `@xyflow/react` to exact version in `frontend/package.json`; upgrade only in a dedicated issue with manual regression test |
| Custom node SSR hydration mismatch with Next.js App Router | 中 | 中 | Wrap `<WorkflowEditor>` in a `dynamic(() => import('./WorkflowEditor'), { ssr: false })` guard in the page |
| RTK Query integration with backend PUT endpoint (Schema mismatch) | 中 | 中 | Add a `TODO #524` comment; manual browser verification in #524 will surface the mismatch early; no CI gate broken |
| JSON config textarea produces invalid JSON on parse | 中 | 中 | Wrap `JSON.parse` in a try/catch set on the `<textarea>` onChange; on error show inline "Invalid JSON" banner without crashing the editor |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/workflow/
git add frontend/src/app/\(app\)/automation/ frontend/src/components/layout/app-sidebar.tsx
git add frontend/src/lib/api/queries.ts
git commit -m "feat(frontend): add workflow editor React frontend (closes #522)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): workflow editor React frontend" --body "Closes #522"
```

---

## 9. 参考

- 同类参考实现：`frontend/src/app/(app)/automation/rules/page.tsx` — TBD - 待验证：确认前端页面实际路径
- 同类参考实现：[`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) — existing RTK Query definition pattern to follow
- `@xyflow/react` docs：[Getting Started](https://reactflow.dev/docs/learn/getting-started/introduction/) — custom nodes, connection line, drag-and-drop from external source
- 父 issue：#73
- 依赖 issue / 关联：#521---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
