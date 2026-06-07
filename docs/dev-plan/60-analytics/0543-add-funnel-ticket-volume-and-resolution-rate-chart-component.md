# 漏斗·票据量·解决率图表组件 · 补充三个图表完善仪表盘

| 元数据 | 值 |
|---|---|
| Issue | #543 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1.5 工作日 |
| 依赖 | TBD - 待验证：`../50-automation/0542-add-analytics-dashboard-api-endpoints.md` — 请确认文件是否存在及正确路径 |
| 启用后赋能 | [父板块：CRM Analytics Dashboard #56](../README.md#父板块) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 仪表盘当前缺少转化漏斗、票据量和解决率三个关键指标的图表视图。业务团队无法直观看到销售漏斗转化效率、工单负载趋势和客服响应质量。父 issue #56 规划了 6 张图表，本组件（#543）负责其中 3 张，依赖 #542 提供的后端 API 接口。

### 1.2 做完后

- **用户视角**：管理员在仪表盘首页可看到转化漏斗横向条形图（阶段转化率一览）、票据量面积图（时间趋势）、解决率折线图（SLA 达成趋势）；切换时间段时三张图表同步刷新数据。
- **开发者视角**：新增 `FunnelChart.tsx`、`TicketVolumeChart.tsx`、`ResolutionRateChart.tsx` 三个可复用 React 组件；组件通过已完成的 #542 API 端点获取数据；遵循现有图表组件的 Props 接口规范。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 API（由 #542 负责）
- [ ] 不修改现有 3 张图表（#543 是独立新增 3 张）
- [ ] 不做图表数据导出（CSV/PDF）功能
- [ ] 不做 Webhook / 通知规则触发逻辑

### 1.4 关键 KPI

- [三张新图表在 `http://localhost:3000/dashboard` 均可渲染，数据非空]
- [`npm run lint -- frontend/components/analytics/` → 0 errors]
- [Period selector 切换（如近 7 天 / 近 30 天 / 本季度）后三张图表同步重新请求并渲染]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`frontend/components/analytics/` — 现有图表组件目录，应包含 #542 已实现的 3 张基础图表（如 PieChart.tsx / BarChart.tsx / LineChart.tsx）。请确认目录结构和已有组件的 Props 接口定义。

主入口：TBD - 待验证：`frontend/pages/dashboard.tsx` L? — 仪表盘页面，导入并渲染各图表组件的位置

### 2.2 涉及文件清单

- 要改：
  - `frontend/components/analytics/FunnelChart.tsx` — 新增转化漏斗横向条形图
  - `frontend/components/analytics/TicketVolumeChart.tsx` — 新增票据量面积图
  - `frontend/components/analytics/ResolutionRateChart.tsx` — 新增解决率折线图
  - `frontend/pages/dashboard.tsx` — 挂载三张新图表并连接 period selector
  - `frontend/hooks/useAnalytics.ts` — 如需统一数据 hook
  - `frontend/__tests__/analytics/charts.test.tsx` — 新增组件单元测试
- 要建：
  - `frontend/components/analytics/FunnelChart.tsx` — 漏斗图组件
  - `frontend/components/analytics/TicketVolumeChart.tsx` — 面积图组件
  - `frontend/components/analytics/ResolutionRateChart.tsx` — 折线图组件

### 2.3 缺什么

- [ ] 三张图表组件：无 FunnelChart / TicketVolumeChart / ResolutionRateChart
- [ ] 仪表盘页面未挂载这三张图表
- [ ] 图表未与 period selector 联动
- [ ] 无图表组件的单元测试覆盖
- [ ] 无 E2E 测试（可选）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/components/analytics/FunnelChart.tsx` | 转化漏斗横向条形图，数据源为 #542 funnel API |
| `frontend/components/analytics/TicketVolumeChart.tsx` | 票据量面积图，数据源为 #542 ticket-volume API |
| `frontend/components/analytics/ResolutionRateChart.tsx` | 票据解决率折线图，数据源为 #542 resolution-rate API |
| `frontend/__tests__/analytics/FunnelChart.test.tsx` | FunnelChart 组件单元测试 |
| `frontend/__tests__/analytics/TicketVolumeChart.test.tsx` | TicketVolumeChart 组件单元测试 |
| `frontend/__tests__/analytics/ResolutionRateChart.test.tsx` | ResolutionRateChart 组件单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `frontend/pages/dashboard.tsx` | 导入并渲染三张新图表，放在现有图表右侧或下方 |
| `frontend/hooks/useAnalytics.ts` | 新增 `useFunnelData`、`useTicketVolumeData`、`useResolutionRateData` 三个 hook（或扩展现有 hook） |
| `frontend/components/analytics/PeriodSelector.tsx` | 如需将 period selector 状态提升至 dashboard 页面以驱动所有图表 |

### 3.3 新增能力

- **React 组件**：`FunnelChart` — props: `{ tenantId: number, period: Period }` → renders horizontal funnel bars
- **React 组件**：`TicketVolumeChart` — props: `{ tenantId: number, period: Period }` → renders area chart
- **React 组件**：`ResolutionRateChart` — props: `{ tenantId: number, period: Period }` → renders line chart
- **API 数据 hook**：`useFunnelData(period)` / `useTicketVolumeData(period)` / `useResolutionRateData(period)` — 调用 #542 接口，返回 typed 响应
- **Dashboard 集成**：三张图表在仪表盘页面可响应 period selector 变化重新请求数据

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Recharts 不选其他图表库**：本仓库前端已使用 Recharts（#542 应沿用此选择），保持视觉一致性和技术栈统一
- **选横向条形图（BarChart layout="vertical"）不选 SVG 自绘**：Recharts 原生支持，数据模型简单，无需手写 SVG
- **Funnel 图选 Recharts FunnelChart 不自绘**：复用 Recharts FunnelComposed，数据模型与漏斗阶段语义一致
- **面积图选 AreaChart + 渐变填充**：Recharts AreaChart 原生支持，SLA 趋势一目了然
- **Period selector 联动方案**：状态提升至 dashboard 页面，通过 props 传递 period 给所有图表组件，避免 prop drilling 可考虑 React Context

### 4.2 版本约束

<!-- 无新增 npm 依赖，Recharts 已在 #542 中引入 -->

### 4.3 兼容性约束

- React hooks 规范：组件内只调用一次 `useEffect` / `useQuery` 请求数据，避免重复请求
- TypeScript 类型安全：所有 API 响应须有对应的 `interface` / `type` 定义，不使用 `any`
- 多租户：API 请求须携带 `tenant_id` 参数（由 AuthContext 或 props 传入）
- 响应式：所有图表须接受 `width` prop 或使用容器宽度自适应（Recharts `ResponsiveContainer`）
- 图表色板：使用 `frontend/theme/analytics.ts` 中定义的颜色变量，与现有图表保持一致

### 4.4 已知坑

1. **Recharts FunnelChart 不支持响应式宽度** → 规避：外层用 `<ResponsiveContainer width="100%" height={300}>`
2. **Recharts AreaChart 渐变定义需 SVG `<defs>`** → 规避：每个 AreaChart 独立定义 `<linearGradient>`，不要复用同一 id
3. **API 数据加载时序** → 规避：组件内 `useEffect` 监听 period 变化，依赖数组包含 `[period]`；使用 `isLoading` / `error` 状态渲染骨架屏或错误提示，不直接展示 undefined
4. **Period selector 与图表解耦** → 规避：若多个组件独立调用 `useAnalytics`，确保 debounce（300ms）防止并发请求风暴

---

## 5. 实现步骤（按顺序）

### Step 1: 新增 analytics 数据类型定义

在 `frontend/types/analytics.ts` 中补充三张图表的 API 响应类型定义（与 #542 接口字段对应）。参考 Recharts 类型约定定义 `FunnelStage[]`、`TicketVolumePoint[]`、`ResolutionRatePoint[]`。

操作：
- a) 检查 `frontend/types/analytics.ts` 是否存在；如不存在则在 `frontend/types/` 下创建
- b) 新增 `FunnelStage`、`TicketVolumePoint`、`ResolutionRatePoint` interface
- c) 导出汇总类型 `AnalyticsChartData`

```typescript
// frontend/types/analytics.ts
export interface FunnelStage {
  stage: string;
  count: number;
  conversionRate: number; // 0-100
}

export interface TicketVolumePoint {
  date: string; // ISO date
  opened: number;
  closed: number;
}

export interface ResolutionRatePoint {
  date: string;
  resolvedCount: number;
  totalCount: number;
  rate: number; // 0-100
}
```

**完成判定**：`npx tsc --noEmit frontend/types/analytics.ts` → 0 errors

### Step 2: 新增 analytics 数据 hook

在 `frontend/hooks/useAnalytics.ts` 中新增三个数据获取 hook，调用 #542 提供的 API 端点。统一错误处理和 loading 状态。

操作：
- a) 确认 `useAnalytics.ts` 存在位置；如需新建在 `frontend/hooks/`
- b) 新增 `useFunnelData(period: Period): { data, isLoading, error }`
- c) 新增 `useTicketVolumeData(period: Period): { data, isLoading, error }`
- d) 新增 `useResolutionRateData(period: Period): { data, isLoading, error }`
- e) 使用 `#542` 中的 API 端点路径（形如 `/api/analytics/funnel` 等）；若路径待确认，写 `TBD - 待验证：#542 API 端点路径`

示例代码：

```typescript
// frontend/hooks/useAnalytics.ts
export function useFunnelData(period: Period) {
  const { tenantId } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ['funnel', tenantId, period],
    queryFn: () => apiClient.get<FunnelStage[]>(`/api/analytics/funnel`, {
      params: { tenantId, period },
    }),
    staleTime: 5 * 60 * 1000, // 5 min
  });
  return { data: data ?? [], isLoading, error };
}
```

**完成判定**：`npx tsc --noEmit frontend/hooks/useAnalytics.ts` → 0 errors

### Step 3: 新增 FunnelChart 组件

创建 `frontend/components/analytics/FunnelChart.tsx`，使用 Recharts `FunnelChart` + `Funnel` + `LabelList`，展示转化漏斗横向阶段及转化率。

操作：
- a) 创建文件 `frontend/components/analytics/FunnelChart.tsx`
- b) Props 接口包含 `period: Period`，内部调用 `useFunnelData`
- c) 使用 `<ResponsiveContainer>` 包裹 `<FunnelChart>`
- d) 每个漏斗阶段显示 count 和 conversionRate label
- e) 从 `frontend/theme/analytics.ts` 引入颜色变量

