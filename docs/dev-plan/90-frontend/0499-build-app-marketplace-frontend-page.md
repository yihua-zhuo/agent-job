# App Marketplace & Settings Pages · Build marketplace + webhooks + API key frontend

| 元数据 | 值 |
|---|---|
| Issue | #499 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [#498 Build App Marketplace backend](../70-platform/0498-implement-api-key-auth-middleware-and-external-api-router.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 系统没有面向管理员的第三方应用市场、Webhook 管理界面或 API Key 管理界面。用户（通常是管理员或集成负责人）需要在平台层面连接外部系统（Slack、Zapier、HubSpot 等）、配置事件订阅、以及获取 API 凭证——这些能力在后端（#498）已经或即将实现，但对应的前端页面完全缺失，导致管理员无从操作。

### 1.2 做完后

- **用户视角**：管理员访问 `/marketplace` 看到第三方应用列表，点进 `/marketplace/[app_id]` 查看应用详情并点击 Install 触发 OAuth2 连接流程；访问 `/settings/webhooks` 管理事件订阅（列表、新建表单、删除、最近投递、retry、test）；访问 `/settings/api` 管理 API Key（生成、列表、撤销）。
- **开发者视角**：前端团队获得一组新的页面路由和 React 组件，后续可在 `frontend/src/lib/api/queries.ts` 中新增对应的 `useMarketplaceApps` / `useWebhooks` / `useApiKeys` 等 query hook，复用现有 `apiClient` 封装调用后端 REST 接口。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 API 端点（全部由 #498 提供，本板块仅消费）
- [ ] 不实现 OAuth2 Provider 端点或 Token 交换逻辑（#498 负责）
- [ ] 不实现 Webhook 投递的重试队列后端逻辑（#498 负责）
- [ ] 不实现 API Key 的加密存储或 JWT 逻辑（#498 负责）
- [ ] 不实现细粒度的 Webhook 过滤规则编辑 UI（本版只做基础 CRUD）

### 1.4 关键 KPI

- `/marketplace`、`/marketplace/[app_id]`、`/settings/webhooks`、`/settings/api` 四个路由在 Next.js dev server 下均 HTTP 200
- `cd frontend && npx tsc --noEmit` → 0 errors
- `cd frontend && ruff check src/app/\(app\)/marketplace/ src/app/\(app\)/settings/` → 0 errors
- 各页面包含至少一个可交互的表单或操作按钮（提交后调用对应 mutation）

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。本 issue 为纯前端页面搭建，后端 API 由 #498 提供，当前均不存在。

### 2.2 涉及文件清单

- 要改：
  - `frontend/src/components/layout/app-sidebar.tsx` — 在侧边栏新增 Marketplace 导航入口；在 Settings 分组下新增 Webhooks 和 API Keys 子项
  - `frontend/src/lib/api/queries.ts` — 新增 `useMarketplaceApps` / `useMarketplaceApp` / `useWebhooks` / `useApiKeys` 等 query/mutation hook
  - `frontend/src/app/(app)/settings/page.tsx` — 扩展为 Settings 导航容器（webhooks / api 子页通过子路由承载，不改此处内容）
- 要建：
  - `frontend/src/app/(app)/marketplace/page.tsx` — 第三方应用市场列表页
  - `frontend/src/app/(app)/marketplace/[app_id]/page.tsx` — 应用详情页（含 Install/OAuth2 按钮）
  - `frontend/src/app/(app)/settings/webhooks/page.tsx` — Webhook 列表 + 新建表单页
  - `frontend/src/app/(app)/settings/api/page.tsx` — API Key 管理页

### 2.3 缺什么

