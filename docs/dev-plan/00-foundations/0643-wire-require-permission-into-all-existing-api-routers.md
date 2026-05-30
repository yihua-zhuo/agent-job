# 权限管控 · 将 @require_permission 装饰器接入所有现有 API 路由

| 元数据 | 值 |
|---|---|
| Issue | #643 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [#642 创建 @require_permission 装饰器](../70-platform/0642-add-role-and-permission-management-api-endpoints.md) |
| 启用后赋能 | [#38 (父 issue)](../../..) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前所有 API 路由仅使用 `require_auth` 做身份验证，任何已登录用户都可以调用任何端点，包括修改/删除他人数据。这是严重的安全漏洞——多租户环境下一个有权限登录的用户不应该能够访问其他租户或自己无权限的资源。必须将 RBAC 权限体系（《RbacService》的 PERMISSIONS map）接入每个业务路由，让 `ForbiddenException` 在权限不足时生效。

### 1.2 做完后

- **用户视角**：普通用户无法越权访问或操作自己未被授予权限的模块（如普通 agent 无法删除客户，无法查看 reports）。管理员可完整访问。
- **开发者视角**：每个业务端点都有 `@require_permission("resource:action")` 装饰器，权限不足时自动抛出 `ForbiddenException`，无需在 service 层手写权限判断。

### 1.3 不做什么（剔除）

- [ ] 不修改 `src/api/routers/auth.py`（login、logout、refresh、webauthn 等认证端点不受权限管控）
- [ ] 不修改 `src/api/routers/users.py` 中的 `/auth/login` 和 `/auth/register` 端点（无需 JWT）
- [ ] 不实现字段级（column-level）权限，只做端点级（endpoint-level）权限
- [ ] 不在 service 层写权限逻辑，权限检查统一在 router 层通过装饰器完成

### 1.4 关键 KPI

- `ruff check src/api/routers/ --select=ALL --no-fix` → 0 errors（所有文件均无 lint 错误）
- 所有 12 个 router 的每个业务端点均带有 `@require_permission(...)` 装饰器（0 遗漏）
- `PYTHONPATH=src pytest tests/unit/ -v` → 全 passed（含新增的 permission-denied 单元测试）
- 端到端：未授权用户调用 `DELETE /api/v1/customers/1` → HTTP 403 + `ForbiddenException`

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/internal/middleware/fastapi_auth.py`](../../../src/internal/middleware/fastapi_auth.py) L38-L95

```python
38: class AuthContext:
39:     __slots__ = ("user_id", "tenant_id", "roles")
40:     def __init__(self, user_id: int, tenant_id: int | None, roles: list):
41:         self.user_id = user_id
42:         self.tenant_id = tenant_id
43:         self.roles = roles
```

[`src/services/rbac_service.py`](../../../src/services/rbac_service.py) L56-L72（PERMISSIONS map）

```python
56: DEFAULT_PERMISSIONS = [
57:     ("customer:create", "Create Customer", "customer"),
58:     ("customer:read", "Read Customer", "customer"),
59:     ("customer:update", "Update Customer", "customer"),
60:     ("customer:delete", "Delete Customer", "customer"),
61:     ("opportunity:create", "Create Opportunity", "opportunity"),
62:     ("opportunity:read", "Read Opportunity", "opportunity"),
63:     ("opportunity:update", "Update Opportunity", "opportunity"),
64:     ("opportunity:delete", "Delete Opportunity", "opportunity"),
65:     ("ticket:create", "Create Ticket", "ticket"),
66:     ("ticket:read", "Read Ticket", "ticket"),
67:     ("ticket:update", "Update Ticket", "ticket"),
68:     ("ticket:delete", "Delete Ticket", "ticket"),
69:     ("report:read", "Read Report", "report"),
70:     ("report:create", "Create Report", "report"),
71:     ("user:create", "Create User", "user"),
72:     ("user:read", "Read User", "user"),
73:     ("user:update", "Update User", "user"),
74:     ("user:delete", "Delete User", "user"),
75:     ("admin:all", "Full Admin Access", "admin"),
76:     ("rbac:read", "Read RBAC", "rbac"),
77:     ("rbac:manage", "Manage RBAC", "rbac"),
78:     ("tenant:read", "Read Tenant", "tenant"),
79:     ("tenant:manage", "Manage Tenant", "tenant"),
80:     ("activity:read", "Read Activity", "activity"),
81:     ("activity:create", "Create Activity", "activity"),
82:     ("activity:update", "Update Activity", "activity"),
83:     ("activity:delete", "Delete Activity", "activity"),
84:     ("notification:read", "Read Notification", "notification"),
85:     ("notification:send", "Send Notification", "notification"),
86:     ("campaign:read", "Read Campaign", "campaign"),
87:     ("campaign:create", "Create Campaign", "campaign"),
88:     ("campaign:update", "Update Campaign", "campaign"),
89:     ("campaign:delete", "Delete Campaign", "campaign"),
90:     ("automation:read", "Read Automation", "automation"),
91:     ("automation:manage", "Manage Automation", "automation"),
92:     ("ai:access", "Access AI", "ai"),
93:     ("task:read", "Read Task", "task"),
94:     ("task:create", "Create Task", "task"),
95:     ("task:update", "Update Task", "task"),
96:     ("task:delete", "Delete Task", "task"),
97: ]
```

所有 12 个 router 文件均只使用 `ctx: AuthContext = Depends(require_auth)`，没有任何权限检查。

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/users.py`](../../../src/api/routers/users.py) — 非 auth 端点加 `@require_permission`
  - [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/activities.py`](../../../src/api/routers/activities.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/automation.py`](../../../src/api/routers/automation.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/ai.py`](../../../src/api/routers/ai.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/tasks.py`](../../../src/api/routers/tasks.py) — 所有端点加 `@require_permission`
  - [`src/api/routers/lead_routing.py`](../../../src/api/routers/lead_routing.py) — 所有端点加 `@require_permission`
