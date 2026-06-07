# 前端 · 密码重置页面（请求页 + 确认页）

| 元数据 | 值 |
|---|---|
| Issue | #537 |
| 分类 | 90-frontend |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：后端 API 文档路径 |
| 启用后赋能 | 登录页 (#537 前端流程) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #58 定义了完整的密码重置流程，#536 提供了后端 API 支持（发送重置链接 + 验证 token + 更新密码），但前端用户界面尚未实现。当前用户在登录页点击"忘记密码"后无处可去，流程断环。

### 1.2 做完后

- **用户视角**：用户可在 `/password-reset-request` 输入邮箱地址提交重置请求，收到成功提示；收到邮件后访问 `/password-reset/confirm?token=...` 可设置新密码，提交后自动跳转至 `/login`。两次操作均有表单验证与错误提示。
- **开发者视角**：新增两个 React 组件（`PasswordResetRequestPage`、`PasswordResetConfirmPage`），并在路由配置中注册对应的路径。无其他副作用。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 API（已由 #536 完成）
- [ ] 不实现邮件发送逻辑（SMTP / 邮件服务商在后端处理）
- [ ] 不实现 token 刷新或过期提示 UI（后端返回错误即可，前端只需展示错误消息）
- [ ] 不修改登录页或注册页

### 1.4 关键 KPI

- [ ] `ruff check src/frontend/` → 0 errors（如存在 frontend lint 配置）
- [ ] React Router 路由表包含 `/password-reset-request` 与 `/password-reset/confirm` 两个路径
- [ ] 两个组件均导出默认函数并接受 props（无 TypeScript 类型错误）
- [ ] 表单提交路径指向 `#536` 后端已实现的 `/api/auth/password-reset/request` 与 `/api/auth/password-reset/confirm` 端点

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/` 或 `frontend/` 目录结构，以及现有 React 组件的存放路径（常见：`src/components/pages/` 或 `src/pages/`）。

现有登录页如有"忘记密码"链接，需确认其 href 指向的路由是否已注册：

```{text}:src/frontend/components/LoginPage.tsx
import React from 'react';
// TBD — 需要确认是否有忘记密码链接，以及指向哪个路径
```

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/routes/` 或 `src/frontend/App.tsx` — 注册两个新路由
  - `src/frontend/components/LoginPage.tsx` — 确认"忘记密码"链接指向 `/password-reset-request`
- 要建：
  - `src/frontend/components/PasswordResetRequestPage.tsx` — 邮箱输入 + 提交表单
  - `src/frontend/components/PasswordResetConfirmPage.tsx` — token 解析 + 新密码 + 确认密码表单

### 2.3 缺什么

- [ ] 路由注册：`/password-reset-request` 和 `/password-reset/confirm` 均未注册
- [ ] `PasswordResetRequestPage` 组件：邮箱验证 + POST `/api/auth/password-reset/request` + 成功提示 UI
- [ ] `PasswordResetConfirmPage` 组件：从 URL 提取 `token` 查询参数 + 双字段验证 + POST `/api/auth/password-reset/confirm` + 成功后跳转 `/login`
- [ ] 两个页面之间共享表单验证逻辑（可抽取为 `src/frontend/utils/validation.ts`）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/components/PasswordResetRequestPage.tsx` | 密码重置请求页：邮箱表单 + 提交逻辑 + 成功/错误消息 |
| `src/frontend/components/PasswordResetConfirmPage.tsx` | 密码重置确认页：解析 token + 新密码表单 + 提交逻辑 + 跳转 |
| `src/frontend/utils/validation.ts` | 共享表单验证工具（邮箱格式、密码强度、确认匹配） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/App.tsx` 或 `src/frontend/routes/index.tsx` | 注册 `/password-reset-request` 和 `/password-reset/confirm` 两个路由 |
| `src/frontend/components/LoginPage.tsx` | 确认"忘记密码"链接指向 `/password-reset-request` |

### 3.3 新增能力

- **React 组件**：`PasswordResetRequestPage` — 邮箱提交表单，成功后显示"查收邮件"提示
- **React 组件**：`PasswordResetConfirmPage` — 密码设置表单，读取 URL `?token=` 查询参数，提交成功后 `window.location.href = '/login'`
- **路由**：`/password-reset-request` → `PasswordResetRequestPage`
- **路由**：`/password-reset/confirm` → `PasswordResetConfirmPage`
- **工具函数**：`validateEmail(email: string): boolean`、`validatePassword(password: string): string | null`（返回错误消息或 null）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **页面组件 vs 表单模态框**：选择独立页面而非模态框，理由：token 来自 URL query param，需较宽幅展示；用户可能直接通过邮件链接访问，刷新页面不丢状态。
- **客户端 token 解析 vs 后端 redirect**：选择客户端从 `window.location.search` 解析 token，不做服务端渲染或后端重定向，因为 #536 后端已返回含 token 的邮件，前端只需读取 URL。

### 4.2 版本约束

（无新增 npm 依赖，暂不填）

### 4.3 兼容性约束

- React Router v5/v6 均可，使用 `useSearchParams()` 读取 query string（React Router v6）或 `new URLSearchParams(window.location.search)`（两者兼容）
- 不修改全局状态管理器（Redux/Zustand/Context）— 表单提交后直接跳转，server 返回成功即跳转，无需保留 state
- 密码字段使用 `<input type="password">`，始终不暴露明文

### 4.4 已知坑

1. **React Router v5 不支持 `useSearchParams`** → 规避：使用 `useLocation().search` 或 `new URLSearchParams(window.location.search)` 替代，兼容 v5 和 v6
2. **token 为空或过期时后端返回 4xx 错误，前端需展示错误消息而非崩溃** → 规避：`try/catch` 包裹提交逻辑，错误时设置 `errorMessage` state 并显示

---

## 5. 实现步骤（按顺序）

### Step 1: 搭建新页面组件骨架

在 `src/frontend/components/` 下创建两个空组件文件，导出默认函数，暂不做逻辑填充，以便路由注册可先完成。

操作：
- a) 创建 `src/frontend/components/PasswordResetRequestPage.tsx`，骨架：Props 接口 + 默认导出函数 + `<div>Request Page (TBD)</div>`
- b) 创建 `src/frontend/components/PasswordResetConfirmPage.tsx`，骨架：Props 接口 + 默认导出函数 + `<div>Confirm Page (TBD)</div>`

