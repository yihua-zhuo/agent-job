# 前后端协作 · AI 草稿助手 UI 组件

| 元数据 | 值 |
|---|---|
| Issue | #580 |
| 分类 | 90-frontend |
| 优先级 | 推荐 |
| 工作量 | 3-4 工作日 |
| 依赖 | [#579 AI Draft API 接口](../../../docs/dev-plan/50-automation/0577-add-aidraft-pydantic-schemas-and-aidraftservice.md) |
| 启用后赋能 | 无 — 本组件为最终用户入口，完成后其他模块可直接调用 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

用户需要在 CRM 详情页（客户或商机）内直接调用 AI 草稿生成能力，无需切换工具或复制上下文信息。目前 `POST /ai/draft` API 已存在（#579），但缺少配套的前端交互界面，导致用户无法实际使用该能力。此组件填补这一空白，使 AI 草稿生成成为 CRM 工作流的无缝延伸。

### 1.2 做完后

- **用户视角**：在客户详情页或商机视图内，点击「AI 草稿」面板，选择类型（Email/SMS）、语气、关联客户/商机、模板类型，点击「生成」，即可在页面内编辑 AI 输出内容，并一键复制或跳转至邮件客户端发送。
- **开发者视角**：新增 `AiDraftAssistant.vue` 可复用组件，接收 props（`tenantId`、`customerId`、`opportunityId`），通过 `POST /ai/draft` 与后端交互，遵循项目既有 Vue 组件模式。

### 1.3 不做什么（剔除）

- [ ] 不实现 AI 草稿后端逻辑（由 #579 负责）
- [ ] 不在本次实现中接入真实 LLM 调用链路以外的额外 AI 能力（如 AI 重写、AI 润色面板）
- [ ] 不做移动端响应式 UI 适配（移动端在后续专题处理）
- [ ] 不修改现有 `CustomerService`、`OpportunityService` 等业务逻辑

### 1.4 关键 KPI

- [组件可独立渲染：`PYTHONPATH=src pytest tests/unit/ -v` 不受前端变更影响（0 regressions）]
- [前端构建通过：`cd frontend && npm run build` exit 0]
- [组件内 E2E 测试通过：`cypress run --spec "**/ai-draft-assistant*.cy.ts"` → 全 passed]
- [API 集成验证：`curl -X POST http://localhost:8000/ai/draft -H "Content-Type: application/json" -d '{"draft_type":"email","tone":"professional","tenant_id":1}'` → `{"success":true,"data":{...}}`]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/components/` 目录下现有 Vue 组件目录结构和命名规范，以及 `src/api/routers/ai.py` 中 `POST /ai/draft` 路由定义（来自 #579 依赖）

TBD - 待验证：`src/frontend/pages/` 或 `src/frontend/views/` 下客户详情页和商机视图的路径和组件名称

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/frontend/pages/<customer-detail-or-opp-view>.vue` — 集成 AiDraftAssistant 组件
  - TBD - 待验证：`src/frontend/api/ai.ts` — 如无则新建，封装 `POST /ai/draft` 调用
- 要建：
  - `src/frontend/components/AiDraftAssistant.vue` — 核心 AI 草稿助手组件
  - `src/frontend/types/ai-draft.ts` — TypeScript 类型定义（`AiDraftRequest`、`AiDraftResponse`、`DraftType`、`ToneOption`）
  - `src/frontend/composables/useAiDraft.ts` — 抽取 `useAiDraft()` 可组合函数（生成逻辑、加载态、错误处理）
  - `tests/e2e/ai-draft-assistant.cy.ts` — 组件 E2E 测试
  - `tests/unit/test_ai_draft_service.py` — 如果 #579 尚未完成则本次也不做；否则按 CLAUDE.md 规范补充

### 2.3 缺什么

- [ ] `AiDraftAssistant.vue` 组件：类型切换、语气选择、上下文选择器、模板下拉、生成按钮、输出编辑区、复制/跳转按钮
- [ ] `useAiDraft()` 可组合函数：封装 API 调用逻辑和响应式状态
- [ ] TypeScript 类型定义文件：请求/响应结构
- [ ] API 封装函数（`src/frontend/api/ai.ts`）
- [ ] 集成至客户详情页或商机视图
- [ ] E2E 测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/components/AiDraftAssistant.vue` | AI 草稿助手主组件，含类型切换、语气选择、上下文选择器、生成与输出 |
| `src/frontend/types/ai-draft.ts` | `AiDraftRequest`、`AiDraftResponse` 等 TypeScript 类型定义 |
| `src/frontend/composables/useAiDraft.ts` | `useAiDraft()` 可组合函数，封装 API 调用、加载态、错误处理 |
| `src/frontend/api/ai.ts` | 封装 `POST /ai/draft` 的 API 调用函数 |
| `tests/e2e/ai-draft-assistant.cy.ts` | AI 草稿助手组件 E2E 测试（Cypress） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/frontend/pages/<detail-view>.vue` | 引入并放置 `<AiDraftAssistant>` 组件 |
| TBD - 待验证：`src/frontend/api/index.ts` | 注册 `ai.ts` 导出 |
| TBD - 待验证：`src/frontend/main.ts` 或 `src/frontend/router.ts` | 如有新路由则注册（本次预计无需新路由） |

### 3.3 新增能力

- **Vue 组件**：`AiDraftAssistant.vue` — 可复用 AI 草稿助手 UI 组件
- **Composable**：`useAiDraft()` — 响应式 API 调用封装（`isLoading`、`error`、`draftResult`）
- **API 函数**：`fetchAiDraft(req: AiDraftRequest): Promise<AiDraftResponse>`
- **TypeScript 类型**：`DraftType`（email | sms）、`ToneOption`、`AiDraftRequest`、`AiDraftResponse`
- **E2E 测试**：覆盖组件渲染、类型切换、生成按钮点击、复制功能

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Vue 3 Composition API (`<script setup>`) 不选 Options API**：项目已使用 Vue 3，`<script setup>` 提供更简洁的响应式逻辑，与 `useAiDraft()` composable 模式一致。
- **选独立 `useAiDraft()` composable 而非组件内直接调用 API**：复用性更好，后续在任意页面挂载组件时无需重写调用逻辑；也方便单独做单元测试（Vitest mock）。
- **选将组件集成到现有详情页而非新增独立路由**：减少用户操作路径，AI 草稿生成应在客户/商机上下文中自然触发。
- **选 Tailwind CSS 类而非 scoped CSS**：项目前端使用 Tailwind，遵循既有样式规范，保持一致性。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `vue` | `^3.4` | 支持 `<script setup>` 和 `defineProps` 类型推断 |
| `tailwindcss` | `^3.x` | 项目已有 Tailwind 配置 |
| `@vitejs/plugin-vue` | `^5.x` | Vue 3 SFC 支持 |
| `axios` | `^1.6` | 项目已有 HTTP 客户端（若需替换为 fetch 则注明） |

### 4.3 兼容性约束

- 组件 props 必须包含 `tenantId`（`number` 类型），符合多租户架构
- 组件通过 `customerId`（可选）和 `opportunityId`（可选）确定上下文，至少有一个非空
- API 请求格式必须与 #579 定义的 `POST /ai/draft` 接口 schema 对齐（请求体：`DraftRequest` Pydantic model）
- 不在后端 session 中直接操作数据库，组件仅做 UI 和 HTTP 调用

### 4.4 已知坑

1. **前端构建时 `PYTHONPATH` 不适用** → 规避：前端构建使用 Node.js 工具链（`npm run build`），与 `PYTHONPATH=src` 完全隔离，两者独立验证。
2. **API 响应字段名与前端类型不匹配（后端 snake_case vs 前端 camelCase）** → 规避：在 `api/ai.ts` 中使用 axios 拦截器或手动映射函数统一转换字段名，或在后端路由返回时使用 Pydantic `alias`。
3. **组件内直接使用 `window.location.href` 跳转邮件客户端** → 规避：使用 `mailto:` 链接而非强制跳转；复制功能使用 `navigator.clipboard.writeText()` 并做 Feature Detection 兜底。
4. **AI 生成接口耗时较长导致 UI 无反馈** → 规避：`useAiDraft()` 内维护 `isLoading` 状态，组件内显示 spinner 或 loading 文字；设置合理的超时（如 30s）并在超时时显示友好错误。
5. **E2E 测试依赖后端 `POST /ai/draft` 返回** → 规避：Cypress 测试使用 `cy.intercept()` mock API 响应，避免因后端 LLM 依赖导致测试不稳定。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 TypeScript 类型定义

在 `src/frontend/types/ai-draft.ts` 中定义组件所需的所有类型：

```typescript
// src/frontend/types/ai-draft.ts
export type DraftType = 'email' | 'sms';

export type ToneOption =
  | 'professional'
  | 'friendly'
  | 'urgent'
  | 'empathetic';

export interface AiDraftRequest {
  draft_type: DraftType;
  tone: ToneOption;
  template_type?: string;
  customer_id?: number;
  opportunity_id?: number;
  tenant_id: number;
  context_text?: string;
}

export interface AiDraftResponse {
  draft: string;
  word_count: number;
}
```

**完成判定**：`cd frontend && npx tsc --noEmit types/ai-draft.ts` → exit 0

---

### Step 2: 封装 API 调用函数

在 `src/frontend/api/ai.ts` 中实现 `fetchAiDraft`：

```typescript
// src/frontend/api/ai.ts
import axios from 'axios';
import type { AiDraftRequest, AiDraftResponse } from '../types/ai-draft';

export async function fetchAiDraft(req: AiDraftRequest): Promise<AiDraftResponse> {
  const response = await axios.post<{ success: true; data: AiDraftResponse }>(
    '/ai/draft',
    req
  );
  return response.data.data;
}
```

并在 `src/frontend/api/index.ts` 中导出该函数（追加一行 `export * from './ai';`）。

**完成判定**：`cd frontend && npx tsc --noEmit api/ai.ts` → exit 0

---

### Step 3: 实现 `useAiDraft()` 可组合函数

在 `src/frontend/composables/useAiDraft.ts` 中封装响应式状态和调用逻辑：

```typescript
// src/frontend/composables/useAiDraft.ts
import { ref } from 'vue';
import type { AiDraftRequest, AiDraftResponse } from '../types/ai-draft';
import { fetchAiDraft } from '../api/ai';

export function useAiDraft() {
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const draftResult = ref<string | null>(null);

  async function generateDraft(req: AiDraftRequest): Promise<void> {
    isLoading.value = true;
    error.value = null;
    draftResult.value = null;
    try {
      const resp = await fetchAiDraft(req);
      draftResult.value = resp.draft;
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '生成失败，请重试';
    } finally {
      isLoading.value = false;
    }
  }

  return { isLoading, error, draftResult, generateDraft };
}
```

**完成判定**：`cd frontend && npx tsc --noEmit composables/useAiDraft.ts` → exit 0

---

### Step 4: 实现 `AiDraftAssistant.vue` 主组件

在 `src/frontend/components/AiDraftAssistant.vue` 中实现完整 UI：

- `<template>`：type toggle（email/sms 按钮组）、tone selector（`<select>` 下拉）、context picker（customer dropdown + opportunity dropdown）、template type dropdown、Generate 按钮（`:disabled="isLoading"`）、output textarea（`:readonly="false"`）、Copy to Clipboard 按钮、Open in Email Client 按钮
- `<script setup>`：引入 `useAiDraft()`，定义 `draftType`、`tone`、`selectedCustomerId`、`selectedOpportunityId`、`templateType`、`outputText` 等响应式变量，绑定 `generate()` 方法
- Copy 功能：使用 `navigator.clipboard.writeText(outputText)`，成功后显示 toast 提示
- Open in Email Client：`<a :href="mailtoLink">` 链接，pre-fill subject 和 body

组件 props 接口：

```typescript
// AiDraftAssistant.vue <script setup> 内
interface Props {
  tenantId: number;
  customerId?: number;
  opportunityId?: number;
  customers?: Array<{ id: number; name: string }>;
  opportunities?: Array<{ id: number; name: string }>;
}
const props = withDefaults(defineProps<Props>(), {
  customerId: undefined,
  opportunityId: undefined,
  customers: () => [],
  opportunities: () => [],
});
```

**完成判定**：`cd frontend && npx vue-tsc --noEmit components/AiDraftAssistant.vue` → exit 0（如工具链支持）或 `npm run build` → exit 0

---

### Step 5: 集成至客户详情页（或商机视图）

在目标详情页 `src/frontend/pages/<CustomerDetailView>.vue` 中：

1. 引入 `<AiDraftAssistant>` 组件
2. 从页面 route params 或 store 获取 `tenantId`、`customerId`、`opportunityId`
3. 在合适位置（如侧边栏或 tab 页）放置组件

**完成判定**：TBD - 待验证：目标页面文件中包含 `<AiDraftAssistant` 字符串

---

### Step 6: 编写 E2E 测试

在 `tests/e2e/ai-draft-assistant.cy.ts` 中覆盖关键路径：

```typescript
// tests/e2e/ai-draft-assistant.cy.ts
describe('AiDraftAssistant', () => {
  beforeEach(() => {
    cy.intercept('POST', '/ai/draft', {
      fixture: 'ai-draft-response.json',
    }).as('generateDraft');
  });

  it('renders type toggle and generate button', () => {
    cy.mountWithProviders(AiDraftAssistant, { props: { tenantId: 1 } });
    cy.get('[data-testid="type-toggle"]').should('exist');
    cy.get('button').contains('生成').should('exist');
  });

  it('calls POST /ai/draft on generate click', () => {
    cy.mountWithProviders(AiDraftAssistant, { props: { tenantId: 1 } });
    cy.get('button').contains('生成').click();
    cy.wait('@generateDraft').its('request.body.draft_type').should('eq', 'email');
  });

  it('copies output to clipboard', () => {
    // mock clipboard API
  });
});
```

**完成判定**：`cd frontend && npx cypress run --spec "tests/e2e/ai-draft-assistant.cy.ts"` → 全 passed

---

## 6. 验收

- [ ] `cd frontend && npm run build` → exit 0（前端构建无错误）
- [ ] `cd frontend && npx vue-tsc --noEmit` → exit 0（TypeScript 类型检查通过）
- [ ] `cd frontend && npx cypress run --spec "tests/e2e/ai-draft-assistant.cy.ts"` → 全 passed（E2E 测试通过）
- [ ] `ruff check src/` → 0 errors（如有 Python 变更则验证，后端本次无变更）
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → 0 regressions（后端单元测试仍全绿）
- [ ] 端到端：`curl -X POST http://localhost:8000/ai/draft -H "Content-Type: application/json" -d '{"draft_type":"email","tone":"professional","tenant_id":1}'` → HTTP 200，`{"success":true,"data":{"draft":"...","word_count":N}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #579（后端 API）未完成或 schema 与前端类型不匹配 | 中 | 高 | 组件先用 mock 数据展示 UI；前端独立完成，API 对接在 #579 合并后补测 |
| AI 生成接口响应慢（LLM 调用 > 10s）导致前端超时 | 中 | 中 | `generateDraft()` 内设置 `AbortSignal` 超时（30s），超时后显示友好错误文案 |
| 详情页路由/布局调整导致组件集成位置变化 | 低 | 低 | 组件设计为可复用插槽，集成时调整 `<slot>` 位置即可，不影响组件逻辑 |
| 复制到剪贴板在非 HTTPS 环境（如 localhost）被浏览器拦截 | 低 | 低 | 监听 `navigator.clipboard` 不存在时回退到 `document.execCommand('copy')` 并显示提示 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/components/AiDraftAssistant.vue \
       src/frontend/types/ai-draft.ts \
       src/frontend/composables/useAiDraft.ts \
       src/frontend/api/ai.ts \
       tests/e2e/ai-draft-assistant.cy.ts
git commit -m "feat(frontend): add AiDraftAssistant Vue component"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): AI Draft Assistant UI component" --body "Closes #580

## Summary
- Add AiDraftAssistant.vue with type toggle, tone selector, context picker, template dropdown
- Wire to POST /ai/draft (from #579)
- Integrate into customer detail / opportunity view page

## Test plan
- [x] npm run build → exit 0
- [x] npx vue-tsc --noEmit → exit 0
- [x] npx cypress run --spec tests/e2e/ai-draft-assistant.cy.ts → all passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 父 issue：#50
- 依赖 issue：#579（`POST /ai/draft` 后端 API）
- 前端组件模式参考：TBD - 待验证：`src/frontend/components/` 目录下现有 Vue 组件（如 `CustomerTimeline.vue` 或 `OpportunityPanel.vue`）的 props 定义和 `<script setup>` 风格
- Vue 3 Composition API 文档：[Vue 3 Composition API](https://vuejs.org/api/composition-api-setup.html)
- Tailwind CSS 文档：[Tailwind CSS](https://tailwindcss.com/docs)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
