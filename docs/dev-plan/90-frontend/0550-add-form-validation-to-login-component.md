# Login 表单验证增强 · 为 Login 组件添加客户端字段级与表单级校验

| 元数据 | 值 |
|---|---|
| Issue | #550 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：0551-wire-login-component-to-auth-store-service 依赖文件路径 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 Login 组件 (TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径) 的 Zod 校验规则仅为 `z.string().min(1)`，仅能判断非空，无法拦截明显格式错误的 email（如不含 `@`、无域名），用户体验差。此外，`onError` 处理器将 HTTP 错误统一塞入 `password` 字段的 error，造成 `Invalid credentials` 与 `password is required` 混在一起，用户无法区分"密码为空"与"用户名/密码错误"两种截然不同的失败原因。

### 1.2 做完后

- **用户视角**：输入空表单点击提交，每一空字段下方立即显示 `Username is required` / `Password is required`；输入非邮箱格式内容后提交，显示 `Please enter a valid email address`；输入格式正确但凭证错误时，表单上方显示红色 `Invalid credentials`，字段本身不再被标记为错误。
- **开发者视角**：Login 组件的 `loginSchema` 内含 email 格式校验（`z.string().email()`）；`onError` 将服务器错误以 `form.setError("root.serverError", ...)` 的形式写入根错误，清晰区分字段级与表单级错误状态。

### 1.3 不做什么（剔除）

- [ ] 不修改后端 `/api/v1/auth/login` 接口（仍接受 `OAuth2PasswordRequestForm`，错误响应结构不变）
- [ ] 不引入新的表单管理库（继续用 `react-hook-form`，不迁移至 Formik 或 React Hook Form v8 新特性和废弃 API）
- [ ] 不实现 WebAuthn / 2FA 相关的前端 UI（`account locked` 状态的后端返回结构待确认，本期不处理）

### 1.4 关键 KPI

