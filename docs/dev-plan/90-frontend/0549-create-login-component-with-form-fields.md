# 前端 · 创建登录表单组件（含加载状态）

| 元数据 | 值 |
|---|---|
| Issue | #549 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [0548-create-auth-layout-component](0548-create-auth-layout-component.md) |
| 启用后赋能 | [0549-create-login-component-with-form-fields](0549-create-login-component-with-form-fields.md) 自身完成前无法进行端到端登录流测试；[0550-wire-login-to-auth-api](0550-wire-login-to-auth-api.md) 依赖本组件 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

登录是用户进入 CRM 系统的唯一入口。当前前端代码库中缺少独立的登录表单组件，导致登录页面无法模块化开发，也无法独立测试 UI 交互逻辑（加载状态、字段渲染、提交拦截）。必须先有可渲染的表单骨架，后续 #550 才能在其基础上接入真实认证 API。

### 1.2 做完后

- **用户视角**：访问登录页时看到完整的表单，包含邮箱输入框、密码输入框、「记住我」复选框和「忘记密码」链接。点击提交按钮后按钮变为禁用并显示加载指示器。
- **开发者视角**：`src/frontend/components/Login.tsx` 提供类型安全的 `LoginProps` 接口，组件内部管理 `isLoading` 状态，`onSubmit` prop 接收外部注入的提交逻辑（暂不调 API）。

### 1.3 不做什么（剔除）

- [ ] **不接入**真实认证 API 调用（#550 负责）
- [ ] **不实现**登录成功后的路由跳转（#550 负责）
- [ ] **不实现**「忘记密码」邮箱发送逻辑（独立 issue）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_login_component.py -v` → `N passed`（TBD，取决于测试数量）
- `ruff check src/frontend/components/Login.tsx` → 0 errors
- 组件 Props 类型导出，无 `any` 泄露

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/frontend/components/` 目录是否已存在；`src/frontend/App.tsx` 或 `src/frontend/pages/` 是否已有登录路由占位；`src/frontend/components/` 下是否有其他表单组件（如 `Signup.tsx`、`TextField.tsx`）可作参考

### 2.2 涉及文件清单

- 要改：
  - `src/frontend/App.tsx` — 注册 Login 组件路由（如尚未注册）
  - `src/frontend/pages/AuthPage.tsx` — 引用 Login 组件（如有 auth 页面）
- 要建：
  - `src/frontend/components/Login.tsx` — 登录表单组件
  - `src/frontend/components/__tests__/Login.test.tsx` — 组件单元测试
  - `src/frontend/components/TextField.tsx` — 如无现有 input 封装组件需新建

### 2.3 缺什么

- [ ] `src/frontend/components/Login.tsx` 组件文件不存在
- [ ] 无 `TextField` / `Checkbox` / `Button` 等基础表单组件（需确认是否复用现有 UI 库）
- [ ] 组件无测试文件，无法 CI 覆盖
- [ ] `App.tsx` 中无登录路由注册（待 #548 auth layout 完成后补充）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/components/Login.tsx` | 登录表单组件，含 email/password/remember/forgotPassword 字段和 isLoading 状态 |
| `src/frontend/components/__tests__/Login.test.tsx` | Login 组件 Jest + React Testing Library 单元测试 |
| `src/frontend/components/TextField.tsx` | （如现有 UI 库无可用 input）通用文本输入封装组件 |
| `src/frontend/components/Checkbox.tsx` | （如无现成）通用 Checkbox 封装组件 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/App.tsx` | 注册 `/login` 路由，渲染 Login 组件 |
| `src/frontend/pages/AuthPage.tsx` | 引用 `<Login />` 组件替代硬编码表单（视现有结构而定） |

### 3.3 新增能力

- **React 组件**：`Login` — 接收 `onSubmit: (data: LoginFormData) => void` prop，内部管理 `isLoading: boolean`
- **TypeScript 接口**：`LoginFormData { email: string; password: string; rememberMe: boolean }`
- **UI 状态**：`isLoading === true` 时所有字段禁用 + 按钮显示 loading spinner

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **React Controlled Components 不选 Uncontrolled**：便于测试模拟用户输入，与 TypeScript 类型配合更紧密
- **表单状态放组件内不选 Zustand/Recoil**：本阶段仅单组件，无需跨页共享状态，引入状态库徒增复杂度
- **复用现有 UI 库（Ant Design / shadcn/ui）不手写基础组件**：如项目已有 `Input`、`Checkbox`、`Button`，直接使用；无现成库才新建基础封装组件

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react` | `^18.x` | 随项目现有版本 |
| `@testing-library/react` | `^14.x` | 组件测试标准工具 |