示例代码：

```tsx
// PasswordResetRequestPage.tsx
import React, { useState } from 'react';

interface Props {
  onSuccess?: () => void;
}

const PasswordResetRequestPage: React.FC<Props> = () => {
  return <div>Request Page (TBD)</div>;
};

export default PasswordResetRequestPage;
```

**完成判定**：文件 `<path>/PasswordResetRequestPage.tsx` 存在 / 文件 `<path>/PasswordResetConfirmPage.tsx` 存在 / `ruff check src/frontend/` exit 0

---

### Step 2: 创建共享验证工具

在 `src/frontend/utils/validation.ts` 中实现两个验证函数，供两个页面共用。

操作：
- a) 创建 `src/frontend/utils/validation.ts`
- b) 实现 `validateEmail(email: string): boolean`（标准 RFC 5322 简单校验）
- c) 实现 `validatePassword(password: string): string | null`（至少 8 字符，返回错误消息或 null）
- d) 实现 `validateConfirmPassword(password: string, confirm: string): string | null`

示例代码：

```ts
// src/frontend/utils/validation.ts
export const validateEmail = (email: string): boolean => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

export const validatePassword = (password: string): string | null => {
  if (password.length < 8) return 'Password must be at least 8 characters';
  return null;
};

export const validateConfirmPassword = (password: string, confirm: string): string | null => {
  if (password !== confirm) return 'Passwords do not match';
  return null;
};
```

**完成判定**：`ruff check src/frontend/utils/validation.ts` exit 0 / TypeScript 编译无错误（如有 tsconfig）

---

### Step 3: 实现 PasswordResetRequestPage

完成 `/password-reset-request` 页面：表单 UI + 邮箱验证 + API 调用 + 成功提示。

操作：
- a) 在 `PasswordResetRequestPage.tsx` 中添加 state：`email`、`error`、`success`
- b) 实现 `handleSubmit`：前端校验 → POST `/api/auth/password-reset/request` → 成功则显示"查收邮件"提示，失败则显示 `errorMessage`
- c) JSX：标题"重置密码" + 邮箱 input + 提交按钮 + 条件渲染 success/error 消息 + 返回登录链接

示例代码：

```tsx
// PasswordResetRequestPage.tsx
import React, { useState } from 'react';
import { validateEmail } from '../utils/validation';

const PasswordResetRequestPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }
    try {
      const res = await fetch('/api/auth/password-reset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error('Request failed');
      setSuccess(true);
    } catch {
      setError('Something went wrong. Please try again.');
    }
  };

  if (success) {
    return (
      <div>
        <h1>Check your email</h1>
        <p>If an account exists for <strong>{email}</strong>, we sent a password reset link.</p>
        <a href="/login">Back to login</a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>Reset your password</h1>
      <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Send reset link</button>
      <a href="/login">Back to login</a>
    </form>
  );
};

export default PasswordResetRequestPage;
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_password_reset.py -v` → 全 passed（如已建测试）/ `ruff check src/frontend/components/PasswordResetRequestPage.tsx` exit 0

---

### Step 4: 实现 PasswordResetConfirmPage

完成 `/password-reset/confirm` 页面：URL token 解析 + 密码表单 + API 调用 + 成功后跳转。

操作：
- a) 在 `PasswordResetConfirmPage.tsx` 中用 `new URLSearchParams(window.location.search).get('token')` 读取 token
- b) token 为空时显示"无效链接"提示并阻止提交
- c) 实现 `handleSubmit`：前端校验 → POST `/api/auth/password-reset/confirm` body: `{ token, password }` → 成功则 `window.location.href = '/login'`，失败显示错误
- d) JSX：标题"设置新密码" + 密码 input + 确认密码 input + 提交按钮 + error 消息