- [指标 1：提交空表单，表单中 `formState.errors.username.message` 和 `formState.errors.password.message` 均非空]
- [指标 2：提交格式错误 email（如 `not-an-email`），`formState.errors.username.message` 包含 "email" 关键词]
- [指标 3：提交有效格式但错误凭证，`formState.errors.root.serverError.message` 为 `"Invalid credentials"`，且 `formState.errors.username` 与 `formState.errors.password` 均为 `undefined`]
- [指标 4：`npm --prefix frontend run lint` → 0 errors（含 ESLint + Prettier）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 L{1}-L{95}

后端 auth 路由抛出 `UnauthorizedException("Invalid credentials")`，由 TBD - 待验证：`src/services/auth_service.py` 文件路径 L{143} 和 L{145} 发出：

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 — 增强 Zod schema（email 格式校验）、修复 `onError` 写 root 而非 password 字段、添加 `formState.errors.root.serverError` 的 UI
- 要建：
  - `frontend/src/app/(auth)/login/login.test.tsx` — Vitest + React Testing Library 单元测试

### 2.3 缺什么

- [ ] `loginSchema.username` 缺少 email 格式校验（`z.string().email()` 缺失），无效 email 不被拦截
- [ ] `onError` 将服务器 `Invalid credentials` 错误写入 `password` 字段，造成字段错误与表单错误混淆
- [ ] 无表单级错误展示区域（`formState.errors.root.serverError` 有 UI 但当前从不触发）
- [ ] 缺少 Login 组件的单元测试（Vitest + React Testing Library）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `frontend/src/app/(auth)/login/login.test.tsx` | Vitest 单元测试：覆盖空表单、格式错误、凭证错误三种场景 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 | `username` 改为 `z.string().min(1).email()`；`onError` 改为 `form.setError("root.serverError", ...)`；在提交按钮下方添加 `formState.errors.root.serverError` 展示区域 |

### 3.3 新增能力

- **Zod schema**：`username` 字段新增 `email()` 格式校验，错误消息 "Please enter a valid email address"
- **错误分发**：`onError` 使用 `form.setError("root.serverError", ...)` 将服务器错误写入根节点
- **单元测试**：覆盖空提交（两字段均报错）、无效 email 格式、`Invalid credentials` 服务器错误三种场景

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **继续用 react-hook-form 而非引入新的状态管理**：项目已集成 `react-hook-form` + `@hookform/resolvers/zod`，生态成熟，迁移成本为零；不做 Formik 迁移。
- **`z.string().email()` 而非自定义正则**：Zod 内置 email 校验覆盖 RFC 5322 合规格式，满足 CRM 表单需求，无引入额外依赖。
- **用 `form.setError("root.serverError", ...)` 而非 `form.setError("root", ...)`**：react-hook-form 推荐用 "root.serverError" 作为表单级服务器错误的语义化键值，与字段级错误解耦，便于 UI 独立展示。

### 4.2 版本约束

<!-- 无新增 npm 依赖 -->

### 4.3 兼容性约束

- Next.js 16.2.4 — 组件使用 `"use client"` 声明，为客户端组件，与 App Router 兼容
- Vitest 3 — 现有测试运行器，无需额外配置
- 后端 `/api/v1/auth/login` 接口不变：仍接受 `application/x-www-form-urlencoded`，返回 HTTP 401 + `{"detail": "Invalid credentials"}`

### 4.4 已知坑

1. **Zod v4 email 校验默认不允许 IP 地址格式** → 规避：CRM 用户名均为文本格式（非 IP），`z.string().email()` 行为符合预期；若将来需要支持 `user@192.168.1.1` 格式，需额外加 `.or(z.string().ip())` 组合
2. **react-hook-form `formState.errors.root.serverError` 在字段错误清除后残留** → 规避：每次 `onSuccess` 或表单重置时主动调用 `form.reset()` 清除根错误；`onError` 每次触发直接覆盖旧值

---

## 5. 实现步骤（按顺序）

### Step 1: 增强 loginSchema 为 email 格式校验

将 `username` 字段从 `z.string().min(1, "Username is required")` 升级为 `z.string().min(1, "Username is required").email("Please enter a valid email address")`，保持 `password` 字段的非空校验不变。

操作：
- a) 在 TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 第 12-14 行，找到 `loginSchema` 定义
- b) 将 `username` 的校验链改为：`z.string().min(1, "Username is required").email("Please enter a valid email address")`

```tsx
const loginSchema = z.object({
  username: z.string().min(1, "Username is required").email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
```

**完成判定**：`npm --prefix frontend run lint` → 0 errors（ESLint + Prettier 均通过）

### Step 2: 修复 onError — 将服务器错误写入 root.serverError 而非 password 字段

将 `onError` 中的 `form.setError("password", ...)` 改为 `form.setError("root.serverError", { message: err.message })`，使服务器错误与字段级错误解耦。

操作：
- a) 在 TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 第 41-43 行，找到 `onError` 处理器
- b) 将 `form.setError("password", { message: err.message })` 替换为 `form.setError("root.serverError", { message: err.message })`

```tsx
onError: (err: Error) => {
  form.setError("root.serverError", { message: err.message });
},
```

**完成判定**：`grep -n 'root.serverError' frontend/src/app/\(auth\)/login/page.tsx` 返回包含该字符串的行

### Step 3: 添加表单级错误展示 UI

在提交按钮下方（`</form>` 之前）添加对 `formState.errors.root?.serverError` 的展示区域，当服务器返回认证错误时在表单顶部显示红色提示文字，与字段级错误视觉上保持一致（`text-destructive` 样式）。

操作：
- a) 在 TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 第 81 行（`</form>` 之前）插入以下 JSX：

```tsx
{form.formState.errors.root?.serverError && (
  <p className="text-sm text-destructive">{form.formState.errors.root.serverError.message}</p>
)}
```

**完成判定**：`grep -n 'root.serverError' frontend/src/app/\(auth\)/login/page.tsx` 返回至少 2 处（一处在 `onError` 写入，一处在 JSX 展示）

