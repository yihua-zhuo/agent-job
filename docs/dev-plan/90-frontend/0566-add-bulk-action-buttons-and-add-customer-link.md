# 0566 · Add bulk action buttons and Add Customer link

| 元数据 | 值 |
|---|---|
| Issue | #566 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0565-add-customer-creation-flow](../70-platform/0565-add-customer-creation-flow.md) |
| 启用后赋能 | [0570-customer-list-export](../70-platform/0570-customer-list-export.md), [0571-assign-customer-to-user](../70-platform/0571-assign-customer-to-user.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM users managing large customer lists currently have no way to act on multiple records at once — every export, delete, or reassignment requires individual clicks. Issue #565 adds the customer creation flow; #566 adds the complementary batch UI so users can select rows and trigger bulk operations without leaving the list page.

### 1.2 做完后

- **用户视角**: Each table row shows a checkbox. Selecting one or more rows slides in a bulk-action bar with Export / Delete / Assign buttons. The "Add Customer" button in the page header navigates to `/customers/new`. No bulk action executes until at least one row is selected.
- **开发者视角**: The `BulkActionBar` component is a reusable UI component accepting an `onAction(type)` callback. The table page wires it up with stub handlers for `export`, `delete`, and `assign`. The component renders nothing when selection is empty.

### 1.3 不做什么（剔除）

- [ ] Customer creation form itself — handled by #565
- [ ] Real backend bulk-action endpoints — stubbed with `console.log` + TODO comment referencing the pending endpoint
- [ ] Persisted selection across pagination — selection resets on page change
- [ ] Bulk action analytics / audit log — future work
- [ ] Mobile-responsive compact mode for the bulk bar — desktop view only for now

### 1.4 关键 KPI

- [KPI 1: `ruff check src/frontend/` → 0 errors]
- [KPI 2: `pytest tests/unit/` → all existing tests still pass]
- [KPI 3: Selection of ≥1 row renders bulk-action bar visible (JS assertion or manual smoke test); selecting 0 rows hides it]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/components/table/` 或 `src/frontend/pages/customer-list/` — 现有 table 组件渲染行数据，无 checkbox 状态，无 bulk-action bar。

TBD - 待验证：`src/frontend/pages/customer-list/CustomerListPage.tsx` — 页头有工具栏区域，Add Customer 链接目标 TBD（由 #565 定义）。

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/components/table/TableRow.tsx` — 添加 checkbox 渲染 + selection state
  - `src/frontend/pages/customer-list/CustomerListPage.tsx` — 导入并渲染 BulkActionBar；添加 Add Customer 链接
  - `tests/unit/test_customer_list_page.py` — 新增 bulk-action interaction 测试
- 要建：
  - `src/frontend/components/bulk-action-bar/BulkActionBar.tsx` — 可复用组件
  - `tests/unit/test_bulk_action_bar.py` — 组件单元测试

### 2.3 缺什么

- [ ] Table rows without selection checkboxes — cannot trigger bulk UI
- [ ] BulkActionBar component — not yet created
- [ ] Page-level selection state (which rows selected, count)
- [ ] Add Customer button in page header linked to `/customers/new`
- [ ] Stub handlers for bulk export / delete / assign with TODO comments pointing to pending backend endpoints
- [ ] Bulk action bar visibility toggled by selection count > 0

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/components/bulk-action-bar/BulkActionBar.tsx` | Bulk action bar UI component — renders action buttons when count > 0, hidden otherwise |
| `tests/unit/test_bulk_action_bar.py` | Unit tests for BulkActionBar visibility and callback wiring |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/frontend/components/table/TableRow.tsx`](../../src/frontend/components/table/TableRow.tsx) | Add checkbox cell + `selected` prop; emit `onSelect` event |
| [`src/frontend/pages/customer-list/CustomerListPage.tsx`](../../src/frontend/pages/customer-list/CustomerListPage.tsx) | Add selection state; render `<BulkActionBar>` conditionally; add Add Customer `<Link>` to `/customers/new` |
| [`tests/unit/test_customer_list_page.py`](../../tests/unit/test_customer_list_page.py) | Add test cases: checkboxes visible, selecting row shows bulk bar, Add Customer link navigates |

### 3.3 新增能力