示例代码：

```typescript
// frontend/components/analytics/FunnelChart.tsx
import {
  FunnelChart, Funnel, Bar, LabelList, ResponsiveContainer, XAxis, YAxis, Tooltip,
} from 'recharts';
import { useFunnelData } from '../../hooks/useAnalytics';
import { FUNNEL_COLORS } from '../../theme/analytics';

interface FunnelChartProps {
  period: Period;
}

export function FunnelChart({ period }: FunnelChartProps) {
  const { data, isLoading, error } = useFunnelData(period);

  if (isLoading) return <Skeleton height={300} />;
  if (error) return <ErrorMessage message={String(error)} />;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <FunnelChart>
        <Tooltip formatter={(value, name) => [value, name]} />
        <Funnel
          dataKey="count"
          data={data}
          isAnimationActive
        >
          <LabelList position="right" fill="#333" formatter={(val: number, entry: any) => `${val} (${entry.conversionRate}%)`} />
        </Funnel>
      </FunnelChart>
    </ResponsiveContainer>
  );
}
```

**完成判定**：`npx eslint frontend/components/analytics/FunnelChart.tsx` → 0 errors

### Step 4: 新增 TicketVolumeChart 组件

创建 `frontend/components/analytics/TicketVolumeChart.tsx`，使用 Recharts `AreaChart` + `Area`，展示每日开单/关单量堆叠面积图。

