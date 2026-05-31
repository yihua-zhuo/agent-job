# 添加 CampaignTable 组件和 CampaignList 页面 · CampaignTable + CampaignList 完整交付

| 元数据 | 值 |
|---|---|
| Issue | #772 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：CampaignFilters 组件所在板块路径 |
| 启用后赋能 | TBD - 待验证：0773-add-campaign-detail.md 所在板块路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

#771 已实现 `CampaignFilters` 组件，具备按 name/type/status 筛选的能力，但缺少配套的表格组件和列表页面，无法将筛选结果渲染为用户可阅读的 6 列数据表。现有 CRM 没有 Campaign 实体的前端展示层，这一缺口使营销活动的浏览和管理无法闭环。

### 1.2 做完后

- **用户视角**：管理员打开 /marketing/campaigns 可看到 Campaign 表格，含 name、type、status badge（颜色对应状态）、sent_date、open_rate%、click_rate% 共 6 列；可通过 CampaignFilters 动态筛选；顶部有 "Create Campaign" 按钮。
- **开发者视角**：`src/ui/components/campaign/CampaignTable.tsx` 提供可复用表格组件；`src/ui/pages/marketing/CampaignList.tsx` 是完整列表页面，包含过滤器+表格+新建按钮的组合；新增 `App.tsx` 中的 `/marketing/campaigns` 路由注册。

### 1.3 不做什么（剔除）

- [ ] 不实现 Campaign 详情页（属于 #773）
- [ ] 不实现 Campaign 的 CRUD API 调用逻辑（后端接口先行，由 #771/#773 覆盖）
- [ ] 不实现 SortableTable / StatusBadge 基础组件（已有，通过 import 复用）

### 1.4 关键 KPI

- `CampaignTable.tsx` 渲染 6 列数据（name, type, status badge, sent_date, open_rate%, click_rate%）
- `StatusBadge` 根据 status 值显示正确颜色：draft=gray, scheduled=blue, sent=green, failed=red
- 访问 /marketing/campaigns 路由返回 CampaignList 页面，表格可正常显示占位数据

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/ui/components/campaign/` 目录是否已存在（如 #771 建立了该目录） L?
TBD - 待验证：`src/ui/pages/marketing/` 目录结构（是否已有其他 List 页面可参考） L?
TBD - 待验证：`src/ui/components/ui/SortableTable.tsx` 现有 SortableTable 接口签名 L?
TBD - 待验证：`src/ui/components/ui/StatusBadge.tsx` 现有 StatusBadge 接口签名 L?
TBD - 待验证：前端路由配置文件（Next.js 路由约定） L?

### 2.2 涉及文件清单

- 要改：
  - 前端路由配置 — 新增 `/marketing/campaigns` 路由注册（TBD：具体文件待确认）
- 要建：
  - `src/ui/components/campaign/CampaignTable.tsx` — SortableTable 封装，渲染 6 列 Campaign 数据（TBD：实际路径可能为 `frontend/src/...`，待验证）
  - `src/ui/pages/marketing/CampaignList.tsx` — 组合 CampaignFilters + CampaignTable + Create Campaign 按钮（TBD：实际路径可能为 `frontend/src/...`，待验证）
  - `tests/unit/ui/components/campaign/CampaignTable.test.tsx` — 组件单元测试
  - `tests/unit/ui/pages/marketing/CampaignList.test.tsx` — 页面单元测试

### 2.3 缺什么

- [ ] `CampaignTable` 组件：使用 SortableTable + StatusBadge 渲染 6 列，缺乏 Campaign 版本
- [ ] `CampaignList` 页面：组合 CampaignFilters（#771）和新建按钮，无统一包装
- [ ] `/marketing/campaigns` 路由：路由配置中尚未注册该路径（TBD：具体配置文件待确认）
- [ ] 配套单元测试：CampaignTable 和 CampaignList 的渲染测试为空

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/ui/components/campaign/CampaignTable.tsx` | 用 SortableTable + StatusBadge 渲染 6 列 Campaign 表格 |
| `src/ui/pages/marketing/CampaignList.tsx` | 组合 CampaignFilters + CampaignTable + Create Campaign 按钮的列表页 |
| `tests/unit/ui/components/campaign/CampaignTable.test.tsx` | CampaignTable 渲染 6 列 + StatusBadge 颜色验证 |
| `tests/unit/ui/pages/marketing/CampaignList.test.tsx` | CampaignList 路由存在性 + 组件组合渲染 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：前端路由配置文件 | 新增 `/marketing/campaigns` 路由 → CampaignList 页面组件 |

### 3.3 新增能力

