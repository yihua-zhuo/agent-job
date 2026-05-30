# Revenue / Sales / Acquisition Chart Components

| 元数据 | 值 |
|---|---|
| Issue | #542 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：`docs/dev-plan/60-analytics/0541-add-analytics-data-layer-api-endpoints.md` |
| 启用后赋能 | 90-frontend 板块（Analytics Dashboard 页面） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Analytics Dashboard 需要三个核心图表组件向用户直观展示收入趋势、销售团队表现和客户获取动态。目前前端没有这些组件，Analytics 模块只有裸的数据端点，没有可渲染的视图。缺少图表导致用户无法从数据中快速获取洞察，业务决策依赖人工导表。

### 1.2 做完后

- **用户视角**：Analytics Dashboard 页面渲染三个交互式图表（收入折线/面积图、销售团队条形图、客户获取趋势图），图表随页面顶部的周期选择器（7天/30天/90天/自定义）联动刷新数据。
- **开发者视角**：新增 `RevenueChart`、`SalesChart`、`AcquisitionChart` 三个 React 组件，封装数据获取 → 数据转换 → 渲染逻辑，可被 Dashboard 页面直接引用；组件导出类型供其他模块复用。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 analytics API（由 #541 负责）；本板块只消费 API，不建 API。
- [ ] 不实现图表编辑/导出功能（导出为 PNG/CSV 等）。
- [ ] 不实现权限控制层（图表数据按租户隔离在后端已处理）。

### 1.4 关键 KPI

