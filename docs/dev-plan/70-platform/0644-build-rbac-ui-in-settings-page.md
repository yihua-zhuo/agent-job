# RBAC UI · Settings page role management UI

| 元数据 | 值 |
|---|---|
| Issue | #644 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0643-build-rbac-api](../00-foundations/0643-wire-require-permission-into-all-existing-api-routers.md), [0038-rbac-permission-system](0038-rbac-permission-system.md) |
| 启用后赋能 | [0038-rbac-permission-system](0038-rbac-permission-system.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #38 defines the full RBAC permission system. Issue #643 exposes the backend REST endpoints (GET /roles, GET /permissions, PUT /roles/{id}/permissions, POST /users/{id}/role). Issue #644 delivers the frontend UI layer — without it the RBAC API has no interactive surface, and admins cannot manage roles, permissions, or user assignments.

###1.2 做完后

- **用户视角**：管理员在 Settings 页面看到 Roles 页签，显示角色表格（含权限摘要）、Permission Matrix（角色×资源可编辑网格）、User List 中每行有 Assign Role 下拉菜单，可实时保存调整。
- **开发者视角**：新增 `src/frontend/settings/` 模块，包含 RoleList, PermissionMatrix, UserRoleAssignment 三个组件；组件调用 [#643 的 API endpoints](../00-foundations/0643-wire-require-permission-into-all-existing-api-routers.md)；TypeScript 类型与后端 Pydantic schema 对齐。

### 1.3 不做什么（剔除）

- [ ] 不实现后端 RBAC API（属于 #643范围）
- [ ] 不实现权限检查中间件/装饰器（属于 #38 其他子任务）
- [ ] 不重构已有的其他 Settings 子页（用户 profile、通知等）
- [ ] 不添加 e2e自动化测试（项目暂无 e2e 框架）

### 1.4 关键 KPI

- [指标1：`ls src/frontend/settings/` 目录存在，含 RoleList.tsx / PermissionMatrix.tsx / UserRoleAssignment.tsx 三个组件]
- [指标 2：`npx tsc --noEmit src/frontend/settings/` → 0 errors（TS 类型检查通过）]
- [指标 3：组件引用 GET /roles、GET /permissions、PUT /roles/{id}/permissions、POST /users/{id}/role 四个端点，且参数/响应与 #643 schema 对齐]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：确认 `src/frontend/`目录是否已存在、采用什么前端框架（React/Vue/其他）、项目 CSS方案是否统一。

可能的参考入口点（现有 UI patterns）：
- 如果前端使用 React：查找 `src/frontend/components/` 或 `src/frontend/pages/` 目录
- API客户端调用模式（参考现有类似功能）

### 2.2 涉及文件清单

- 要改：
  - `TBD` —根布局/sidebar 导航（添加 Settings > RBAC 链接）
  - `TBD` —现有 API 客户端文件（添加 roles/permissions 相关请求函数）
- 要建：
  - `src/frontend/settings/` — 模块根目录
  - `src/frontend/settings/RolesPage.tsx` —页面入口容器
  - `src/frontend/settings/RoleList.tsx` — 角色表格组件
  - `src/frontend/settings/PermissionMatrix.tsx` — 权限矩阵组件  - `src/frontend/settings/UserRoleAssignment.tsx` — 用户角色分配组件  - `src/frontend/settings/api.ts` — API 调用封装（调用 #643 endpoints）
  - `src/frontend/settings/types.ts` — TypeScript 类型定义
  - `tests/unit/test_rbac_ui_components.tsx` — 组件单元测试（TBD 框架）

### 2.3 缺什么

- [ ] 没有 RBAC 相关 UI 组件 — 需要新增 `src/frontend/settings/` 目录及三个主组件
- [ ] 没有对应 API客户端函数 — 需要在 `api.ts` 中封装对 #643 四个 endpoints 的调用
- [ ] 没有 TypeScript 类型定义 — 需要定义 Role、Permission、PermissionMatrix、UserRole 接口与 #643 schema 对齐
- [ ] Sidebar 导航中没有 Settings/RBAC 入口 — 需要在根布局中添加链接
- [ ] 没有组件单元测试 — 需要补充 mock API响应的测试---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/settings/RolesPage.tsx` | Settings 页面 RBAC 子页容器，包含 Role List / Permission Matrix / Assign Role 三个子视图的 Tab 切换 |
| `src/frontend/settings/RoleList.tsx` | 角色表格：展示角色名称、描述、权限摘要列，支持点击展开详情（或跳转 Matrix） |
| `src/frontend/settings/PermissionMatrix.tsx` | 可编辑权限矩阵：行为角色、列为资源（customers/opportunities/tickets/reports/settings），单元格为允许操作，支持 PUT 保存 |
| `src/frontend/settings/UserRoleAssignment.tsx` | 用户角色分配：列表每行展示用户名 + 当前角色下拉框，支持 POST 保存 |
| `src/frontend/settings/api.ts` | API客户端：封装 GET /roles、GET /permissions、PUT /roles/{id}/permissions、POST /users/{id}/role 调用 |
| `src/frontend/settings/types.ts` | TypeScript Interface：Role、Permission、PermissionMatrix、UserRoleAssignment 与 #643 后端 schema 对齐 |
| `tests/unit/test_rbac_ui_components.tsx` | 组件单元测试：mock API 响应，验证 RoleList/Matrix/Assignment 渲染和交互逻辑 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/frontend/layouts/` 或 `src/frontend/App.tsx` | 在 Settings nav 中增加 RBAC 链接（路由指向 RolesPage） |
| `src/frontend/api/`（如已存在） | 添加 roles/permissions 相关 API 请求函数导出（若 api.ts 已存在则合并） |

### 3.3 新增能力

- **UI Component**：`RolesPage` — Settings 下 `/settings/roles` 路由入口- **UI Component**：`RoleList` — 调用 `GET /roles`，渲染表格 + 权限摘要
- **UI Component**：`PermissionMatrix` — 调用 `GET /permissions`，渲染可编辑网格 + PUT 保存
- **UI Component**：`UserRoleAssignment` — 调用 `POST /users/{id}/role`，inline 下拉保存
- **API Client**：`src/frontend/settings/api.ts` — 四个 endpoint 调用函数
- **TypeScript Types**：`Role` / `Permission` / `PermissionMatrixCell` / `UserWithRole` interfaces

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **使用 React +现有 UI组件库**（若有）**不选全新 UI 库**：保持项目一致性，减少样式碎片- **使用 local state + REST轮询**（若无实时需求）**不选 WebSocket**：RBAC 变更频率低，轮询成本可接受
- **矩阵单元格使用 Checkbox/Radio组件**（若项目有 Form组件）**不选手写样式**：复用已有表单组件保证一致性

### 4.2 版本约束

<!-- 无新增前端依赖，整段保留但不填 -->

|依赖 | 版本 | 理由 |
|------|------|------|
| `react` | `TBD`（使用项目现有版本） |保持与项目 React 版本一致 |
| `typescript` | `TBD`（使用项目现有版本） | 保持与项目 TS 版本一致 |

### 4.3 兼容性约束

- 所有 API 调用必须注入当前 `tenant_id`（从 auth context 读取，与 #643 后端约定一致）
- API响应处理需处理401/403/404/422 错误码并映射为用户 toast提示
- 组件必须支持 `tenant_id` 切换场景（管理员切换租户时重新加载数据）
- TypeScript 类型与 #643 backend Pydantic schema 严格对齐（`PermissionMatrixCell.actions[]` 为 string array）

### 4.4 已知坑

1. **前端 API client TypeScript 类型与后端 schema 不对齐导致运行时 NaN/undefined** → 规避：在 `types.ts` 中用 `// @ts-ignore` 或手工对齐每个字段类型；用 `npx tsc --noEmit` 在 CI强制检查
2. **RoleList权限摘要列过长导致表格列溢出** → 规避：权限摘要用逗号截断 + Tooltip 显示完整列表，Matrix 中用 Chips展示操作3. **PUT /roles/{id}/permissions 请求 body 格式与后端期望不符** → 规避：`api.ts` 中写死符合 #643 schema 的 body 结构（含 `permissions: [{resource, actions}]`）；添加单元测试 mock 验证序列化结果

---

## 5. 实现步骤（按顺序）

### Step 1:搭建前端目录结构与 TypeScript 类型创建 `src/frontend/settings/` 目录并定义接口类型文件，与 #643 后端 schema 对齐。

操作：
- a) 创建目录 `src/frontend/settings/`
- b) 创建 `src/frontend/settings/types.ts`，写入以下内容：

```typescript
// src/frontend/settings/types.ts
export interface Role {
  id: number;
  name: string;
  description: string | null;
  permissions_summary: string[]; // e.g. ["customers:read", "opportunities:write"]
  is_system: boolean; // system roles cannot be deleted
  created_at: string;
}

export interface Permission {
  id: number;
  resource: "customers" | "opportunities" | "tickets" | "reports" | "settings";
  action: "create" | "read" | "update" | "delete" | "assign";
  description: string;
}

export interface PermissionMatrixCell {
  resource: string;
  actions: string[];
}

export interface RolePermissionsPayload {
  permissions: PermissionMatrixCell[];
}

export interface UserWithRole {
  id: number;
  email: string;
  name: string | null;
  role_id: number | null;
  role_name: string | null;
}

export interface AssignRolePayload {
  role_id: number;
}
```

- c) 创建 `src/frontend/settings/api.ts` 框架（函数体暂时 return Promise.resolve()，下一步填充）：