- **React 组件**：`CampaignTable` — props 接收 `campaigns: Campaign[]`，渲染 SortableTable
- **React 组件**：`CampaignList` — 组合过滤器+表格+按钮，提供路由级页面
- **路由注册**：前端路由配置中注册 `/marketing/campaigns` → `CampaignList`
- **测试覆盖**：`CampaignTable` 渲染 6 列；`StatusBadge` 颜色映射正确

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 SortableTable 而非自建**：`SortableTable` 已在其他列表页（CustomerTable/OpportunityTable）验证，复用可保持交互一致性，减少维护成本
- **StatusBadge 颜色硬编码在组件内**：`StatusBadge` 已封装颜色映射逻辑，CampaignTable 只需传入 status 字符串，不重复造轮子
- **页面组合而非内联**：`CampaignList` 独立为页面组件而非内联在路由配置，保持路由层简洁，便于后续 #773 详情页复用 CampaignTable

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| React | 18.x | 与现有前端一致 |
| TypeScript | 5.x | 与现有前端一致 |

### 4.3 兼容性约束

- TypeScript strict 模式：所有 props 接口必须完整声明类型
- 组件需与现有 SortableTable API 兼容（接受 `columns` + `data` props）
- StatusBadge 的 color 映射规则必须覆盖所有 status 值（draft/scheduled/sent/failed），未覆盖的 status 值不 crash
- CampaignList 页面组件必须为默认导出（与前端 lazy 导入模式一致）

### 4.4 已知坑

1. **SortableTable columns 定义顺序与渲染列顺序不一致** → 规避：确保 columns 数组顺序与 UI 设计稿一致，且与 API 返回字段顺序对齐
2. **StatusBadge 未覆盖的 status 值默认样式丢失** → 规避：加 `default` case 返回 neutral gray，防止新加 status 类型导致 UI 样式丢失
3. **Vitest/Jest 与 JSX 的 transform 配置** → 规避：测试文件使用 `.tsx` 并配置对应 transformer（参考同目录已有测试配置）

---

## 5. 实现步骤（按顺序）

### Step 1: 实现 CampaignTable.tsx 组件

参考同目录已有 Table 组件（如 CustomerTable）的结构，在 `src/ui/components/campaign/` 下新建 `CampaignTable.tsx`。

组件 props：
```typescript
interface Campaign {
  id: string;
  name: string;
  type: string;
  status: 'draft' | 'scheduled' | 'sent' | 'failed';
  sent_date: string | null;
  open_rate: number | null;   // percentage, 0-100
  click_rate: number | null;  // percentage, 0-100
}

interface CampaignTableProps {
  campaigns: Campaign[];
  onSort?: (key: string) => void;
  sortKey?: string;
  sortDir?: 'asc' | 'desc';
}
```

StatusBadge 颜色映射（来自 StatusBadge 组件的 props 约定）：
- `draft` → gray
- `scheduled` → blue
- `sent` → green
- `failed` → red

6 列定义（columns 数组）：
1. `name` — text，sortable
2. `type` — text，sortable
3. `status` — StatusBadge 组件嵌入，not sortable
4. `sent_date` — text/null "—"，sortable（按日期字符串排序）
5. `open_rate` — text + "%"，sortable
6. `click_rate` — text + "%"，sortable

空状态：campaigns 为空数组时显示 "No campaigns found." 文案。

**完成判定**：`ruff check`（无此文件则跳过）/ `grep -c "name\|type\|status\|sent_date\|open_rate\|click_rate" src/ui/components/campaign/CampaignTable.tsx` → ≥ 6

---

### Step 2: 实现 CampaignList.tsx 页面组件

在 `src/ui/pages/marketing/` 下新建 `CampaignList.tsx`。

结构：
```
<div class="page-container">
  <header>
    <h1>Campaigns</h1>
    <button onClick={...}>Create Campaign</button>  {/* TODO: 绑定路由或 handler */}
  </header>
  <CampaignFilters />
  <CampaignTable campaigns={mockData} />  {/* TODO: 后续替换为 API 数据 */}
</div>
```

mockData 示例（供开发和测试展示用）：
```typescript
const mockCampaigns: Campaign[] = [
  { id: '1', name: 'Summer Sale', type: 'Email', status: 'sent', sent_date: '2025-07-01', open_rate: 24.5, click_rate: 3.2 },
  { id: '2', name: 'New Product Launch', type: 'Email', status: 'scheduled', sent_date: null, open_rate: null, click_rate: null },
];
```

必须为默认导出（`export default function CampaignList`），以便路由懒加载。