- [ ] `/marketplace` 路由及页面组件缺失，无法浏览第三方应用
- [ ] `/marketplace/[app_id]` 详情页缺失，无法查看应用描述、发起 OAuth2 安装
- [ ] `/settings/webhooks` 路由及页面缺失，无法 CRUD Webhook 订阅
- [ ] `/settings/api` 路由及页面缺失，无法生成/撤销 API Key
- [ ] `queries.ts` 缺少 Marketplace / Webhook / API Key 相关的 query hook
- [ ] 侧边栏缺少 Marketplace 导航入口

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/app/(app)/marketplace/page.tsx` | 应用市场列表页（卡片网格，静态配置或从 API 拉取） |
| `frontend/src/app/(app)/marketplace/[app_id]/page.tsx` | 应用详情页（描述、截图/图标、Install OAuth2 按钮） |
| `frontend/src/app/(app)/settings/webhooks/page.tsx` | Webhook 管理页（列表 + 新建表单 + 删除 + 详情抽屉） |
| `frontend/src/app/(app)/settings/api/page.tsx` | API Key 管理页（列表 + 生成表单 + 撤销操作） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`frontend/src/components/layout/app-sidebar.tsx`](../../../frontend/src/components/layout/app-sidebar.tsx) | 在 `systemItems` 后新增 `{ href: "/marketplace", label: "Marketplace", icon: Store }`；在 Settings 区域新增 `href: "/settings/webhooks"` 和 `href: "/settings/api"` 子项 |
| [`frontend/src/lib/api/queries.ts`](../../../frontend/src/lib/api/queries.ts) | 新增 `qk.marketplaceApps / qk.webhooks / qk.apiKeys`；新增 `useMarketplaceApps / useInstallApp / useWebhooks / useCreateWebhook / useDeleteWebhook / useApiKeys / useCreateApiKey / useRevokeApiKey` |

### 3.3 新增能力

- **Next.js Route**：`GET /marketplace` → 应用市场列表页
- **Next.js Route**：`GET /marketplace/[app_id]` → 应用详情页
- **Next.js Route**：`GET /settings/webhooks` → Webhook 管理页
- **Next.js Route**：`GET /settings/api` → API Key 管理页
- **React Component**：`MarketplaceGrid` — 应用卡片网格展示组件
- **React Component**：`WebhookTable` — Webhook 列表 + 投递状态展示
- **React Component**：`ApiKeyTable` — API Key 列表（含部分遮蔽的 key、创建时间、撤销按钮）
- **Sidebar Item**：`Marketplace` → `/marketplace`
- **Sidebar Item**：`Webhooks` → `/settings/webhooks`（Settings 分组下）
- **Sidebar Item**：`API Keys` → `/settings/api`（Settings 分组下）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **OAuth2 Install 流程**：点击 Install 按钮直接 `window.location.href = app.authorization_url` 跳转至第三方授权页，不在应用内做 popup 子窗口（简化实现，第三方 OAuth Provider 不一定支持 CORS callback）；回调由后端（#498）处理后重定向回 `/marketplace/[app_id]?installed=true`。
- **Webhook 测试/重试**：测试投递在页面内调用 `POST /webhooks/{id}/test`，展示响应状态码和 body（不阻塞 UI）；重试调用 `POST /webhooks/{id}/retry`。
- **API Key 展示策略**：创建成功后一次性展示完整 key 正文，存入后端仅存 hash；后续列表页只显示 key 前缀（如 `sk_live_abc…`）和创建时间，不显示完整 key。
- **静态 vs 动态应用列表**：优先实现静态配置（`const MARKETPLACE_APPS = [...]`），方便 UI 开发；如 #498 提供动态 API，再切换为 `useQuery` 拉取。

### 4.2 版本约束

本 issue 无新增外部 npm 依赖需求。

### 4.3 兼容性约束

- 页面组件遵循现有 `frontend/src/app/(app)/` 布局约定（共享 sidebar）
- 所有 API 调用走 `NEXT_PUBLIC_API_BASE_URL` 环境变量或 fallback 到 `/api/v1`
- TypeScript 严格模式：不得使用 `any`，不得关闭 `noImplicitAny`
- React Query hooks 签名遵循 `queries.ts` 现有模式（queryKey + apiClient + useAuthStore 取 token）
- `"use client"` 指令：所有包含 useState / useEffect / useMutation 的组件文件必须声明
- 侧边栏新增导航项不破坏现有 NavGroup 渲染逻辑

### 4.4 已知坑

1. **Next.js `"use client"` 声明遗漏** → 规避：所有包含 `useState`/`useEffect`/`useMutation` 的组件文件首行必须加 `"use client"` 指令
2. **OAuth2 redirect 回跳时 401** → 规避：Install 跳转前将 `app_id` 存入 `sessionStorage`，回跳后从 sessionStorage 恢复状态，不依赖 URL 参数（避免 token 未刷新的空档期）
3. **API Key 创建后刷新列表不自动失效** → 规避：调用 `useCreateApiKey` mutation 后调用 `queryClient.invalidateQueries({ queryKey: qk.apiKeys })` 主动刷新
4. **Webhook 投递列表过长导致页面卡顿** → 规避：投递历史列表分页（每 Webhook 最多显示最近 20 条），点击"查看更多"展开完整历史

---

## 5. 实现步骤（按顺序）

### Step 1: 扩展 queries.ts 添加 Marketplace / Webhook / API Key hooks

在 `frontend/src/lib/api/queries.ts` 中新增 query key 常量和所有 CRUD hooks，供各页面使用。

操作：
- a) 在 `qk` 对象中添加 `marketplaceApps`、`marketplaceApp`、`webhooks`、`webhook`、`webhookDeliveries`、`apiKeys` key factories
- b) 在 `useCurrentUser` 之后添加 `useMarketplaceApps`、`useMarketplaceApp`、`useInstallApp`、`useWebhooks`、`useCreateWebhook`、`useDeleteWebhook`、`useWebhookDeliveries`、`useTestWebhook`、`useRetryWebhook`、`useApiKeys`、`useCreateApiKey`、`useRevokeApiKey`

```typescript
// frontend/src/lib/api/queries.ts 新增片段

