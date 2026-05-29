# 0564 · Filter panel for customers page

| 元数据 | 值 |
|---|---|
| Issue | #564 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0563](./0563-add-customer-status-industry-lead-tier-columns.md) |
| 启用后赋能 | [0557](./0557-customer-list-page-with-search-pagination.md)（客户列表完整过滤能力） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The `/customers` page currently fetches rows but offers no way to narrow results by customer classification fields. Status, industry, and lead tier are stored on each customer record, and the last-activity timestamp exists but is unused as a filter axis. Without a filter panel, users managing large CRM datasets must scroll or search by name only — slow and error-prone.

### 1.2 做完后

- **用户视角**: On the `/customers` page a collapsible filter sidebar appears on the left (or as a top drawer on mobile). Dropdowns for Status, Industry, and Lead Tier, plus a date-range picker for Last Activity, let users narrow the visible customer rows instantly. A "Clear all" button resets all filters at once.
- **开发者视角**: A reusable `FilterPanel` component is added to `src/components/` with typed props for each filter axis. The customer page integrates the panel and manages filter state locally (useState). Service and router are unchanged — this is pure client-side filtering against already-fetched rows.

### 1.3 不做什么（剔除）

- [ ] Backend search or server-side filter query parameters — this is client-side only.
- [ ] Multi-select dropdowns beyond what the native `<select>` or a lightweight third-party library supports without new dep.
- [ ] Persisting filter state to localStorage or URL params.
- [ ] Exporting filtered rows to CSV.
- [ ] Any changes to `CustomerService`, ORM models, or alembic migrations — no schema work here.

### 1.4 关键 KPI

- Filter panel renders on `/customers` page in ≤ 500 ms after page load.
- Selecting a value in any filter control narrows displayed rows within 100 ms.
- "Clear all" resets all filter controls to their default/unselected state and restores all rows.
- `PYTHONPATH=src pytest tests/unit/test_filter_panel.py -v` → all passed (if test file exists; otherwise no regression in existing tests).

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD — 待验证：`src/pages/customers/` 或 `src/app/customers/page.tsx` 是否已建；`src/components/` 目录是否存在。客户数据通过 API `GET /customers` 获取，字段包括 `status`, `industry`, `lead_tier`, `last_activity_at`。

### 2.2 涉及文件清单

- 要改：
  - `src/pages/customers/` — 添加 FilterPanel 集成 + filter state
  - `src/components/` — 新增 FilterPanel 组件
- 要建：
  - `src/components/FilterPanel.tsx` — 可折叠过滤面板（status / industry / lead tier 下拉 + 日期范围）
  - `src/components/FilterPanel.css`（或 Tailwind class 方案）— 样式
  - `tests/unit/test_filter_panel.ts` — 组件单元测试

### 2.3 缺什么

- [ ] No FilterPanel component exists in the repo.
- [ ] Customer page has no filter state management.
- [ ] Dropdown options for `status`, `industry`, `lead_tier` are not enumerated in the frontend (enum values must be sourced from the API or hardcoded constants).
- [ ] Date-range picker component is not present.
- [ ] "Clear all / reset" button / interaction is not designed or implemented.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/components/FilterPanel.tsx` | 可折叠过滤面板：status / industry / lead tier 下拉 + last activity 日期范围 |
| `src/components/FilterPanel.css` | FilterPanel 样式（Tailwind class 或 CSS 模块） |
| `tests/unit/test_filter_panel.ts` | FilterPanel 组件单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/pages/customers/` | 引入 FilterPanel，管理 filter state (useState)，在表格渲染前过滤 rows |
| `src/components/` | 如需通用 DateRangePicker 子组件，在此新建 |

### 3.3 新增能力

