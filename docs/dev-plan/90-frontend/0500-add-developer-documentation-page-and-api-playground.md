# 开发者文档与 API 演练场

| 元数据 | 值 |
|---|---|
| Issue | #500 |
| 分类 | 90-frontend |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |

---

## 1. 目标与背景

### 1.1 为什么做

目前该 CRM 系统缺乏面向开发者的集中文档与交互式接口调试工具。外部集成者或内部前端团队在对接 API 时，需要在多个分散渠道之间跳转，无法在一个页面内查阅端点说明、请求示例并直接发起测试请求。提升文档可发现性和降低 API 调试门槛，是加速集成落地的关键。

### 1.2 做完后

- **用户视角**：开发者访问 `/developer/docs` 可在一个页面内看到完整的端点参考、认证说明、Webhook 事件列表与 SDK 下载入口；访问 `/developer/playground` 可直接在浏览器内填写参数并发起真实请求，无需切换到 Postman 或 curl。
- **开发者视角**：前端开发者可通过文档页面快速定位接口路径、请求体结构和错误码含义；集成者可在 playground 填入 tenant_id 和 token 后立即验证接口行为，缩短调试循环。

### 1.3 不做什么（剔除）

- [ ] 不新增任何后端 API 端点或 service 层逻辑
- [ ] 不修改现有数据模型或数据库 schema
- [ ] 不实现 SDK 下载功能本身（仅放置指向现有产物的链接占位）
- [ ] 不实现 OpenAPI spec 的自动生成（页面使用静态定义或手动维护的 spec 文件）

### 1.4 关键 KPI

- `/developer/docs` 和 `/developer/playground` 两个路由在 Next.js dev server 启动后均可访问（HTTP 200）
- `cd frontend && npx tsc --noEmit` → 0 errors
- `cd frontend && ruff check src/app/\(app\)/developer/` → 0 errors
- 页面内容包含：认证说明章节、Webhook 事件列表示例 ≥ 5 条、Playground 包含至少 1 个可用的 try-it-out 组件

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。本 issue 为纯前端路由创建，不涉及对现有后端代码的修改。

### 2.2 涉及文件清单

- 要改：
  - `frontend/src/app/(app)/developer/docs/page.tsx` — 开发者文档页（新建）
  - `frontend/src/app/(app)/developer/playground/page.tsx` — API 演练场页（新建）
  - `frontend/src/components/layout/app-sidebar.tsx` — 在侧边栏新增开发者文档入口（可选，如现有 sidebar 路由配置支持动态注册）
  - `frontend/src/app/(app)/developer/page.tsx` — 新建 redirect 或 layout 容器（如需要两级路由分组）
- 要建：
  - `frontend/src/lib/api/openapi-spec.ts` — OpenAPI spec 静态定义文件，供 docs 和 playground 共用
  - `docs/dev-plan/90-frontend/0500-add-developer-documentation-page-and-api-playground.md` — 本板块文档（新建）

### 2.3 缺什么

- [ ] `/developer/docs` 路由及页面组件缺失
- [ ] `/developer/playground` 路由及页面组件缺失
- [ ] 侧边栏缺少开发者文档入口
- [ ] 没有集中的端点参考文档（当前散落在 README 或外部 wiki）
- [ ] 没有可交互的 API 演练场组件
- [ ] 没有 Webhook 事件目录的标准格式定义
- [ ] 认证流程（token 换取、刷新）缺少面向开发者的操作指南

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/app/(app)/developer/docs/page.tsx` | 开发者文档主页：端点参考、认证指南、Webhook 目录 |
| `frontend/src/app/(app)/developer/playground/page.tsx` | API 演练场：交互式请求构造与发送组件 |
| `frontend/src/lib/api/openapi-spec.ts` | 静态 OpenAPI spec（或各端点定义片段），docs 和 playground 共用 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `frontend/src/components/layout/app-sidebar.tsx` | 新增 `/developer/docs` 导航项 |
| `frontend/src/lib/api/queries.ts` | 新增 `fetchApi` / `buildRequest` 等 playground 所需的基础调用封装 |

### 3.3 新增能力

- **Next.js Route**：`GET /developer/docs` → 文档页面（含端点参考、认证指南、Webhook 目录）
- **Next.js Route**：`GET /developer/playground` → API 演练场页面
- **React Component**：`ApiPlayground` — 可配置 method/url/headers/body 的 try-it-out 组件，支持响应展示
- **React Component**：`EndpointCard` — 展示单个端点的 method、path、描述与请求示例
- **Sidebar Item**：`开发者文档` → `/developer/docs`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Swagger UI / ReDoc vs 自研 try-it-out**：选择自研最小化 try-it-out 组件，不引入额外的 Swagger UI bundle（减少前端产物体积约 200-400 KB）；后期可按需替换为嵌入 Swagger UI 的 iframe 方案。
- **OpenAPI spec 来源**：使用手动维护的 `openapi-spec.ts` 静态文件，而非从后端自动拉取（后端当前无 OpenAPI 路由暴露）。随接口迭代手动同步 spec 文件。
- **Playground 鉴权方式**：复用前端已有的 `useSession` / `useAuth` hook，从 localStorage 读取当前用户的 bearer token，避免让用户在 playground 手动填 token。

### 4.2 版本约束

本 issue 无新增外部 npm 依赖需求。

### 4.3 兼容性约束

- 页面组件遵循现有 `frontend/src/app/(app)/` 的布局约定（共享 layout，包含 sidebar）
- 所有 API 调用走 `NEXT_PUBLIC_API_BASE_URL` 环境变量（如尚未定义则 fallback 到 `/api/v1`）
- TypeScript 严格模式：不得使用 `any`，不得关闭 `noImplicitAny`
- 不得破坏现有侧边栏导航行为

### 4.4 已知坑

1. **Next.js `use client"` 声明遗漏** → 规避：所有包含 `useState`/`useEffect`/`useAuth` 的组件文件首行必须加 `"use client"` 指令
2. **API 基础 URL 环境变量不存在** → 规避：Playground 组件在 `NEXT_PUBLIC_API_BASE_URL` 未定义时 fallback 到相对路径 `/api/v1`，并显示 warning banner
3. **跨租户数据隔离** → 规避：Playground 默认填入当前登录用户的 `tenant_id`，请求示例中显式注释「替换为实际 tenant_id」

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 OpenAPI spec 静态定义文件