// qk 新增
marketplaceApps: () => ["marketplace_apps"] as const,
marketplaceApp: (id: string) => ["marketplace_app", id] as const,
webhooks: (page = 1) => ["webhooks", page] as const,
webhook: (id: number) => ["webhook", id] as const,
webhookDeliveries: (webhookId: number) => ["webhook", webhookId, "deliveries"] as const,
apiKeys: () => ["api_keys"] as const,

// useMarketplaceApps
export function useMarketplaceApps() {
  return useQuery({ queryKey: qk.marketplaceApps(), queryFn: () => apiClient.get("/marketplace/apps") });
}

// useInstallApp
export function useInstallApp() {
  return useMutation({ mutationFn: (appId: string) => apiClient.post(`/marketplace/apps/${appId}/install`, {}) });
}

// useWebhooks
export function useWebhooks(page = 1) {
  return useQuery({ queryKey: qk.webhooks(page), queryFn: () => apiClient.get(`/webhooks?page=${page}`) });
}

// useCreateWebhook
export function useCreateWebhook() {
  return useMutation({ mutationFn: (data) => apiClient.post("/webhooks", data) });
}

// useDeleteWebhook
export function useDeleteWebhook() {
  return useMutation({ mutationFn: (id: number) => apiClient.delete(`/webhooks/${id}`) });
}

// useApiKeys
export function useApiKeys() {
  return useQuery({ queryKey: qk.apiKeys(), queryFn: () => apiClient.get("/api-keys") });
}

// useCreateApiKey
export function useCreateApiKey() {
  return useMutation({ mutationFn: (data) => apiClient.post("/api-keys", data) });
}