- **React component**：`FilterPanel` — accepts `filters` / `onChange` props; collapsible via toggle button
- **Filter state**：customer page manages `Record<FilterKey, FilterValue>` in useState
- **Client-side filter logic**：inline JS `Array.filter()` or utility function that guards on each non-null filter key
- **Clear all**：single callback resets all filter fields and table rows

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Inline client-side filter vs. URL param / query-string**: Chosen client-side because the parent issue (#557) states filters operate against fetched rows, and the customer list is paginated server-side so URL params would require re-fetching anyway. URL param persistence can be added as a follow-up on #557.
- **Date range picker**: Use native `<input type="date">` two-field approach (start / end) rather than installing a third-party date library, to avoid a new dependency for a two-field use case. Style with Tailwind to match the CRM theme.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| React | ^18.x | Matches existing frontend stack |
| Tailwind CSS | ^3.x | Matches existing frontend styling |

### 4.3 兼容性约束

- Filter panel must be a controlled component (props in / callbacks out) to remain testable and reusable.
- Customer page must not change the API contract for `GET /customers`.
- All filter state is local to the customer page component — no global state store required for this scope.

### 4.4 已知坑

1. **Date inputs accept invalid date strings** (e.g. Feb 30) silently in Chrome →规避：validate start ≤ end in `onChange` and show inline validation message if not.
2. **Uncontrolled vs. controlled select values** →规避：always use `value={field}` + `onChange={setField}` pattern; never mix with defaultValue.
3. **Tailwind + CSS module conflict** →规避：if FilterPanel uses Tailwind, do not co-locate a `.css` file for the same class names; prefer Tailwind `className` strings only or a dedicated `*.module.css` isolated by filename.

---

## 5. 实现步骤（按顺序）

### Step 1: Create FilterPanel component scaffold

Add `src/components/FilterPanel.tsx` with the component signature and collapsible shell (toggle button + collapse body). Include TypeScript interfaces for `FilterValues` and `FilterConfig`.

```tsx
// src/components/FilterPanel.tsx
interface FilterValues {
  status: string;
  industry: string;
  leadTier: string;
  lastActivityFrom: string; // YYYY-MM-DD
  lastActivityTo: string;   // YYYY-MM-DD
}

interface FilterPanelProps {
  values: FilterValues;
  onChange: (updated: FilterValues) => void;
}

export function FilterPanel({ values, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(true);
  // ...
}
```

**完成判定**：`grep -n "export function FilterPanel" src/components/FilterPanel.tsx` → 1 match

### Step 2: Add filter controls

Inside the FilterPanel body, add:
- `<select>` for `status` (options: `active`, `inactive`, `churned`)
- `<select>` for `industry` (options sourced from API or constants list)
- `<select>` for `lead_tier` (options: `hot`, `warm`, `cold`)
- Two `<input type="date">` fields for `lastActivityFrom` / `lastActivityTo`
- Each control's `onChange` updates the corresponding key in `values` and calls `onChange`

**完成判定**：`grep -c "onChange" src/components/FilterPanel.tsx` → ≥ 5

### Step 3: Add "Clear all" button

Add a "Clear all" `<button>` at the bottom of the panel body. On click, call `onChange` with all filter fields reset to `""` (empty string = no filter applied).

**完成判定**：`grep -n "Clear all" src/components/FilterPanel.tsx` → 1 match

### Step 4: Integrate FilterPanel into customers page

Open the customers page file (path TBD — verify at `src/pages/customers/` or `src/app/customers/`), import `FilterPanel`, add `useState` for filter values, and apply `customers.filter(...)` before rendering the table. Preserve all existing pagination, search, and sort behavior.

**完成判定**：`grep -n "FilterPanel" src/pages/customers/` → 1 match (import line)

### Step 5: Write unit test for FilterPanel

Create `tests/unit/test_filter_panel.ts` (or `.tsx` if the framework supports it) covering:
- Panel renders collapsed / expanded on toggle click
- Each `<select>` updates the corresponding filter value
- "Clear all" resets all values to empty string

**完成判定**：`PYTHONPATH=src pytest tests/unit/ -v` runs without import errors (or `vitest run` if using Vitest)

---

## 6. 验收

- [ ] `grep -r "FilterPanel" src/` → ≥ 2 files (component + customer page integration)
- [ ] `grep -n "Clear all" src/components/FilterPanel.tsx` → 1 match
- [ ] `grep -n "lastActivityFrom\|lastActivityTo" src/components/FilterPanel.tsx` → ≥ 2 matches
- [ ] `grep -n "status\|industry\|leadTier" src/components/FilterPanel.tsx` → ≥ 3 matches
- [ ] Customer page renders without console error when FilterPanel is present
- [ ] All new files pass linter (`npx eslint src/components/FilterPanel.tsx` → 0 errors or no output if no ESLint config)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Date-range logic has off-by-one errors (e.g. inclusive vs. exclusive boundary) | 中 | 中 | Add explicit `>= start && <= end` comparison in the filter function; write a unit test with known boundary dates |
| Filter state causes full row re-render on every keystroke / change | 低 | 低 | No action needed — client-side filter of a paginated table is trivial; memoize `filteredRows` with `useMemo` if profiling shows issues |
| Customer page integration conflicts with existing search/sort state | 中 | 高 | Isolate filter state into its own `useState`; only apply `.filter()` to the already-fetched rows array; do not modify existing `searchTerm` or `sortKey` state |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/components/FilterPanel.tsx src/pages/customers/
git commit -m "feat(frontend): add FilterPanel with status/industry/lead-tier/daterange filters for customers page"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): filter panel for customers page (closes #564)" --body "Closes #564"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD — 待验证：`src/components/` 中是否有类似下拉/表单组件可参照（如 `Dropdown.tsx`, `DatePicker.tsx`）
- 第三方文档：[React useState docs](https://react.dev/reference/react/useState), [Tailwind forms plugin](https://tailwindcss.com/docs/forms-plugin)
- 父 issue / 关联：#557, #563

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