- [指标 1：`ls frontend/components/analytics/` 包含 `RevenueChart.tsx`、`SalesChart.tsx`、`AcquisitionChart.tsx` 三个文件]
- [指标 2：三个组件均通过 `npm run typecheck`（无 TypeScript 错误）]
- [指标 3：`npm test` → 三个组件的单元测试 ≥ 9 passed（每个组件 ≥ 3 个测试用例）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`frontend/components/analytics/` 目录是否存在；当前是否有 Recharts 库或 D3 库已安装在 `package.json` 中

当前 Dashboard 入口（推测路径）：
```
frontend/pages/dashboard/analytics.tsx   # TBD - 待验证
frontend/components/analytics/          # 可能尚不存在
```

Recharts 库可能在 `package.json` 中已有，以下命令可验证：
```bash
grep -E "recharts|d3" frontend/package.json
```

### 2.2 涉及文件清单

- 要改：
  - `frontend/package.json` — 添加图表依赖（如 Recharts 未装）
- 要建：
  - `frontend/components/analytics/RevenueChart.tsx` — 收入折线/面积图组件
  - `frontend/components/analytics/SalesChart.tsx` — 销售团队/人员条形图组件
  - `frontend/components/analytics/AcquisitionChart.tsx` — 客户获取趋势折线图组件
  - `frontend/components/analytics/index.ts` — 三组件统一导出
  - `tests/unit/frontend/RevenueChart.test.tsx` — RevenueChart 单元测试
  - `tests/unit/frontend/SalesChart.test.tsx` — SalesChart 单元测试
  - `tests/unit/frontend/AcquisitionChart.test.tsx` — AcquisitionChart 单元测试
  - `alembic/versions/<id>_add_analytics_tables.sql` — 若 #541 需要（由 #541 负责，本板块不新建 migration）

### 2.3 缺什么

- [ ] 没有 RevenueChart 组件，收入数据无法可视化
- [ ] 没有 SalesChart 组件，销售团队排名无法可视化
- [ ] 没有 AcquisitionChart 组件，客户增长趋势无法可视化
- [ ] 前端没有统一的数据获取 hook（`useAnalyticsData` 或类似）导致组件各自重复 fetch 逻辑
- [ ] 没有图表公共类型定义（`ChartDataPoint`、`Period` 等），组件间无共享类型
- [ ] 没有周期选择器（PeriodSelector）组件（可能由其他 frontend 板块实施，但图表需要响应其变化）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/components/analytics/RevenueChart.tsx` | 收入折线/面积图，响应 PeriodSelector 联动 |
| `frontend/components/analytics/SalesChart.tsx` | 销售团队/人员条形图，显示排名和绝对值 |
| `frontend/components/analytics/AcquisitionChart.tsx` | 客户获取趋势折线图，显示月/周维度新增数 |
| `frontend/components/analytics/index.ts` | 三组件及公共类型统一导出 |
| `frontend/hooks/useAnalytics.ts` | 数据获取 hook，统一处理 API 调用和 loading/error 状态 |
| `tests/unit/frontend/RevenueChart.test.tsx` | RevenueChart 渲染和数据映射测试 |
| `tests/unit/frontend/SalesChart.test.tsx` | SalesChart 渲染和数据映射测试 |
| `tests/unit/frontend/AcquisitionChart.test.tsx` | AcquisitionChart 渲染和数据映射测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `frontend/package.json` | 添加 `recharts`（或确认已有）|
| `frontend/pages/dashboard/analytics.tsx` | 导入并渲染三个图表组件，传入 period 参数 |

### 3.3 新增能力

- **React 组件**：`RevenueChart` — 收入折线/面积图，支持自定义颜色、图例、Tooltip
- **React 组件**：`SalesChart` — 销售团队/人员分组条形图，支持排序
- **React 组件**：`AcquisitionChart` — 客户获取趋势折线图，支持多系列（新增/流失/净增）
- **Custom Hook**：`useAnalytics(period: Period): { revenue, sales, acquisition, loading, error }`
- **类型定义**：`ChartDataPoint`、`Period`、`ChartResponse` 接口在 `frontend/types/analytics.ts`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Recharts 不选 D3**：Recharts API 简洁，TypeScript 支持好，社区活跃；D3 学习成本高、维护成本高，本项目非数据可视化专业团队。
- **选折线+条形组合不选纯表格**：Issue 要求图表而非表格，Recharts 的 `<LineChart>` / `<BarChart>` 已满足需求，无需额外图表库。
- **在组件内做数据转换而非在 hook 内**：图表需要的数据格式（`{ name: string, value: number }[]`）与 API 返回格式可能不同；转换逻辑放在组件内可读性更好，hook 只负责 fetch。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `recharts` | `^2.x` | 稳定版本，支持 React 18 和 TypeScript |

### 4.3 兼容性约束

- React 版本：组件需兼容 React 18（当前项目使用的版本）
- 图表必须响应 `period` prop 变化，自动重新请求数据
- 图表组件必须支持 SSR（服务端渲染），使用动态导入或 `useMounted` guard
- 所有组件导出 TypeScript 类型，外部无法推断类型的场景需提供 generic

### 4.4 已知坑

1. **Recharts 在 SSR 环境下报 `window is not defined`** → 规避：组件使用 `React.lazy()` 动态导入，或在 Chart 外层包 `import('recharts').then(...)`
2. **数据为空时图表显示 "No data" 或空白而非占位** → 规避：在每个组件的 `data` prop 为空数组时显示友好的空状态文案（非 Recharts 默认行为）
3. **周期选择器变化导致多个组件同时发请求导致并发风暴** → 规避：使用 `useAnalytics` hook 内部统一缓存（`useSWR` 或 `useQuery`），相同 `period` 的请求共享结果

---

## 5. 实现步骤（按顺序）

### Step 1: 搭建图表目录结构和公共类型

创建 `frontend/components/analytics/` 目录及公共类型文件，定义本板块所有组件共享的接口。

操作：
a) 确认 `frontend/components/analytics/` 目录存在（不存在则创建）
b) 创建 `frontend/types/analytics.ts`，定义以下接口：

```typescript
// frontend/types/analytics.ts
export type Period = '7d' | '30d' | '90d' | 'custom';

export interface ChartDataPoint {
  name: string;
  value: number;
}

export interface RevenueDataPoint extends ChartDataPoint {
  period: string;
}

export interface SalesDataPoint extends ChartDataPoint {
  team: string;
  rep?: string;
}

export interface AcquisitionDataPoint extends ChartDataPoint {
  type: 'new' | 'churned' | 'net';
}

export interface ChartResponse<T> {
  data: T[];
  updated_at: string;
}
```

c) 创建 `frontend/components/analytics/index.ts`：

```typescript
// frontend/components/analytics/index.ts
export { default as RevenueChart } from './RevenueChart';
export { default as SalesChart } from './SalesChart';
export { default as AcquisitionChart } from './AcquisitionChart';
export * from './types'; // 或从 frontend/types/analytics.ts 重导出
```

**完成判定**：`ls frontend/components/analytics/` 包含全部 4 个文件；`ruff check src/` 或 `tsc --noEmit frontend/types/analytics.ts` exit 0（无 TypeScript 错误）

---

### Step 2: 实现 `useAnalytics` 数据获取 Hook

创建统一的 hook，避免三个组件各自重复 fetch 逻辑和并发请求问题。

操作：
a) 创建 `frontend/hooks/useAnalytics.ts`：

```typescript
// frontend/hooks/useAnalytics.ts
import { useState, useEffect } from 'react';
import type { Period, RevenueDataPoint, SalesDataPoint, AcquisitionDataPoint } from '../types/analytics';

interface AnalyticsData {
  revenue: RevenueDataPoint[];
  sales: SalesDataPoint[];
  acquisition: AcquisitionDataPoint[];
}

interface UseAnalyticsResult {
  data: AnalyticsData | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useAnalytics(period: Period): UseAnalyticsResult {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 简单的内存缓存：key = period，value = AnalyticsData
  const cache = new Map<string, AnalyticsData>();

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 三个端点并行请求，由 #541 后端提供
      const [rev, sales, acq] = await Promise.all([
        fetch(`/api/analytics/revenue?period=${period}`).then(r => r.json()),
        fetch(`/api/analytics/sales?period=${period}`).then(r => r.json()),
        fetch(`/api/analytics/acquisition?period=${period}`).then(r => r.json()),
      ]);
      setData({ revenue: rev.data, sales: sales.data, acquisition: acq.data });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch analytics data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [period]);

  return { data, loading, error, refetch: fetchData };
}
```

**完成判定**：`ls frontend/hooks/useAnalytics.ts` 存在；`npx tsc --noEmit frontend/hooks/useAnalytics.ts` exit 0

---

### Step 3: 实现 `RevenueChart.tsx`

收入折线/面积图，支持多系列（收入、回款、毛利）切换。

操作：
a) 创建 `frontend/components/analytics/RevenueChart.tsx`：

```typescript
// frontend/components/analytics/RevenueChart.tsx
import React, { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, Legend,
} from 'recharts';
import type { RevenueDataPoint } from '../../types/analytics';

interface RevenueChartProps {
  data: RevenueDataPoint[];
  loading?: boolean;
}

const PERIOD_LABELS: Record<string, string> = {
  '7d': '最近7天',
  '30d': '最近30天',
  '90d': '最近90天',
};

export default function RevenueChart({ data, loading }: RevenueChartProps) {
  const chartData = useMemo(() => data.map(d => ({
    ...d,
    label: d.period,
  })), [data]);

  if (loading) return <div data-testid="revenue-chart-loading">加载中…</div>;

  return (
    <div data-testid="revenue-chart">
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis tickFormatter={(v) => `¥${v}`} />
          <Tooltip formatter={(value: number) => [`¥${value}`, '收入']} />
          <Legend />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#8884d8"
            fill="#8884d8"
            fillOpacity={0.3}
            name="收入"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**完成判定**：`ls frontend/components/analytics/RevenueChart.tsx` 存在；组件包含 `data-testid="revenue-chart"`；无 TypeScript 错误

---

### Step 4: 实现 `SalesChart.tsx`

销售团队/人员分组条形图，支持按团队或人员维度展示。

操作：
a) 创建 `frontend/components/analytics/SalesChart.tsx`：

```typescript
// frontend/components/analytics/SalesChart.tsx
import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LabelList,
} from 'recharts';
import type { SalesDataPoint } from '../../types/analytics';

interface SalesChartProps {
  data: SalesDataPoint[];
  loading?: boolean;
}

export default function SalesChart({ data, loading }: SalesChartProps) {
  const chartData = useMemo(() => {
    return [...data].sort((a, b) => b.value - a.value); // 从高到低排序
  }, [data]);

  if (loading) return <div data-testid="sales-chart-loading">加载中…</div>;

  return (
    <div data-testid="sales-chart">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="team" />
          <YAxis tickFormatter={(v) => `¥${v}`} />
          <Tooltip formatter={(value: number) => [`¥${value}`, '销售额']} />
          <Legend />
          <Bar dataKey="value" fill="#82ca9d" name="销售额">
            <LabelList dataKey="value" position="top" formatter={(v: number) => `¥${v}`} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**完成判定**：`ls frontend/components/analytics/SalesChart.tsx` 存在；组件包含 `data-testid="sales-chart"`；无 TypeScript 错误

---

### Step 5: 实现 `AcquisitionChart.tsx`

客户获取趋势折线图，显示新增/流失/净增三系列。

操作：
a) 创建 `frontend/components/analytics/AcquisitionChart.tsx`：

```typescript
// frontend/components/analytics/AcquisitionChart.tsx
import React, { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import type { AcquisitionDataPoint } from '../../types/analytics';

interface AcquisitionChartProps {
  data: AcquisitionDataPoint[];
  loading?: boolean;
}

const SERIES_COLORS: Record<string, string> = {
  new: '#8884d8',
  churned: '#ef4444',
  net: '#22c55e',
};

const SERIES_LABELS: Record<string, string> = {
  new: '新增客户',
  churned: '流失客户',
  net: '净增客户',
};

export default function AcquisitionChart({ data, loading }: AcquisitionChartProps) {
  const grouped = useMemo(() => {
    // 按 period 分组，将 { type, value } 转为 { period, new, churned, net }
    const map = new Map<string, Record<string, number>>();
    data.forEach(pt => {
      if (!map.has(pt.name)) map.set(pt.name, { name: pt.name } as Record<string, number>);
      map.get(pt.name)![pt.type] = pt.value;
    });
    return Array.from(map.values());
  }, [data]);

  const series = ['new', 'churned', 'net'] as const;

  if (loading) return <div data-testid="acquisition-chart-loading">加载中…</div>;

  return (
    <div data-testid="acquisition-chart">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={grouped} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          {series.map(s => (
            <Line
              key={s}
              type="monotone"
              dataKey={s}
              stroke={SERIES_COLORS[s]}
              name={SERIES_LABELS[s]}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**完成判定**：`ls frontend/components/analytics/AcquisitionChart.tsx` 存在；组件包含 `data-testid="acquisition-chart"`；无 TypeScript 错误

---

### Step 6: 编写三个组件的单元测试

使用 Vitest + React Testing Library（或其他项目已用的测试框架）。

操作：
a) 创建 `tests/unit/frontend/RevenueChart.test.tsx`：

```typescript
// tests/unit/frontend/RevenueChart.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import RevenueChart from '../../frontend/components/analytics/RevenueChart';
import type { RevenueDataPoint } from '../../frontend/types/analytics';

const mockData: RevenueDataPoint[] = [
  { name: '1月', value: 10000, period: '2025-01' },
  { name: '2月', value: 15000, period: '2025-02' },
  { name: '3月', value: 12000, period: '2025-03' },
];

describe('RevenueChart', () => {
  it('renders chart container', () => {
    render(<RevenueChart data={mockData} />);
    expect(screen.getByTestId('revenue-chart')).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<RevenueChart data={[]} loading />);
    expect(screen.getByText('加载中…')).toBeTruthy();
  });

  it('renders empty state when no data', () => {
    render(<RevenueChart data={[]} />);
    expect(screen.getByTestId('revenue-chart')).toBeTruthy();
  });
});
```

b) 创建 `tests/unit/frontend/SalesChart.test.tsx`，覆盖渲染、loading、空状态 3 个用例

c) 创建 `tests/unit/frontend/AcquisitionChart.test.tsx`，覆盖渲染、loading、空状态、多系列 4 个用例

**完成判定**：`npm test -- tests/unit/frontend/ --run` → ≥ 10 passed（RevenueChart 3 + SalesChart 3 + AcquisitionChart 4）

---

### Step 7: 在 Analytics Dashboard 页面集成三个图表组件

将三个图表接入 Dashboard 页面的周期选择器联动。

操作：
a) 编辑 `frontend/pages/dashboard/analytics.tsx`（或对应 Dashboard 文件），在返回的 JSX 中添加：

```typescript
import { RevenueChart, SalesChart, AcquisitionChart } from '../components/analytics';
import { useAnalytics } from '../hooks/useAnalytics';
import type { Period } from '../types/analytics';

// 假设页面已有 period state 和 selector
// const [period, setPeriod] = useState<Period>('30d');

const { data, loading, error } = useAnalytics(period);

return (
  <>
    {/* PeriodSelector 由其他板块提供，本板块假设其存在 */}
    <RevenueChart data={data?.revenue ?? []} loading={loading} />
    <SalesChart data={data?.sales ?? []} loading={loading} />
    <AcquisitionChart data={data?.acquisition ?? []} loading={loading} />
    {error && <div role="alert">{error}</div>}
  </>
);
```

b) 更新 `frontend/components/analytics/index.ts` 确保导出链路正确

**完成判定**：`npx tsc --noEmit` exit 0；`npm run build` exit 0（如项目有 build script）

---

## 6. 验收

- [ ] `ls frontend/components/analytics/` 包含 `RevenueChart.tsx`、`SalesChart.tsx`、`AcquisitionChart.tsx`、`index.ts`
- [ ] `ls frontend/types/analytics.ts` 存在并导出 `Period`、`ChartDataPoint` 等类型
- [ ] `ls frontend/hooks/useAnalytics.ts` 存在
- [ ] `npm run typecheck` → 0 errors（如项目有 typecheck script）
- [ ] `npm test -- tests/unit/frontend/ --run` → ≥ 10 passed
- [ ] `ruff check frontend/` → 0 errors（如项目对 frontend 有 lint 配置）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #541 后端 analytics API 未完成或格式不一致，导致图表无法渲染真实数据 | 中 | 中 | 用 mock 数据（`useAnalytics` hook 扩展 `mockData` 参数）绕过；图表组件自身逻辑不受影响 |
| PeriodSelector 组件由其他板块负责，本板块依赖其接口，接口不匹配导致联动失效 | 低 | 中 | 图表接收外部传入的 `period` prop，不依赖 selector 实现；独立测试通过后可安全集成 |
| Recharts SSR 兼容性导致部署到 Node 环境时报错 | 中 | 高 | 所有图表组件用 `React.lazy()` + `Suspense` 动态导入，SSR 时不执行 recharts 初始化代码 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/components/analytics/ frontend/hooks/useAnalytics.ts \
        frontend/types/analytics.ts tests/unit/frontend/
git commit -m "feat(analytics): add revenue, sales, and acquisition chart components"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add #542 Revenue/Sales/Acquisition charts" --body "Closes #542"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`frontend/components/` 下是否有其他图表/可视化组件可参考目录结构和模式
- 父 issue / 关联：#56（Analytics 模块父 issue），#541（analytics 数据层 API — 本板块依赖的前置板块）
- Recharts 文档：https://recharts.org/
