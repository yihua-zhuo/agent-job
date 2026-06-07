# Campaign Builder · Marketing campaigns edit page

| 元数据 | 值 |
|---|---|
| Issue | #532 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0531-marketing-campaign-apis](./0531-build-campaign-list-ui-page.md) |
| 启用后赋能 | [0533-campaign-analytics](./0533-build-campaign-stats-ui-page.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The parent issue #62 tracks a full marketing campaigns suite; #531 provides the backend API layer. Issue #532 delivers the interactive UI that lets marketers author, configure, and schedule campaigns. Without this page the backend APIs are unreachable by end users, blocking the entire campaigns workflow.

### 1.2 做完后

- **用户视角**: Marketing managers open `/marketing/campaigns/:id/edit` and see a fully rendered form: campaign name, description, type selector (Email / SMS / Push), audience segment dropdown, content editor with template picker and channel-appropriate input (rich text for Email, character counter for SMS), and a schedule toggle. Saving posts all fields to the API and navigates back to the campaign list.
- **开发者视角**: `src/ui/pages/marketing/CampaignBuilder.tsx` becomes a typed React form component that calls `campaignService.update(id, payload)`. The component follows the repository's established page/component patterns and passes all unit tests.

### 1.3 不做什么（剔除）

- [ ] Building the campaign list / overview page (belongs to a separate issue)
- [ ] Implementing push notification payload construction (backend API concern)
- [ ] Designing or implementing the audience segment builder UI (segment management is out of scope; only consuming a pre-saved dropdown)
- [ ] Adding real-time character counting websockets — character count is client-side only
- [ ] Multi-language / i18n of form labels (future work)

### 1.4 关键 KPI

- `PYTHONPATH=src ruff check src/ui/pages/marketing/CampaignBuilder.tsx` → 0 errors (lint must pass)
- Unit tests in `tests/unit/test_campaign_builder.ts` → ≥ 8 passed (all form-field render + submit tests)
- `CampaignBuilder` renders all 6 named form sections without console errors in dev
- Form submission calls `campaignService.update()` with correct payload shape
- Schedule toggle persists `scheduled_at` as ISO-8601 string to the API

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/ui/pages/marketing/CampaignBuilder.tsx` — current state unknown. May not yet exist (new module) or may be a stub. Check for existing exports in `src/ui/pages/marketing/index.ts`.

TBD - 待验证：`src/ui/services/campaignService.ts` — expected API client for campaign CRUD. Check for `update(id, payload)` method returning `Promise<Campaign>`.

TBD - 待验证：`src/ui/components/` patterns — existing form component library (e.g. `FormField`, `Select`, `RichTextEditor`, `Toggle`). Line count and API unknown.

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/ui/pages/marketing/CampaignBuilder.tsx` — primary implementation target
  - TBD - 待验证：`src/ui/pages/marketing/index.ts` — add / update route export
  - TBD - 待验证：`src/ui/services/campaignService.ts` — add `update` method if missing
- 要建：
  - `tests/unit/test_campaign_builder.ts` — form render + submit unit tests
  - TBD - 待验证：`src/ui/components/campaign/` directory — reusable sub-components (TypeSelector, AudienceSelector, ContentEditor, ScheduleToggle) if extracted

### 2.3 缺什么

- [ ] CampaignBuilder page component (file may not exist)
- [ ] Type selector UI (Email / SMS / Push tri-state toggle)
- [ ] Audience segment dropdown (reads from saved segments API)
- [ ] Content editor with channel-aware mode: rich text for Email, character-count textarea for SMS, raw input for Push
- [ ] Template selector (dropdown populated from a templates API)
- [ ] Schedule toggle + datetime picker (ISO-8601 scheduling)
- [ ] Form submission wiring to `campaignService.update()`
- [ ] Unit test coverage for the page

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_campaign_builder.ts` | Unit tests for form rendering and submit paths |
| TBD - 待验证：`src/ui/components/campaign/TypeSelector.tsx` | Radio/toggle for Email / SMS / Push selection |
| TBD - 待验证：`src/ui/components/campaign/AudienceSelector.tsx` | Dropdown listing saved segments from API |
| TBD - 待验证：`src/ui/components/campaign/ContentEditor.tsx` | Channel-aware editor (rich text / SMS counter) |
| TBD - 待验证：`src/ui/components/campaign/ScheduleToggle.tsx` | Toggle + datetime input for scheduled send |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/ui/pages/marketing/CampaignBuilder.tsx` | Implement full form with all 6 sections, wire to service |
| TBD - 待验证：`src/ui/pages/marketing/index.ts` | Export CampaignBuilder at `/marketing/campaigns/:id/edit` route |
| TBD - 待验证：`src/ui/services/campaignService.ts` | Ensure `update(id: string, payload: CampaignPayload): Promise<Campaign>` exists |

### 3.3 新增能力

- **Page component**: `CampaignBuilder` renders at `/marketing/campaigns/:id/edit`
- **Form fields**: name (text), description (textarea), type (Email|SMS|Push), audience (segment dropdown), template (dropdown), content (channel-specific editor), schedule (toggle + datetime)
- **Service call**: `campaignService.update(id, payload)` on form submit
- **Conditional UI**: SMS type shows character counter (160 GSM single-SMS threshold highlighted); Email shows rich-text toolbar; Push shows plain textarea
- **Error handling**: Field-level validation errors display inline; API errors shown as toast/banner

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Rich text editor**: Use the same library already in use elsewhere in `src/ui/components/editor/` (TBD - 待验证 which library). Do not introduce a new dep. If none exists, use a lightweight `contenteditable` wrapper or the `react-quill` package — do not add `TipTap` or `@tiptap/react` unless confirmed to already be in `package.json`.
- **Form state management**: Use React `useState` + `useForm` from the existing form library (TBD - 待验证: `react-hook-form` or internal equivalent). Do not introduce Redux for this page.
- **Routing**: Use `react-router-dom` v6 `useParams` to read the campaign `:id`. Do not use Next.js pages — confirm this is a SPA (FastAPI backend only).

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react-router-dom` | `^6` | Required for `useParams` and nested routing pattern |
| `react-hook-form` | `^7` | If adopted; match existing form pattern in the UI layer |

### 4.3 兼容性约束

- All API payloads must include `tenant_id` — the `campaignService` layer handles this (injected from auth context)
- Campaign `type` values sent to the API must be lowercase strings: `"email"`, `"sms"`, `"push"` (verify against #531 API schema)
- `scheduled_at` must be ISO-8601 string or `null` when scheduling is disabled

### 4.4 已知坑

1. **Rich text editor SSR/hydration mismatch** → Workaround: render editor only inside `useEffect` / after mount, or mark the component `"use client"` boundary if using Next.js.
2. **SMS character counter off-by-one for concatenated SMS** → Display: "160 / 153 chars (GSM)" so the user understands the split threshold; do not silently truncate.
3. **Form losing dirty state on navigation** → Add `useBlocker` from `react-router-dom` to warn about unsaved changes before navigating away.
4. **Segment list API loading state** → Show skeleton loader while `audienceSegments` fetch is pending; do not flash empty dropdown.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify existing patterns and scaffold test file

Audit the UI layer to confirm: form component library location, `campaignService` location/methods, routing setup, and test runner (Jest / Vitest). Scaffold the test file as the first action so tests drive the implementation.

操作：
- a) Run `find src/ui -name "*.tsx" | head -20` to discover file layout conventions
- b) Check `package.json` for test runner and form library entries
- c) Create `tests/unit/test_campaign_builder.ts` with pending tests for each form field and the submit path
- d) Run `npm test -- --testPathPattern="test_campaign_builder" --passWithNoTests` to confirm the file is picked up

**完成判定**: `npm test -- test_campaign_builder` exits 0 with at least 2 pending/placeholder tests listed.

---

### Step 2: Implement CampaignBuilder page with form skeleton

Build the outer page component with React Router `useParams` for the campaign `id`. Add a `useEffect` to fetch the campaign record via `campaignService.get(id)` and pre-fill the form. Wire up the submit handler to `campaignService.update()`.

操作：
- a) Create / overwrite `src/ui/pages/marketing/CampaignBuilder.tsx`
- b) Import `useParams`, `useNavigate` from `react-router-dom`
- c) Import `useForm` (or existing form hook) and `campaignService`
- d) Implement:
  ```tsx
  // src/ui/pages/marketing/CampaignBuilder.tsx
  import { useParams, useNavigate } from "react-router-dom";
  import { useForm } from "react-hook-form";
  import { campaignService } from "services/campaignService";
  import { segmentService } from "services/segmentService"; // TBD - 待验证 service name

  interface CampaignFormData {
    name: string;
    description: string;
    type: "email" | "sms" | "push";
    segment_id: number | null;
    template_id: number | null;
    content: string;
    scheduled_at: string | null;
    schedule_enabled: boolean;
  }

  export function CampaignBuilder() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const form = useForm<CampaignFormData>({ defaultValues: { type: "email", schedule_enabled: false } });
    // fetch campaign on mount, reset form with fetched data
  }
  ```
- e) Add submit handler: validate form, build payload (exclude `schedule_enabled` from API body), call `campaignService.update(id, payload)`, `navigate` on success

**完成判定**: `CampaignBuilder` compiles with `tsc --noEmit` and renders a `<form>` element in the DOM.

---

### Step 3: Implement type selector (Email / SMS / Push)

Add a three-way toggle for campaign type. Changing the type resets the `content` field and switches the content editor's mode.

操作：
- a) Create `src/ui/components/campaign/TypeSelector.tsx` (inline in `CampaignBuilder.tsx` if project prefers single-file pages)
- b) Render three `<button>` or `<RadioOption>` elements for `"email"`, `"sms"`, `"push"`
- c) On change: call `form.setValue("type", value)` and `form.setValue("content", "")`
- d) Add unit tests for switching type and verifying `form.getValues("type")` returns correct value

**完成判定**: `npm test -- test_campaign_builder --testNamePattern="type selector"` → passed.

---

### Step 4: Implement audience and template selectors

Add dropdown selects for saved segments and content templates. These load data asynchronously from their respective API endpoints.

操作：
- a) Import `useQuery` from the existing data-fetching library (React Query / SWR — TBD)
- b) Add `GET /segments` call via `segmentService.list()` to populate audience dropdown
- c) Add `GET /campaign-templates` call via `campaignTemplateService.list()` to populate template dropdown
- d) Render `<select>` elements bound to `form.register("segment_id")` and `form.register("template_id")`
- e) On template selection, optionally pre-fill `content` field if the template has body content

**完成判定**: `npm test -- test_campaign_builder --testNamePattern="audience|template"` → passed.

---

### Step 5: Implement channel-aware content editor

The content editor changes its UI based on the selected campaign type.

操作：
- a) In `CampaignBuilder.tsx`, add a `switch (form.watch("type"))` render block
- b) `email` → render `<RichTextEditor value={content} onChange={v => form.setValue("content", v)} />` (TBD - 待验证: existing editor component path)
- c) `sms` → render `<textarea>` with `maxLength={1530}` (10 × 153) and a character counter display: `"N / 160 (GSM)"`, highlight in red when > 160
- d) `push` → render a plain `<textarea>` with a subject line `<input>` field
- e) Add unit tests: switch type and verify correct editor is rendered

**完成判定**: `npm test -- test_campaign_builder --testNamePattern="content editor"` → passed.

---

### Step 6: Implement schedule toggle

Add a toggle switch that shows/hides a datetime input. When disabled, `scheduled_at` is `null`; when enabled, the user picks a datetime and `scheduled_at` is set to ISO-8601.

操作：
- a) Add `schedule_enabled: boolean` and `scheduled_at: string | null` to `CampaignFormData`
- b) Render `<Toggle checked={form.watch("schedule_enabled")} onChange={v => form.setValue("schedule_enabled", v)} />`
- c) Conditionally render `<input type="datetime-local" />` bound to `scheduled_at`; set value to local-datetime string or `""`
- d) On submit, only include `scheduled_at` in payload when `schedule_enabled === true`
- e) Add unit tests for toggle behavior and ISO-8601 formatting

**完成判定**: `npm test -- test_campaign_builder --testNamePattern="schedule"` → passed.

---

### Step 7: Final lint and full test run

Run the full unit test suite and lint check.

操作：
- a) `ruff check src/ui/pages/marketing/CampaignBuilder.tsx src/ui/components/campaign/` (if files exist there) — 0 errors
- b) `npm test -- test_campaign_builder` — all tests pass
- c) Verify no TypeScript errors: `npx tsc --noEmit src/ui/pages/marketing/CampaignBuilder.tsx`

**完成判定**: All three commands exit 0.

---

## 6. 验收

- [ ] `npx tsc --noEmit src/ui/pages/marketing/CampaignBuilder.tsx` → no errors
- [ ] `npm test -- test_campaign_builder` → ≥ 8 passed (form field render, type switch, audience, template, content editor × channel, schedule toggle, submit)
- [ ] `ruff check src/ui/pages/marketing/CampaignBuilder.tsx` → 0 errors
- [ ] Form fields render for all 6 sections: name, description, type selector, audience selector, content editor, schedule toggle
- [ ] Switching type selector between Email / SMS / Push shows the correct content editor variant
- [ ] SMS character counter displays `N / 160 (GSM)` format and turns red above 160 characters
- [ ] Submit button calls `campaignService.update()` with correct payload (type as lowercase string, `scheduled_at` as ISO-8601 string or omitted when scheduling disabled)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Backend API (#531) not ready when this page is implemented, causing submit tests to fail | 中 | 高 | Mock `campaignService.update` in tests with `jest.mock(...)`; mark integration test as skipped (`@ts-expect-error` / `test.skip`) until #531 merges |
| Existing rich text editor library has API incompatible with form integration | 低 | 中 | Fall back to a plain `<textarea>` for Email type; do not block the page; file follow-up issue |
| Segment / template APIs return unexpected shape causing dropdowns to break | 低 | 低 | Add defensive `?.` chaining; show "Failed to load" message in dropdown; tests validate error path |
| React Router version mismatch between this page and the router setup | 低 | 高 | Pin `react-router-dom` version in `package.json`; verify with `npm ls react-router-dom` before implementation |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ui/pages/marketing/CampaignBuilder.tsx
git add tests/unit/test_campaign_builder.ts
git add src/ui/components/campaign/  # if extracted components were created
git commit -m "feat(marketing): build CampaignBuilder UI page for /marketing/campaigns/:id/edit

Closes #532"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(marketing): CampaignBuilder UI page (#532)" --body "Closes #532

## Summary
- Implements CampaignBuilder page with name, description, type selector (Email/SMS/Push)
- Audience segment dropdown, template selector
- Channel-aware content editor (rich text for Email, character counter for SMS, plain textarea for Push)
- Schedule toggle with datetime picker
- All unit tests pass; ruff clean

## Test plan
- [ ] npm test -- test_campaign_builder → ≥ 8 passed
- [ ] ruff check src/ui/pages/marketing/CampaignBuilder.tsx → 0 errors
- [ ] Manual: open /marketing/campaigns/1/edit, verify all 6 form sections render"

# 2. Update progress
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Subtask of: #62
- Depends on: #531 (marketing campaign API layer — must be merged first)
- TBD - 待验证: existing UI form patterns in `src/ui/components/forms/`
- TBD - 待验证: existing editor component in `src/ui/components/editor/`
- TBD - 待验证: existing `campaignService` in `src/ui/services/`

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
```

**What changed:**

- Line 9: `../50-campaigns/0531-build-marketing-campaign-apis.md` → `./0531-build-campaign-list-ui-page.md`
- Line 10: `../60-analytics/0533-campaign-analytics-dashboard.md` → `./0533-build-campaign-stats-ui-page.md`

Both target files exist — they just live under `90-frontend/` alongside this board, not under `50-campaigns/` or `60-analytics/`. The link texts were kept as-is since they describe the dependency/empowerment intent.