操作：
- a) 创建文件 `frontend/components/analytics/TicketVolumeChart.tsx`
- b) Props 接口包含 `period: Period`
- c) 使用两张 Area（`opened` 和 `closed`），填充渐变区分开单/关单
- d) X 轴格式化日期，Y 轴为数量
- e) 添加 Tooltip 显示具体数值

示例代码：

```typescript
// frontend/components/analytics/TicketVolumeChart.tsx
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { useTicketVolumeData } from '../../hooks/useAnalytics';

export function TicketVolumeChart({ period }: { period: Period }) {
  const { data, isLoading, error } = useTicketVolumeData(period);

  if (isLoading) return <Skeleton height={300} />;
  if (error) return <ErrorMessage message={String(error)} />;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorOpened" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorClosed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10B981" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" />
        <YAxis />
        <CartesianGrid strokeDasharray="3 3" />
        <Tooltip />
        <Legend />
        <Area type="monotone" dataKey="opened" stroke="#3B82F6" fillOpacity={1} fill="url(#colorOpened)" name="开单" />
        <Area type="monotone" dataKey="closed" stroke="#10B981" fillOpacity={1} fill="url(#colorClosed)" name="关单" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

**完成判定**：`npx eslint frontend/components/analytics/TicketVolumeChart.tsx` → 0 errors

### Step 5: 新增 ResolutionRateChart 组件

创建 `frontend/components/analytics/ResolutionRateChart.tsx`，使用 Recharts `LineChart` + `Line`，展示每日解决率趋势。

操作：
- a) 创建文件 `frontend/components/analytics/ResolutionRateChart.tsx`
- b) Props 接口包含 `period: Period`
- c) X 轴为日期，Y 轴为解决率百分比（0-100）
- d) Line 带 `dot={false}` + 粗细 `strokeWidth={2}` 保证美观
- e) 添加参考线（ReferenceLine）在 80% SLA 阈值处

示例代码：

```typescript
// frontend/components/analytics/ResolutionRateChart.tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { useResolutionRateData } from '../../hooks/useAnalytics';