### 4.3 兼容性约束

- 组件必须是 **controlled component**（受控组件），所有字段值由 `useState` 管理
- `onSubmit` prop 必须接受 `LoginFormData` 类型参数，不接受 `any`
- 加载状态下必须将 `disabled` 传给所有表单元素（可访问性要求）

### 4.4 已知坑

1. **表单提交不触发页面刷新但控制台出现警告** → 规避：`onSubmit` handler 必须调用 `e.preventDefault()`
2. **TypeScript 未定义 `email` input type** → 规避：使用 `<input type="email" />` 标准 HTML5 类型，无需额外类型声明
3. **Jest + ESM 模块解析失败（vite / tsconfig paths）** → 规避：测试文件使用 `@testing-library/react` 的 `render` 而非直接 `import` 组件工厂；在 `jest.config.ts` 中配置 `moduleNameMapper` 映射 `@/` 前缀

---

## 5. 实现步骤（按顺序）

### Step 1: 搭建 Login 组件骨架

在 `src/frontend/components/Login.tsx` 创建组件文件，定义 `LoginFormData` 接口，使用 `useState` 管理 `email`、`password`、`rememberMe` 和 `isLoading` 状态。实现 `handleSubmit` 拦截 `e.preventDefault()`，设置 `isLoading = true`，调用 `onSubmit(formData)`，外部调用方（#550）负责在成功后重置。

```tsx
// src/frontend/components/Login.tsx
import React, { useState, type FormEvent } from 'react';

export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginProps {
  onSubmit: (data: LoginFormData) => void;
}

export const Login: React.FC<LoginProps> = ({ onSubmit }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await onSubmit({ email, password, rememberMe });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={isLoading} />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={isLoading} />
      <label>
        <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} disabled={isLoading} />
        Remember me
      </label>
      <a href="/forgot-password">Forgot password?</a>
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Loading...' : 'Sign in'}
      </button>
    </form>
  );
};
```

**完成判定**：`ruff check src/frontend/components/Login.tsx` → 0 errors（若有 ruff 配置检查 TSX）

### Step 2: 创建基础表单封装组件（如项目无可复用 UI 库）

检查 `src/frontend/components/` 是否已有 `TextField`、`Checkbox`、`Button` 组件，如有则跳 Step 3。如无，创建：

```tsx
// src/frontend/components/TextField.tsx
import React, { type InputHTMLAttributes } from 'react';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

export const TextField: React.FC<TextFieldProps> = ({ label, id, ...props }) => (
  <label htmlFor={id}>
    {label}
    <input id={id} {...props} />
  </label>
);
```

```tsx
// src/frontend/components/Checkbox.tsx
import React, { type InputHTMLAttributes } from 'react';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
}

export const Checkbox: React.FC<CheckboxProps> = ({ label, id, ...props }) => (
  <label htmlFor={id}>
    <input type="checkbox" id={id} {...props} />
    {label}
  </label>
);
```

**完成判定**：`ls src/frontend/components/TextField.tsx` 文件存在 + `ls src/frontend/components/Checkbox.tsx` 文件存在（或步骤跳过说明已有）

### Step 3: 在 App.tsx 中注册 /login 路由