- 要建：
  - `tests/unit/test_permission_denied.py` — 新建：测试所有路由的权限拒绝场景

### 2.3 缺什么

- [ ] `@require_permission` 装饰器尚不存在（由 #642 提供）
- [ ] 所有 12 个 router 的 90+ 个端点均无权限检查
- [ ] 无权限拒绝场景的单元测试
- [ ] `RBACService.has_permission(role, permission)` 可直接用于装饰器实现，无需新增 DB 查询

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_permission_denied.py` | 测试所有 router 端点的权限拒绝场景（403 ForbiddenException） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) | 13 个端点 + `@require_permission("customer:*")`；leads/recycle 保留 admin/manager 角色检查 |
| [`src/api/routers/sales.py`](../../../src/api/routers/sales.py) | 12 个端点加 `@require_permission("opportunity:*")` 和 `"pipeline:*"` |
| [`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) | 12 个端点 + `@require_permission("ticket:*")`；SLA endpoints + `"ticket:read"` |
| [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) | 7 个端点 + `"report:read/create/delete"` |
| [`src/api/routers/users.py`](../../../src/api/routers/users.py) | 8 个非 auth 端点 + `"user:*"`；跳过 login/register |
| [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) | 13 个端点 + `"rbac:read"` 或 `"rbac:manage"` |
| [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) | 7 个端点 + `"tenant:read"` 或 `"tenant:manage"` |
| [`src/api/routers/activities.py`](../../../src/api/routers/activities.py) | 8 个端点 + `"activity:*"` |
| [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) | 10 个端点 + `"notification:*"` |
| [`src/api/routers/automation.py`](../../../src/api/routers/automation.py) | 7 个端点 + `"automation:*"` |
| [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) | 6 个端点 + `"campaign:*"` |
| [`src/api/routers/ai.py`](../../../src/api/routers/ai.py) | 3 个端点 + `"ai:access"` |
| [`src/api/routers/tasks.py`](../../../src/api/routers/tasks.py) | 5 个端点 + `"task:*"` |
| [`src/api/routers/lead_routing.py`](../../../src/api/routers/lead_routing.py) | 7 个端点；write 端点保留 admin/manager 角色检查 + `"automation:manage"` |

### 3.3 新增能力

