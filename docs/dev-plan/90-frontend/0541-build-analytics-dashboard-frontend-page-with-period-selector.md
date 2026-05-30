# 分析 · 构建数据分析仪表盘前端页面

| 元数据 | 值 |
|---|---|
| Issue | #541 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [构建分析 API 端点](60-analytics/0540-add-analytics-api-endpoints-and-service-wiring.md) |
| 启用后赋能 | 分析数据可视化（#56 子任务后续），全栈功能入口 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 系统缺少数据分析前端入口，用户无法可视化查看销售漏斗、工单状态等关键业务指标。作为 #56 的子任务，#540 已构建分析 API 端点，本板块负责前端页面 shell 与用户交互层，使数据得以呈现。

### 1.2 做完后

- **用户视角**：访问 `/analytics` 页面，可通过 period selector（今日 / 7 天 / 30 天 / 90 天 / 自定义）切换时间范围，页面自动重新请求 API 并渲染图表容器；6 种图表类型均显示占位骨架或真实数据。
- **开发者视角**：获得 `frontend/pages/analytics.tsx` 页面组件及可复用的图表容器组件，后续接入真实数据源时只需替换 fetch 调用；无新增 service/router 依赖，纯前端工作。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 analytics API（由 #540 负责）
- [ ] 不引入新的图表库——使用 `package.json` 中已有库
- [ ] 不实现数据导出或打印功能
- [ ] 不实现用户权限控制（auth 由其他板块覆盖）

### 1.4 关键 KPI

