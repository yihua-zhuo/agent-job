# 前端 · Wiring Login component to auth store/service

| 元数据 | 值 |
|---|---|
| Issue | #551 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [#550 auth store/service foundation](0550-auth-store-service-setup.md) |
| 启用后赋能 | [dashboard 路由守卫](../README.md) — 需要有效 token 才能进入受保护页面 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Login 组件已创建但尚未与 auth store/service 连接，无法处理真实用户认证。表单提交后没有调用 auth store，无法验证凭证、无法存储 token、无法重定向用户，也无法显示 API 返回的错误信息（如"invalid credentials"或"account locked"）。这是登录功能的最后一个缺口。

### 1.2 做完后

- **用户视角**：输入正确凭证后页面跳转到 `/dashboard`；输入错误凭证或账户被锁时，表单内联显示错误提示，不跳转。
- **开发者视角**：`useAuth()` hook 暴露 `login(credentials)` 方法；auth store 管理 token 生命周期并暴露 `isAuthenticated` / `user` 状态；路由守卫可依赖 auth store 实现页面保护。

### 1.3 不做什么（剔除）

- [ ] 不修改 auth service 后端端点或请求格式（由 #550 定义）
- [ ] 不实现多因素认证（MFA）UI
- [ ] 不实现"记住我"持久化登录（sessionStorage 而非 localStorage）
- [ ] 不修改其他页面组件，所有重定向仅限 `/dashboard`

### 1.4 关键 KPI

- [指标 1：正确凭证 → `pytest tests/unit/test_login.py -v` → `PASSED` + 浏览器 URL 含 `/dashboard`]
- [指标 2：错误凭证 → Login 组件显示内联错误文本，无重定向]
- [指标 3：锁定账户 → Login 组件显示"account locked"内联错误文本，无重定向]
- [指标 4：`ruff check src/frontend/` → 0 errors（如有前端源文件）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/stores/auth_store.ts` — 需确认现有 auth store 文件路径和结构（是否有 `login` action / method）

TBD - 待验证：`src/frontend/components/auth/Login.tsx` 或 `src/frontend/pages/login/` — 需确认 Login 组件文件路径

现有 auth store 推测结构（待验证）：

```typescript
// TBD - 待验证：src/frontend/stores/auth_store.ts
interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
}
// store 有 token 存储和 isAuthenticated getter
// 但 login() 方法尚未与 Login 组件连接
```

现有 Login 组件推测结构（待验证）：

```tsx
// TBD - 待验证：src/frontend/components/auth/Login.tsx
// 组件内已有 form 结构、email/password 字段、submit handler
// submit handler 当前为空或仅做前端验证
// 未调用 auth store login()
// 未处理 error state
```

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/stores/auth_store.ts` — 添加 `login(credentials)` 方法，处理 token 存储、错误解析、重定向触发
  - `src/frontend/components/auth/Login.tsx` — 表单提交调用 auth store login，处理成功/失败分支
- 要建：
  - `tests/unit/test_login_auth_wiring.py` — Login 组件与 auth store 交互的单元测试
  - `tests/unit/test_auth_store.py` — auth store login/logout 方法测试

### 2.3 缺什么

- [ ] Login 组件 submit handler 未调用 auth store `login()` 方法
- [ ] auth store 缺少 `login()` 方法（接收 email + password，调用 auth service，存储 token）
- [ ] auth store 无 `logout()` 方法（清除 token，重定向到 /login）
- [ ] 无错误状态映射（API "invalid credentials" → 显示内联错误，"account locked" → 显示内联错误）
- [ ] 无登录成功后的 `/dashboard` 重定向逻辑

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_login_auth_wiring.py` | 测试 Login 组件调用 auth store login 并正确处理成功/失败响应 |
| `tests/unit/test_auth_store.py` | 测试 auth store login/logout 方法的 token 存储和行为 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/stores/auth_store.ts` | 添加 `login(credentials)` 方法（调用 auth service、存储 token/session、触发重定向）；添加 `logout()` 方法（清除存储、重定向） |
| `src/frontend/components/auth/Login.tsx` | submit handler 调用 `useAuth().login()`；成功时 `router.push('/dashboard')`；失败时显示 inline error（取自 auth store error state） |

### 3.3 新增能力