- **装饰器**：`@require_permission("resource:action")` 在 `#642` 中实现，本 issue 将其接入全部路由
- **端点权限表**：

| Router | 端点 | 所需权限 |
|--------|------|---------|
| customers | POST / | `customer:create` |
| customers | GET /, GET /search | `customer:read` |
| customers | GET /{id}, GET /{id}/assignment | `customer:read` |
| customers | PUT /{id}, PUT /{id}/status, PUT /{id}/owner | `customer:update` |
| customers | DELETE /{id} | `customer:delete` |
| customers | POST /{id}/tags, DELETE /{id}/tags | `customer:update` |
| customers | GET /leads, POST /leads/recycle | `customer:read`（已含 admin/manager 角色检查） |
| customers | POST /import | `customer:create` |
| customers | POST /{id}/assign, POST /{id}/reassign | `customer:update` |
| sales | POST/GET /pipelines | `pipeline:create`/`pipeline:read` |
| sales | GET /pipelines/{id}, /pipelines/{id}/stats, /pipelines/{id}/funnel | `pipeline:read` |
| sales | POST/GET/PUT /opportunities, GET /opportunities/{id} | `opportunity:create/read/update` |
| sales | PUT /opportunities/{id}/stage | `opportunity:update` |
| sales | GET /forecast | `opportunity:read` |
| tickets | POST /tickets | `ticket:create` |
| tickets | GET /tickets, GET /tickets/{id} | `ticket:read` |
| tickets | PUT /tickets/{id}, PUT /tickets/{id}/assign, PUT /tickets/{id}/status | `ticket:update` |
| tickets | POST /tickets/{id}/replies, GET /tickets/{id}/replies | `ticket:update`/`ticket:read` |
| tickets | GET /tickets/customer/{id}, GET /tickets/{id}/activity | `ticket:read` |
| tickets | GET /tickets/sla/breaches, POST /tickets/bulk-update, POST /tickets/{id}/auto-assign | `ticket:read` |
| tickets | GET /sla/status/{id}, GET /sla/breaches, GET /sla/summary | `ticket:read` |
| reports | POST/GET/PUT/DELETE / | `report:create/read/update/delete` |
| reports | POST /pdf, POST /excel, POST /csv | `report:read` |
| users | POST/GET/PUT/DELETE /users | `user:create/read/update/delete` |
| users | GET /users/me, PATCH /users/me, POST /auth/change-password | `user:read` |
| users | POST /users/search, POST /users/{id}/password | `user:read` |
| users | POST /auth/register, POST /auth/login | **不需权限** |
| rbac | POST/GET /roles, GET /roles/{id} | `rbac:manage`/`rbac:read` |
| rbac | PUT/DELETE /roles/{id} | `rbac:manage` |
| rbac | GET /permissions, GET/PUT /roles/{id}/permissions | `rbac:read`/`rbac:manage` |
| rbac | POST/DELETE/PUT /users/{id}/roles, GET /users/{id}/roles/permissions | `rbac:manage` |
| rbac | GET /roles/{id}/users | `rbac:read` |
| tenants | POST / | `tenant:manage` |
| tenants | GET /stats, GET /usage, GET /{id}, GET / | `tenant:read` |
| tenants | PUT/DELETE /{id} | `tenant:manage` |
| activities | POST / | `activity:create` |
| activities | GET /, GET /{id}, GET /summary, GET /customer/{id}, GET /opportunity/{id} | `activity:read` |
| activities | PUT/DELETE /{id} | `activity:update`/`activity:delete` |
| activities | POST /search | `activity:read` |
| notifications | GET /notifications, POST /notifications/send, PUT /notifications/{id}/read | `notification:read`/`notification:send` |
| notifications | DELETE /notifications/{id}, POST /notifications/mark-all-read | `notification:read` |
| notifications | GET/PUT /notifications/preferences | `notification:read` |
| notifications | POST/GET/DELETE /reminders | `notification:read` |
| automation | POST/GET /rules | `automation:manage`/`automation:read` |
| automation | GET/PUT/DELETE /rules/{id}, POST /rules/{id}/toggle | `automation:read`/`automation:manage` |
| automation | POST /trigger, GET /logs | `automation:manage`/`automation:read` |
| marketing | GET /campaigns | `campaign:read` |
| marketing | POST /campaigns | `campaign:create` |
| marketing | GET /campaigns/{id} | `campaign:read` |
| marketing | PUT/PATCH /campaigns/{id} | `campaign:update` |
| marketing | DELETE /campaigns/{id} | `campaign:delete` |
| ai | POST /chat, POST /conversation, GET /conversation/{id} | `ai:access` |
| tasks | POST /tasks | `task:create` |
| tasks | GET /tasks, GET /tasks/{id} | `task:read` |
| tasks | PATCH /tasks/{id}, POST /tasks/{id}/complete | `task:update` |
| tasks | DELETE /tasks/{id} | `task:delete` |
| lead_routing | GET / | `automation:read` |
| lead_routing | POST / | `automation:manage`（保留 admin/manager 角色检查）|
| lead_routing | POST /test | `automation:read` |
| lead_routing | GET/PUT/DELETE /{id}, PUT /priority, PUT /{id}/toggle | `automation:manage`（保留 admin/manager 角色检查）|

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用装饰器而非中间件**：每个端点的权限需求不同，装饰器比全局中间件更灵活，且装饰器可精确控制到单个路由。
- **用 `RBACService.has_permission(role, permission)` 而非每次查 DB**：权限装饰器基于 `AuthContext.roles`（JWT payload 中已有），无需为每次请求额外查询 DB，性能最优。
- **写端点（POST/PUT/DELETE）用 `rbac:manage`，读端点（GET）用 `rbac:read`**：即使 RBAC 端点本身也受权限管控，防止普通用户枚举角色/权限。
- **保留 lead_routing 的 admin/manager 角色检查**：原有角色检查与新权限系统并存，两者都需要满足。
- **auth 端点不添加权限装饰器**：login/logout/register/webauthn 等是系统入口，权限装饰器会阻止未登录用户访问。

