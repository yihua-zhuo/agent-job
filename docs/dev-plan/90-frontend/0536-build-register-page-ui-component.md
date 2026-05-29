# 注册页面 · Build Register Page UI component

| 元数据 | 值 |
|---|---|
| Issue | #536 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0535-build-login-page-ui-component](../50-automation/0535-build-login-page-ui-component.md) |
| 启用后赋能 | [0537-build-forgot-password-flow-ui](../50-automation/0537-build-forgot-password-flow-ui.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently has a login page (#535) but no self-service registration flow. New users must be manually provisioned by an admin, creating an operational bottleneck and a poor onboarding experience. This issue introduces the `/register` page so prospective users can create their own accounts directly.

### 1.2 做完后

- **用户视角**: A new user lands on `/register`, fills in their name, email, password, confirms the password, sees a real-time password strength meter, checks the terms of service box, and clicks Register. On success they are redirected to `/login`. If the email is already taken or the password is too weak, inline error messages appear without a full-page reload.
- **开发者视角**: A `Register` component is available at `src/frontend/pages/Register.tsx`, backed by `src/frontend/utils/validation.ts` (password strength + email format) and `src/frontend/utils/register-api.ts` (submission + error parsing). The router exposes `GET /register` and `POST /register`.

### 1.3 不做什么（剔除）

- [ ] No backend database models, services, or migrations — this is purely a frontend UI component.
- [ ] No email verification step (future work, tracked separately).
- [ ] No OAuth / social login buttons (future work, tracked separately).

### 1.4 关键 KPI

- `pytest tests/unit/test_validation.py -v` → ≥ 6 passed (password strength levels + email regex + confirm-password match)
- `pytest tests/unit/test_register_page.py -v` → ≥ 4 passed (render, submit, error states, redirect)
- `ruff check src/frontend/` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

TBD - 待验证：`src/frontend/` 目录是否存在及其中 `pages/` / `utils/` 子目录结构（如存在，补充具体路径）

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/router.tsx` — 添加 `/register` 路由配置
- 要建：
  - `src/frontend/pages/Register.tsx` — 注册页面组件
  - `src/frontend/utils/validation.ts` — 密码强度 + 邮箱格式 + 确认密码校验
  - `src/frontend/utils/register-api.ts` — 调用注册 API，解析错误响应
  - `tests/unit/test_validation.py` — 校验逻辑单元测试
  - `tests/unit/test_register_page.py` — Register 组件单元测试

### 2.3 缺什么

- [ ] No `GET /register` route defined — users cannot reach the page at all
- [ ] No `Register` component with name / email / password / confirm-password / terms fields
- [ ] No real-time password strength indicator (visual, auto-updates as user types)
- [ ] No client-side validation for weak passwords (min length, complexity rules)
- [ ] No handling of `email-already-exists` error from the API response
- [ ] No terms-of-service checkbox with required validation
- [ ] No redirect to `/login` on success

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/pages/Register.tsx` | 注册页面：表单、状态管理、错误展示、成功跳转 |
| `src/frontend/utils/validation.ts` | 密码强度评分函数、邮箱正则、确认密码匹配校验 |
| `src/frontend/utils/register-api.ts` | 调用 `POST /auth/register` 并解析 `409 email-already-exists` / `422 weak-password` 错误 |
| `tests/unit/test_validation.py` | 覆盖所有校验函数的单元测试 |
| `tests/unit/test_register_page.py` | 覆盖组件 render / submit / error / redirect 的单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/router.tsx` | 新增 `Route path="/register" element={<Register />}` |

### 3.3 新增能力

- **React Component**：`Register` — fully controlled form with 5 fields
- **Password strength indicator**：实时显示 4 档（Weak / Fair / Good / Strong），基于长度 + 数字 + 大小写 + 特殊字符评分
- **Validation suite**：`validateEmail(str)`, `validatePassword(str)`, `validateConfirmPassword(pw, confirm)` — exported from `validation.ts`
- **API layer**：`registerUser(payload)` in `register-api.ts` — calls `POST /auth/register`, returns typed success/error
- **Router entry**：`GET /register` mapped to `Register` component

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use a scoring function for password strength rather than a regex-only check** — a numeric score (0–100) feeds both the colour indicator and the `weak-password` rejection threshold. This is easier to test and tune than a set of boolean rules.
- **Store form state in a single `useState` object rather than one `useState` per field** — reduces boilerplate for the 5-field form and makes resetting on success trivial.
- **Parse API error responses in `register-api.ts` rather than in the component** — keeps error-type mapping (409 → `email-already-exists`, 422 → `weak-password`) in one place and makes the component purely presentational.

### 4.2 版本约束

TBD - 待补充：前端框架版本（如 React 18.x）及必要依赖（如 react-hook-form / zod 版本），由开发时确认。

### 4.3 兼容性约束

- No backend changes — API contract must already support `POST /auth/register` returning `409` for duplicate email and `422` for weak password.
- All form fields are required; the terms-of-service checkbox must be checked before submission is enabled.
- After successful registration the user is **always** redirected to `/login`; no intermediate "check your email" screen in this issue.

### 4.4 已知坑

1. **Password strength indicator flickers on every keystroke** → 规避：在 `validation.ts` 中使用防抖（debounce）封装评分函数，或在组件层使用 `useDeferredValue` 确保 indicator 不阻塞 input。
2. **TypeScript `useState` for form object may allow extra fields** → 规避：定义 `RegisterFormData` interface with exact fields; use `Partial<RegisterFormData>` only during intermediate state, never as the persistent state type。
3. **No existing frontend test infrastructure** (if `tests/unit/` only covers Python) → 规避：参考现有 Python 测试 fixture 风格，在 `tests/unit/` 下新建 `frontend/` 子目录，配置 Vitest + React Testing Library 独立于 Python 测试运行。

---

## 5. 实现步骤（按顺序）

### Step 1: Register frontend route

在 `src/frontend/router.tsx` 的路由列表中添加 `/register` 条目，指向 `<Register />`。

操作：
- a) 在 `router.tsx` 的 route 数组中插入：

```tsx
// src/frontend/router.tsx（插入位置由文件结构决定，需验证具体行号）
{
  path: "/register",
  element: <Register />,
},
```

**完成判定**：`ruff check src/frontend/router.tsx` exit 0

---

### Step 2: Create `validation.ts`

新建 `src/frontend/utils/validation.ts`，导出三个纯函数：

```typescript
// src/frontend/utils/validation.ts
export type PasswordStrength = "weak" | "fair" | "good" | "strong";

export function getPasswordStrength(password: string): PasswordStrength {
  if (password.length < 6) return "weak";
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (score <= 1) return "weak";
  if (score === 2) return "fair";
  if (score === 3) return "good";
  return "strong";
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function validateConfirmPassword(
  password: string,
  confirm: string,
): string | null {
  return password === confirm ? null : "Passwords do not match";
}
```

**完成判定**：`ruff check src/frontend/utils/validation.ts` exit 0

---

### Step 3: Create `register-api.ts`

新建 `src/frontend/utils/register-api.ts`，封装 API 调用和错误解析：

```typescript
// src/frontend/utils/register-api.ts
export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

export type RegisterError =
  | { type: "email-already-exists"; message: string }
  | { type: "weak-password"; message: string }
  | { type: "unknown"; message: string };

export async function registerUser(
  payload: RegisterPayload,
): Promise<{ ok: true } | { ok: false; error: RegisterError }> {
  const res = await fetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res.ok) return { ok: true };

  if (res.status === 409) {
    return { ok: false, error: { type: "email-already-exists", message: "This email is already registered" } };
  }
  if (res.status === 422) {
    const data = await res.json().catch(() => ({}));
    return { ok: false, error: { type: "weak-password", message: data.detail ?? "Password is too weak" } };
  }
  return { ok: false, error: { type: "unknown", message: "Something went wrong" } };
}
```

**完成判定**：`ruff check src/frontend/utils/register-api.ts` exit 0

---

### Step 4: Build `Register.tsx`

新建 `src/frontend/pages/Register.tsx` — 完整注册页面组件。

关键结构：
- `useState` 持有 `{ name, email, password, confirmPassword, agreedToTerms }`
- `handlePasswordChange` 调用 `getPasswordStrength` 实时更新强度条
- `handleSubmit` 调用 `registerUser`，根据返回的 error 类型设置 inline error
- 成功时 `window.location.href = "/login"`（或 `navigate("/login")` 若使用 react-router）
- 密码强度条：4 档颜色（红 / 橙 / 黄 / 绿）配合文字标签

```tsx
// src/frontend/pages/Register.tsx（核心片段，完整代码见文件）
import { useState } from "react";
import { getPasswordStrength, isValidEmail, validateConfirmPassword } from "../utils/validation";
import { registerUser } from "../utils/register-api";

export function Register() {
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "", agreedToTerms: false });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string>("");
  const strength = getPasswordStrength(form.password);
  // ... full implementation
}
```

**完成判定**：`ruff check src/frontend/pages/Register.tsx` exit 0

---

### Step 5: Write `test_validation.py`

新建 `tests/unit/test_validation.py`（Vitest 或 Jest 测试文件，取决于前端测试框架配置）。

测试用例：
- `getPasswordStrength`: "abc" → weak, "Abc123!" → fair, "Abcdef1!" → good, "Abcdefgh1!X" → strong
- `isValidEmail`: valid + invalid addresses
- `validateConfirmPassword`: match → null, mismatch → error string

**完成判定**：`pytest tests/unit/test_validation.py -v` → all passed（如前端使用 Vitest，替换为对应 test runner 命令）

---

### Step 6: Write `test_register_page.py`

新建 `tests/unit/test_register_page.py`，测试 Register 组件行为。

测试用例：
- 页面 render：5 个 input + 1 个 checkbox 存在
- 提交时必填项校验：空表单提交显示 field-level 错误
- 密码确认不匹配：`confirmPassword` 失配文案显示
- API 错误展示：`email-already-exists` → 正确文案；`weak-password` → 正确文案
- 成功时 redirect 调用（mock `navigate` 或 `window.location`）

**完成判定**：`pytest tests/unit/test_register_page.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/frontend/pages/Register.tsx src/frontend/utils/validation.ts src/frontend/utils/register-api.ts src/frontend/router.tsx` → 0 errors
- [ ] `pytest tests/unit/test_validation.py -v` → ≥ 6 passed
- [ ] `pytest tests/unit/test_register_page.py -v` → ≥ 4 passed
- [ ] 手动验证：打开 `/register`，5 个字段均可见；输入 "test@example.com" + 弱密码 "abc" 显示 "Weak" 红色条；提交后看到 inline 错误

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 后端 `/auth/register` 接口尚未实现或响应格式不一致 | 中 | 中 | 本次工作不阻塞 — 前端单独验收；接口就绪后做一次端到端 smoke test |
| 前端测试框架（Vitest/Jest）未配置导致测试无法运行 | 低 | 中 | 先用简单的 `console.assert` 验证校验函数行为，框架配置作为单独 setup 任务 |
| 密码强度阈值导致误判（"Good" 仍被后端判为 weak） | 低 | 低 | 调低阈值或与后端协商统一规则；不阻塞 UI 可用性 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/pages/Register.tsx \
      src/frontend/utils/validation.ts \
      src/frontend/utils/register-api.ts \
      src/frontend/router.tsx \
      tests/unit/test_validation.py \
      tests/unit/test_register_page.py
git commit -m "feat(frontend): add /register page with password strength indicator"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): build Register page UI component" --body "Closes #536"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/frontend/pages/Login.tsx` L? — 已完成 #535 的登录页，结构可直接参照
- 父 issue / 关联：#58, #535

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