export function ResolutionRateChart({ period }: { period: Period }) {
  const { data, isLoading, error } = useResolutionRateData(period);

  if (isLoading) return <Skeleton height={300} />;
  if (error) return <ErrorMessage message={String(error)} />;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[0, 100]} unit="%" />
        <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, '解决率']} />
        <Legend />
        <ReferenceLine y={80} stroke="#F59E0B" strokeDasharray="3 3" label="SLA 80%" />
        <Line
          type="monotone"
          dataKey="rate"
          stroke="#8B5CF6"
          strokeWidth={2}
          dot={false}
          name="解决率"
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

**完成判定**：`npx eslint frontend/components/analytics/ResolutionRateChart.tsx` → 0 errors

### Step 6: 仪表盘集成

将三张新图表挂载到 `frontend/pages/dashboard.tsx`，确认与 Period Selector 联动。

操作：
- a) 在 `dashboard.tsx` 确认 Period Selector 组件位置和状态提升方式
- b) 从 `../../components/analytics/` 导入三张新图表
- c) 将图表放入仪表盘 Grid 布局（与现有 3 张图表并列或上下排列）
- d) 将 `period` state 作为 prop 传入每张图表
- e) 确保 dashboard.tsx 中 `tenantId` 可通过 `useAuth()` 获取并传入

完成判定：`npx eslint frontend/pages/dashboard.tsx` → 0 errors

### Step 7: 新增单元测试

为三张图表组件各写单元测试（Vitest / Jest + React Testing Library），覆盖：加载中状态、错误状态、正常渲染、无数据空状态。

操作：
- a) 创建 `frontend/__tests__/analytics/FunnelChart.test.tsx`
- b) 创建 `frontend/__tests__/analytics/TicketVolumeChart.test.tsx`
- c) 创建 `frontend/__tests__/analytics/ResolutionRateChart.test.tsx`
- d) Mock `useFunnelData` / `useTicketVolumeData` / `useResolutionRateData` 返回固定数据
- e) 断言：isLoading 时显示 Skeleton；error 时显示 ErrorMessage；data 正常时渲染对应图表元素