### Step 4: 编写 login.test.tsx Vitest 单元测试

创建 `frontend/src/app/(auth)/login/login.test.tsx`，使用 Vitest + React Testing Library，覆盖以下场景：
1. 提交空表单 → 两字段均报错，无表单级错误
2. 提交非邮箱格式（如 `not-an-email`）→ `username` 字段报错包含 "email"
3. `login` API 返回错误（mock `fetch` 或直接 mock `login` 函数）→ `root.serverError` 被设置，字段错误为空

操作：
- a) 创建 `frontend/src/app/(auth)/login/login.test.tsx`
- b) 从 `@/lib/api/auth` mock `login` 函数
- c) 用 `render(<LoginPage />)` 渲染组件，用 `fireEvent` 触发提交和输入事件

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";
import * as auth from "@/lib/api/auth";

vi.mock("@/lib/api/auth", () => ({
  login: vi.fn(),
  getMe: vi.fn().mockResolvedValue({ data: { id: 1, tenant_id: 1, username: "a", email: "a@b.com", role: "user", status: "active" } }),
}));

describe("LoginForm validation", () => {
  it("shows required errors on empty submit", async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/username is required/i)).toBeInTheDocument();
    expect(screen.getByText(/password is required/i)).toBeInTheDocument();
  });

  it("shows email format error for invalid email", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByPlaceholderText(/username/i), "not-an-email");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/please enter a valid email address/i)).toBeInTheDocument();
  });

  it("sets root.serverError on invalid credentials", async () => {
    vi.mocked(auth.login).mockRejectedValue(new Error("Invalid credentials"));
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByPlaceholderText(/username/i), "user@example.com");
    await user.type(screen.getByPlaceholderText(/\*\*\*/i), "wrongpassword");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
  });
});
```

**完成判定**：`npm --prefix frontend run test` → 3 passed（含新增测试文件）

---

## 6. 验收

- [ ] `npm --prefix frontend run lint` → 0 errors（ESLint + Prettier 均通过）
- [ ] `npm --prefix frontend run test` → 全 pass（含 `login.test.tsx` 3 个用例）
- [ ] `git diff frontend/src/app/\(auth\)/login/page.tsx | grep -E 'email|root.serverError'` → 至少各返回 1 行
- [ ] 手动验收：提交空表单，两字段报错；提交 `foo` 用户名，报 `Please enter a valid email address`；提交正确格式用户名+错误密码，表单上方显示 `Invalid credentials`（字段无红色边框）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `z.string().email()` 在 Zod v4 对特殊格式（加号寻址、含域名别名）拒绝率略高于 v3，导致部分真实邮箱无法通过 | 低 | 低 | 将 `.email()` 替换为 `.includes("@", { message: "Please enter a valid email address" })` 作为临时回退 |
| `onError` 未被 react-hook-form v7 正确清除，导致后续表单提交仍残留旧 `root.serverError` | 低 | 中 | 提交成功后显式调用 `form.reset()` 清除所有错误（含 root）— 已有此处理，无需额外改动 |
| Vitest / jsdom 环境对 Next.js 客户端组件 `useRouter` / `useAuthStore` mock 不完整导致测试失败 | 中 | 低 | 在 `login.test.tsx` 顶部使用 `vi.mock("next/navigation", ...)` 和 `vi.mock("@/lib/store/auth-store", ...)` 兜底 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add frontend/src/app/\(auth\)/login/page.tsx frontend/src/app/\(auth\)/login/login.test.tsx
git commit -m "feat(login): add email format validation and root.serverError for auth failures"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#550): add form validation to Login component" --body "Closes #550"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`frontend/src/app/(auth)/login/page.tsx` 文件路径 — 当前 Login 组件（待修改）
- 父 issue / 关联：#535
- 依赖 issue：#549

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
```

----- END CORRECTED BOARD -----