### 4.2 版本约束

无新依赖引入。`@require_permission` 装饰器由 #642 实现并提供。

### 4.3 兼容性约束

- 每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- `AuthContext.roles` 来自 JWT payload，装饰器无需额外 DB 查询即可做权限判断

### 4.4 已知坑

1. **`RBACService.has_permission(role, permission)` 基于 DEFAULT_ROLE_PERMISSIONS 静态字典** → 装饰器只能检查用户角色对应的默认权限，无法检查用户通过 RBAC API 自定义分配的精细权限。**规避**：本 issue 结束后，装饰器实现（#642）应升级为调用 `RBACService.get_user_permissions(user_id, tenant_id)` 从 DB 取用户实际权限。
2. **AI router 端点缺少 `session` 参数导致 FastAPI 依赖注入失败** → `@ai_router.post("/chat")` 在 `#642` 装饰器接入前不会报错，接入后若 `session` 参数类型标注缺失，类型检查会失败。**规避**：ai.py 中 `chat()` 函数已有 `session: AsyncSession = Depends(get_db)`，无需额外处理。
3. **tenant_id 为 None 时权限装饰器行为** → `require_auth` 返回的 `AuthContext` 可能 `tenant_id=None`（如来自旧 token）。权限装饰器应在 tenant_id 缺失时也拒绝访问。**规避**：装饰器在 `ctx.tenant_id is None` 时抛出 `ForbiddenException`。

---

## 5. 实现步骤（按顺序）

### Step 1: 在 `customers.py` 所有端点接入 `@require_permission`

`#642` 完成后，`@require_permission` 装饰器在 `fastapi_auth.py` 中可用。将每个端点的 `ctx: AuthContext = Depends(require_auth)` 替换为 `ctx: AuthContext = Depends(require_auth), _: None = Depends(require_permission("customer:create"))`，权限字符串按 §3.3 分配。