在 `src/frontend/App.tsx` 中添加路由：

```tsx
import { Login } from './components/Login';

// 在路由表中添加：
// <Route path="/login" element={<Login onSubmit={(data) => console.log(data)} />} />
```

（如 `App.tsx` 结构未知，TBD - 待验证：`src/frontend/App.tsx` 现有路由配置）

**完成判定**：`grep -n "Login" src/frontend/App.tsx` 输出包含 Login 引用

### Step 4: 编写 Login 组件单元测试

创建 `src/frontend/components/__tests__/Login.test.tsx`，使用 `@testing-library/react`：

- 测试一：渲染所有字段（email input、password input、remember me checkbox、forgot password link）
- 测试二：提交表单触发 `onSubmit` 回调，传入正确 `LoginFormData`
- 测试三：`isLoading === true` 时按钮显示 "Loading..." 文本且所有字段 `disabled`

```tsx
// src/frontend/components/__tests__/Login.test.tsx（框架参考）
import { render, screen, fireEvent } from '@testing-library/react';
import { Login, type LoginFormData } from '../Login';

const mockSubmit = jest.fn();

beforeEach(() => { mockSubmit.mockClear(); });

test('renders all required fields', () => {
  render(<Login onSubmit={mockSubmit} />);
  expect(screen.getByRole('textbox', { name: /email/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: /remember me/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /forgot password/i })).toBeInTheDocument();
});

test('shows loading indicator on submit', async () => {
  render(<Login onSubmit={mockSubmit} />);
  const btn = screen.getByRole('button', { name: /sign in/i });
  fireEvent.click(btn);
  expect(await screen.findByText('Loading...')).toBeInTheDocument();
});
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_login_component.py -v` → 实际前端测试框架命令请用 `npm test -- --testPathPattern="Login.test"` 并确认 passed（无 PYTHONPATH 前端命令，pytest 仅覆盖后端）

### Step 5: 验证 ruff 检查

确认新文件通过 lint 检查：

```bash
ruff check src/frontend/components/Login.tsx
```

**完成判定**：`ruff check src/frontend/components/Login.tsx` → exit 0，无输出

---

## 6. 验收

- [ ] `ruff check src/frontend/components/Login.tsx` → 0 errors
- [ ] `npm test -- --testPathPattern="Login.test"` → 全 passed（如项目配置了 npm test）
- [ ] `ls src/frontend/components/Login.tsx` → 文件存在
- [ ] `grep "isLoading" src/frontend/components/Login.tsx` → 找到 `isLoading` 状态管理代码
- [ ] `grep "onSubmit" src/frontend/components/Login.tsx` → 找到 `onSubmit` prop 定义和 `LoginFormData` 接口导出

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 项目已有登录实现与本组件冲突 | 低 | 中 | #548 auth layout 如已包含登录表单，则本组件改为复用 layout 内表单而非新建独立组件 |
| 前端测试环境 jest 配置缺失 | 中 | 低 | 先用手动渲染测试（storybook 或 dev server），CI 覆盖在后续 #550 阶段补齐 |
| UI 组件库与手写组件混用导致样式不一致 | 低 | 中 | 统一使用现有 UI 库组件（Ant Design / shadcn/ui），不新建冲突的基础组件 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/components/Login.tsx
git add src/frontend/components/__tests__/Login.test.tsx
git add src/frontend/components/TextField.tsx  # 如有新建
git add src/frontend/components/Checkbox.tsx   # 如有新建
git commit -m "feat(frontend): add Login form component with loading state"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(frontend): Login form component #549" --body "Closes #549"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/frontend/components/` 下相似表单组件（如 `Signup.tsx`）
- 第三方文档：[React Hook Form docs](https://react.dev/learn/managing-state) — 状态管理模式参考；[Testing Library Guiding Principles](https://testing-library.com/docs/guiding-principles)
- 父 issue / 关联：#535（父），#548（依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