在 `frontend/src/lib/api/openapi-spec.ts` 中定义所有已实现的 API 端点元数据，供 docs 页面和 playground 共用。

```typescript
// frontend/src/lib/api/openapi-spec.ts
export interface Endpoint {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  summary: string;
  description: string;
  requestBody?: {
    mediaType: string;
    example: unknown;
  };
  responseExamples: Array<{ status: number; body: unknown }>;
  tags: string[];
}

export const OPENAPI_SPEC: Record<string, Endpoint[]> = {
  Customers: [
    {
      method: "GET",
      path: "/customers",
      summary: "List customers",
      description: "Returns paginated customer list for the current tenant.",
      responseExamples: [{ status: 200, body: { success: true, data: { items: [], total: 0 } } }],
      tags: ["Customers"],
    },
  ],
};
```

**完成判定**：`cd frontend && npx tsc --noEmit src/lib/api/openapi-spec.ts` → exit 0

---

### Step 2: 构建开发者文档页 `/developer/docs`

在 `frontend/src/app/(app)/developer/docs/page.tsx` 实现文档主页，包含：

- 顶部 Tab 切换：端点参考 / 认证指南 / Webhook 目录
- 端点参考 Tab：`EndpointCard` 组件列表，展示 method badge、path、summary、请求示例（使用 `OPENAPI_SPEC` 渲染）
- 认证指南 Tab：说明如何获取 bearer token、token 刷新流程、tenant_id 获取方式
- Webhook 目录 Tab：静态表格（事件类型、payload 结构、触发时机）

```tsx
// frontend/src/app/(app)/developer/docs/page.tsx
"use client";

import { useState } from "react";
import { OPENAPI_SPEC } from "@/lib/api/openapi-spec";

const WEBHOOK_CATALOG = [
  { event: "customer.created", payload: { customer_id: "int", name: "string" }, description: "客户创建后触发" },
  { event: "ticket.updated", payload: { ticket_id: "int", status: "string" }, description: "工单状态变更后触发" },
];

export default function DeveloperDocsPage() {
  const [activeTab, setActiveTab] = useState<"endpoints" | "auth" | "webhooks">("endpoints");
  return (
    <div className="space-y-6">
      <h1>开发者文档</h1>
      <div className="flex gap-4 border-b">
        {(["endpoints", "auth", "webhooks"] as const).map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={activeTab === tab ? "border-b-2 border-blue-600" : ""}>
            {tab === "endpoints" ? "端点参考" : tab === "auth" ? "认证指南" : "Webhook 目录"}
          </button>
        ))}
      </div>
      {activeTab === "endpoints" && <EndpointReference />}
      {activeTab === "auth" && <AuthGuide />}
      {activeTab === "webhooks" && <WebhookCatalog />}
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors；`ruff check src/app/\(app\)/developer/docs/page.tsx` → 0 errors

---

### Step 3: 构建 API 演练场 `/developer/playground`

在 `frontend/src/app/(app)/developer/playground/page.tsx` 实现可交互的 API 演练场：

- 端点选择器（method dropdown + path input，预填来自 `OPENAPI_SPEC` 的可选列表）
- 请求 Headers 编辑区（默认填充 `Authorization: Bearer <token>`）
- 请求 Body 编辑区（JSON textarea，带格式校验）
- 发送按钮 → 调用 `fetch(NEXT_PUBLIC_API_BASE_URL + path, {method, headers, body})`
- 响应展示区（status badge + formatted JSON + elapsed time）

```tsx
// frontend/src/app/(app)/developer/playground/page.tsx
"use client";