- **Store method**：`authStore.login({ email, password })` → 调用 auth service → 存储 token → 更新 `isAuthenticated = true`
- **Store method**：`authStore.logout()` → 清除 token 和 user 状态 → 重定向到 `/login`
- **Component behavior**：Login form 提交 → 调用 `login()` → 成功则 `router.push('/dashboard')` → 失败则显示内联错误文本
- **Error display**：auth store 暴露 `error: string | null`，Login 组件读取并在表单内联显示

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **token 存储在 sessionStorage 而非 localStorage**：避免多 tab 共享会话，减少锁定账户被长期利用的风险（由 #550 auth store foundation 定义）
- **登录后立即重定向到 `/dashboard`**：`router.push('/dashboard')` 在 store login 方法 resolve 后执行，不在组件层等待
- **错误消息从 auth store error state 读取**：Login 组件直接读取 `authStore.error`，不需要在组件内维护独立的 error state

### 4.2 版本约束

<!-- 无新增前端依赖，全部使用现有包。-->

| 依赖 | 版本 | 理由 |
|------|------|------|
| `<前端框架>` | TBD - 待确认 | 现有项目使用的框架版本（如 React 18 / Vue 3 / Svelte 4 等） |

### 4.3 兼容性约束

- auth service API 接口由 #550 定义，本板块只调用不修改
- Login 组件错误显示字段名应与 API 错误响应格式匹配（"invalid credentials" / "account locked"）
- auth store 的 token 存储 key 由 #550 定义，本板块不重新定义

### 4.4 已知坑

1. **Login 组件在 auth store login 进行中时重复提交** → 规避：提交期间禁用 submit button（`disabled={isLoading}`），isLoading 状态由 auth store 暴露
2. **错误消息未在重试时清除** → 规避：auth store `login()` 方法在每次调用前先将 `error` 设为 `null`，Login 组件在 handleSubmit 开头也清除本地 error 状态
3. **前端路由守卫在 token 验证前就允许访问受保护页面** → 规避：路由守卫检查 `authStore.isAuthenticated` 和 token 存在性，未登录跳转到 `/login?redirect=<original-path>`

---

## 5. 实现步骤（按顺序）

### Step 1: 在 auth store 添加 login/logout 方法

在 auth store 文件中添加 `login` 和 `logout` 方法。`login` 方法接收 `{ email, password }` 对象，调用 auth service 的 `/auth/login` 端点，成功后将 token 存入 sessionStorage 并设置 `user` 状态，失败时设置 `error` 字段。`logout` 方法清除 sessionStorage 中的 token 和 user 状态。

操作：
- a) 读取 `src/frontend/stores/auth_store.ts`（如存在）
- b) 在 store 内添加 `login(credentials: { email: string; password: string }): Promise<void>` 方法
- c) 在 store 内添加 `logout(): void` 方法
- d) 添加 `isLoading` 和 `error` 状态字段

示例代码（auth store 新增部分）：

```typescript
// src/frontend/stores/auth_store.ts — 新增 login/logout
async login(credentials: { email: string; password: string }): Promise<void> {
  this.error = null;
  this.isLoading = true;
  try {
    const response = await authService.login(credentials);
    this.token = response.token;
    this.user = response.user;
    sessionStorage.setItem('auth_token', response.token);
    router.push('/dashboard');
  } catch (err) {
    this.error = err.message; // "Invalid credentials" / "Account locked"
    throw err; // 让 Login 组件也能 catch 到以控制 UI
  } finally {
    this.isLoading = false;
  }
}

logout(): void {
  this.token = null;
  this.user = null;
  this.error = null;
  sessionStorage.removeItem('auth_token');
  router.push('/login');
}
```

**完成判定**：`ruff check src/frontend/stores/auth_store.ts` → 0 errors（如文件存在）/ 文件 `src/frontend/stores/auth_store.ts` 存在

---

### Step 2: 将 Login 组件连接到 auth store

修改 Login 组件的 form submit handler。调用 `useAuth().login({ email, password })`。成功时不操作（auth store 已处理重定向）。失败时 catch 错误并确保 inline error 显示（从 `authStore.error` 读取）。提交期间禁用 button（`disabled={authStore.isLoading}`）。

