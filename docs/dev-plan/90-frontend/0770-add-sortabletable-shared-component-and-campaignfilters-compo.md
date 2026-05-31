# 可排序表格与筛选组件 · 添加 SortableTable 和 CampaignFilters

| 元数据 | 值 |
|---|---|
| Issue | #770 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无（#769 为前置但不影响本板块实现方式） |
| 启用后赋能 | [#772](./0772-add-campaigntable-component-and-campaignlist-page.md) — CampaignTable 需要 SortableTable 和 CampaignFilters 作为构建块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #531 规划了 CampaignTable 页面，该页面需要两个可复用构建块：(1) 一个通用排序表格组件 SortableTable，可以对任意数据类型渲染可点击排序列；(2) 一个筛选控件 CampaignFilters，提供状态过滤和排序方向控制。目前这两个组件均不存在，直接导致下游 CampaignTable 无法实现。

### 1.2 做完后

- **用户视角**：无直接用户可见变化 — 这是底层 UI 组件，为后续页面提供基础能力。
- **开发者视角**：`SortableTable` 可在任何页面通过 `Column<T>` 配置渲染排序表格，无需重复实现列头点击逻辑；`CampaignFilters` 提供 6 个状态选项的下拉框以及升序/降序切换控件，直接嵌入 CampaignTable。

### 1.3 不做什么（剔除）

- [ ] 不实现 CampaignTable 本身 — 该组件由 #772 处理。
- [ ] 不实现后端 API 或数据库变更 — 本板块纯前端组件。
- [ ] 不实现多选行、虚拟滚动、远程分页等高级表格功能 — 留待后续专项 issue。

### 1.4 关键 KPI

- SortableTable 组件可通过 `Column<T>` 泛型配置渲染任意数据类型的列，并在列头点击时触发 `onSort` 回调。
- CampaignFilters 渲染全部 6 个状态选项（All / Draft / Pending Review / Approved / Rejected / Archived）。
- 组件有对应 TypeScript 类型定义，无 `any` 类型泄露。
- `ruff check src/ui/components/` → 0 errors。

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。本板块为 greenfield，创建 `src/ui/components/shared/SortableTable.tsx` 和 `src/ui/components/campaign/CampaignFilters.tsx` 两个新文件。

### 2.2 涉及文件清单

- 要建：
  - `src/ui/components/shared/SortableTable.tsx` — 通用排序表格组件
  - `src/ui/components/campaign/CampaignFilters.tsx` — 活动筛选控件
  - `src/ui/types/sortable.ts` — SortableTable 相关的共享类型定义（Column<T>、SortDirection 等）
  - `tests/unit/test_sortable_table.ts` — SortableTable 单元测试
  - `tests/unit/test_campaign_filters.ts` — CampaignFilters 单元测试

### 2.3 缺什么

- [ ] 通用排序表格组件 — SortableTable.tsx，需支持泛型 Column 配置和 onSort 回调。
- [ ] 排序方向类型定义 — SortDirection（asc | desc）及其切换逻辑。
- [ ] 列配置类型 — Column<T> 接口，包含 key、label、sortable 等属性。
- [ ] CampaignFilters 组件 — 状态选择下拉框（6 选项）+ 排序字段/方向控件。
- [ ] Campaign 状态枚举 — 与后端 Campaign 模型对齐的 5 种业务状态类型。

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/ui/types/sortable.ts` | SortDirection、Column<T> 等共享类型定义 |
| `src/ui/components/shared/SortableTable.tsx` | 通用排序表格，列头可点击排序 |
| `src/ui/components/campaign/CampaignFilters.tsx` | 活动筛选控件：状态下拉 + 排序方向 |
| `tests/unit/test_sortable_table.ts` | SortableTable 渲染和排序回调测试 |
| `tests/unit/test_campaign_filters.ts` | CampaignFilters 状态选项渲染测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/ui/components/shared/index.ts` | 新增 SortableTable 导出 |
| `src/ui/components/campaign/index.ts` | 新增 CampaignFilters 导出 |

### 3.3 新增能力

- **Type**：`SortDirection`（`asc` | `desc`）、`Column<T>` 泛型接口、`SortState` 接口
- **React 组件**：`SortableTable<T>` — 接收 `columns: Column<T>[]`、`data: T[]`、`onSort: (key: string, direction: SortDirection) => void`
- **React 组件**：`CampaignFilters` — 接收 `status`、`sortField`、`sortDirection`、`onChange` props，渲染状态选择和排序控件
- **枚举**：`CampaignStatus`（Draft / PendingReview / Approved / Rejected / Archived）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **受控组件而非非受控**：`SortableTable` 接收 `onSort` 回调而非自己管理排序状态，这样父组件（CampaignTable）统一控制排序状态，组件职责单一，易于测试。
- **Column<T> 泛型接口**：`Column<T>` 为泛型接口，允许任意数据类型使用同一排序表格，不限定为 Campaign 类型。
- **SortDirection 为联合类型而非布尔值**：使用 `asc | desc` 而非 `isDesc: boolean`，避免调用方做布尔转换。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react` | `^18.x` | 项目现有依赖 |
| `@testing-library/react` | `^14.x` | 项目现有测试工具 |

### 4.3 兼容性约束

- 所有 React 组件使用 TypeScript，props 有完整类型定义，禁止 `any`。
- `SortableTable` 为纯展示组件，无副作用，不使用 `useEffect` / `useContext`。
- 排序回调 `onSort(key, direction)` 的 `key` 为 `string`，兼容任意对象属性名。
- CampaignFilters 的状态选项列表从常量导出，不硬编码在组件内部。

### 4.4 已知坑

1. **TypeScript 泛型与 JSX 混用时 children 类型冲突** → 规避：SortableTable 不使用 children prop，直接用 `data` prop 渲染行。
2. **列头排序图标（▲/▼）在首次点击时视觉状态不一致** → 规避：初始 direction 为 `undefined`，不显示排序图标；点击后显示当前方向的图标。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建排序相关共享类型

在 `src/ui/types/sortable.ts` 中定义 `SortDirection` 联合类型、`Column<T>` 泛型接口、`SortState` 接口。类型定义与具体 UI 无关，可独立验证。

```typescript
export type SortDirection = 'asc' | 'desc';

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (value: unknown, row: T) => React.ReactNode;
}