// useRevokeApiKey
export function useRevokeApiKey() {
  return useMutation({ mutationFn: (id: number) => apiClient.delete(`/api-keys/${id}`) });
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/lib/api/queries.ts` → exit 0

---

### Step 2: 将 Marketplace 和子 Settings 页加入侧边栏

编辑 `frontend/src/components/layout/app-sidebar.tsx`，在 `systemItems` 数组最后新增 Marketplace 项，在 Settings 分组下新增 Webhooks 和 API Keys 子项（通过 `settingsItems` 子数组实现）。

```tsx
// frontend/src/components/layout/app-sidebar.tsx 改动片段

const systemItems = [
  { href: "/settings", label: "Settings", icon: SettingsIcon },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/ai", label: "AI", icon: Sparkles },
  { href: "/import-export", label: "Import/Export", icon: Upload },
  { href: "/marketplace", label: "Marketplace", icon: Store },
];

const settingsSubItems = [
  { href: "/settings/webhooks", label: "Webhooks" },
  { href: "/settings/api", label: "API Keys" },
];
```

**完成判定**：`ruff check frontend/src/components/layout/app-sidebar.tsx` → 0 errors；`cd frontend && npx tsc --noEmit src/components/layout/app-sidebar.tsx` → exit 0

---

### Step 3: 构建应用市场列表页 `/marketplace`

在 `frontend/src/app/(app)/marketplace/page.tsx` 实现应用市场列表页（使用静态数据 MARKETPLACE_APPS）。

操作：
- a) 定义 `MARKETPLACE_APPS` 静态数组（至少 4 个示例应用：Slack、Zapier、HubSpot、Intercom，含 id / name / description / icon / category / authorization_url）
- b) 实现 MarketplaceGrid 组件：网格布局（响应式 1-3 列），每个 AppCard 展示 icon + name + description + category badge + "View Details" 链接到 `/marketplace/[app_id]`
- c) 页面标题 "App Marketplace"，副标题 "Connect your favourite tools"

```tsx
// frontend/src/app/(app)/marketplace/page.tsx
"use client";

import Link from "next/link";

const MARKETPLACE_APPS = [
  { id: "slack", name: "Slack", description: "Send notifications and alerts to Slack channels.", category: "Notifications", icon: "💬", authorization_url: "/api/marketplace/slack/authorize" },
  { id: "zapier", name: "Zapier", description: "Automate workflows with 5000+ Zapier integrations.", category: "Automation", icon: "⚡", authorization_url: "/api/marketplace/zapier/authorize" },
  { id: "hubspot", name: "HubSpot", description: "Sync CRM contacts and deals with HubSpot.", category: "CRM", icon: "🔶", authorization_url: "/api/marketplace/hubspot/authorize" },
  { id: "intercom", name: "Intercom", description: "Connect customer conversations from Intercom.", category: "Support", icon: "💬", authorization_url: "/api/marketplace/intercom/authorize" },
];

export default function MarketplacePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">App Marketplace</h1>
        <p className="text-muted-foreground">Connect your favourite tools and extend your CRM workflow.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {MARKETPLACE_APPS.map((app) => (
          <Link key={app.id} href={`/marketplace/${app.id}`} className="group border rounded-lg p-4 hover:border-primary transition-colors block">
            <div className="flex items-start gap-3">
              <span className="text-3xl">{app.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold group-hover:text-primary">{app.name}</h2>
                  <span className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded">{app.category}</span>
                </div>
                <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{app.description}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/app/\(app\)/marketplace/page.tsx` → exit 0；页面在 dev server 下 HTTP 200

---

### Step 4: 构建应用详情页 `/marketplace/[app_id]`

在 `frontend/src/app/(app)/marketplace/[app_id]/page.tsx` 实现详情页，读取静态数据或调用 `useMarketplaceApp(id)`。

操作：
- a) `useMarketplaceApps` 静态数据中查找对应 app；若 app 不存在返回 404 UI
- b) 展示应用 icon、name、category、full description
- c) Install 按钮：点击后 `window.location.href = app.authorization_url`（发起 OAuth2）
- d) 若 URL 包含 `?installed=true`，显示 "Installed successfully!" toast/alert

```tsx
// frontend/src/app/(app)/marketplace/[app_id]/page.tsx
"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useMarketplaceApps, useInstallApp } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

const MARKETPLACE_APPS = [
  { id: "slack", name: "Slack", description: "Send notifications and alerts to Slack channels.", fullDescription: "The Slack integration lets you send real-time CRM events to any Slack channel. Configure which events trigger notifications, choose target channels, and format message templates.", category: "Notifications", icon: "💬", authorization_url: "/api/marketplace/slack/authorize" },
  { id: "zapier", name: "Zapier", description: "Automate workflows with 5000+ Zapier integrations.", fullDescription: "Connect your CRM to Zapier to trigger Zaps on customer, opportunity, and ticket events. Use Zapier to push data to Google Sheets, Airtable, Notion, and thousands of other apps.", category: "Automation", icon: "⚡", authorization_url: "/api/marketplace/zapier/authorize" },
  { id: "hubspot", name: "HubSpot", description: "Sync CRM contacts and deals with HubSpot.", fullDescription: "Bidirectional sync of customers and opportunities with HubSpot CRM. Keep both systems in sync automatically.", category: "CRM", icon: "🔶", authorization_url: "/api/marketplace/hubspot/authorize" },
  { id: "intercom", name: "Intercom", description: "Connect customer conversations from Intercom.", fullDescription: "Pull Intercom conversations and contacts into your CRM. Link conversations to the correct customer record automatically.", category: "Support", icon: "💬", authorization_url: "/api/marketplace/intercom/authorize" },
];

export default function MarketplaceAppDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const appId = params.app_id as string;
  const installed = searchParams.get("installed") === "true";
  const app = MARKETPLACE_APPS.find((a) => a.id === appId);

  if (!app) {
    return <div className="text-center py-20"><h1 className="text-xl font-bold">App not found</h1><Link href="/marketplace" className="text-primary underline">Back to Marketplace</Link></div>;
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {installed && <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg px-4 py-3 text-sm">Installed successfully! The app is now connected.</div>}
      <Link href="/marketplace" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to Marketplace
      </Link>
      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center gap-4">
            <span className="text-5xl">{app.icon}</span>
            <div>
              <h1 className="text-2xl font-bold">{app.name}</h1>
              <span className="text-sm bg-muted px-2 py-0.5 rounded text-muted-foreground">{app.category}</span>
            </div>
          </div>
          <p className="text-muted-foreground">{app.fullDescription}</p>
          <Button
            onClick={() => { sessionStorage.setItem("installing_app", app.id); window.location.href = app.authorization_url; }}
            className="w-full"
          >
            Install {app.name}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/app/\(app\)/marketplace/\[app_id\]/page.tsx` → exit 0；`ruff check src/app/\(app\)/marketplace/\[app_id\]/page.tsx` → 0 errors

---

### Step 5: 构建 Webhook 管理页 `/settings/webhooks`

在 `frontend/src/app/(app)/settings/webhooks/page.tsx` 实现 Webhook CRUD 页面。

操作：
- a) `useWebhooks` 渲染列表（endpoint URL、events、active 状态、created_at）
- b) 新建表单 Dialog：填写 endpoint URL、选择 events 列表（checkbox）、设置 active 开关；提交调用 `useCreateWebhook`
- c) 每行有 Delete 按钮（调用 `useDeleteWebhook` + `queryClient.invalidateQueries`）
- d) 每行有 "Test" 按钮（调用 `useTestWebhook`，显示结果 dialog）
- e) 每行有 "Deliveries" 展开（调用 `useWebhookDeliveries`，显示最近 5 条状态）

```tsx
// frontend/src/app/(app)/settings/webhooks/page.tsx
"use client";

import { useState } from "react";
import { useWebhooks, useCreateWebhook, useDeleteWebhook, useTestWebhook } from "@/lib/api/queries";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Zap, ChevronDown } from "lucide-react";

const EVENT_OPTIONS = ["customer.created", "customer.updated", "ticket.created", "ticket.updated", "opportunity.created"];

export default function WebhooksPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useWebhooks();
  const createWebhook = useCreateWebhook();
  const deleteWebhook = useDeleteWebhook();
  const testWebhook = useTestWebhook();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ url: "", events: [] as string[], active: true });
  const [testResult, setTestResult] = useState<{ status: number; body: string } | null>(null);

  async function handleCreate() {
    await createWebhook.mutateAsync(form);
    queryClient.invalidateQueries({ queryKey: qk.webhooks() });
    setShowForm(false);
    setForm({ url: "", events: [], active: true });
  }

  async function handleDelete(id: number) {
    await deleteWebhook.mutateAsync(id);
    queryClient.invalidateQueries({ queryKey: qk.webhooks() });
  }

  async function handleTest(id: number) {
    const result = await testWebhook.mutateAsync(id);
    setTestResult({ status: result.status, body: result.body ?? "" });
  }

  const webhooks = (data?.data?.items ?? []) as Array<{ id: number; url: string; events: string[]; active: boolean; created_at: string }>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Webhooks</h1>
          <p className="text-muted-foreground text-sm">Receive real-time event notifications at your endpoint.</p>
        </div>
        <Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4 mr-1" /> New Webhook</Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader><CardTitle className="text-base">Create Webhook</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Endpoint URL</label>
              <Input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="https://your-server.com/webhook" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Events</label>
              <div className="flex flex-wrap gap-2">
                {EVENT_OPTIONS.map((ev) => (
                  <label key={ev} className="flex items-center gap-1 text-sm">
                    <input type="checkbox" checked={form.events.includes(ev)} onChange={(e) => {
                      setForm((f) => ({ ...f, events: e.target.checked ? [...f.events, ev] : f.events.filter((x) => x !== ev) }));
                    }} /> {ev}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={createWebhook.isPending}>Save</Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading ? <p className="text-muted-foreground">Loading…</p> : webhooks.length === 0 ? (
        <p className="text-muted-foreground">No webhooks configured yet.</p>
      ) : (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <Card key={wh.id}>
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-sm truncate">{wh.url}</p>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {wh.events.map((ev) => <span key={ev} className="text-xs bg-muted px-1.5 py-0.5 rounded">{ev}</span>)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Created {new Date(wh.created_at).toLocaleDateString()}</p>
                </div>
                <div className="flex gap-2 items-center ml-4">
                  <Button size="sm" variant="outline" onClick={() => handleTest(wh.id)} disabled={testWebhook.isPending}><Zap className="h-3 w-3 mr-1" />Test</Button>
                  <Button size="sm" variant="destructive" onClick={() => handleDelete(wh.id)} disabled={deleteWebhook.isPending}><Trash2 className="h-3 w-3" /></Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {testResult && (
        <Card>
          <CardContent className="p-4">
            <p className="text-sm font-medium">Test Result: <span className={testResult.status < 300 ? "text-green-600" : "text-red-600"}>{testResult.status}</span></p>
            <pre className="text-xs bg-muted p-2 mt-2 rounded overflow-x-auto">{testResult.body}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/app/\(app\)/settings/webhooks/page.tsx` → exit 0；`ruff check src/app/\(app\)/settings/webhooks/page.tsx` → 0 errors

---

### Step 6: 构建 API Key 管理页 `/settings/api`

在 `frontend/src/app/(app)/settings/api/page.tsx` 实现 API Key CRUD 页面。

操作：
- a) `useApiKeys` 渲染列表（key 前缀、名称、创建时间、最后使用时间、撤销按钮）
- b) 生成新 Key Dialog：填写 Key 名称（label），提交调用 `useCreateApiKey`；成功后弹窗展示完整 key 文本，提示"请立即复制，关闭后不再显示"
- c) 撤销按钮：调用 `useRevokeApiKey` + `queryClient.invalidateQueries`
- d) 列表顶部显示说明文字 "API Keys let external systems authenticate as your account"

```tsx
// frontend/src/app/(app)/settings/api/page.tsx
"use client";

import { useState } from "react";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/lib/api/queries";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Copy } from "lucide-react";

interface ApiKey {
  id: number;
  key_hint: string;   // e.g. "sk_live_abc…"
  label: string;
  created_at: string;
  last_used_at: string | null;
}

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useApiKeys();
  const createKey = useCreateApiKey();
  const revokeKey = useRevokeApiKey();

  const [showForm, setShowForm] = useState(false);
  const [label, setLabel] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  async function handleCreate() {
    const result = await createKey.mutateAsync({ label });
    setCreatedKey((result.data as { key: string }).key);
    queryClient.invalidateQueries({ queryKey: qk.apiKeys() });
    setLabel("");
    setShowForm(false);
  }

  async function handleRevoke(id: number) {
    await revokeKey.mutateAsync(id);
    queryClient.invalidateQueries({ queryKey: qk.apiKeys() });
  }

  const keys = (data?.data?.items ?? []) as ApiKey[];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-muted-foreground text-sm">API Keys let external systems authenticate as your account. Keep them secret.</p>
        </div>
        <Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4 mr-1" /> Generate New Key</Button>
      </div>

      {createdKey && (
        <Card className="border-green-300 bg-green-50">
          <CardContent className="p-4 space-y-3">
            <p className="text-sm font-semibold text-green-800">Your new API Key — copy it now, it will not be shown again:</p>
            <div className="flex gap-2">
              <Input value={createdKey} readOnly className="font-mono text-sm bg-white" />
              <Button size="icon" variant="outline" onClick={() => navigator.clipboard.writeText(createdKey)}><Copy className="h-4 w-4" /></Button>
            </div>
            <Button size="sm" onClick={() => setCreatedKey(null)}>Done</Button>
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card>
          <CardHeader><CardTitle className="text-base">Generate New API Key</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Key Label</label>
              <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Zapier Integration" />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={createKey.isPending || !label}>Generate</Button>
              <Button variant="outline" onClick={() => { setShowForm(false); setLabel(""); }}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading ? <p className="text-muted-foreground">Loading…</p> : keys.length === 0 ? (
        <p className="text-muted-foreground">No API keys yet. Generate one to get started.</p>
      ) : (
        <div className="space-y-3">
          {keys.map((key) => (
            <Card key={key.id}>
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium">{key.label}</p>
                  <p className="font-mono text-sm text-muted-foreground">{key.key_hint}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Created {new Date(key.created_at).toLocaleDateString()}
                    {key.last_used_at ? ` · Last used ${new Date(key.last_used_at).toLocaleDateString()}` : " · Never used"}
                  </p>
                </div>
                <Button size="sm" variant="destructive" onClick={() => handleRevoke(key.id)} disabled={revokeKey.isPending}>
                  <Trash2 className="h-3 w-3 mr-1" /> Revoke
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

**完成判定**：`cd frontend && npx tsc --noEmit src/app/\(app\)/settings/api/page.tsx` → exit 0；`ruff check src/app/\(app\)/settings/api/page.tsx` → 0 errors

---

### Step 7: 端到端类型检查与 lint

操作：
- a) `cd frontend && npx tsc --noEmit`
- b) `cd frontend && ruff check src/app/\(app\)/marketplace/ src/app/\(app\)/settings/webhooks/page.tsx src/app/\(app\)/settings/api/page.tsx src/lib/api/queries.ts src/components/layout/app-sidebar.tsx`

**完成判定**：两条命令均 exit 0

---

## 6. 验收

- [ ] `cd frontend && npx tsc --noEmit` → 0 errors
- [ ] `cd frontend && ruff check src/app/\(app\)/marketplace/ src/app/\(app\)/settings/webhooks/page.tsx src/app/\(app\)/settings/api/page.tsx src/lib/api/queries.ts src/components/layout/app-sidebar.tsx` → 0 errors
- [ ] `ls frontend/src/app/\(app\)/marketplace/page.tsx frontend/src/app/\(app\)/marketplace/\[app_id\]/page.tsx frontend/src/app/\(app\)/settings/webhooks/page.tsx frontend/src/app/\(app\)/settings/api/page.tsx` → 四个文件均存在
- [ ] `curl -s http://localhost:3000/marketplace | grep -q "App Marketplace"` → exit 0（如 dev server 运行）
- [ ] `curl -s http://localhost:3000/settings/webhooks | grep -q "Webhooks"` → exit 0（如 dev server 运行）
- [ ] `curl -s http://localhost:3000/settings/api | grep -q "API Keys"` → exit 0（如 dev server 运行）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 后端 #498 API 尚未完成，前端调用 404 | 中 | 中 | 前端所有 API 调用加 `try/catch`，错误时展示 "Connection failed — backend not ready yet" 提示；不阻塞 UI 渲染 |
| OAuth2 跳转后第三方回调地址配置错误 | 中 | 高 | Install 按钮点击前加确认 dialog，显示目标 URL；后端配置错误时用户看到 400 错误页而非白屏 |
| Webhook 列表数据量大导致渲染卡顿 | 低 | 低 | 使用 React Query 的 `staleTime: 30_000` 避免频繁 refetch；列表页加虚拟滚动（如数据 > 50 条）|
| API Key revoke 操作误触 | 低 | 中 | Revoke 按钮加 `window.confirm("Revoke this API key? This cannot be undone.")；操作后即时刷新列表 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/app/\(app\)/marketplace/ frontend/src/app/\(app\)/settings/webhooks/page.tsx \
         frontend/src/app/\(app\)/settings/api/page.tsx frontend/src/lib/api/queries.ts \
         frontend/src/components/layout/app-sidebar.tsx \
         docs/dev-plan/90-frontend/0499-build-app-marketplace-frontend-page.md
git commit -m "feat(frontend): add /marketplace, /settings/webhooks, /settings/api pages"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): add App Marketplace and Settings pages (#499)" --body "Closes #499"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`frontend/src/app/(app)/settings/page.tsx` — 现有 Settings 页面的表单和 Card 布局模式
- 同类参考实现：`frontend/src/app/(app)/automation/rules/page.tsx` — 列表页 + 新建表单 Dialog 的交互模式
- 同类参考实现：`frontend/src/components/layout/app-sidebar.tsx` — 侧边栏导航项注册规范
- 父 issue / 关联：#78
- 前置依赖：#498