- **React component**: `BulkActionBar` in `src/frontend/components/bulk-action-bar/BulkActionBar.tsx`
- **Page state**: selection set tracked in `CustomerListPage` (useState-based, resets on page change)
- **Router link**: Add Customer button → `/customers/new` (route defined in #565)
- **Stub handlers**: `handleExport`, `handleDelete`, `handleAssign` in `CustomerListPage` each call `console.log('[TODO] bulk <action> — endpoint pending')`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Checkbox column first column, left-aligned** — consistent with CRM list UX patterns; does not shift data columns off-screen on small viewports.
- **BulkActionBar as a fixed bottom bar (overlay)** — avoids reflowing the page content when selection changes. Slides in from bottom with CSS transition.
- **Stub handlers over commented-out code** — `console.log` + TODO comment is intentional so the stubs are visible in DevTools and grep-able, not silently absent.

### 4.2 版本约束

<!-- 没有新依赖时整段删掉。如有，按下表填：-->

N/A — 无新 npm 依赖引入；使用现有 frontend 技术栈（React 18 + TypeScript）。

### 4.3 兼容性约束

- TypeScript strict mode: all new components typed fully, no `any` except in stub callback signatures
- BulkActionBar `onAction(type: 'export' | 'delete' | 'assign')` — string union type prevents typo-driven runtime errors
- No breaking changes to existing TableRow props — new `selected` and `onSelect` props are optional, existing callers unaffected
- Page component uses existing routing (`useNavigate` from react-router) — consistent with rest of frontend

### 4.4 已知坑

1. **Checkbox column nudges first data column** → 规避：set `position: sticky` on checkbox column + fixed width (`40px`); data columns scroll beneath independently
2. **Selection state lost on pagination** → 规避：documented as excluded scope; selection resets to empty on page change (acceptable per §1.3)
3. **No backend endpoint for bulk actions** → 规避：stub handlers log `[TODO] bulk <action> — endpoint pending`; add a `// TODO(#573): wire to POST /customers/bulk-<action>` comment per stub

---

## 5. 实现步骤（按顺序）

### Step 1: Create BulkActionBar component

Create `src/frontend/components/bulk-action-bar/BulkActionBar.tsx`. The component receives `selectedCount: number` and `onAction: (type: 'export' | 'delete' | 'assign') => void`. Renders nothing when `selectedCount === 0`. When count > 0: shows count badge + three buttons. Fixed at viewport bottom, full width, subtle shadow.

```tsx
// src/frontend/components/bulk-action-bar/BulkActionBar.tsx
import React from 'react';

type ActionType = 'export' | 'delete' | 'assign';

interface BulkActionBarProps {
  selectedCount: number;
  onAction: (type: ActionType) => void;
}

export const BulkActionBar: React.FC<BulkActionBarProps> = ({ selectedCount, onAction }) => {
  if (selectedCount === 0) return null;

  return (
    <div className="bulk-action-bar">
      <span className="selection-count">{selectedCount} selected</span>
      <button onClick={() => onAction('export')}>Export</button>
      <button onClick={() => onAction('delete')}>Delete</button>
      <button onClick={() => onAction('assign')}>Assign</button>
    </div>
  );
};
```

Add `src/frontend/components/bulk-action-bar/index.ts` exporting the component for cleaner imports.

**完成判定**: `ruff check src/frontend/components/bulk-action-bar/` → 0 errors / 文件存在

---

### Step 2: Add checkbox to TableRow

Modify `src/frontend/components/table/TableRow.tsx` — add optional `selected?: boolean` and `onSelect?: (id: number) => void` props. Render a `<td>` with `<input type="checkbox">` as the first cell. When checkbox changes, call `onSelect(rowId)` if provided.

Example diff snippet:

```diff
 interface TableRowProps {
   id: number;
   data: Record<string, string>;
+  selected?: boolean;
+  onSelect?: (id: number) => void;
 }

 const TableRow: React.FC<TableRowProps> = ({ id, data, selected, onSelect }) => {
   return (
     <tr className={selected ? 'row-selected' : ''}>
+      <td><input type="checkbox" checked={selected} onChange={() => onSelect?.(id)} /></td>
       {/* existing data cells */}
     </tr>
   );
 };
```

**完成判定**: `ruff check src/frontend/components/table/TableRow.tsx` → 0 errors

---

### Step 3: Wire selection state in CustomerListPage

Modify `src/frontend/pages/customer-list/CustomerListPage.tsx`:
- Add `useState<Set<number>>(new Set())` for `selectedIds`
- Add `handleSelect(id: number)` toggles id in/out of set
- Render `<BulkActionBar selectedCount={selectedIds.size} onAction={handleBulkAction} />`
- Stub `handleBulkAction`:

```ts
const handleBulkAction = (type: 'export' | 'delete' | 'assign') => {
  // TODO(#573): wire to POST /customers/bulk-<type>
  console.log(`[TODO] bulk ${type} — endpoint pending, ids:`, [...selectedIds]);
};
```

- Add Add Customer link in page header: `<Link to="/customers/new">Add Customer</Link>`

**完成判定**: `ruff check src/frontend/pages/customer-list/CustomerListPage.tsx` → 0 errors

---

### Step 4: Add unit tests for BulkActionBar

Create `tests/unit/test_bulk_action_bar.py`. Test cases:
- `selectedCount=0` → component returns `None` (renders nothing)
- `selectedCount>0` → component renders selection count badge and three buttons
- Each button calls `onAction` with correct type string

```python
import pytest
from frontend.components.bulk_action_bar import BulkActionBar

def test_renders_nothing_when_count_zero():
    result = BulkActionBar(selected_count=0, on_action=lambda t: None)
    assert result is None

def test_renders_bar_and_buttons_when_count_positive():
    result = BulkActionBar(selected_count=3, on_action=lambda t: None)
    assert result is not None
    assert "3 selected" in str(result)
    assert len(result.findall("button")) == 3

def test_export_button_calls_on_action_with_export():
    called_with: list = []
    result = BulkActionBar(selected_count=1, on_action=lambda t: called_with.append(t))
    result.find("button", text="Export").click()
    assert called_with == ["export"]
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_bulk_action_bar.py -v` → `3 passed`

---

### Step 5: Add integration test for CustomerListPage bulk flow

Extend `tests/unit/test_customer_list_page.py` with:
- `test_checkbox_renders_for_each_row` — confirms TableRow receives `onSelect` prop
- `test_bulk_bar_appears_after_single_selection` — simulate clicking one checkbox, assert BulkActionBar visible
- `test_add_customer_link_points_to_new_route` — assert `<Link to="/customers/new">` present in page

```python
def test_bulk_bar_appears_after_single_selection(customer_list_page):
    page = customer_list_page
    page.select_row(0)
    assert page.bulk_action_bar_visible()

def test_add_customer_link(customer_list_page):
    page = customer_list_page
    link = page.find_link("Add Customer")
    assert link.attributes["href"] == "/customers/new"
```

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_customer_list_page.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/frontend/components/bulk-action-bar/ src/frontend/components/table/TableRow.tsx src/frontend/pages/customer-list/CustomerListPage.tsx` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_bulk_action_bar.py -v` → `3 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_list_page.py -v` → 全 passed（含新增 bulk-flow 测试）
- [ ] 端到端 smoke（可选手动）：打开客户列表页面 → 勾选任意行 → bulk action bar 出现且显示正确 count → 点击 Add Customer → 导航至 `/customers/new`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| TableRow prop injection breaks existing callers that don't pass `selected`/`onSelect` | 低 | 中 | Make `selected` and `onSelect` truly optional with no-op defaults; no existing call site changes required |
| BulkActionBar CSS overlaps fixed footer in certain viewport sizes | 低 | 低 | Add `z-index` and position override; scoped CSS class prevents global pollution |
| Backend bulk endpoints (#573) delayed, stubs accumulate without cleanup | 中 | 低 | TODO comments with `#573` tag ensure stubs are grep-able; add an `// eslint-disable-next-line no-console` to suppress lint noise on stub log lines |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/components/bulk-action-bar/ \
        src/frontend/components/table/TableRow.tsx \
        src/frontend/pages/customer-list/CustomerListPage.tsx \
        tests/unit/test_bulk_action_bar.py \
        tests/unit/test_customer_list_page.py
git commit -m "feat(frontend): add bulk action bar and Add Customer link to customer list page

Closes #566"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): bulk action buttons and Add Customer link (#566)" --body "## Summary
- Add BulkActionBar component with Export/Delete/Assign stub handlers
- Add checkbox column to TableRow with selection state in CustomerListPage
- Add Add Customer link to /customers/new (route from #565)
- Stub handlers log TODO + #573 reference; wire to backend in future work

## Test plan
- [ ] pytest tests/unit/test_bulk_action_bar.py -v → 3 passed
- [ ] pytest tests/unit/test_customer_list_page.py -v → all passed
- [ ] ruff check src/frontend/ → 0 errors

Closes #566"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/frontend/components/table/TableRow.tsx`](../../src/frontend/components/table/TableRow.tsx) — 现有 TableRow component, extended with optional selection props
- 第三方文档：[React TypeScript component patterns](https://react.dev/learn) — 函数组件 + FC 泛型模式
- 父 issue / 关联：#557, #565

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