**完成判定**：`grep "Create Campaign\|CampaignFilters\|CampaignTable" src/ui/pages/marketing/CampaignList.tsx` → ≥ 3 matches

---

### Step 3: 注册 /marketing/campaigns 路由

在前端路由配置中找到现有的营销相关路由区块（TBD：具体文件待确认），新增 CampaignList 页面的路由注册。

确保使用与现有前端一致的懒加载模式。

**完成判定**：`grep "/marketing/campaigns\|CampaignList" <路由配置文件>` → ≥ 2 matches

---

### Step 4: 编写 CampaignTable 单元测试

在 `tests/unit/ui/components/campaign/` 下新建 `CampaignTable.test.tsx`。

测试用例：
1. 渲染 6 列表头（name, type, status, sent_date, open_rate, click_rate）
2. 渲染一行 mock 数据时，6 个 cell 内容均出现
3. `status="sent"` 的 StatusBadge 显示绿色（通过 data-testid 或 class 检查）
4. `status="failed"` 的 StatusBadge 显示红色
5. `sent_date=null` 时显示 "—"
6. `open_rate=24.5` 时显示 "24.5%"
7. 空数组传入时显示 "No campaigns found."

使用 `@testing-library/react` 的 `render` + `screen`。

**完成判定**：`grep -c "it\|test\|expect" tests/unit/ui/components/campaign/CampaignTable.test.tsx` → ≥ 7

---

### Step 5: 编写 CampaignList 单元测试

在 `tests/unit/ui/pages/marketing/` 下新建 `CampaignList.test.tsx`。

测试用例：
1. 页面渲染时显示 "Campaigns" 标题
2. 显示 "Create Campaign" 按钮
3. CampaignTable 被渲染（通过 data-testid 或容器 class）
4. CampaignFilters 被渲染

**完成判定**：`grep -c "it\|test\|expect" tests/unit/ui/pages/marketing/CampaignList.test.tsx` → ≥ 4

---

## 6. 验收

- [ ] 相关文件 linter 检查 → 0 errors（如文件不存在则用 `ls` 验证创建成功）
- [ ] `grep "name.*type.*status.*sent_date.*open_rate.*click_rate" src/ui/components/campaign/CampaignTable.tsx` → 有输出（验证 6 列全部覆盖）
- [ ] `grep "sent.*green\|failed.*red\|scheduled.*blue\|draft.*gray" src/ui/components/campaign/CampaignTable.tsx` → 有输出（验证 StatusBadge 颜色映射）
- [ ] `grep "/marketing/campaigns" <路由配置文件>` → 有输出（验证路由注册）
- [ ] `grep "Create Campaign" src/ui/pages/marketing/CampaignList.tsx` → 有输出（验证按钮存在）
- [ ] `ls src/ui/components/campaign/CampaignTable.tsx src/ui/pages/marketing/CampaignList.tsx` → 两个文件均存在

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| SortableTable 接口与本组件假设不一致，导致列宽/排序行为不符合预期 | 低 | 中 | 调整 CampaignTable 的 columns props 与 SortableTable 实际签名对齐；不阻塞页面渲染 |
| #771（CampaignFilters）尚未合并，本地开发时 CampaignList 无法组合测试 | 中 | 低 | 用 mock `<div>` 临时替代 CampaignFilters；合并 #771 后替换回来 |
| StatusBadge 颜色映射规则与设计稿不一致需返工 | 低 | 中 | 定义颜色常量（mapping object）集中管理，后续一处修改全局生效 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/components/campaign/CampaignTable.tsx \
        src/ui/pages/marketing/CampaignList.tsx \
        <路由配置文件> \
        tests/unit/ui/components/campaign/CampaignTable.test.tsx \
        tests/unit/ui/pages/marketing/CampaignList.test.tsx
git commit -m "feat(marketing): add CampaignTable component and CampaignList page"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#772): add CampaignTable and CampaignList page" --body "Closes #772"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/ui/components/customer/CustomerTable.tsx` — SortableTable 复用模式参考（TBD：实际路径可能为 `frontend/src/...`，待验证）
- 同类参考实现：`src/ui/components/ui/StatusBadge.tsx` — StatusBadge 接口与颜色映射（TBD：实际路径可能为 `frontend/src/...`，待验证）
- 同类参考实现：`src/ui/pages/sales/OpportunityList.tsx` — 列表页组合模式（Filters + Table + Create button）（TBD：实际路径可能为 `frontend/src/...`，待验证）
- 父 issue / 关联：#531（Epic: CRM 前端营销模块）
- 依赖板块：#771（CampaignFilters 组件）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