```typescript
// src/frontend/settings/api.ts
import type {
  Role, Permission, PermissionMatrixCell,
  RolePermissionsPayload, UserWithRole, AssignRolePayload
} from "./types";

const BASE = "/api/v1";

export async function getRoles(tenantId: number): Promise<Role[]> {
  const res = await fetch(`${BASE}/roles?tenant_id=${tenantId}`);
  const json = await res.json();
  return json.data as Role[];
}

export async function getPermissions(tenantId: number): Promise<Permission[]> {
  const res = await fetch(`${BASE}/permissions?tenant_id=${tenantId}`);
  const json = await res.json();
  return json.data as Permission[];
}

export async function putRolePermissions(
  tenantId: number, roleId: number, body: RolePermissionsPayload
): Promise<void> {
  const res = await fetch(`${BASE}/roles/${roleId}/permissions?tenant_id=${tenantId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`putRolePermissions failed: ${res.status}`);
}

export async function assignUserRole(
  tenantId: number, userId: number, body: AssignRolePayload
): Promise<void> {
  const res = await fetch(`${BASE}/users/${userId}/role?tenant_id=${tenantId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`assignUserRole failed: ${res.status}`);
}

export async function getUsersWithRoles(tenantId: number): Promise<UserWithRole[]> {
  const res = await fetch(`${BASE}/users?tenant_id=${tenantId}`);
  const json = await res.json();
  return json.data as UserWithRole[];
}
```

**完成判定**：`npx tsc --noEmit src/frontend/settings/types.ts src/frontend/settings/api.ts` →0 errors（若项目无独立 tsconfig 可用 `tsc --noEmit --strict --esModuleInterop src/frontend/settings/types.ts` 测试）

### Step 2: 实现 RoleList 组件

创建角色表格组件，调用 GET /roles，展示角色列表和权限摘要。

操作：
- a) 创建 `src/frontend/settings/RoleList.tsx`，内容：

```typescript
// src/frontend/settings/RoleList.tsx
import React, { useEffect, useState } from "react";
import type { Role } from "./types";
import { getRoles } from "./api";

interface Props {
  tenantId: number;
  onEditRole?: (role: Role) => void;
}

export function RoleList({ tenantId, onEditRole }: Props) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRoles(tenantId)
      .then(setRoles)
      .catch(() => setError("加载角色失败"))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) return <div>加载中...</div>;
  if (error) return <div style={{ color: "red" }}>{error}</div>;

  return (
    <table>
      <thead>
        <tr>
          <th>ID</th><th>角色名</th><th>描述</th>
          <th>权限摘要</th><th>系统角色</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        {roles.map(role => (
          <tr key={role.id}>
            <td>{role.id}</td>
            <td>{role.name}</td>
            <td>{role.description ?? "-"}</td>
            <td>
              {role.permissions_summary.slice(0, 3).join(", ")}
              {role.permissions_summary.length > 3 && "…"}
            </td>
            <td>{role.is_system ? "是" : "否"}</td>
            <td>
              {!role.is_system && onEditRole && (
                <button onClick={() => onEditRole(role)}>编辑权限</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**完成判定**：文件 `src/frontend/settings/RoleList.tsx` 存在且 `npx tsc --noEmit` 0 errors

### Step 3: 实现 PermissionMatrix 组件

创建可编辑权限矩阵组件，调用 GET /permissions（角色×资源授权网格），支持 PUT 保存。

操作：
- a) 创建 `src/frontend/settings/PermissionMatrix.tsx`，核心结构：

```typescript
// src/frontend/settings/PermissionMatrix.tsx
import React, { useEffect, useState } from "react";
import type { Permission } from "./types";
import { getPermissions, putRolePermissions } from "./api";

const RESOURCES: Permission["resource"][] = [
  "customers", "opportunities", "tickets", "reports", "settings",
];
const ACTIONS = ["create", "read", "update", "delete", "assign"];

interface Props {
  tenantId: number;
  roleId: number;
  initialPermissionsMatrix: Record<string, string[]>;
}

export function PermissionMatrix({ tenantId, roleId, initialPermissionsMatrix }: Props) {
  const [matrix, setMatrix] = useState<Record<string, string[]>>(initialPermissionsMatrix);
  const [saving, setSaving] = useState(false);

  const toggle = (resource: string, action: string) => {
    setMatrix(prev => {
      const current = prev[resource] ?? [];
      const next = current.includes(action)
        ? current.filter(a => a !== action)
        : [...current, action];
      return { ...prev, [resource]: next };
    });
  };

  const save = async () => {
    setSaving(true);
    const body = { permissions: RESOURCES.map(r => ({ resource: r, actions: matrix[r] ?? [] })) };
    try {
      await putRolePermissions(tenantId, roleId, body);
 } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>资源</th>
            {ACTIONS.map(a => <th key={a}>{a}</th>)}
          </tr>
        </thead>
        <tbody>
          {RESOURCES.map(res => (
            <tr key={res}>
              <td>{res}</td>
              {ACTIONS.map(act => (
                <td key={act}>
                  <input
                    type="checkbox"
                    checked={(matrix[res] ?? []).includes(act)}
                    onChange={() => toggle(res, act)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={save} disabled={saving}>
        {saving ? "保存中..." : "保存权限"}
      </button>
    </div>
  );
}
```

**完成判定**：文件 `src/frontend/settings/PermissionMatrix.tsx` 存在且 `npx tsc --noEmit` 0 errors

### Step 4: 实现 UserRoleAssignment 组件

创建用户角色分配组件，调用 GET /users 和 POST /users/{id}/role，支持 inline 下拉保存。

操作：
- a) 创建 `src/frontend/settings/UserRoleAssignment.tsx`:

```typescript
// src/frontend/settings/UserRoleAssignment.tsx
import React, { useEffect, useState } from "react";
import type { UserWithRole, Role } from "./types";
import { getUsersWithRoles, getRoles, assignUserRole } from "./api";

interface Props {
  tenantId: number;
}

export function UserRoleAssignment({ tenantId }: Props) {
  const [users, setUsers] = useState<UserWithRole[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<Record<number, number | null>>({});

  useEffect(() => {
    Promise.all([getUsersWithRoles(tenantId), getRoles(tenantId)])
      .then(([u, r]) => { setUsers(u); setRoles(r); })
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) return <div>加载中...</div>;

  return (
    <table>
      <thead>
        <tr><th>用户</th><th>邮箱</th><th>当前角色</th><th>分配角色</th></tr>
      </thead>
      <tbody>
        {users.map(user => (
          <tr key={user.id}>
            <td>{user.name ?? "-"}</td>
            <td>{user.email}</td>
            <td>{user.role_name ?? "未分配"}</td>
            <td>
              <select
                value={user.role_id ?? ""}
                onChange={async (e) => {
                  const roleId = e.target.value ? Number(e.target.value) : null;
                  setPending(p => ({ ...p, [user.id]: roleId }));
                  await assignUserRole(tenantId, user.id, { role_id: roleId ?? 0 });
                  setUsers(u => u.map(x => x.id === user.id ? { ...x, role_id: roleId, role_name: roles.find(r => r.id === roleId)?.name ?? null } : x));
                }}
              >
                <option value="">-- 不分配 --</option>
                {roles.map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**完成判定**：文件 `src/frontend/settings/UserRoleAssignment.tsx` 存在且 `npx tsc --noEmit` 0 errors

### Step 5: 实现 RolesPage 容器并挂载路由

创建页面容器，整合 RoleList / PermissionMatrix / UserRoleAssignment 为 Tab 切换，并在应用路由中注册。

操作：
- a) 创建 `src/frontend/settings/RolesPage.tsx`:

```typescript
// src/frontend/settings/RolesPage.tsx
import React, { useState } from "react";
import type { Role } from "./types";
import { RoleList } from "./RoleList";
import { PermissionMatrix } from "./PermissionMatrix";
import { UserRoleAssignment } from "./UserRoleAssignment";

type Tab = "roles" | "matrix" | "assign";

export function RolesPage({ tenantId }: { tenantId: number }) {
  const [tab, setTab] = useState<Tab>("roles");
  const [editingRole, setEditingRole] = useState<Role | null>(null);

  return (
    <div>
      <h2>角色与权限管理</h2>
      <nav>
        {(["roles", "matrix", "assign"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}>{t === "roles" ? "角色列表" : t === "matrix" ? "权限矩阵" : "分配角色"}</button>
        ))}
      </nav>
      {tab === "roles" && (
        <RoleList tenantId={tenantId} onEditRole={(r) => { setEditingRole(r); setTab("matrix"); }} />
      )}
      {tab === "matrix" && editingRole && (
        <PermissionMatrix
          tenantId={tenantId}
          roleId={editingRole.id}
          initialPermissionsMatrix={{}}
        />
      )}
      {tab === "assign" && <UserRoleAssignment tenantId={tenantId} />}
    </div>
  );
}
```

- b) 若现有项目有 `src/frontend/App.tsx` 或路由文件，在 Settings 相关路由处添加：

在 `src/frontend/App.tsx`（或等价入口）的 settings 相关路由块添加子路由：

```
/settings/roles → <RolesPage tenantId={currentTenantId} />
```

**完成判定**：`src/frontend/settings/RolesPage.tsx` 存在且 `npx tsc --noEmit src/frontend/settings/` 0 errors；路由文件包含 `/settings/roles` 路径

### Step 6: 补充组件单元测试

为三个主组件编写测试文件，使用 mock fetch 函数替代真实 API 调用。

操作：
- a) 创建 `tests/unit/test_rbac_ui_components.tsx`（框架假设使用 Jest + @testing-library/react，若项目用 Vitest 需调整 import）：

```typescript
// tests/unit/test_rbac_ui_components.tsx
import React from "react";

// Mock fetch globally for all tests
beforeAll(() => {
  global.fetch = jest.fn();
});

afterAll(() => {
  delete global.fetch;
});

describe("RoleList", () => {
  it("renders loading state initially", async () => {
    // TODO: render(<RoleList tenantId={1} />)
    // assert text "加载中..."
 });

  it("renders roles after load", async () => {
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        data: [{ id: 1, name: "Admin", description: null, permissions_summary: ["customers:read"], is_system: true, created_at: "2026-01-01T00:00:00Z" }],
      }),
    });
    // TODO: render, wait for table rows, assert role name  });

  it("shows error on fetch failure", async () => {
    (fetch as jest.Mock).mockRejectedValueOnce(new Error("network error"));
    // TODO: render, assert error message
  });
});

describe("PermissionMatrix", () => {
  it("toggles checkbox state", async () => {
    // TODO: render with initialPermissionsMatrix={}, click checkbox, assert matrix state updated
  });
});

describe("UserRoleAssignment", () => {
  it("renders user list after load", async () => {
    (fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ data: [{ id: 1, name: "Alice", email: "alice@test.com", role_id: null, role_name: null }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ data: [{ id: 1, name: "Admin", description: null, permissions_summary: [], is_system: true, created_at: "2026-01-01T00:00:00Z" }] }) });
    // TODO: render, assert user row "Alice"
  });
});
```

**完成判定**：文件 `tests/unit/test_rbac_ui_components.tsx` 存在（允许 `// TODO:` 占位，框架验证测试文件语法正确）

---

## 6. 验收

- [ ] `ls src/frontend/settings/` →目录存在，且含 RolesPage.tsx、RoleList.tsx、PermissionMatrix.tsx、UserRoleAssignment.tsx、api.ts、types.ts
- [ ] `npx tsc --noEmit src/frontend/settings/` → 0 errors（TS 类型完整对齐 #643 schema）
- [ ] `ruff check src/frontend/settings/` →0 errors（若有 .py 残留文件）
- [ ] 文件 `tests/unit/test_rbac_ui_components.tsx` 存在且语法正确（Jest/Vitest 可解析）
- [ ] 三个组件引用正确的4 个 endpoint：`GET /roles`、`GET /permissions`、`PUT /roles/{id}/permissions`、`POST /users/{id}/role`（代码审查确认）
- [ ] `types.ts` 中 `Role`、`Permission`、`PermissionMatrixCell`、`UserWithRole` 接口与 #643 后端 schema 字段名一致（代码审查确认）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #643 后端 API尚未完成导致前端无法联调 | 中 | 中 | 先用 mock data 开发组件，联调前用 `npx tsc --noEmit` 验证类型，接口完成后切换真实调用 |
| 前端项目结构不可预期（目录名/CSS 方案未知） | 低 | 中 | 在 README.md 或 CLAUDE.md 中记录 `src/frontend/settings/` 规范；若有冲突，按项目现有约定调整目录名 |
| PermissionMatrix PUT body格式与后端不合 | 中 | 中 | `api.ts` 中 `putRolePermissions` body 严格对标 #643 request schema（`permissions: [{resource, actions}]`），单元测试 mock验证序列化输出 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/settings/
git commit -m "feat(settings): add RBAC UI — role list, permission matrix, user role assignment"

# 2. 更新进度
# docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Backend API依赖（#643）：TBD - 待验证：确认 #643 对应文件是否位于 `00-foundations/0643-wire-require-permission-into-all-existing-api-routers.md`
- 父 issue /关联：TBD - 待验证：确认 #38 RBAC 权限系统的规划文档路径

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