export interface SortState {
  key: string;
  direction: SortDirection;
}
```

操作：
- a) 创建 `src/ui/types/` 目录（如不存在）
- b) 新建 `src/ui/types/sortable.ts`，写入上述类型定义
- c) 如存在 `src/ui/types/index.ts`，追加导出

**完成判定**：`ruff check src/ui/types/sortable.ts` → 0 errors / `npx tsc --noEmit src/ui/types/sortable.ts` → 0 errors

### Step 2: 创建 CampaignStatus 枚举

在 `src/ui/types/` 下新建 `campaign.ts`，定义 5 种业务状态枚举及 `CAMPAIGN_STATUS_OPTIONS` 常量数组（包含 All 选项共 6 项）。

操作：
- a) 新建 `src/ui/types/campaign.ts`
- b) 枚举值与后端 `campaign_status` 枚举对齐（如后端用字符串则用字符串，用整型则对齐整型）
- c) 导出 `CAMPAIGN_STATUS_OPTIONS` 数组供 CampaignFilters 使用

**完成判定**：`npx tsc --noEmit src/ui/types/campaign.ts` → 0 errors

### Step 3: 实现 SortableTable 组件

创建 `src/ui/components/shared/SortableTable.tsx`，组件签名：

```typescript
interface SortableTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onSort: (key: string, direction: SortDirection) => void;
  sortState?: SortState;
}
```

- 表格结构：`<table>` + `<thead>`（列头 `<th>` 可点击） + `<tbody>`
- 列头：点击时调用 `onSort`，如果 `column.sortable !== false` 则显示排序图标
- 排序图标：direction 为 `asc` 显示 ▲，direction 为 `desc` 显示 ▼，无 direction 则不显示
- 行渲染：`columns.map` 遍历，每列调用 `column.render ?? ((val) => String(val))`

操作：
- a) 创建 `src/ui/components/shared/SortableTable.tsx`
- b) 实现上述逻辑，确保泛型约束
- c) 更新 `src/ui/components/shared/index.ts` 导出该组件

**完成判定**：`npx tsc --noEmit src/ui/components/shared/SortableTable.tsx` → 0 errors / 文件存在

### Step 4: 实现 CampaignFilters 组件

创建 `src/ui/components/campaign/CampaignFilters.tsx`，组件 props：

```typescript
interface CampaignFiltersProps {
  status: string;
  sortField: string;
  sortDirection: SortDirection;
  onChange: (updates: Partial<{status: string; sortField: string; sortDirection: SortDirection}>) => void;
}
```

- 状态下拉框：从 `CAMPAIGN_STATUS_OPTIONS` 渲染 6 个 `<option>`，value 对应枚举值
- 排序字段下拉框：提供 `name` 和 `created_at` 两个可排序字段选项
- 排序方向切换：两个 `<button>` 或 `<select>`，切换 asc/desc
- onChange 调用：`onChange({ status: e.target.value })` 等模式

操作：
- a) 创建 `src/ui/components/campaign/CampaignFilters.tsx`
- b) 从 `../../types/campaign` 导入枚举和常量
- c) 更新 `src/ui/components/campaign/index.ts` 导出该组件

**完成判定**：`npx tsc --noEmit src/ui/components/campaign/CampaignFilters.tsx` → 0 errors / 文件存在

### Step 5: 编写 SortableTable 单元测试

创建 `tests/unit/test_sortable_table.ts`（Vitest + Testing Library）：

- 渲染测试：给定 columns 和 data，表格正确显示表头和数据行
- 排序回调测试：点击 `<th>` 触发 `onSort`，验证 key 和 direction 参数
- 无排序配置时：某列 `sortable: false` 时点击不触发回调
- 初始状态：sortState 为 undefined 时列头无排序图标

操作：
- a) 创建 `tests/unit/test_sortable_table.ts`
- b) 运行 `PYTHONPATH=src pytest tests/unit/...`（如有 JS 测试命令则替换，下游验收中给出实际命令）

**完成判定**：`npm test tests/unit/test_sortable_table.ts` → 全 passed / 文件存在

### Step 6: 编写 CampaignFilters 单元测试

创建 `tests/unit/test_campaign_filters.ts`：

- 状态选项渲染测试：验证 6 个 `<option>` 存在，value 正确
- onChange 调用测试：选择不同状态时调用 `onChange` 并传入正确值
- 排序方向切换测试：验证 sortDirection 变化时 UI 更新

操作：
- a) 创建 `tests/unit/test_campaign_filters.ts`
- b) 运行测试

**完成判定**：`npm test tests/unit/test_campaign_filters.ts` → 全 passed / 文件存在

### Step 7: Lint 全部新文件

对所有新增的 `.tsx` 和 `.ts` 文件运行 lint 和类型检查。

操作：
- a) `ruff check src/ui/types/sortable.ts src/ui/types/campaign.ts`
- b) `ruff check src/ui/components/shared/SortableTable.tsx src/ui/components/campaign/CampaignFilters.tsx`
- c) `npx tsc --noEmit` 对整个 `src/ui/` 目录（如项目配置支持）

**完成判定**：`ruff check src/ui/` → 0 errors / `npx tsc --noEmit` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/ui/types/sortable.ts src/ui/types/campaign.ts src/ui/components/shared/SortableTable.tsx src/ui/components/campaign/CampaignFilters.tsx` → 0 errors
- [ ] `npx tsc --noEmit src/ui/types/sortable.ts src/ui/types/campaign.ts src/ui/components/shared/SortableTable.tsx src/ui/components/campaign/CampaignFilters.tsx` → 0 errors（无 any 类型泄露）
- [ ] `npm test tests/unit/test_sortable_table.ts` → 全 passed
- [ ] `npm test tests/unit/test_campaign_filters.ts` → 全 passed
- [ ] SortableTable 导出存在于 `src/ui/components/shared/index.ts`，CampaignFilters 导出存在于 `src/ui/components/campaign/index.ts`
- [ ] 手动验证（通过代码审查）：`SortableTable<Campaign>` 接受 `Column<Campaign>[]`，点击列头时 onSort 被调用且传入正确的 key 和 direction；CampaignFilters 渲染 All / Draft / Pending Review / Approved / Rejected / Archived 六个选项

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 后端 CampaignStatus 枚举值与前端不一致 | 低 | 中 | 前端使用字符串常量如 `DRAFT`，后端对齐后通过 #772 集成测试发现并修复 |
| SortableTable 的泛型约束过于严格导致后续无法扩展（如需要嵌套列） | 低 | 中 | SortableTable 只处理扁平行数据，嵌套列场景在 #772 或后续专项 issue 中单独处理 |
| CampaignFilters 的 onChange 接口与父组件（CampaignTable）期望不一致 | 中 | 中 | 在 #772 实现 CampaignTable 时如发现接口不匹配，在此板块补充调整接口定义 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/types/sortable.ts src/ui/types/campaign.ts src/ui/components/shared/SortableTable.tsx src/ui/components/shared/index.ts src/ui/components/campaign/CampaignFilters.tsx src/ui/components/campaign/index.ts tests/unit/test_sortable_table.ts tests/unit/test_campaign_filters.ts
git commit -m "feat(ui): add SortableTable and CampaignFilters components"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#770): add SortableTable and CampaignFilters" --body "Closes #770"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/ui/components/shared/` 目录下是否已有类似表格组件（如 DataTable、PaginatedTable 等）可参照其目录结构和测试模式
- 第三方文档：[React TypeScript Generics in Component Props](https://react.dev/learn/typescript)、[Vitest Testing Library 文档](https://testing-library.com/docs/react-testing-library/intro/)
- 父 issue / 关联：#531（父：CampaignTable 完整实现）、#769（依赖：前期 UI 组件）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
