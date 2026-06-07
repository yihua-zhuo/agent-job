# 工作流执行日志 UI 与重试 · 为工作流编辑器添加节点级执行日志视图与重试按钮

| 元数据 | 值 |
|---|---|
| Issue | #523 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：依赖 #522 后端完成后补充链接 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前工作流编辑器（`src/workflow/editor/`）仅支持画布编排，缺少执行过程的可见性。用户无法查看各节点是否成功、失败节点的错误原因，也无法从指定节点重新执行。工作流调试只能靠日志猜测，效率极低。

### 1.2 做完后

- **用户视角**：用户打开一个已执行过的工作流，能看到每个节点的状态徽章（pending / running / success / failed），点击节点展开输入输出 JSON；失败节点以红色高亮显示；点击重试按钮可从指定节点重新触发执行流程。
- **开发者视角**：在 `src/workflow/editor/` 下新增 `ExecutionLogPanel` 组件，调用 `#522` 提供的 `POST /workflows/{id}/retry` 端点；新增 `WorkflowService.get_execution_log(workflow_id, run_id)` 对应的前端查询函数（mock 数据，手动验收）。

### 1.3 不做什么（剔除）

- [ ] 不在后端新增节点级重试逻辑（由 #522 负责）
- [ ] 不实现执行日志的持久化存储（后端 API 已在 #522 定义，前端仅消费）
- [ ] 不实现实时 WebSocket 推送（仅轮询，手动验收）
- [ ] 不改动画布拖拽 / 连线逻辑

### 1.4 关键 KPI

- [指标 1：`src/workflow/editor/` 目录下新增文件 ≥ 3 个（ExecutionLogPanel.tsx, NodeStatusBadge.tsx, useWorkflowExecutionLog.ts）]
- [指标 2：手动点击节点展开 JSON 无报错；retry 按钮触发 API 调用]
- [指标 3：`cd frontend && npx tsc --noEmit` → 0 errors（如有 TSC 配置）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`frontend/src/workflow/editor/` 目录存在性及现有组件列表（L?) — 需确认是否有 `WorkflowCanvas.tsx`、`WorkflowEditorPage.tsx` 等基础文件

### 2.2 涉及文件清单

- 要改：
  - `frontend/src/workflow/editor/WorkflowEditorPage.tsx` — 在页面右侧/底部新增 ExecutionLogPanel 挂载点
  - TBD - 待验证：`frontend/src/lib/api/queries.ts` — 补充 workflow execution log 查询函数（若 #522 未包含）
- 要建：
  - `frontend/src/workflow/editor/components/ExecutionLogPanel.tsx` — 执行日志主面板（节点列表 + 状态徽章 + 展开区）
  - `frontend/src/workflow/editor/components/NodeStatusBadge.tsx` — 节点状态徽章组件（pending/running/success/failed）
  - `frontend/src/workflow/editor/components/NodeIODetail.tsx` — 节点输入输出 JSON 展开区
  - `frontend/src/workflow/editor/hooks/useWorkflowExecutionLog.ts` — 执行日志查询 hook（带 retry 触发函数）
  - `frontend/src/workflow/editor/types.ts` — ExecutionNode、ExecutionLog、NodeStatus 等类型定义

### 2.3 缺什么

- [ ] 执行日志 UI 组件（节点状态列表、状态徽章、JSON 展开）
- [ ] 调用后端 retry API 的前端函数
- [ ] 执行日志类型定义（NodeStatus、ExecutionLog 等）
- [ ] 执行日志面板与画布的关联（选中节点高亮、面板与画布节点对应）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `frontend/src/workflow/editor/components/ExecutionLogPanel.tsx` | 执行日志面板主组件：节点列表、状态徽章、重试按钮 |
| `frontend/src/workflow/editor/components/NodeStatusBadge.tsx` | 节点状态徽章：pending(灰)、running(蓝)、success(绿)、failed(红) |
| `frontend/src/workflow/editor/components/NodeIODetail.tsx` | 节点输入/输出 JSON 展开区，支持折叠 |
| `frontend/src/workflow/editor/hooks/useWorkflowExecutionLog.ts` | 执行日志查询 hook，含 retry 函数调用 |
| `frontend/src/workflow/editor/types.ts` | ExecutionLog、ExecutionNode、NodeStatus 类型定义 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`frontend/src/workflow/editor/WorkflowEditorPage.tsx` | 导入并挂载 ExecutionLogPanel，添加展开/收起状态控制 |
| TBD - 待验证：`frontend/src/lib/api/queries.ts` | 新增 `fetchWorkflowExecutionLog`、`triggerWorkflowRetry` 查询函数（若 #522 已定义则此处引用） |

