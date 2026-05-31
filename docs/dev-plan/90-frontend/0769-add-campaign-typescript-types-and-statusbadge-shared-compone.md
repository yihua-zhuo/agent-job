# 0770 · Add Campaign TypeScript types and StatusBadge shared component

| 元数据 | 值 |
|---|---|
| Issue | #769 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：确认 0768 文件路径是否存在 |
| 启用后赋能 | [0771 - Add CampaignService and useCampaignList hook](0771-add-campaignservice-and-usecampaignlist-hook.md), [0772 - Add CampaignTable component and CampaignList page](0772-add-campaigntable-component-and-campaignlist-page.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #769 is a prerequisite for all downstream UI work on the campaign feature. The backend Pydantic schema for campaigns was defined in issue #530, but the frontend TypeScript types and a reusable StatusBadge component are missing. Without a typed `Campaign` interface and `CampaignStatus` enum, downstream pages will resort to `any` types or duplicative inline status rendering — both sources of bugs and inconsistency.

### 1.2 做完后

- **用户视角**：无直接用户-visible change — this is a pure frontend typing/infrastructure task.
- **开发者视角**：
  - `src/ui/types/campaign.ts` exports `CampaignStatus` enum and `Campaign` interface aligned with the backend schema from #530.
  - `src/ui/components/shared/StatusBadge.tsx` exports a reusable `<StatusBadge>` React component accepting `status: CampaignStatus` and rendering a colored badge (gray / blue / yellow / green / red) per status value.
  - Downstream components can import these types and component with zero duplication.

### 1.3 不做什么（剔除）

- [ ] No backend schema changes — types are derived from existing backend Pydantic schemas only.
- [ ] No Storybook configuration or stories file — acceptance criteria verify `tsc --noEmit` and color rendering via dev tools only.
- [ ] No API data fetching hooks — those belong to #0771.

### 1.4 关键 KPI

- `tsc --noEmit` on `src/ui/types/campaign.ts` → exit 0
- `tsc --noEmit` on `src/ui/components/shared/StatusBadge.tsx` → exit 0
- StatusBadge renders 5 distinct CSS classes matching the five CampaignStatus variants (gray / blue / yellow / green / red)

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

There is currently no `src/ui/types/` directory and no shared `StatusBadge` component in `src/ui/components/shared/`. These are greenfield additions required by the campaign feature.

### 2.2 涉及文件清单

- 要建：
  - `src/ui/types/campaign.ts` — CampaignStatus enum + Campaign interface
  - `src/ui/components/shared/StatusBadge.tsx` — colored status badge React component
  - `src/ui/components/shared/StatusBadge.stories.tsx` — Storybook story (optional, not required for acceptance)
  - `tests/unit/test_status_badge.tsx` — Vitest unit test for StatusBadge color rendering
  - `tests/unit/test_campaign_types.ts` — Type compile-only test (no runtime logic)
- 要改：无

### 2.3 缺什么

- [ ] `CampaignStatus` enum: DRAFT / SCHEDULED / SENDING / SENT / FAILED
- [ ] `Campaign` TypeScript interface aligned with the backend Pydantic schema from #530
- [ ] `StatusBadge` component with five distinct badge colors (gray / blue / yellow / green / red)
- [ ] TypeScript compile verification for both new files

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/ui/types/campaign.ts` | CampaignStatus enum and Campaign TypeScript interface |
| `src/ui/components/shared/StatusBadge.tsx` | Reusable React badge component, one color per CampaignStatus |
| `tests/unit/test_campaign_types.ts` | Type-check only test verifying the Campaign interface |
| `tests/unit/test_status_badge.tsx` | Vitest unit test verifying StatusBadge renders correct color class per status |

### 3.2 修改文件

（无修改文件）

### 3.3 新增能力

- **TypeScript type**：`CampaignStatus` enum — `DRAFT | SCHEDULED | SENDING | SENT | FAILED`
- **TypeScript interface**：`Campaign` with fields: `id`, `name`, `status`, `tenant_id`, `created_at`, `updated_at`, and any additional fields from the backend Pydantic schema in #530
- **React component**：`StatusBadge` — `props: { status: CampaignStatus }` → renders a `<span>` with a CSS class determined by status value
- **Unit tests**: compile-time type check + color-class rendering assertions

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **StatusBadge color palette — Chakra UI semantic tokens**：`gray` for DRAFT, `blue` for SCHEDULED, `yellow` for SENDING, `green` for SENT, `red` for FAILED. This follows the existing color semantics used by other status components in the CRM UI.
- **CSS class approach vs inline style**: Use CSS classes (e.g. `status-badge status-badge--draft`) rather than inline `style` objects, so the badge color is themeable and consistent across the app.
- **No external status-badge library**: The requirement is simple enough to implement in-house without a third-party dependency.

### 4.2 版本约束

（无新增外部依赖）

### 4.3 兼容性约束

- The `Campaign` interface fields must stay in sync with the backend Pydantic schema from #530. When the backend schema changes, this types file must be updated in the same PR.
- `StatusBadge` must accept `CampaignStatus` (not a raw string) to benefit from TypeScript exhaustiveness checking.
- Tests must run under `vitest` (the existing test runner for the frontend, per the repo's existing configuration). Do not introduce Jest.

### 4.4 已知坑

1. **TypeScript enum value mismatch with backend** → 规避：derive enum members explicitly from the backend Pydantic enum (check `src/models/` for the matching Pydantic schema) and add a compile-time check that the TypeScript enum has the same member count as the backend one.
2. **Storybook not configured** → 规避：acceptance criteria explicitly use `tsc --noEmit` and dev-tools color verification instead of requiring a full Storybook setup.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/ui/types/campaign.ts`

Create `src/ui/types/` directory and the `campaign.ts` file containing the `CampaignStatus` enum and `Campaign` interface.

```typescript
// src/ui/types/campaign.ts
export enum CampaignStatus {
  DRAFT = "DRAFT",
  SCHEDULED = "SCHEDULED",
  SENDING = "SENDING",
  SENT = "SENT",
  FAILED = "FAILED",
}

export interface Campaign {
  id: number;
  name: string;
  status: CampaignStatus;
  tenant_id: number;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}
```

**完成判定**：`tsc --noEmit src/ui/types/campaign.ts` → exit 0

---

### Step 2: Create `src/ui/components/shared/StatusBadge.tsx`

Create `src/ui/components/shared/` directory and `StatusBadge.tsx`. Export a component with a `status: CampaignStatus` prop that renders a `<span>` with a CSS class named `status-badge--<kebab-case-status>`.

```tsx
// src/ui/components/shared/StatusBadge.tsx
import React from "react";
import { CampaignStatus } from "../../types/campaign";

interface StatusBadgeProps {
  status: CampaignStatus;
}

const STATUS_LABELS: Record<CampaignStatus, string> = {
  [CampaignStatus.DRAFT]: "Draft",
  [CampaignStatus.SCHEDULED]: "Scheduled",
  [CampaignStatus.SENDING]: "Sending",
  [CampaignStatus.SENT]: "Sent",
  [CampaignStatus.FAILED]: "Failed",
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const kebab = status.toLowerCase();
  return (
    <span className={`status-badge status-badge--${kebab}`}>
      {STATUS_LABELS[status]}
    </span>
  );
};
```

**完成判定**：`tsc --noEmit src/ui/components/shared/StatusBadge.tsx` → exit 0

---

### Step 3: Add CSS for `status-badge--*` classes

Add the badge color styles to the global or component-level CSS file. The CSS must define five classes:

```css
/* src/ui/styles/status-badge.css */
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge--draft   { background-color: #e2e8f0; color: #475569; }
.status-badge--scheduled { background-color: #dbeafe; color: #1d4ed8; }
.status-badge--sending { background-color: #fef9c3; color: #854d0e; }
.status-badge--sent    { background-color: #dcfce7; color: #15803d; }
.status-badge--failed  { background-color: #fee2e2; color: #b91c1c; }
```

**完成判定**：File `<path>` exists / `ruff check` passes on any modified CSS file

---

### Step 4: Write unit tests

Create `tests/unit/test_campaign_types.ts` (type-only compile check):

```typescript
// tests/unit/test_campaign_types.ts
import { CampaignStatus, Campaign } from "../../src/ui/types/campaign";

// Compile-time check: Campaign interface has required fields
const _campaign: Campaign = {
  id: 1,
  name: "Test Campaign",
  status: CampaignStatus.DRAFT,
  tenant_id: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// Compile-time check: all enum members are valid CampaignStatus
const _allStatuses: CampaignStatus[] = [
  CampaignStatus.DRAFT,
  CampaignStatus.SCHEDULED,
  CampaignStatus.SENDING,
  CampaignStatus.SENT,
  CampaignStatus.FAILED,
];
```

Create `tests/unit/test_status_badge.tsx` (Vitest):

```tsx
// tests/unit/test_status_badge.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatusBadge } from "../../src/ui/components/shared/StatusBadge";
import { CampaignStatus } from "../../src/ui/types/campaign";

describe("StatusBadge", () => {
  const statuses = [
    { status: CampaignStatus.DRAFT, expectedClass: "status-badge--draft" },
    { status: CampaignStatus.SCHEDULED, expectedClass: "status-badge--scheduled" },
    { status: CampaignStatus.SENDING, expectedClass: "status-badge--sending" },
    { status: CampaignStatus.SENT, expectedClass: "status-badge--sent" },
    { status: CampaignStatus.FAILED, expectedClass: "status-badge--failed" },
  ];

  statuses.forEach(({ status, expectedClass }) => {
    it(`renders correct CSS class for ${status}`, () => {
      const { container } = render(<StatusBadge status={status} />);
      const span = container.querySelector("span");
      expect(span).not.toBeNull();
      expect(span!.className).toContain(expectedClass);
    });
  });
});
```

**完成判定**：`vitest run tests/unit/test_campaign_types.ts tests/unit/test_status_badge.tsx` → all passed

---

### Step 5: Verify TypeScript compilation for all new files

Run `tsc --noEmit` on both files in sequence.

**完成判定**：`tsc --noEmit` exit 0 on both `src/ui/types/campaign.ts` and `src/ui/components/shared/StatusBadge.tsx`

---

## 6. 验收

- [ ] `tsc --noEmit src/ui/types/campaign.ts` → exit 0
- [ ] `tsc --noEmit src/ui/components/shared/StatusBadge.tsx` → exit 0
- [ ] `vitest run tests/unit/test_campaign_types.ts tests/unit/test_status_badge.tsx` → all passed
- [ ] StatusBadge renders 5 distinct CSS classes (`status-badge--draft`, `status-badge--scheduled`, `status-badge--sending`, `status-badge--sent`, `status-badge--failed`) — verified by the unit test assertions in `test_status_badge.tsx`
- [ ] `ruff check src/` → 0 errors (lint the Python side of the repo is unaffected, but the check confirms no regressions)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Backend Pydantic schema from #530 changes mid-flight, causing TypeScript/Backend type drift | 低 | 中 | Add a comment in `campaign.ts` pointing to the source Pydantic model; update types in the same PR as the schema change |
| StatusBadge color tokens diverge from the rest of the CRM UI design system | 低 | 中 | Use existing semantic color tokens from the Chakra UI theme; if none exist, extract to a shared CSS variable in `status-badge.css` for centralized theming |
| Unit test runner (vitest) is not yet configured in the repo | 中 | 低 | The unit tests are optional — the primary acceptance criteria (`tsc --noEmit`) is unaffected; skip vitest tests if the runner is not set up yet |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/types/campaign.ts \
       src/ui/components/shared/StatusBadge.tsx \
       src/ui/styles/status-badge.css \
       tests/unit/test_campaign_types.ts \
       tests/unit/test_status_badge.tsx
git commit -m "feat(ui): add Campaign TypeScript types and StatusBadge component

Closes #769"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ui): add Campaign TypeScript types and StatusBadge component" --body "Closes #769"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/ui/types/` 或 `src/ui/components/shared/` 目录下是否已有类似 types 文件和 shared 组件的结构可参考
- 第三方文档：[TypeScript Enums handbook](https://www.typescriptlang.org/docs/handbook/enums.html)
- 父 issue / 关联：#531 (parent epic), #768 (dependency), #530 (backend Pydantic schema source of truth)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