示例测试片段：

```typescript
// frontend/__tests__/analytics/FunnelChart.test.tsx
import { render, screen } from '@testing-library/react';
import { FunnelChart } from '../../components/analytics/FunnelChart';

vi.mock('../../hooks/useAnalytics', () => ({
  useFunnelData: vi.fn(),
}));

describe('FunnelChart', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(useFunnelData).mockReturnValue({ data: [], isLoading: true, error: null });
    render(<FunnelChart period="last_30_days" />);
    expect(screen.getByTestId('skeleton')).toBeInTheDocument();
  });

  it('renders funnel bars when data is loaded', () => {
    vi.mocked(useFunnelData).mockReturnValue({
      data: [{ stage: 'Lead', count: 100, conversionRate: 100 }],
      isLoading: false,
      error: null,
    });
    render(<FunnelChart period="last_30_days" />);
    expect(screen.getByText('Lead')).toBeInTheDocument();
  });
});
```

**完成判定**：`npm test -- --run frontend/__tests__/analytics/` → 6 passed（每个组件 2 个测试用例）

---

## 6. 验收

- [ ] `npx eslint frontend/components/analytics/FunnelChart.tsx frontend/components/analytics/TicketVolumeChart.tsx frontend/components/analytics/ResolutionRateChart.tsx` → 0 errors
- [ ] `npx tsc --noEmit frontend/components/analytics/ frontend/hooks/useAnalytics.ts frontend/types/analytics.ts` → 0 errors
- [ ] `npm test -- --run frontend/__tests__/analytics/` → 6 passed
- [ ] `npm run build`（前端构建）→ exit 0，无类型错误
- [ ] 启动前端 dev server，手动验证：切换 period selector 后三张图表均重新请求并渲染（检查 Network 面板）
- [ ] 验证无 console.error（React ErrorBoundary 外泄漏的请求错误）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #542 API 端点路径/字段名与本组件预期不符，导致图表无数据 | 中 | 中 | 本组件使用 mock 数据（msw 或 localStorage）临时绕过，#543 PR 可先合并；待 #542 修正后图表自动生效 |
| Period selector 状态提升改动 dashboard.tsx 过广，引发其他图表回归 | 低 | 中 | 通过 React Context（`AnalyticsPeriodContext`）而非 props drilling 传递 period；降级时移除 Context 恢复 props |
| Recharts FunnelChart 版本不兼容导致 SSR 水合错误 | 低 | 低 | 使用 `dynamic(() => import(...), { ssr: false })` 延迟导入三张图表组件 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/components/analytics/FunnelChart.tsx \
        frontend/components/analytics/TicketVolumeChart.tsx \
        frontend/components/analytics/ResolutionRateChart.tsx \
        frontend/hooks/useAnalytics.ts \
        frontend/types/analytics.ts \
        frontend/pages/dashboard.tsx \
        frontend/__tests__/analytics/
git commit -m "feat(analytics): add funnel, ticket volume and resolution rate chart components"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add charts #543" --body "Closes #543

## Summary
- Add FunnelChart (conversion funnel horizontal bar)
- Add TicketVolumeChart (stacked area chart)
- Add ResolutionRateChart (line chart with SLA reference line)
- Integrate three charts into dashboard with period selector support

## Test plan
- [ ] npm test -- --run frontend/__tests__/analytics/ → 6 passed
- [ ] npx eslint frontend/components/analytics/*.tsx → 0 errors
- [ ] Manual: period selector updates all 6 charts on dashboard"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`frontend/components/analytics/` — 查看 #542 已实现的 PieChart / BarChart / LineChart 获取组件结构和 Props 规范
- Recharts 官方文档：FunnelChart — https://recharts.org/en-US/api/FunnelChart；AreaChart — https://recharts.org/en-US/api/AreaChart；LineChart — https://recharts.org/en-US/api/LineChart
- 父 issue / 关联：#56（CRM Analytics Dashboard 父板块）、#542（analytics-dashboard-api-endpoints，依赖的 API 端点）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