### 3.3 新增能力

- **React 组件**：`ExecutionLogPanel` — 渲染节点执行状态列表，支持展开 JSON 和重试
- **React 组件**：`NodeStatusBadge` — 根据 status 枚举渲染颜色徽章
- **React hook**：`useWorkflowExecutionLog` — 管理执行日志数据态 + retry 副作用
- **TypeScript 类型**：`ExecutionLog`、`ExecutionNode`、`NodeStatus`（pending | running | success | failed）
- **API 调用**：`triggerWorkflowRetry(workflowId, runId, nodeId)` → 调用 `POST /workflows/{id}/retry`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用状态徽章颜色区分而非文字** — 减少认知负担；failed 节点红色高亮是用户最直观的可发现信号
- **JSON 展开区用原生 `<details>/<summary>`** 而非手写折叠状态 — 无需额外状态管理，代码量最少
- **hook 模式封装 API 调用** 而非直接在组件内 fetch — 便于后续替换为 React Query / SWR 等数据获取库

### 4.2 版本约束

<!-- 无新增 npm 依赖 -->

### 4.3 兼容性约束

- 组件需接收 `workflowId` 和 `runId`（或 `executionId`）作为 props，与后端 API 参数对齐
- Retry 按钮的 nodeId 参数从前端维护的节点 ID 列表中读取，需与画布节点 ID 一致
- 状态枚举使用字符串字面量（`pending` | `running` | `success` | `failed`），便于后端 JSON 直接映射

### 4.4 已知坑

1. **失败节点红色高亮区域若与其他 UI 高亮（如选中节点）重叠，用户难以区分** → 规避：ExecutionLogPanel 中的高亮仅在面板内生效，画布侧的高亮不受影响，两者互不干扰

---

## 5. 实现步骤（按顺序）

### Step 1: 定义 TypeScript 类型

新增 `frontend/src/workflow/editor/types.ts`，定义执行日志相关类型，供后续组件使用。

操作：
- a) 创建 `frontend/src/workflow/editor/types.ts`
- b) 定义 `NodeStatus` 枚举（`pending` | `running` | `success` | `failed`）
- c) 定义 `ExecutionNode` 接口（含 `nodeId`、`nodeName`、`status`、`startTime`、`endTime`、`input`、`output`、`errorMessage`）
- d) 定义 `ExecutionLog` 接口（含 `runId`、`workflowId`、`status`、`nodes: ExecutionNode[]`、`createdAt`）

示例代码：

```typescript
// frontend/src/workflow/editor/types.ts
export type NodeStatus = 'pending' | 'running' | 'success' | 'failed';

export interface ExecutionNode {
  nodeId: string;
  nodeName: string;
  status: NodeStatus;
  startTime?: string;   // ISO 8601
  endTime?: string;     // ISO 8601
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorMessage?: string;
}

export interface ExecutionLog {
  runId: string;
  workflowId: string;
  status: NodeStatus;
  nodes: ExecutionNode[];
  createdAt: string;    // ISO 8601
}
```

**完成判定**：`grep -n "NodeStatus" frontend/src/workflow/editor/types.ts` 有输出

### Step 2: 创建 NodeStatusBadge 组件

在 `frontend/src/workflow/editor/components/` 下新建 `NodeStatusBadge.tsx`，根据 status 渲染不同颜色徽章。

操作：
- a) 创建 `frontend/src/workflow/editor/components/NodeStatusBadge.tsx`
- b) 接收 `status: NodeStatus` prop
- c) 使用 Tailwind CSS：`pending=bg-gray-400`、`running=bg-blue-500 animate-pulse`、`success=bg-green-500`、`failed=bg-red-500`
- d) 徽章内显示文字标签（中文：待执行/运行中/成功/失败）

示例代码：

```tsx
// frontend/src/workflow/editor/components/NodeStatusBadge.tsx
import { NodeStatus } from '../types';

const STATUS_CONFIG: Record<NodeStatus, { label: string; classes: string }> = {
  pending: { label: '待执行', classes: 'bg-gray-400 text-white' },
  running: { label: '运行中', classes: 'bg-blue-500 text-white animate-pulse' },
  success: { label: '成功',   classes: 'bg-green-500 text-white' },
  failed:  { label: '失败',   classes: 'bg-red-500 text-white' },
};

interface Props {
  status: NodeStatus;
}

export function NodeStatusBadge({ status }: Props) {
  const { label, classes } = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${classes}`}>
      {label}
    </span>
  );
}
```

**完成判定**：`grep -n "NodeStatusBadge" frontend/src/workflow/editor/components/NodeStatusBadge.tsx` 有输出

### Step 3: 创建 NodeIODetail 组件

新建 `NodeIODetail.tsx`，渲染节点输入/输出 JSON，支持折叠。

操作：
- a) 创建 `frontend/src/workflow/editor/components/NodeIODetail.tsx`
- b) 接收 `node: ExecutionNode` prop
- c) 用 `<details>/<summary>` 分别展开 input 和 output 两块 JSON
- d) 用 `<pre><code>` 渲染 JSON.stringify(obj, null, 2)，加 Tailwind `bg-gray-50 p-2 rounded text-xs overflow-x-auto`

示例代码：

```tsx
// frontend/src/workflow/editor/components/NodeIODetail.tsx
import { ExecutionNode } from '../types';