- [页面加载：刷新 `/analytics` 无 JS error，控制台无 Warning]
- [Period selector 切换：`today → 7d → 30d → 90d → custom` 每次切换触发一次 fetch，console 无 error]
- [`ruff check frontend/` → 0 errors（若项目有 frontend lint 配置）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`frontend/pages/` 目录是否存在，页面路由是否基于文件约定（Next.js / React Router / Vite）—— 需要先读取 `package.json` 确认前端框架

TBD - 待验证：`frontend/` 下是否有已有的图表组件文件（如 `ChartContainer`、`LineChart`、`BarChart`）—— 如果已有则复用，如果没有则新建 `frontend/components/charts/`

TBD - 待验证：`package.json` 中的图表库（推测可能为 Recharts / Chart.js / Apache ECharts）

现有页面参考（同类页面结构）：TBD - 待验证：`frontend/pages/` 下现有的 `.tsx` 页面文件结构，作为本页面参考

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`frontend/package.json` — 确认图表库版本及依赖
- 要建：
  - `frontend/pages/analytics.tsx` — 分析页面主入口，集成 period selector
  - `frontend/components/charts/ChartContainer.tsx` — 图表容器封装（如不存在）
  - `frontend/hooks/useAnalytics.ts` — 分析数据 fetch hook（复用 #540 API 端点）
  - `frontend/components/PeriodSelector.tsx` — 时间范围选择器组件
  - `frontend/components/AnalyticsSkeleton.tsx` — 图表加载骨架屏
  - `frontend/__tests__/analytics.test.tsx` — 页面单元测试

### 2.3 缺什么

- [ ] 缺少 `/analytics` 路由页面
- [ ] 缺少 period selector 组件（today / 7d / 30d / 90d / custom）
- [ ] 缺少调用 #540 后端 API 的 frontend fetch 层（hook/service）
- [ ] 缺少 6 种图表类型的容器组件或占位实现
- [ ] 缺少加载状态 / 错误状态的 UI 处理

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/pages/analytics.tsx` | 分析仪表盘主页面，含 period selector + 6 个图表容器 |
| `frontend/components/PeriodSelector.tsx` | 时间范围选择器，支持预设 + 自定义日期 |
| `frontend/hooks/useAnalytics.ts` | 封装 fetch 调用 #540 API，支持 period 参数与自动重请求 |
| `frontend/components/charts/ChartContainer.tsx` | 通用图表容器（骨架屏 / 错误 / 真实图表封装） |
| `frontend/__tests__/analytics.test.tsx` | 页面渲染测试 + selector 切换行为测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`frontend/package.json` | 如需新增图表库依赖则更新（原则上不引入新库） |

### 3.3 新增能力

- **页面路由**：`/analytics` — 分析仪表盘（含 period selector + 6 chart containers）
- **前端 Hook**：`useAnalytics(period: Period) → { data, loading, error, refetch }`
- **组件**：`PeriodSelector`（today/7d/30d/90d/custom）、`ChartContainer`（占位/数据展示）
- **API 调用**：GET 请求至 #540 端点（如 `/api/analytics/sales-funnel`、`/api/analytics/ticket-volume` 等）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 package.json 已有图表库而非引入新库**：减少 bundle 体积与维护成本；如无可用库则通过 npm install 添加并在 §4.2 记录版本约束。
- **用 React Hook 封装 fetch 而非 Redux/Context**：轻量级数据获取，selector 切换直接触发 re-render；状态简单无需全局 store。
- **用条件渲染实现 skeleton vs chart vs error 三态**：不引入额外 loading 库，保持组件自包含。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| TBD - 待确认：图表库（如 Recharts） | `^2.x` 或 `^3.x` | 需确认 package.json 现有版本以保持兼容 |

### 4.3 兼容性约束

- 前端 framework：使用项目当前框架（Next.js Page Router 或 React Router v6），不引入 SSR 特殊处理
- 类型安全：TypeScript strict 模式，props 和 API 响应均有类型定义
- 多租户：前端无需处理 tenant_id，API 调用由后端通过 session/cookie 读取

### 4.4 已知坑

1. **Period selector 切换过快导致请求竞态** → 规避：使用 `useEffect` 清理或 `AbortController` 取消上一次请求
2. **自定义日期 range 未验证格式** → 规避：`PeriodSelector` 内部做日期格式校验，非法输入显示错误提示
3. **图表库 SSR 不兼容（Next.js）** → 规避：图表组件用 `dynamic(() => import(...), { ssr: false })` 懒加载
4. **TBD - 待验证：`frontend/` 目录结构** → 如项目使用 Vite 而非 Next.js，路由与懒加载策略需相应调整

---

## 5. 实现步骤（按顺序）

### Step 1: 确认前端技术栈与图表库

读取 `frontend/package.json`（或项目根目录的 `package.json`）确认：
- 前端框架（Next.js / React + Vite）
- 已安装的图表库及版本
- 现有组件目录结构

若 `frontend/pages/` 不存在则说明项目可能使用 Vite 路由，页面文件应放在 `src/pages/` 或 `src/routes/`。

完成后判定：`grep -r "recharts\|chart\.js\|echarts" frontend/package.json || grep -r "recharts\|chart\.js\|echarts" package.json` 有输出

### Step 2: 创建 PeriodSelector 组件

在 `frontend/components/PeriodSelector.tsx` 创建时间范围选择器组件：

```tsx
// frontend/components/PeriodSelector.tsx
type Period = 'today' | '7d' | '30d' | '90d' | 'custom';

interface PeriodSelectorProps {
  value: Period;
  onChange: (period: Period, customRange?: { from: string; to: string }) => void;
  disabled?: boolean;
}

export function PeriodSelector({ value, onChange, disabled }: PeriodSelectorProps) {
  // 预设选项 + custom 时渲染日期选择器
  return (...)
}
```

完成后判定：`ls frontend/components/PeriodSelector.tsx` 文件存在，`ruff check frontend/components/PeriodSelector.tsx` 无 error（如配置存在）

### Step 3: 创建 useAnalytics hook

在 `frontend/hooks/useAnalytics.ts` 封装 fetch 逻辑：

```tsx
// frontend/hooks/useAnalytics.ts
import { useState, useEffect, useCallback } from 'react';

type Period = 'today' | '7d' | '30d' | '90d' | 'custom';

interface AnalyticsParams {
  period: Period;
  customRange?: { from: string; to: string };
}

export function useAnalytics(params: AnalyticsParams) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({ period: params.period });
      const res = await fetch(`/api/analytics?${query}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [params.period, params.customRange]);

  useEffect(() => {
    const controller = new AbortController();
    // 调用 fetchData 并在 cleanup 中 abort
    return () => controller.abort();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
```

完成后判定：`ls frontend/hooks/useAnalytics.ts` 文件存在

### Step 4: 创建 ChartContainer 组件

在 `frontend/components/charts/ChartContainer.tsx` 创建图表容器，支持 skeleton / chart / error 三态：

```tsx
// frontend/components/charts/ChartContainer.tsx
interface ChartContainerProps {
  title: string;
  loading?: boolean;
  error?: string | null;
  children: React.ReactNode;
}

export function ChartContainer({ title, loading, error, children }: ChartContainerProps) {
  return (
    <div className="chart-container">
      <h3>{title}</h3>
      {loading && <div className="skeleton" />}
      {error && <div className="error-msg">{error}</div>}
      {!loading && !error && children}
    </div>
  );
}
```

完成后判定：`ls frontend/components/charts/ChartContainer.tsx` 文件存在

### Step 5: 构建 analytics.tsx 主页面

在 `frontend/pages/analytics.tsx`（或对应框架路由目录）创建主页面，整合所有组件：

```tsx
// frontend/pages/analytics.tsx
import { useState } from 'react';
import { PeriodSelector } from '../components/PeriodSelector';
import { useAnalytics } from '../hooks/useAnalytics';
import { ChartContainer } from '../components/charts/ChartContainer';

// 6 种图表类型对应的 API 端点（来自 #540）
const CHART_ENDPOINTS = [
  { key: 'sales-funnel', title: '销售漏斗' },
  { key: 'ticket-volume', title: '工单量趋势' },
  { key: 'revenue-trend', title: '收入趋势' },
  { key: 'customer-growth', title: '客户增长' },
  { key: 'campaign-performance', title: '营销活动效果' },
  { key: 'sla-compliance', title: 'SLA 合规率' },
];

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'today' | '7d' | '30d' | '90d' | 'custom'>('7d');
  const [customRange, setCustomRange] = useState<{ from: string; to: string } | undefined>();

  const { data, loading, error } = useAnalytics({ period, customRange });

  return (
    <main>
      <h1>数据分析</h1>
      <PeriodSelector
        value={period}
        onChange={(p, range) => { setPeriod(p); setCustomRange(range); }}
      />
      <div className="charts-grid">
        {CHART_ENDPOINTS.map(chart => (
          <ChartContainer
            key={chart.key}
            title={chart.title}
            loading={loading}
            error={error}
          >
            {/* 调用真实 API 渲染图表，暂用占位 div */}
            <div className="chart-placeholder" data-chart={chart.key} />
          </ChartContainer>
        ))}
      </div>
    </main>
  );
}
```

完成后判定：`ls frontend/pages/analytics.tsx` 文件存在

### Step 6: 编写页面测试

在 `frontend/__tests__/analytics.test.tsx` 编写测试：

```tsx
// frontend/__tests__/analytics.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AnalyticsPage from '../pages/analytics';

describe('AnalyticsPage', () => {
  it('renders page title', () => {
    render(<AnalyticsPage />);
    expect(screen.getByText('数据分析')).toBeInTheDocument();
  });

  it('renders all 6 chart containers', () => {
    render(<AnalyticsPage />);
    expect(screen.getAllByRole('region')).toHaveLength(6);
  });

  it('period selector triggers re-fetch', async () => {
    render(<AnalyticsPage />);
    const button = screen.getByRole('button', { name: /30 天/i });
    fireEvent.click(button);
    // 验证 loading 状态出现
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).toBeInTheDocument();
    });
  });
});
```

完成后判定：`ls frontend/__tests__/analytics.test.tsx` 文件存在

---

## 6. 验收

- [ ] `ls frontend/pages/analytics.tsx` → 文件存在（页面入口）
- [ ] `ls frontend/components/PeriodSelector.tsx` && `ls frontend/hooks/useAnalytics.ts` → 全部存在
- [ ] `ls frontend/components/charts/ChartContainer.tsx` → 文件存在（如已有则跳过）
- [ ] `ls frontend/__tests__/analytics.test.tsx` → 文件存在
- [ ] 页面渲染：`npm run test -- frontend/__tests__/analytics.test.tsx` → 全 passed（如使用 jest/vitest）
- [ ] 代码质量：`ruff check frontend/` → 0 errors（如项目配置 frontend lint）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #540 后端 API 未就绪，前端无真实数据可调 | 中 | 中 | useAnalytics hook 捕获 fetch 错误并显示 error state；图表容器显示"数据加载失败"而非崩溃；不影响页面加载验收 |
| package.json 中无图表库，需引入新依赖 | 中 | 低 | 引入 Recharts（轻量、TypeScript 支持好），在 §4.2 记录版本约束；不阻塞开发进度 |
| 前端 framework 与预期不符（Next.js vs Vite） | 低 | 中 | 根据实际框架调整路由文件路径与 SSR 处理方式；图表动态导入策略保持不变 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/pages/analytics.tsx \
       frontend/components/PeriodSelector.tsx \
       frontend/hooks/useAnalytics.ts \
       frontend/__tests__/analytics.test.tsx
git commit -m "feat(frontend): add /analytics dashboard page with period selector"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): build analytics dashboard page #541" --body "Closes #541"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`frontend/pages/` 下现有页面组件结构（用于参考路由/组件写法）
- 第三方文档：[Recharts 官方文档](https://recharts.org/en-US/)（如选用 Recharts）
- 父 issue / 关联：#56（分析仪表盘父任务），#540（分析 API 后端），#541（本板块）