import { useState } from "react";

export default function ApiPlaygroundPage() {
  const [method, setMethod] = useState("GET");
  const [path, setPath] = useState("/customers");
  const [headers, setHeaders] = useState(`{"Content-Type": "application/json", "Authorization": "Bearer <token>"}`);
  const [body, setBody] = useState("");
  const [response, setResponse] = useState<{ status: number; body: string; elapsed: number } | null>(null);

  const sendRequest = async () => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
    const start = Date.now();
    const res = await fetch(`${base}${path}`, {
      method,
      headers: JSON.parse(headers),
      body: ["POST", "PUT", "PATCH"].includes(method) ? body : undefined,
    });
    const text = await res.text();
    setResponse({ status: res.status, body: text, elapsed: Date.now() - start });
  };

  return (
    <div className="space-y-4">
      <h1>API 演练场</h1>
      <div className="flex gap-2">
        <select value={method} onChange={(e) => setMethod(e.target.value)} className="border rounded px-2">
          {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <input value={path} onChange={(e) => setPath(e.target.value)} className="flex-1 border rounded px-2" placeholder="/customers" />
        <button onClick={sendRequest} className="bg-blue-600 text-white px-4 py-1 rounded">发送</button>
      </div>
      <textarea value={headers} onChange={(e) => setHeaders(e.target.value)} className="w-full border rounded p-2 font-mono text-sm" rows={3} />
      {["POST", "PUT", "PATCH"].includes(method) && (
        <textarea value={body} onChange={(e) => setBody(e.target.value)} className="w-full border rounded p-2 font-mono text-sm" rows={6} placeholder='{"name": "..."}' />
      )}
      {response && (
        <div className="border rounded p-3">
          <span className={`font-bold ${response.status < 300 ? "text-green-600" : "text-red-600"}`}>
            {response.status}
          </span>
          <span className="ml-2 text-gray-500">{response.elapsed}ms</span>
          <pre className="mt-2 text-sm overflow-x-auto">{response.body}</pre>
        </div>
      )}
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit` → 0 errors；Playground 页面 `GET /developer/playground` 在 dev server 下 HTTP 200

---

### Step 4: 将开发者文档入口加入侧边栏

编辑 `frontend/src/components/layout/app-sidebar.tsx`，在现有导航项列表中新增：

```tsx
{
  label: "开发者文档",
  href: "/developer/docs",
  icon: <BookOpenIcon className="w-4 h-4" />,
},
```

**完成判定**：`ruff check src/components/layout/app-sidebar.tsx` → 0 errors；侧边栏渲染无 TypeScript 错误

---

### Step 5: 添加端到端类型检查与 lint 验证

运行完整前端类型检查和 lint：

```bash
cd frontend && npx tsc --noEmit
ruff check src/app/\(app\)/developer/ src/lib/api/openapi-spec.ts
```

**完成判定**：两条命令均 exit 0

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 errors
- [ ] `cd frontend && ruff check src/app/\(app\)/developer/ src/lib/api/openapi-spec.ts src/components/layout/app-sidebar.tsx` → 0 errors
- [ ] `curl -s http://localhost:3000/developer/docs | grep -q "开发者文档"` → exit 0（如 dev server 运行）
- [ ] `curl -s http://localhost:3000/developer/playground | grep -q "API 演练场"` → exit 0（如 dev server 运行）
- [ ] `ls frontend/src/app/\(app\)/developer/docs/page.tsx frontend/src/app/\(app\)/developer/playground/page.tsx frontend/src/lib/api/openapi-spec.ts` → 三个文件均存在

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Playground 跨域请求被浏览器拦截（CORS） | 低 | 中 | 降级为仅展示示例代码，不发起真实请求；或通过 Next.js API 代理路由（`/api/proxy`）转发 |
| OpenAPI spec 与实际后端接口不一致 | 中 | 高 | 在 spec 文件顶部加 `// TODO: 每次接口变更后同步此文件` 注释；CI 加入 diff 检查 |
| 侧边栏修改影响现有导航项渲染 | 低 | 中 | 独立 `<DeveloperNavItem />` 子组件，不修改已有 menu item 渲染逻辑 |
| 新路由未纳入布局（无 sidebar） | 低 | 中 | 确认路由在 `(app)` route group 下，自动继承父布局 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/app/\(app\)/developer/ frontend/src/lib/api/openapi-spec.ts \
         frontend/src/components/layout/app-sidebar.tsx \
         docs/dev-plan/90-frontend/0500-add-developer-documentation-page-and-api-playground.md
git commit -m "feat(frontend): add /developer/docs and /developer/playground"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): add developer documentation page and API playground" --body "Closes #500"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`frontend/src/app/(app)/automation/rules/page.tsx` — 现有列表页面的 Tab 切换布局可参考
- 同类参考实现：`frontend/src/app/(app)/tickets/[id]/page.tsx` — 现有详情页的请求/响应展示片段
- 父 issue / 关联：#78
- 前置依赖：#499

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