操作：
- 在 `customers.py` 顶部 import 添加 `require_permission`
- `POST /` → `require_permission("customer:create")`
- `GET /`, `GET /search` → `require_permission("customer:read")`
- `GET /{customer_id}`, `GET /{customer_id}/assignment` → `require_permission("customer:read")`
- `PUT /{customer_id}` → `require_permission("customer:update")`
- `DELETE /{customer_id}` → `require_permission("customer:delete")`
- `POST /{customer_id}/tags`, `DELETE /{customer_id}/tags/{tag}` → `require_permission("customer:update")`
- `PUT /{customer_id}/status`, `PUT /{customer_id}/owner` → `require_permission("customer:update")`
- `POST /import` → `require_permission("customer:create")`
- `GET /leads` → `require_permission("customer:read")`
- `POST /leads/recycle` → `require_permission("customer:read")`（原有 admin/manager 检查保留）
- `POST /{customer_id}/assign`, `POST /{customer_id}/reassign` → `require_permission("customer:update")`

示例代码：

```python
from internal.middleware.fastapi_auth import AuthContext, require_auth, require_permission

@customers_router.post("", status_code=201)
async def create_customer(
    body: CustomerCreate,
    ctx: AuthContext = Depends(require_auth),
    _: None = Depends(require_permission("customer:create")),
    session: AsyncSession = Depends(get_db),
):
    ...
```

**完成判定**：`ruff check src/api/routers/customers.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v -k customer` → 全 passed

### Step 2: 在 `sales.py` 所有端点接入 `@require_permission`

操作：
- `POST /pipelines` → `require_permission("pipeline:create")`
- `GET /pipelines` → `require_permission("pipeline:read")`
- `GET /pipelines/{pipeline_id}`, `GET /pipelines/{pipeline_id}/stats`, `GET /pipelines/{pipeline_id}/funnel` → `require_permission("pipeline:read")`
- `POST /opportunities` → `require_permission("opportunity:create")`
- `GET /opportunities`, `GET /opportunities/{opp_id}` → `require_permission("opportunity:read")`
- `PUT /opportunities/{opp_id}` → `require_permission("opportunity:update")`
- `PUT /opportunities/{opp_id}/stage` → `require_permission("opportunity:update")`
- `GET /forecast` → `require_permission("opportunity:read")`

**完成判定**：`ruff check src/api/routers/sales.py` → 0 errors

### Step 3: 在 `tickets.py` 所有端点接入 `@require_permission`

操作：
- `POST /tickets` → `require_permission("ticket:create")`
- `GET /tickets`, `GET /tickets/{ticket_id}`, `GET /tickets/customer/{customer_id}`, `GET /tickets/sla/breaches` → `require_permission("ticket:read")`
- `PUT /tickets/{ticket_id}`, `PUT /tickets/{ticket_id}/assign`, `PUT /tickets/{ticket_id}/status`, `POST /tickets/bulk-update`, `POST /tickets/{ticket_id}/auto-assign` → `require_permission("ticket:update")`
- `POST /tickets/{ticket_id}/replies` → `require_permission("ticket:update")`
- `GET /tickets/{ticket_id}/replies`, `GET /tickets/{ticket_id}/activity` → `require_permission("ticket:read")`
- `GET /sla/status/{ticket_id}`, `GET /sla/breaches`, `GET /sla/summary` → `require_permission("ticket:read")`

**完成判定**：`ruff check src/api/routers/tickets.py` → 0 errors

### Step 4: 在 `reports.py`、`users.py`、`rbac.py`、`tenants.py` 接入 `@require_permission`

操作（reports.py）：
- `POST /` → `require_permission("report:create")`
- `GET /`, `GET /{report_id}` → `require_permission("report:read")`
- `PUT /{report_id}` → `require_permission("report:update")`
- `DELETE /{report_id}` → `require_permission("report:delete")`
- `POST /pdf`, `POST /excel`, `POST /csv` → `require_permission("report:read")`

操作（users.py）：
- 跳过 `POST /auth/login`, `POST /auth/register`（无需 auth）
- `POST /users`, `POST /users/search` → `require_permission("user:create")`
- `GET /users`, `GET /users/me`, `GET /users/{user_id}` → `require_permission("user:read")`
- `PUT /users/{user_id}`, `PATCH /users/me` → `require_permission("user:update")`
- `DELETE /users/{user_id}`, `POST /users/{user_id}/password`, `POST /auth/change-password` → `require_permission("user:update")`