操作：
- a) 读取 `src/frontend/components/auth/Login.tsx`（如存在）
- b) import `useAuth` hook
- c) 在 form submit handler 内调用 `authStore.login(credentials)`
- d) 在组件 render 中读取 `authStore.error` 并在 form 内显示
- e) submit button 添加 `disabled={authStore.isLoading}`

示例代码（Login 组件 handleSubmit 部分）：

```tsx
// src/frontend/components/auth/Login.tsx — handleSubmit 修改
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  authStore.error = null; // 清除上次错误
  try {
    await authStore.login({ email, password });
    // 重定向由 authStore.login() 处理 (router.push('/dashboard'))
  } catch {
    // authStore.error 已由 store 设置，UI 会自动反映
  }
};

// render 内 error 显示（放在表单内）
{authStore.error && (
  <div role="alert" className="inline-error">
    {authStore.error}
  </div>
)}
```

**完成判定**：`ruff check src/frontend/components/auth/Login.tsx` → 0 errors（如文件存在）

---

### Step 3: 编写 auth store 单元测试

创建 `tests/unit/test_auth_store.py`（或对应的前端测试文件如 `tests/unit/test_auth_store.ts`，格式依项目测试框架而定）。测试覆盖：
- `login()` 正确凭证 → token 存入 sessionStorage，`isAuthenticated = true`
- `login()` 错误凭证 → 抛出异常，`error` 字段被设置，无 token 存储
- `login()` 锁定账户 → 抛出异常，`error` 显示"account locked"
- `logout()` → 清除 token 和 `isAuthenticated`

操作：
- a) 创建 `tests/unit/test_auth_store.py` 或对应前端测试文件
- b) Mock auth service `login` 方法
- c) 编写上述三个场景的测试用例

**完成判定**：`pytest tests/unit/test_auth_store.py -v` → `3 passed`（或对应测试框架的等效命令）

---

### Step 4: 编写 Login 组件 auth 连接测试

创建 `tests/unit/test_login_auth_wiring.py`（或对应前端测试文件）。验证：
- 提交正确凭证 → `authStore.login` 被调用一次
- 提交错误凭证 → inline error 元素出现在 DOM 中，无重定向
- 提交锁定账户凭证 → inline error 显示对应文本，无重定向

操作：
- a) 创建 `tests/unit/test_login_auth_wiring.py` 或对应前端测试文件
- b) Mock `useAuth()` hook 返回测试用 authStore
- c) 编写上述三个场景的测试用例

**完成判定**：`pytest tests/unit/test_login_auth_wiring.py -v` → `3 passed`（或对应测试框架的等效命令）

---

## 6. 验收

- [ ] `ruff check src/frontend/stores/auth_store.ts src/frontend/components/auth/Login.tsx` → 0 errors（如相关文件存在）
- [ ] `pytest tests/unit/test_auth_store.py -v` → 全 passed（如有后端测试文件）
- [ ] `pytest tests/unit/test_login_auth_wiring.py -v` → 全 passed（如有后端测试文件）
- [ ] 端到端：正确凭证登录后 URL 变为 `/dashboard`；错误凭证登录后页面显示内联错误文本且 URL 不变；锁定账户登录后显示内联错误文本

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| auth service `/auth/login` 端点响应格式与预期不符（如错误字段名不是 `message`） | 低 | 高 | auth store login 方法捕获后以 `err.response?.data?.detail || err.message` 作为 error 文本，兼容多种错误格式 |
| 前端 router（如 React Router / Vue Router）版本与 `router.push()` API 不兼容 | 低 | 中 | 使用 `window.location.href = '/dashboard'` 作为 fallback 重定向方式 |
| auth store login 在测试中被 mock 但 mock 失效导致测试假通过 | 中 | 高 | 每个测试明确 reset auth store state（清除 token/error），测试间隔离 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/stores/auth_store.ts src/frontend/components/auth/Login.tsx tests/unit/test_auth_store.py tests/unit/test_login_auth_wiring.py
git commit -m "feat(frontend): wire Login component to auth store/service"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): wire Login component to auth store/service (#551)" --body "Closes #551"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/frontend/stores/` — 确认现有 store 的 action/method 写法风格（Zustand / Pinia / Vuex / MobX）
- 父 issue / 关联：#535（父），#550（依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
