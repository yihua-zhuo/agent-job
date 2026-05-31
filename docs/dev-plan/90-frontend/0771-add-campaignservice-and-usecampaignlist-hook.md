# CampaignService + useCampaignList 抽象层 · 为 CampaignList 提供数据与状态挂载点

| 元数据 | 值 |
|---|---|
| Issue | #771 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [#770](./0770-add-campaign-router-and-paginated-list.md) — TBD - 待验证：campaign router and paginated list 后端路由文档 |
| 启用后赋能 | [#531](./0531-build-campaign-list-ui-page.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CampaignList 组件直接内联 fetch 逻辑，紧耦合于 UI 层，无法在多个视图间复用，也无法独立测试 API 请求行为。一旦 GET /api/v1/marketing/campaigns 的参数结构或鉴权方式变化，所有消费方都必须同步修改。抽象出 service + hook 是 #531 推进功能 parity 的关键前置步骤，也符合前端架构"数据层与视图层解耦"的要求。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层重构。
- **开发者视角**：可在任意组件中 import { useCampaignList } from "hooks/useCampaignList"，传入 status / sortBy / sortOrder 即可获得 Campaign[]、loading、error，且调用 setStatus / setSortBy / setSortOrder 自动触发重新请求，无需手动管理 refetch 逻辑。service 层可独立单元测试。

### 1.3 不做什么（剔除）

- [ ] 不实现 CampaignList UI 组件本身（留在下游板块）
- [ ] 不实现 create / update / delete campaign 的写操作 API 封装（本板块仅覆盖 list 查询）
- [ ] 不引入 React Query / SWR 等第三方状态管理库，优先使用原生 useState + useEffect
- [ ] 不修改后端 router 或 service 层代码（本板块仅前端）

### 1.4 关键 KPI

- `ruff check src/ui/services/campaignService.ts src/ui/hooks/useCampaignList.ts` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_campaign_service.py -v` → 全 passed（如存在）
- TypeScript 编译 `npx tsc --noEmit` → 0 errors
- useCampaignList 导出类型包含 `Campaign[]`、`loading: boolean`、`error: string | null` 及三个 setter
- 调用 setStatus 后自动触发 useEffect 重新请求（通过 dependency array 控制）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/ui/` 目录下是否存在 `services/` 子目录或 `hooks/` 子目录 — 如不存在则为新建模块

### 2.2 涉及文件清单

- 要改：
  - TBD — 待验证是否存在 `src/ui/services/` 或 `src/ui/hooks/` 目录需确认
- 要建：
  - `src/ui/services/campaignService.ts` — 封装 GET /api/v1/marketing/campaigns 的 fetch 调用，接受 status / sortBy / sortOrder 参数
  - `src/ui/hooks/useCampaignList.ts` — 提供 useCampaignList hook，返回 data / loading / error + 三个 setter
  - `tests/unit/test_campaign_service.ts` — campaignService 单元测试（fetch mock）
  - `tests/unit/test_useCampaignList.ts` — useCampaignList hook 单元测试（React Testing Library）

### 2.3 缺什么

- [ ] `src/ui/services/campaignService.ts` — 缺失统一的 campaign list API 封装
- [ ] `src/ui/hooks/useCampaignList.ts` — 缺失响应式数据 hook，组件无法解耦 fetch 逻辑
- [ ] 后端 GET /api/v1/marketing/campaigns 接口已由 #770 提供，本板块依赖该 router 存在
- [ ] 缺少前端测试基础设施配置（Vitest + React Testing Library），如尚未引入需记录
- [ ] 缺少 Campaign 类型定义（interface），建议在 `src/ui/types/campaign.ts` 统一导出

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/ui/services/campaignService.ts` | 封装 GET /api/v1/marketing/campaigns，接收 status / sortBy / sortOrder 参数，返回 Promise |
| `src/ui/hooks/useCampaignList.ts` | useCampaignList hook，暴露 Campaign[]、loading、error 及 setStatus / setSortBy / setSortOrder |
| `src/ui/types/campaign.ts` | 导出 Campaign 接口类型（如不存在则新建） |
| `tests/unit/test_campaign_service.ts` | campaignService 单元测试，mock fetch |
| `tests/unit/test_useCampaignList.ts` | useCampaignList 单元测试，mock service |
| `docs/dev-plan/90-frontend/0771-add-campaignservice-and-usecampaignlist-hook.md` | 本板块文档 |

### 3.2 修改文件

TBD - 待验证是否有现有 `src/ui/services/` 或 `src/ui/hooks/` 目录需确认结构；若无侧修改文件

### 3.3 新增能力

- **Service method**：`campaignService.getCampaignList(params: CampaignListParams): Promise<CampaignListResponse>`
- **Hook**：`useCampaignList(initialParams?: CampaignListParams) → { data: Campaign[], loading: boolean, error: string | null, setStatus, setSortBy, setSortOrder }`
- **Type**：Campaign 接口 / CampaignListParams 接口 / CampaignListResponse 接口
- **API endpoint（本板块不实现，但封装其调用）**：`GET /api/v1/marketing/campaigns?status=&sort_by=&sort_order=`（由 #770 提供）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 React 原生 useState + useEffect 而非 React Query / SWR**：当前项目前端无状态管理库依赖，引入 React Query 会增加包体积与学习成本；原生实现足够覆盖 list + filter + sort 场景，且更易与现有测试框架对齐。
- **选 service 独立封装而非直接在 hook 内 fetch**：复用性更强，service 可被非 React 上下文调用（如其他工具函数）；测试时可独立注入 mock。
- **setStatus/setSortBy/setSortOrder 直接替换状态而非合并参数**：避免部分参数被旧状态污染，每次 setter 调用保证请求参数是完整快照。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| React | ≥18.x | 项目现有版本，useState / useEffect API 稳定 |
| TypeScript | ≥5.x | 项目现有版本，支持 satisfies、interface extends 等特性 |

### 4.3 兼容性约束

- 所有 API 请求必须携带认证 token（从 localStorage / cookie / Context 获取），参考现有 `src/ui/services/` 中其他 service 的实现方式
- hook 必须在 React 函数组件或自定义 hook 内部调用（遵守 React hooks 规则）
- status 参数枚举值必须与后端一致（pending / active / paused / completed 等），类型用 string union 定义
- 多租户：后端接口隐含 tenant_id（由 backend session / header 携带），前端无需显式传递

### 4.4 已知坑

1. **fetch 不支持 proxy 导致 CORS** → 规避：确认 dev server 已配置 API 代理（如 vite proxy / next.config.js rewrites）；测试时用 msw（Mock Service Worker）或 vi.mock 拦截 fetch
2. **useEffect 依赖数组遗漏导致 stale closure** → 规避：setter 使用 functional update 或在 dependency array 中显式加入 params 对象（useRef 包裹避免无限循环）；setStatus 调用后立即触发 re-fetch 的逻辑通过 useEffect([params]) 自动完成
3. **TypeScript 类型未对齐后端响应结构导致 runtime error** → 规避：在 `src/ui/types/campaign.ts` 中定义与后端 Pydantic schema 对应的 interface，并添加 JSDoc 或 tdoc 注释；与 #770 确认响应体字段

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 Campaign 类型定义文件

在 `src/ui/types/campaign.ts` 定义所有相关 TypeScript 接口，确保与后端 Pydantic schema 对齐。

```typescript
// src/ui/types/campaign.ts
export type CampaignStatus = "pending" | "active" | "paused" | "completed";

export interface Campaign {
  id: number;
  name: string;
  status: CampaignStatus;
  created_at: string;
  updated_at: string;
}

export interface CampaignListParams {
  status?: CampaignStatus;
  sort_by?: "created_at" | "name" | "status";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface CampaignListResponse {
  items: Campaign[];
  total: number;
  page: number;
  page_size?: number;
}
```

操作：
- a) 创建 `src/ui/types/` 目录（如不存在）
- b) 新建 `src/ui/types/campaign.ts`，粘贴以上内容
- c) 从 `src/ui/types/index.ts` 导出（若 index.ts 不存在则新建并导出）

**完成判定**：`npx tsc --noEmit src/ui/types/campaign.ts` → 0 errors

---

### Step 2: 创建 campaignService.ts

在 `src/ui/services/campaignService.ts` 封装 GET /api/v1/marketing/campaigns 请求。

```typescript
// src/ui/services/campaignService.ts
import type { CampaignListParams, CampaignListResponse } from "../types/campaign";

const BASE_URL = "/api/v1/marketing";

export async function campaignService(
  params: CampaignListParams = {}
): Promise<CampaignListResponse> {
  const url = new URL(`${BASE_URL}/campaigns`, window.location.origin);
  if (params.status) url.searchParams.set("status", params.status);
  if (params.sort_by) url.searchParams.set("sort_by", params.sort_by);
  if (params.sort_order) url.searchParams.set("sort_order", params.sort_order);
  if (params.page) url.searchParams.set("page", String(params.page));
  if (params.page_size) url.searchParams.set("page_size", String(params.page_size));

  const token = localStorage.getItem("auth_token");
  const res = await fetch(url.toString(), {
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<CampaignListResponse>;
}
```

操作：
- a) 创建 `src/ui/services/` 目录（如不存在）
- b) 新建 `src/ui/services/campaignService.ts`，粘贴以上内容
- c) 如有现有 `src/ui/services/index.ts` 则追加导出

**完成判定**：`npx tsc --noEmit src/ui/services/campaignService.ts` → 0 errors；`ruff check src/ui/services/campaignService.ts` → 0 errors（如启用 ruff 对 ts 文件检查）

---

### Step 3: 创建 useCampaignList.ts hook

在 `src/ui/hooks/useCampaignList.ts` 提供响应式 hook，暴露 data / loading / error 及三个 setter。

```typescript
// src/ui/hooks/useCampaignList.ts
import { useState, useEffect, useCallback, useRef } from "react";
import { campaignService } from "../services/campaignService";
import type { Campaign, CampaignListParams, CampaignStatus } from "../types/campaign";

export interface UseCampaignListReturn {
  data: Campaign[];
  loading: boolean;
  error: string | null;
  setStatus: (status: CampaignStatus | undefined) => void;
  setSortBy: (sortBy: "created_at" | "name" | "status" | undefined) => void;
  setSortOrder: (order: "asc" | "desc" | undefined) => void;
}

export function useCampaignList(initialParams: CampaignListParams = {}): UseCampaignListReturn {
  const [params, setParams] = useState<CampaignListParams>(initialParams);
  const [data, setData] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    campaignService({ ...params, signal: controller.signal })
      .then((res) => {
        setData(res.items);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => controller.abort();
  }, [params]); // eslint-disable-line react-hooks/exhaustive-deps

  const setStatus = useCallback((status: CampaignStatus | undefined) => {
    setParams((prev) => ({ ...prev, status }));
  }, []);

  const setSortBy = useCallback((sort_by: "created_at" | "name" | "status" | undefined) => {
    setParams((prev) => ({ ...prev, sort_by }));
  }, []);

  const setSortOrder = useCallback((sort_order: "asc" | "desc" | undefined) => {
    setParams((prev) => ({ ...prev, sort_order }));
  }, []);

  return { data, loading, error, setStatus, setSortBy, setSortOrder };
}
```

操作：
- a) 创建 `src/ui/hooks/` 目录（如不存在）
- b) 新建 `src/ui/hooks/useCampaignList.ts`，粘贴以上内容
- c) 如有现有 `src/ui/hooks/index.ts` 则追加导出

**完成判定**：`npx tsc --noEmit src/ui/hooks/useCampaignList.ts` → 0 errors

---

### Step 4: 编写 campaignService 单元测试

用 Vitest + vi.mock 拦截 fetch，验证参数构造和错误处理。

```typescript
// tests/unit/test_campaign_service.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { campaignService } from "../../src/ui/services/campaignService";

global.fetch = vi.fn();

const mockFetch = global.fetch as ReturnType<typeof vi.fn>;

describe("campaignService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("builds URL with status param", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 20 }),
    });

    await campaignService({ status: "active" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("status=active"),
      expect.any(Object)
    );
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: "Unauthorized" }),
    });

    await expect(campaignService()).rejects.toThrow("Unauthorized");
  });

  it("returns items array", async () => {
    const mockItems = [{ id: 1, name: "Campaign A", status: "active", created_at: "", updated_at: "" }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: mockItems, total: 1, page: 1, page_size: 20 }),
    });

    const res = await campaignService();
    expect(res.items).toHaveLength(1);
  });
});
```

操作：
- a) 确保 `tests/unit/` 下有 Vitest 配置（`vitest.config.ts`）
- b) 新建 `tests/unit/test_campaign_service.ts` 粘贴以上内容
- c) 运行测试确认通过

**完成判定**：`npx vitest run tests/unit/test_campaign_service.ts` → 3 passed

---

### Step 5: 编写 useCampaignList hook 单元测试

用 React Testing Library 的 `renderHook` + service mock，验证 loading / error 状态和 setter 触发 re-fetch。

```typescript
// tests/unit/test_useCampaignList.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { UseCampaignList } from "../../src/ui/hooks/useCampaignList";
import { campaignService } from "../../src/ui/services/campaignService";