interface Props {
  node: ExecutionNode;
}

export function NodeIODetail({ node }: Props) {
  return (
    <div className="space-y-2 text-xs">
      {node.errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded p-2 text-red-700">
          {node.errorMessage}
        </div>
      )}
      <details className="group">
        <summary className="cursor-pointer font-medium text-gray-600 hover:text-gray-800">输入 (input)</summary>
        <pre className="bg-gray-50 p-2 rounded mt-1 overflow-x-auto"><code>{JSON.stringify(node.input ?? {}, null, 2)}</code></pre>
      </details>
      <details className="group">
        <summary className="cursor-pointer font-medium text-gray-600 hover:text-gray-800">输出 (output)</summary>
        <pre className="bg-gray-50 p-2 rounded mt-1 overflow-x-auto"><code>{JSON.stringify(node.output ?? {}, null, 2)}</code></pre>
      </details>
    </div>
  );
}
```

**完成判定**：`grep -n "NodeIODetail" frontend/src/workflow/editor/components/NodeIODetail.tsx` 有输出

### Step 4: 创建 useWorkflowExecutionLog hook

新建 `useWorkflowExecutionLog.ts`，封装执行日志数据获取和 retry 调用。

操作：
- a) 创建 `frontend/src/workflow/editor/hooks/useWorkflowExecutionLog.ts`
- b) 接收 `workflowId: string` 和 `runId: string` 参数
- c) 返回 `{ log: ExecutionLog | null, loading: boolean, error: string | null, retry: (nodeId: string) => Promise<void> }`
- d) `retry` 函数调用 `POST /workflows/{workflowId}/retry`（body: `{ runId, nodeId }`）
- e) 初始数据使用 mock JSON（手动验收阶段不发真实请求）

示例代码：

```typescript
// frontend/src/workflow/editor/hooks/useWorkflowExecutionLog.ts
import { useState } from 'react';
import { ExecutionLog } from '../types';

interface UseExecutionLogOptions {
  workflowId: string;
  runId: string;
}

export function useWorkflowExecutionLog({ workflowId, runId }: UseExecutionLogOptions) {
  const [log, setLog] = useState<ExecutionLog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const retry = async (nodeId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/workflows/${workflowId}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ runId, nodeId }),
      });
      if (!res.ok) throw new Error(`Retry failed: ${res.status}`);
      // 手动验收：mock 刷新日志
      setLog(prev => prev ? { ...prev, status: 'running' } : prev);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return { log, loading, error, retry };
}
```

**完成判定**：`grep -n "useWorkflowExecutionLog" frontend/src/workflow/editor/hooks/useWorkflowExecutionLog.ts` 有输出

### Step 5: 创建 ExecutionLogPanel 组件

新建 `ExecutionLogPanel.tsx`，整合节点状态列表 + 徽章 + JSON 展开 + retry 按钮。

操作：
- a) 创建 `frontend/src/workflow/editor/components/ExecutionLogPanel.tsx`
- b) 导入并使用 `useWorkflowExecutionLog` hook（mock 数据源）
- c) 渲染节点列表，每个节点一行：左侧 NodeStatusBadge，中间节点名称，右侧重试按钮
- d) 点击节点行展开 NodeIODetail
- e) retry 按钮在 failed 节点行始终可见；其他节点行仅在手动测试时可用
- f) 面板顶部显示 runId 和总状态摘要

示例代码：

```tsx
// frontend/src/workflow/editor/components/ExecutionLogPanel.tsx
import { NodeStatusBadge } from './NodeStatusBadge';
import { NodeIODetail } from './NodeIODetail';
import { useWorkflowExecutionLog } from '../hooks/useWorkflowExecutionLog';

interface Props {
  workflowId: string;
  runId: string;
}