示例代码：

```tsx
// PasswordResetConfirmPage.tsx
import React, { useState, useEffect } from 'react';
import { validatePassword, validateConfirmPassword } from '../utils/validation';

const PasswordResetConfirmPage: React.FC = () => {
  const token = new URLSearchParams(window.location.search).get('token');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [invalidToken, setInvalidToken] = useState(false);

  useEffect(() => {
    if (!token) setInvalidToken(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const pwErr = validatePassword(password);
    if (pwErr) { setError(pwErr); return; }
    const confirmErr = validateConfirmPassword(password, confirm);
    if (confirmErr) { setError(confirmErr); return; }
    try {
      const res = await fetch('/api/auth/password-reset/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      if (!res.ok) throw new Error('Reset failed');
      window.location.href = '/login';
    } catch {
      setError('Failed to reset password. Please try again.');
    }
  };

  if (invalidToken) return <div><h1>Invalid link</h1><p>This password reset link is invalid or has expired.</p><a href="/login">Back to login</a></div>;

  return (
    <form onSubmit={handleSubmit}>
      <h1>Set new password</h1>
      <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="New password" />
      <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirm password" />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Reset password</button>
    </form>
  );
};

export default PasswordResetConfirmPage;
```

**完成判定**：`ruff check src/frontend/components/PasswordResetConfirmPage.tsx` exit 0

---

### Step 5: 注册路由

在 `App.tsx` 或路由配置文件中注册两个新页面路由。

操作：
- a) 找到现有路由配置文件（如 `src/frontend/App.tsx` 或 `src/frontend/routes/index.tsx`）
- b) import `PasswordResetRequestPage` 和 `PasswordResetConfirmPage`
- c) 在路由表中添加：

```tsx
// App.tsx (snippet)
import PasswordResetRequestPage from './components/PasswordResetRequestPage';
import PasswordResetConfirmPage from './components/PasswordResetConfirmPage';

// 在 <Routes> 内添加：
<Route path="/password-reset-request" element={<PasswordResetRequestPage />} />
<Route path="/password-reset/confirm" element={<PasswordResetConfirmPage />} />
```

**完成判定**：`ruff check src/frontend/App.tsx` exit 0 / 路由文件中包含两个新路径字符串

---

### Step 6: 确认 LoginPage 链接指向正确路径

验证登录页"忘记密码"链接 href 指向 `/password-reset-request`，如有需要则更新。

操作：
- a) 在 `LoginPage.tsx` 中搜索"忘记密码"或"forgot password"相关文案
- b) 确认 `<a href="/password-reset-request">` 或更新为该路径

**完成判定**：`grep -n "password-reset" src/frontend/components/LoginPage.tsx` 有输出

---

## 6. 验收

- [ ] `ruff check src/frontend/components/PasswordResetRequestPage.tsx src/frontend/components/PasswordResetConfirmPage.tsx src/frontend/utils/validation.ts` → 0 errors
- [ ] 文件 `src/frontend/components/PasswordResetRequestPage.tsx` 存在且默认导出 `PasswordResetRequestPage` 组件
- [ ] 文件 `src/frontend/components/PasswordResetConfirmPage.tsx` 存在且默认导出 `PasswordResetConfirmPage` 组件
- [ ] 路由配置包含 `/password-reset-request` 和 `/password-reset/confirm` 两个路径
- [ ] `PasswordResetRequestPage` 中 `fetch` 请求指向 `/api/auth/password-reset/request`（由 #536 实现）
- [ ] `PasswordResetConfirmPage` 中 `fetch` 请求指向 `/api/auth/password-reset/confirm`（由 #536 实现），成功后 `window.location.href = '/login'`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #536 后端 API 尚未合并，导致前端提交请求 404 | 低 | 中 | 前端先完成 UI 逻辑，API 端点路径硬编码为已知约定 `#536` 后再验证；404 不影响页面结构验收 |
| React Router 版本与示例不兼容（v5 vs v6 API 差异） | 低 | 中 | 如项目使用 v5，替换 `useSearchParams` 为 `useLocation().search`；如使用 v6，仅需小幅调整 |
| token 无效时后端返回非 4xx（如 200 with error body） | 低 | 中 | `PasswordResetConfirmPage` 的 `handleSubmit` 需检查 `res.ok` 并解析响应 body，避免静默失败 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/components/PasswordResetRequestPage.tsx \
       src/frontend/components/PasswordResetConfirmPage.tsx \
       src/frontend/utils/validation.ts \
       src/frontend/App.tsx  # 或对应的路由配置文件
git commit -m "feat(frontend): add password reset request and confirm pages"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): build password reset UI (#537)" --body "Closes #537"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#58
- 依赖 issue（后端 API）：#536
- React Router 文档（URL query param 读取）：TBD - 待验证：项目使用的 react-router 版本（v5 或 v6）
- 同类参考实现（登录页组件结构）：TBD - 待验证：`src/frontend/components/LoginPage.tsx` 的组件模式

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