vi.mock("../../src/ui/services/campaignService");

const mockService = campaignService as ReturnType<typeof vi.fn>;

describe("useCampaignList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockService.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  });

  it("returns loading=true then data", async () => {
    const { result } = renderHook(() => useCampaignList());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual([]);
  });

  it("returns error on failure", async () => {
    mockService.mockRejectedValueOnce(new Error("Network error"));
    const { result } = renderHook(() => useCampaignList());
    await waitFor(() => expect(result.current.error).toBe("Network error"));
  });

  it("setStatus triggers re-fetch", async () => {
    const { result } = renderHook(() => useCampaignList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    result.current.setStatus("active");
    await waitFor(() => expect(result.current.loading).toBe(true));
    await waitFor(() => expect(mockService).toHaveBeenCalledTimes(2));
  });
});
```

操作：
- a) 新建 `tests/unit/test_useCampaignList.ts` 粘贴以上内容
- b) 运行测试确认通过

**完成判定**：`npx vitest run tests/unit/test_useCampaignList.ts` → 3 passed

---

## 6. 验收

- [ ] `npx tsc --noEmit src/ui/services/campaignService.ts src/ui/hooks/useCampaignList.ts src/ui/types/campaign.ts` → 0 errors
- [ ] `npx vitest run tests/unit/test_campaign_service.ts` → 3 passed
- [ ] `npx vitest run tests/unit/test_useCampaignList.ts` → 3 passed
- [ ] `ruff check src/ui/services/campaignService.ts src/ui/hooks/useCampaignList.ts` → 0 errors（如 repo 对 TypeScript 文件启用 ruff）
- [ ] 端到端（启动 dev server 后）：`curl http://localhost:3000/api/v1/marketing/campaigns?status=active` 或在浏览器 Network 面板确认 CampaignList 消费 `useCampaignList` 成功渲染数据（手动验证，测试框架无法覆盖 UI 集成）
- [ ] useCampaignList.ts 中 `setStatus` 的调用链经过 useEffect([params]) 触发 re-fetch — 通过 Step 5 测试验证

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 后端 GET /api/v1/marketing/campaigns 参数名与前端不一致（sort_by vs sortBy） | 中 | 高 | 在 campaignService 中做字段映射；与 #770 作者对齐接口；最坏回退：修改 service 参数序列化逻辑 |
| React Testing Library / Vitest 版本不兼容导致测试失败 | 低 | 中 | 锁定 `vitest` 和 `@testing-library/react` 版本到已知兼容版本；CI 失败则降级到 jest |
| setStatus 触发 re-fetch 时产生竞态（旧请求覆盖新请求） | 中 | 中 | 使用 AbortController 取消进行中请求（已在 Step 3 实现），测试覆盖此场景 |
| 前端无现有 service/hook 目录结构，本板块新建后其他同学消费路径不一致 | 低 | 低 | 在 `src/ui/services/index.ts` 和 `src/ui/hooks/index.ts` 统一导出；文档记录在 #531 父 issue 中 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/types/campaign.ts src/ui/services/campaignService.ts src/ui/hooks/useCampaignList.ts
git add tests/unit/test_campaign_service.ts tests/unit/test_useCampaignList.ts
git commit -m "feat(frontend): add campaignService and useCampaignList hook"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): campaignService + useCampaignList hook (closes #771)" --body "Closes #771"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`TBD - 待验证：src/ui/services/ 目录下已有其他 *_service.ts 文件可作参照，如 customerService 或 opportunityService 的封装风格`
- 父 issue / 关联：#531（Campaign Feature Parity 主线）、#770（Campaign Router + Paginated List 后端）
- 第三方文档：[React Hooks 官方文档](https://react.dev/reference/react)、[Vitest 官方文档](https://vitest.dev/)、[@testing-library/react 文档](https://testing-library.com/docs/react-testing-library/intro/)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