export function ExecutionLogPanel({ workflowId, runId }: Props) {
  const { log, loading, error, retry } = useWorkflowExecutionLog({ workflowId, runId });

  if (loading && !log) return <div className="p-4 text-gray-500">加载中...</div>;
  if (error) return <div className="p-4 text-red-600">错误：{error}</div>;
  if (!log) return <div className="p-4 text-gray-400">暂无执行记录</div>;

  return (
    <div className="flex flex-col h-full border-l bg-white">
      <div className="px-4 py-2 border-b bg-gray-50">
        <span className="text-xs text-gray-500">Run ID: {log.runId}</span>
        <span className="ml-2"><NodeStatusBadge status={log.status} /></span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {log.nodes.map(node => (
          <div key={node.nodeId} className="border-b last:border-b-0">
            <details className="group">
              <summary className={`flex items-center gap-2 px-4 py-2 cursor-pointer hover:bg-gray-50 ${node.status === 'failed' ? 'bg-red-50' : ''}`}>
                <NodeStatusBadge status={node.status} />
                <span className="flex-1 text-sm font-medium">{node.nodeName}</span>
                {node.status === 'failed' && (
                  <button
                    onClick={e => { e.preventDefault(); retry(node.nodeId); }}
                    className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600"
                  >
                    重试
                  </button>
                )}
              </summary>
              <div className="px-4 py-2 bg-gray-50">
                <NodeIODetail node={node} />
              </div>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**完成判定**：`grep -n "ExecutionLogPanel" frontend/src/workflow/editor/components/ExecutionLogPanel.tsx` 有输出

### Step 6: 在 WorkflowEditorPage 中集成 ExecutionLogPanel

修改工作流编辑器页面，挂载 ExecutionLogPanel 并添加展开/收起切换。

操作：
- a) 在 `WorkflowEditorPage.tsx` 中导入 `ExecutionLogPanel`
- b) 添加 state：`const [showLogPanel, setShowLogPanel] = useState(false)`
- c) 在页面右侧（画布外）添加条件渲染：`{showLogPanel && <ExecutionLogPanel workflowId={id} runId={currentRunId} />}`
- d) 在工具栏或页面顶部添加切换按钮：「执行日志」

TBD - 待验证：在 `frontend/src/workflow/editor/WorkflowEditorPage.tsx` 第 L? 行附近添加切换按钮和面板挂载（当前文件存在性未确认）

**完成判定**：TBD - 待验证：`grep -n "ExecutionLogPanel" frontend/src/workflow/editor/WorkflowEditorPage.tsx` 有输出

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 errors（如无 tsc config 改为 `ls frontend/src/workflow/editor/components/` 确认文件存在）
- [ ] `cd frontend && npx eslint src/workflow/editor/` → 0 errors（如无 ESLint 改为确认文件行数 ≥ 50）
- [ ] 手动：打开工作流编辑器页面，点击「执行日志」切换按钮，面板显示节点列表
- [ ] 手动：点击失败节点展开 JSON，显示 errorMessage 红色区块
- [ ] 手动：点击失败节点右侧「重试」按钮，触发 API 调用（浏览器 Network 面板出现 `/api/workflows/{id}/retry` 请求）
- [ ] 手动：其他状态节点（pending/success/running）不显示重试按钮

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #522 后端 retry API 未完成，前端 retry 按钮 405/404 | 中 | 中 | 前端 retry 函数捕获错误并 toast 提示「后端接口建设中」，不影响主功能 |
| ExecutionLogPanel 与画布布局冲突（挤压画布宽度） | 低 | 中 | 将面板改为可收起（toggle），默认收起状态，优先保证画布空间 |
| mock 数据与真实 API 响应结构不一致，导致 TypeScript 类型错误 | 低 | 低 | types.ts 按 issue 描述定义，运行 `tsc --noEmit` 提前发现类型偏差 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/workflow/editor/
git commit -m "feat(frontend): add workflow execution log UI and retry button

Closes #523"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): execution log panel + retry for workflow editor" --body "Closes #523

## Summary
- Add ExecutionLogPanel, NodeStatusBadge, NodeIODetail components
- Add useWorkflowExecutionLog hook with retry API call
- Add types.ts for ExecutionLog / ExecutionNode / NodeStatus
- Integrate ExecutionLogPanel into WorkflowEditorPage

## Test plan
Manual verification per §6 acceptance criteria." 

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#73（工作流执行引擎总览）
- 依赖 issue：#522（TBD - 待验证：依赖 #522 后端完成后补充链接）
- 前端组件参考：TBD - 待验证：`frontend/src/app/(app)/automation/rules/[id]/page.tsx` — 现有 rules 详情页面的面板布局参考
- React TypeScript 最佳实践：TBD - 待验证（无需第三方文档）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