操作（rbac.py）：
- `POST /roles`, `DELETE /roles/{role_id}`, `PUT /roles/{role_id}/permissions`, `POST /users/{user_id}/roles`, `DELETE /users/{user_id}/roles/{role_id}`, `PUT /users/{user_id}/roles` → `require_permission("rbac:manage")`
- 其余端点 → `require_permission("rbac:read")`

操作（tenants.py）：
- `POST /` → `require_permission("tenant:manage")`
- `GET /stats`, `GET /usage`, `GET /{tenant_id}`, `GET /` → `require_permission("tenant:read")`
- `PUT /{tenant_id}`, `DELETE /{tenant_id}` → `require_permission("tenant:manage")`

**完成判定**：`ruff check src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py` → 0 errors

### Step 5: 在 `activities.py`、`notifications.py`、`automation.py`、`marketing.py` 接入 `@require_permission`

操作（activities.py）：
- `POST /` → `require_permission("activity:create")`
- `GET /`, `GET /summary`, `GET /{activity_id}`, `GET /customer/{customer_id}`, `GET /opportunity/{opp_id}`, `POST /search` → `require_permission("activity:read")`
- `PUT /{activity_id}` → `require_permission("activity:update")`
- `DELETE /{activity_id}` → `require_permission("activity:delete")`

操作（notifications.py）：
- `GET /notifications`, `PUT /notifications/{id}/read`, `DELETE /notifications/{id}`, `POST /notifications/mark-all-read`, `GET /notifications/preferences`, `PUT /notifications/preferences` → `require_permission("notification:read")`
- `POST /notifications/send` → `require_permission("notification:send")`
- `POST /reminders`, `GET /reminders`, `DELETE /reminders/{id}` → `require_permission("notification:read")`

操作（automation.py）：
- `GET /rules`, `GET /rules/{rule_id}`, `GET /logs` → `require_permission("automation:read")`
- `POST /rules`, `PUT /rules/{rule_id}`, `DELETE /rules/{rule_id}`, `POST /rules/{rule_id}/toggle`, `POST /trigger` → `require_permission("automation:manage")`

操作（marketing.py）：
- `GET /campaigns`, `GET /campaigns/{id}` → `require_permission("campaign:read")`
- `POST /campaigns` → `require_permission("campaign:create")`
- `PUT /campaigns/{id}`, `PATCH /campaigns/{id}` → `require_permission("campaign:update")`
- `DELETE /campaigns/{id}` → `require_permission("campaign:delete")`

**完成判定**：`ruff check src/api/routers/activities.py src/api/routers/notifications.py src/api/routers/automation.py src/api/routers/marketing.py` → 0 errors

### Step 6: 在 `ai.py`、`tasks.py`、`lead_routing.py` 接入 `@require_permission`

操作（ai.py）：
- `POST /chat`, `POST /conversation`, `GET /conversation/{id}` → `require_permission("ai:access")`

操作（tasks.py）：
- `POST /tasks` → `require_permission("task:create")`
- `GET /tasks`, `GET /tasks/{id}` → `require_permission("task:read")`
- `PATCH /tasks/{id}`, `POST /tasks/{id}/complete` → `require_permission("task:update")`
- `DELETE /tasks/{id}` → `require_permission("task:delete")`

操作（lead_routing.py）：
- `GET /` → `require_permission("automation:read")`
- `POST /`, `PUT /{id}`, `DELETE /{id}`, `PUT /priority`, `PUT /{id}/toggle` → 保留原有 admin/manager 角色检查，添加 `require_permission("automation:manage")`
- `POST /test` → `require_permission("automation:read")`

**完成判定**：`ruff check src/api/routers/ai.py src/api/routers/tasks.py src/api/routers/lead_routing.py` → 0 errors

### Step 7: 新建 `tests/unit/test_permission_denied.py`

为每个 router 编写 1 个 happy-path 测试（权限足够时正常返回）和 1 个权限不足测试（无对应权限时收到 `ForbiddenException`）。

操作：
- 在 `tests/unit/conftest.py` 中添加 `make_auth_context_with_roles()` 辅助函数，生成带有特定 roles 的 `AuthContext`
- 测试 12 个 router，每个至少 2 个测试用例
- 覆盖场景：权限不足 → 403 ForbiddenException；权限足够 → 正常处理

示例代码：

```python
import pytest
from internal.middleware.fastapi_auth import AuthContext

def make_auth_ctx(user_id: int = 1, tenant_id: int = 1, roles: list[str] | None = None) -> AuthContext:
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles or ["user"])

class TestCustomerRouterPermissions:
    async def test_create_customer_without_permission_raises_403(self, mock_db_session):
        ctx = make_auth_ctx(roles=["user"])  # no customer:create
        with pytest.raises(ForbiddenException):
            await CustomerService(mock_db_session).create_customer({...}, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` → ≥ 30 passed

### Step 8: 全局 lint + 单元测试验证

操作：
- 运行 `ruff check src/api/routers/`
- 运行 `PYTHONPATH=src pytest tests/unit/ -v`
- 检查无新增 lint 错误，无测试 regression

**完成判定**：`ruff check src/api/routers/` → 0 errors；`PYTHONPATH=src pytest tests/unit/ -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/customers.py src/api/routers/sales.py src/api/routers/tickets.py src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py src/api/routers/activities.py src/api/routers/notifications.py src/api/routers/automation.py src/api/routers/marketing.py src/api/routers/ai.py src/api/routers/tasks.py src/api/routers/lead_routing.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` → ≥ 30 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → 全 passed（含新增测试，无 regression）
- [ ] 每个 router 文件底部有一个注释行 `# Permission map applied: resource:action` 注明权限已接入
- [ ] `auth.py` 的 login/logout/register/webauthn 端点**无** `@require_permission` 装饰器（人工确认）
- [ ] 端到端：用户无 `customer:delete` 权限时调用 `curl -X DELETE http://localhost:8000/api/v1/customers/1 -H "Authorization: Bearer <token>"` → HTTP 403

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#642` 装饰器实现与当前代码不兼容（参数签名变化） | 低 | 中 | 临时用 `ruff check` 的类型检查结果作为接口契约；若装饰器参数变化，修改本 issue 的 import 和调用方式 |
| 遗漏某个端点未加装饰器（覆盖不完整） | 中 | 高 | 在 §6 验收步骤中用脚本扫描所有 router 文件中 `Depends(require_auth)` 但缺少 `Depends(require_permission)` 的端点；发现遗漏立即补加 |
| 新增测试导致单元测试超时（mock session 复杂） | 低 | 低 | 减少 mock session 依赖，仅测试权限拒绝路径，不测试业务逻辑 |
| auth 端点被误加装饰器导致登录失败 | 中 | 高 | 验收步骤第 4 项专门检查 auth.py 无权限装饰器；若有误加，直接 revert 该文件改动即可，不阻塞其他 router |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/customers.py \
      src/api/routers/sales.py \
      src/api/routers/tickets.py \
      src/api/routers/reports.py \
      src/api/routers/users.py \
      src/api/routers/rbac.py \
      src/api/routers/tenants.py \
      src/api/routers/activities.py \
      src/api/routers/notifications.py \
      src/api/routers/automation.py \
      src/api/routers/marketing.py \
      src/api/routers/ai.py \
      src/api/routers/tasks.py \
      src/api/routers/lead_routing.py \
      tests/unit/test_permission_denied.py
git commit -m "feat(rbac): wire @require_permission into all existing API routers (closes #643)"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(rbac): wire @require_permission into all existing API routers" --body "Closes #643

- Adds @require_permission decorators to all business endpoints across 13 routers
- Skips auth endpoints (login/logout/register/webauthn) as they are unauthenticated entry points
- New tests in tests/unit/test_permission_denied.py cover permission-denied scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 当前唯一使用角色检查的端点（leads/recycle，admin/manager 角色检查）
- 第三方文档：[FastAPI Depends 文档](https://fastapi.tiangolo.com/tutorial/dependencies/)
- 父 issue / 关联：#38 (父 issue), #642 (依赖项，提供 `@require_permission` 装饰器)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
